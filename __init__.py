"""Deep Notes by AnkiMonkey - scratchpad panel for the Anki reviewer.

Features
- dockable panel (left/right), adjustable + remembered width, collapse to a thin strip
- text mode (free scratchpad) or table mode (template column + your own column)
- TXT templates: loaded automatically per card (by tag -> deck -> default.txt)
  or manually via "Import TXT"
- tag rules: e.g. tag Kosti (or Kosti::HK, Kosti::DK ...) -> kosti_notes.txt
- settings dialog (gear button, Alt+S, or Tools > Add-ons > Config)
- keyboard shortcuts (configurable): Alt+N collapse, Alt+I import, Alt+T mode,
  Alt+= / Alt+- width, Alt+S settings
Everything is local, no cloud.
"""

import os

from aqt import gui_hooks, mw
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QCheckBox,
    QComboBox,
    QDesktopServices,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFont,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPixmap,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    Qt,
    QUrl,
    QTableWidget,
    QTableWidgetItem,
    QTextCursor,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import tooltip

ADDON_DIR = os.path.dirname(__file__)
ADDON_KEY = __name__

DEFAULTS = {
    "dock_area": "right",
    "dock_width": 320,
    "min_width": 180,
    "width_step": 40,
    "remember_width": True,
    "collapsed": False,
    "font_size": 16,
    "font_family": "Arial",
    "show_logo": True,
    "logo_height": 36,
    "mode": "text",
    "clear_after_answer": True,
    "auto_focus": False,
    "hide_outside_review": True,
    "template_dir": "",
    "auto_load_template": True,
    "default_template": "default.txt",
    "tag_rules": [],
    "rules_first_tag_only": False,
    "table_separator": "\t",
    "table_headers": ["Základ", "Moje"],
    "table_template_readonly": True,
    "table_empty_rows": 5,
    "shortcut_collapse": "Alt+N",
    "shortcut_import": "Alt+I",
    "shortcut_mode": "Alt+T",
    "shortcut_wider": "Alt+=",
    "shortcut_narrower": "Alt+-",
    "shortcut_settings": "Alt+S",
}

COLLAPSED_WIDTH = 30
QT_MAX = 16777215

state = {
    "dock": None,
    "body": None,
    "text_box": None,
    "table": None,
    "mode_btn": None,
    "collapse_btn": None,
    "source_label": None,
    "card_id": None,
    "tools": None,
    "width": None,
    "shortcuts": [],
}


# ----------------------------------------------------------------- config

def cfg() -> dict:
    user = mw.addonManager.getConfig(ADDON_KEY) or {}
    merged = dict(DEFAULTS)
    merged.update(user)
    return merged


def save_cfg(**changes) -> None:
    conf = cfg()
    conf.update(changes)
    mw.addonManager.writeConfig(ADDON_KEY, conf)


# -------------------------------------------------------------- templates

def template_dir() -> str:
    custom = cfg()["template_dir"].strip()
    if custom:
        return os.path.expandvars(os.path.expanduser(custom))
    # user_files survives add-on updates from AnkiWeb
    return os.path.join(ADDON_DIR, "user_files", "templates")


def _candidates(card) -> list:
    """File names to try, most specific first: tags, deck, default."""
    names = []
    tags = sorted(card.note().tags, key=lambda t: t.count("::"), reverse=True)
    for tag in tags:
        parts = tag.split("::")
        for i in range(len(parts), 0, -1):
            names.append("__".join(parts[:i]) + ".txt")
    deck = mw.col.decks.name(card.did)
    parts = deck.split("::")
    for i in range(len(parts), 0, -1):
        names.append("__".join(parts[:i]) + ".txt")
    names.append(cfg()["default_template"])
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def rule_file(card):
    """First matching tag rule wins (rules are checked top to bottom).

    Rule tag "Kosti" matches tags "Kosti", "Kosti::HK", "Kosti::DK::femur" ...
    Rule tag "Kosti::HK" matches only that branch. Case-insensitive.
    """
    conf = cfg()
    tags = [t.casefold() for t in card.note().tags]
    if conf["rules_first_tag_only"]:
        tags = tags[:1]
    for rule in conf["tag_rules"] or []:
        rtag = str(rule.get("tag", "")).strip().casefold()
        fname = str(rule.get("file", "")).strip()
        if not rtag or not fname:
            continue
        for t in tags:
            if t == rtag or t.startswith(rtag + "::"):
                return fname
    return None


def find_template(card):
    folder = template_dir()
    if not os.path.isdir(folder):
        return None, None
    by_rule = rule_file(card)
    if by_rule:
        path = by_rule if os.path.isabs(by_rule) else os.path.join(folder, by_rule)
        if os.path.isfile(path):
            return path, read_txt(path)
    for name in _candidates(card):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path, read_txt(path)
    return None, None


def read_txt(path: str) -> str:
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


# ------------------------------------------------------------------ fills

def set_source(text: str) -> None:
    lbl = state["source_label"]
    if lbl:
        lbl.setText(text)


def fill_text(template: str) -> None:
    box = state["text_box"]
    box.setPlainText(template or "")
    box.moveCursor(QTextCursor.MoveOperation.End)


def fill_table(template: str) -> None:
    conf = cfg()
    table = state["table"]
    sep = conf["table_separator"] or "\t"
    lines = [ln for ln in (template or "").splitlines() if ln.strip()]
    table.setRowCount(0)
    if not lines:
        for _ in range(int(conf["table_empty_rows"])):
            add_row()
        return
    for ln in lines:
        base, _, mine = ln.partition(sep)
        add_row(base.strip(), mine.strip(), locked=conf["table_template_readonly"])
    table.resizeRowsToContents()


def add_row(base: str = "", mine: str = "", locked: bool = False) -> None:
    table = state["table"]
    r = table.rowCount()
    table.insertRow(r)
    a = QTableWidgetItem(base)
    if locked and base:
        a.setFlags(a.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(r, 0, a)
    table.setItem(r, 1, QTableWidgetItem(mine))


def load_for_card(card) -> None:
    if not cfg()["auto_load_template"]:
        return
    path, text = find_template(card)
    if cfg()["mode"] == "table":
        fill_table(text)
    else:
        fill_text(text)
    set_source(os.path.basename(path) if path else "")


def clear_all() -> None:
    if state["text_box"]:
        state["text_box"].clear()
        state["text_box"].setPlaceholderText("Cleared ✓")
    if state["table"]:
        state["table"].setRowCount(0)
    set_source("")


# ---------------------------------------------------------------- actions

def import_txt() -> None:
    if not state["dock"]:
        return
    start = template_dir() if os.path.isdir(template_dir()) else os.path.expanduser("~")
    path, _ = QFileDialog.getOpenFileName(mw, "Import TXT", start, "Text (*.txt);;All (*)")
    if not path:
        return
    text = read_txt(path)
    if cfg()["mode"] == "table":
        fill_table(text)
    else:
        box = state["text_box"]
        current = box.toPlainText()
        fill_text((current + "\n" + text) if current.strip() else text)
    set_source(os.path.basename(path))
    expand()


def toggle_mode() -> None:
    if not state["dock"]:
        return
    new = "table" if cfg()["mode"] == "text" else "text"
    save_cfg(mode=new)
    apply_mode()
    card = mw.reviewer.card if mw.state == "review" else None
    if card:
        load_for_card(card)
    tooltip(f"Deep Notes: {new}")


def apply_mode() -> None:
    if not state["text_box"]:
        return
    table_mode = cfg()["mode"] == "table"
    state["text_box"].setVisible(not table_mode)
    state["table"].setVisible(table_mode)
    if state["mode_btn"]:
        state["mode_btn"].setText("¶" if table_mode else "▦")
        state["mode_btn"].setToolTip(
            ("Prepnúť na text" if table_mode else "Prepnúť na tabuľku")
            + f" ({cfg()['shortcut_mode']})"
        )


def set_width(width: int) -> None:
    dock = state["dock"]
    if not dock:
        return
    conf = cfg()
    width = max(int(conf["min_width"]), int(width))
    dock.setMinimumWidth(int(conf["min_width"]))
    dock.setMaximumWidth(QT_MAX)
    mw.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
    state["width"] = width
    if conf["remember_width"]:
        save_cfg(dock_width=width)


def _current_width() -> int:
    """Last width we set, unless the user dragged the splitter since then."""
    real = state["dock"].width()
    last = state.get("width")
    if last is None or abs(real - last) > int(cfg()["width_step"]):
        return real
    return last


def wider() -> None:
    if not state["dock"]:
        return
    expand()
    set_width(_current_width() + int(cfg()["width_step"]))


def narrower() -> None:
    if not state["dock"]:
        return
    expand()
    set_width(_current_width() - int(cfg()["width_step"]))


def collapse() -> None:
    dock = state["dock"]
    if not dock or not state["body"].isVisible():
        return
    if cfg()["remember_width"]:
        save_cfg(dock_width=dock.width())
    state["body"].hide()
    state["tools"].hide()
    dock.setMinimumWidth(COLLAPSED_WIDTH)
    dock.setMaximumWidth(COLLAPSED_WIDTH)
    mw.resizeDocks([dock], [COLLAPSED_WIDTH], Qt.Orientation.Horizontal)
    state["collapse_btn"].setText("⇤" if cfg()["dock_area"] == "right" else "⇥")
    save_cfg(collapsed=True)


def expand() -> None:
    dock = state["dock"]
    if not dock or state["body"].isVisible():
        return
    state["body"].show()
    state["tools"].show()
    dock.setMaximumWidth(QT_MAX)
    state["collapse_btn"].setText("⇥" if cfg()["dock_area"] == "right" else "⇤")
    save_cfg(collapsed=False)
    set_width(cfg()["dock_width"])


def toggle_collapse() -> None:
    if not state["dock"]:
        return
    if state["body"].isVisible():
        collapse()
    else:
        expand()


# --------------------------------------------------------------------- ui

def _btn(text: str, tip: str, slot) -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setFixedHeight(24)
    b.setFixedWidth(22 if len(text) <= 2 else 30)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.clicked.connect(slot)
    return b


def create_dock() -> None:
    if state["dock"]:
        return
    conf = cfg()

    dock = QDockWidget("", mw)
    dock.setObjectName("DeepNotesDock")
    dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
    )
    dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
    dock.setTitleBarWidget(QWidget())
    dock.setMinimumWidth(int(conf["min_width"]))

    root = QWidget()
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(4, 4, 4, 4)
    root_layout.setSpacing(4)

    # top row: collapse button (always visible) + tools (hidden when collapsed)
    top = QHBoxLayout()
    top.setSpacing(1)
    collapse_btn = _btn("⇥", f"Zbaliť / rozbaliť ({conf['shortcut_collapse']})", toggle_collapse)
    top.addWidget(collapse_btn, 0, Qt.AlignmentFlag.AlignTop)
    state["collapse_btn"] = collapse_btn

    tools_w = QWidget()
    tools = QHBoxLayout(tools_w)
    tools.setContentsMargins(0, 0, 0, 0)
    tools.setSpacing(1)
    tools.addWidget(_btn("−", f"Užší ({conf['shortcut_narrower']})", narrower))
    tools.addWidget(_btn("+", f"Širší ({conf['shortcut_wider']})", wider))
    tools.addWidget(_btn("TXT", f"Import TXT ({conf['shortcut_import']})", import_txt))
    mode_btn = _btn("▦", f"Text / tabuľka ({conf['shortcut_mode']})", toggle_mode)
    tools.addWidget(mode_btn)
    state["mode_btn"] = mode_btn
    tools.addWidget(_btn("＋", "Pridať riadok do tabuľky", lambda: add_row()))
    tools.addWidget(_btn("⚙", f"Nastavenia ({conf['shortcut_settings']})", open_settings))
    tools.addStretch()

    if conf["show_logo"]:
        pix = None
        for name in ("logo.png", "logo2.png"):
            p = os.path.join(ADDON_DIR, name)
            if os.path.isfile(p):
                pix = QPixmap(p)
                break
        if pix and not pix.isNull():
            logo = QLabel()
            logo.setPixmap(
                pix.scaledToHeight(int(conf["logo_height"]), Qt.TransformationMode.SmoothTransformation)
            )
            logo.setToolTip("Deep Notes by AnkiMonkey")
            logo.setMinimumWidth(0)
            logo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            tools.addWidget(logo)

    top.addWidget(tools_w, 1)
    root_layout.addLayout(top)
    state["tools"] = tools_w

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(4)

    source = QLabel("")
    source.setStyleSheet("font-size: 11px; color: gray;")
    source.setMinimumWidth(0)
    source.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    body_layout.addWidget(source)
    state["source_label"] = source

    font = QFont(conf["font_family"], int(conf["font_size"]))

    text_box = QTextEdit()
    text_box.setFont(font)
    text_box.setPlaceholderText("Write thoughts, reasoning, hypotheses...")
    text_box.setMinimumWidth(60)
    body_layout.addWidget(text_box)
    state["text_box"] = text_box

    table = QTableWidget(0, 2)
    table.setFont(font)
    table.setMinimumWidth(60)
    headers = list(conf["table_headers"])[:2] + ["", ""]
    table.setHorizontalHeaderLabels(headers[:2])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(True)
    table.setEditTriggers(
        QAbstractItemView.EditTrigger.DoubleClicked
        | QAbstractItemView.EditTrigger.EditKeyPressed
        | QAbstractItemView.EditTrigger.AnyKeyPressed
    )
    body_layout.addWidget(table)
    state["table"] = table

    root_layout.addWidget(body, 1)

    dock.setWidget(root)
    state["dock"] = dock
    state["body"] = body

    area = (
        Qt.DockWidgetArea.LeftDockWidgetArea
        if conf["dock_area"] == "left"
        else Qt.DockWidgetArea.RightDockWidgetArea
    )
    mw.addDockWidget(area, dock)

    apply_mode()
    if conf["collapsed"]:
        collapse()
    else:
        set_width(conf["dock_width"])


def register_shortcuts() -> None:
    if state["shortcuts"]:
        return
    conf = cfg()
    pairs = [
        ("shortcut_collapse", toggle_collapse),
        ("shortcut_import", import_txt),
        ("shortcut_mode", toggle_mode),
        ("shortcut_wider", wider),
        ("shortcut_narrower", narrower),
        ("shortcut_settings", open_settings),
    ]
    for key, fn in pairs:
        seq = conf.get(key)
        if not seq:
            continue
        sc = QShortcut(QKeySequence(seq), mw)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(fn)
        state["shortcuts"].append(sc)


def add_menu() -> None:
    act = QAction("Deep Notes: zbaliť / rozbaliť panel", mw)
    act.triggered.connect(lambda: (create_dock(), state["dock"].show(), toggle_collapse()))
    mw.form.menuTools.addAction(act)


# --------------------------------------------------------------- settings

SEPARATORS = [("Tabulátor (\\t)", "\t"), ("Bodkočiarka ;", ";"), ("Zvislá čiara |", "|"), ("Čiarka ,", ",")]

# (tab, key, label, kind, extra, help)
SPEC = [
    ("Panel", "dock_area", "Strana panela", "choice", ["right", "left"],
     "Vpravo alebo vľavo. Zmena platí po reštarte Anki."),
    ("Panel", "dock_width", "Šírka (px)", "int", (60, 3000),
     "Šírka panela. Mení sa aj tlačidlami − / + a skratkami."),
    ("Panel", "min_width", "Minimálna šírka (px)", "int", (60, 1500),
     "Užšie sa panel nedá potiahnuť (pôvodne natvrdo 400)."),
    ("Panel", "width_step", "Krok šírky (px)", "int", (5, 500),
     "O koľko menia šírku tlačidlá − / + a skratky."),
    ("Panel", "remember_width", "Pamätať šírku", "bool", None,
     "Po reštarte Anki ostane posledná šírka."),
    ("Panel", "hide_outside_review", "Skryť mimo opakovania", "bool", None,
     "V prehľade deckov a v Browse panel zmizne."),
    ("Panel", "show_logo", "Zobraziť logo", "bool", None,
     "Logo AnkiMonkey v lište panela. Zmena platí po reštarte Anki."),
    ("Panel", "logo_height", "Výška loga (px)", "int", (12, 200),
     "Zmena platí po reštarte Anki."),
    ("Písanie", "font_family", "Písmo", "str", None,
     "Napr. Arial, Consolas, Segoe UI."),
    ("Písanie", "font_size", "Veľkosť písma", "int", (6, 72), ""),
    ("Písanie", "mode", "Režim", "choice", ["text", "table"],
     "text = voľný zápisník, table = tabuľka Základ / Moje (Alt+T prepína)."),
    ("Písanie", "clear_after_answer", "Vyčistiť po odpovedi", "bool", None,
     "Po ohodnotení karty sa panel vyprázdni."),
    ("Písanie", "auto_focus", "Kurzor do panela", "bool", None,
     "Po zobrazení otázky skočí kurzor do panela. Pozor: medzerník potom píše do panela."),
    ("Šablóny", "template_dir", "Priečinok šablón", "dir", None,
     "Prázdne = user_files/templates v add-one (Anki ho pri update neprepíše)."),
    ("Šablóny", "auto_load_template", "Načítať šablónu automaticky", "bool", None,
     "Pri každej karte sa nájde a vloží šablóna (pravidlá → tag → deck → default)."),
    ("Šablóny", "default_template", "Predvolená šablóna", "str", None,
     "Súbor, keď nesedí žiadne pravidlo, tag ani deck."),
    ("Šablóny", "rules_first_tag_only", "Pravidlá len pre prvý tag", "bool", None,
     "Zapnuté = berie sa iba prvý tag poznámky (Anki ich radí abecedne). "
     "Vypnuté = platí prvé pravidlo zhora, ktoré sedí na hocijaký tag."),
    ("Tabuľka", "table_header_1", "Názov 1. stĺpca", "str", None, "Stĺpec zo šablóny."),
    ("Tabuľka", "table_header_2", "Názov 2. stĺpca", "str", None, "Stĺpec, ktorý dopisuješ."),
    ("Tabuľka", "table_separator", "Oddeľovač v TXT", "sep", None,
     "Text pred oddeľovačom ide do 1. stĺpca, za ním do 2. stĺpca."),
    ("Tabuľka", "table_template_readonly", "Zamknúť stĺpec zo šablóny", "bool", None,
     "1. stĺpec sa nedá prepísať."),
    ("Tabuľka", "table_empty_rows", "Prázdne riadky", "int", (0, 50),
     "Koľko prázdnych riadkov, keď šablóna nie je."),
    ("Skratky", "shortcut_collapse", "Zbaliť / rozbaliť", "str", None, "Zmena platí po reštarte Anki."),
    ("Skratky", "shortcut_import", "Import TXT", "str", None, ""),
    ("Skratky", "shortcut_mode", "Text / tabuľka", "str", None, ""),
    ("Skratky", "shortcut_wider", "Širší", "str", None, ""),
    ("Skratky", "shortcut_narrower", "Užší", "str", None, ""),
    ("Skratky", "shortcut_settings", "Nastavenia", "str", None, ""),
]


def _help_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: gray; font-size: 11px;")
    return lbl


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Deep Notes – nastavenia")
        self.setMinimumWidth(560)
        self.conf = cfg()
        self.widgets = {}
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        forms = {}
        for tab, key, label, kind, extra, helptext in SPEC:
            if tab not in forms:
                page = QWidget()
                form = QFormLayout(page)
                tabs.addTab(page, tab)
                forms[tab] = form
                if tab == "Šablóny":
                    self._rules_box(form)
            form = forms[tab]
            w = self._make(key, kind, extra)
            w.setToolTip(helptext)
            form.addRow(label, w)
            if helptext:
                form.addRow("", _help_label(helptext))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---- widgets
    def _value(self, key):
        headers = list(self.conf["table_headers"]) + ["", ""]
        if key == "table_header_1":
            return headers[0]
        if key == "table_header_2":
            return headers[1]
        return self.conf.get(key, DEFAULTS.get(key))

    def _make(self, key, kind, extra):
        val = self._value(key)
        if kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(val))
        elif kind == "int":
            w = QSpinBox()
            w.setRange(*extra)
            w.setValue(int(val))
        elif kind == "choice":
            w = QComboBox()
            w.addItems(extra)
            if val in extra:
                w.setCurrentText(val)
        elif kind == "sep":
            w = QComboBox()
            for name, ch in SEPARATORS:
                w.addItem(name, ch)
            idx = [ch for _, ch in SEPARATORS].index(val) if val in [c for _, c in SEPARATORS] else 0
            w.setCurrentIndex(idx)
        elif kind == "dir":
            w = QWidget()
            row = QHBoxLayout(w)
            row.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(str(val or ""))
            edit.setPlaceholderText(os.path.join("user_files", "templates"))
            browse = QPushButton("…")
            browse.setFixedWidth(30)
            browse.clicked.connect(lambda: self._browse(edit))
            open_btn = QPushButton("Otvoriť")
            open_btn.clicked.connect(open_template_dir)
            row.addWidget(edit, 1)
            row.addWidget(browse)
            row.addWidget(open_btn)
            w.edit = edit
        else:
            w = QLineEdit(str(val or ""))
        self.widgets[key] = (kind, w)
        return w

    def _browse(self, edit):
        start = edit.text() or template_dir()
        path = QFileDialog.getExistingDirectory(self, "Priečinok šablón", start)
        if path:
            edit.setText(path)

    def _rules_box(self, form):
        form.addRow(QLabel("<b>Pravidlá podľa tagu</b> (prvé zhora, ktoré sedí, vyhráva)"))
        form.addRow("", _help_label(
            "Tag „Kosti“ sedí na Kosti, Kosti::HK, Kosti::DK::femur … "
            "Tag „Kosti::HK“ len na tú vetvu. Súbor sa hľadá v priečinku šablón "
            "(alebo zadaj celú cestu)."
        ))
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Tag", "Súbor .txt"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(140)
        for rule in self.conf.get("tag_rules") or []:
            self._rule_row(table, rule.get("tag", ""), rule.get("file", ""))
        btns = QHBoxLayout()
        add = QPushButton("Pridať pravidlo")
        add.clicked.connect(lambda: self._rule_row(table, "", ""))
        rem = QPushButton("Odstrániť")
        rem.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        up = QPushButton("▲")
        up.setFixedWidth(30)
        up.clicked.connect(lambda: self._move(table, -1))
        down = QPushButton("▼")
        down.setFixedWidth(30)
        down.clicked.connect(lambda: self._move(table, 1))
        for b in (add, rem, up, down):
            btns.addWidget(b)
        btns.addStretch()
        form.addRow(table)
        form.addRow(btns)
        self.rules_table = table

    def _rule_row(self, table, tag, fname):
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(tag))
        table.setItem(r, 1, QTableWidgetItem(fname))

    def _move(self, table, step):
        r = table.currentRow()
        t = r + step
        if r < 0 or t < 0 or t >= table.rowCount():
            return
        for c in range(2):
            a, b = table.takeItem(r, c), table.takeItem(t, c)
            table.setItem(r, c, b)
            table.setItem(t, c, a)
        table.setCurrentCell(t, 0)

    # ---- save
    def save(self):
        new = {}
        headers = list(self.conf["table_headers"]) + ["", ""]
        for key, (kind, w) in self.widgets.items():
            if kind == "bool":
                v = w.isChecked()
            elif kind == "int":
                v = w.value()
            elif kind == "choice":
                v = w.currentText()
            elif kind == "sep":
                v = w.currentData()
            elif kind == "dir":
                v = w.edit.text().strip()
            else:
                v = w.text().strip()
            if key == "table_header_1":
                headers[0] = v
            elif key == "table_header_2":
                headers[1] = v
            else:
                new[key] = v
        new["table_headers"] = headers[:2]
        rules = []
        t = self.rules_table
        for r in range(t.rowCount()):
            tag = (t.item(r, 0).text() if t.item(r, 0) else "").strip()
            fname = (t.item(r, 1).text() if t.item(r, 1) else "").strip()
            if tag and fname:
                rules.append({"tag": tag, "file": fname})
        new["tag_rules"] = rules
        save_cfg(**new)
        apply_settings()
        tooltip("Deep Notes: uložené")
        self.accept()


def open_settings() -> None:
    SettingsDialog(mw).exec()


def open_template_dir() -> None:
    folder = template_dir()
    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def apply_settings() -> None:
    """Apply what can change live; area, logo and shortcuts need a restart."""
    if not state["dock"]:
        return
    conf = cfg()
    font = QFont(conf["font_family"], int(conf["font_size"]))
    state["text_box"].setFont(font)
    state["table"].setFont(font)
    headers = list(conf["table_headers"]) + ["", ""]
    state["table"].setHorizontalHeaderLabels(headers[:2])
    apply_mode()
    if state["body"].isVisible():
        set_width(conf["dock_width"])
    card = mw.reviewer.card if mw.state == "review" else None
    if card:
        load_for_card(card)


# ------------------------------------------------------------------ hooks

def on_show_question(card) -> None:
    create_dock()
    register_shortcuts()
    state["dock"].show()
    if state["card_id"] != card.id:
        state["card_id"] = card.id
        load_for_card(card)
    if cfg()["auto_focus"] and state["body"].isVisible():
        target = state["table"] if cfg()["mode"] == "table" else state["text_box"]
        target.setFocus()


def on_answer(reviewer, card, ease) -> None:
    if cfg()["clear_after_answer"]:
        clear_all()
    state["card_id"] = None


def on_state_change(new_state, old_state) -> None:
    if state["dock"] and cfg()["hide_outside_review"] and new_state != "review":
        state["dock"].hide()


def on_profile_close() -> None:
    dock = state["dock"]
    if dock and state["body"].isVisible() and cfg()["remember_width"]:
        save_cfg(dock_width=dock.width())


gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.state_did_change.append(on_state_change)
gui_hooks.profile_will_close.append(on_profile_close)
gui_hooks.main_window_did_init.append(add_menu)
mw.addonManager.setConfigAction(ADDON_KEY, open_settings)
