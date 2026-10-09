"""Deep Notes by AnkiMonkey - scratchpad panel for the Anki reviewer.

Features
- dockable panel (left/right), adjustable + remembered width, collapse to a thin strip
- text mode (free scratchpad) or table mode (template column + your own column)
- TXT templates: loaded automatically per card (by tag -> deck -> default.txt)
  or manually via "Import TXT"
- keyboard shortcuts (configurable): Alt+N collapse, Alt+I import, Alt+T mode,
  Alt+= / Alt+- width
Everything is local, no cloud.
"""

import os

from aqt import gui_hooks, mw
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QDockWidget,
    QFileDialog,
    QFont,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPixmap,
    QPushButton,
    QShortcut,
    Qt,
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
    "table_separator": "\t",
    "table_headers": ["Základ", "Moje"],
    "table_template_readonly": True,
    "table_empty_rows": 5,
    "shortcut_collapse": "Alt+N",
    "shortcut_import": "Alt+I",
    "shortcut_mode": "Alt+T",
    "shortcut_wider": "Alt+=",
    "shortcut_narrower": "Alt+-",
}

COLLAPSED_WIDTH = 30

state = {
    "dock": None,
    "body": None,
    "text_box": None,
    "table": None,
    "mode_btn": None,
    "collapse_btn": None,
    "source_label": None,
    "card_id": None,
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


def find_template(card):
    folder = template_dir()
    if not os.path.isdir(folder):
        return None, None
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
        state["mode_btn"].setText("Text" if table_mode else "Tabuľka")


def set_width(width: int) -> None:
    dock = state["dock"]
    if not dock:
        return
    conf = cfg()
    width = max(int(conf["min_width"]), int(width))
    dock.setMinimumWidth(int(conf["min_width"]))
    mw.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
    if conf["remember_width"]:
        save_cfg(dock_width=width)


def wider() -> None:
    expand()
    set_width(state["dock"].width() + int(cfg()["width_step"]))


def narrower() -> None:
    expand()
    set_width(state["dock"].width() - int(cfg()["width_step"]))


def collapse() -> None:
    dock = state["dock"]
    if not dock or not state["body"].isVisible():
        return
    if cfg()["remember_width"]:
        save_cfg(dock_width=dock.width())
    state["body"].hide()
    dock.setMinimumWidth(COLLAPSED_WIDTH)
    mw.resizeDocks([dock], [COLLAPSED_WIDTH], Qt.Orientation.Horizontal)
    state["collapse_btn"].setText("⇤" if cfg()["dock_area"] == "right" else "⇥")
    save_cfg(collapsed=True)


def expand() -> None:
    dock = state["dock"]
    if not dock or state["body"].isVisible():
        return
    state["body"].show()
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
    b.setMinimumWidth(24)
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

    # toolbar: always visible (also when collapsed)
    bar = QHBoxLayout()
    bar.setSpacing(2)
    collapse_btn = _btn("⇥", f"Zbaliť / rozbaliť ({conf['shortcut_collapse']})", toggle_collapse)
    bar.addWidget(collapse_btn, 0, Qt.AlignmentFlag.AlignTop)
    state["collapse_btn"] = collapse_btn

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(4)

    tools = QHBoxLayout()
    tools.setSpacing(2)
    tools.addWidget(_btn("−", f"Užší ({conf['shortcut_narrower']})", narrower))
    tools.addWidget(_btn("+", f"Širší ({conf['shortcut_wider']})", wider))
    tools.addWidget(_btn("TXT", f"Import TXT ({conf['shortcut_import']})", import_txt))
    mode_btn = _btn("Tabuľka", f"Text / tabuľka ({conf['shortcut_mode']})", toggle_mode)
    tools.addWidget(mode_btn)
    state["mode_btn"] = mode_btn
    tools.addWidget(_btn("＋riadok", "Pridať riadok do tabuľky", lambda: add_row()))
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
            tools.addWidget(logo)

    body_layout.addLayout(tools)

    source = QLabel("")
    source.setStyleSheet("font-size: 11px; color: gray;")
    body_layout.addWidget(source)
    state["source_label"] = source

    font = QFont(conf["font_family"], int(conf["font_size"]))

    text_box = QTextEdit()
    text_box.setFont(font)
    text_box.setPlaceholderText("Write thoughts, reasoning, hypotheses...")
    body_layout.addWidget(text_box)
    state["text_box"] = text_box

    table = QTableWidget(0, 2)
    table.setFont(font)
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

    bar.addWidget(body, 1)
    root_layout.addLayout(bar, 1)

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
