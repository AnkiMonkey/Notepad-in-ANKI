"""Deep Notes by AnkiMonkey - scratchpad panel for the Anki reviewer.

Features
- dockable panel (left/right), adjustable + remembered width, collapse to a thin strip
- text mode (free scratchpad) or table mode (template column + your own column)
- table without a template asks "Rows?" on every card (number + Enter)
- TXT templates: loaded automatically per card (by tag -> deck -> default.txt)
  or manually via "Import TXT"
- tag rules: e.g. tag Bones (or Bones::UpperLimb ...) -> bones_notes.txt
- settings dialog (gear button, Alt+S, or Tools > Add-ons > Config)
- keyboard shortcuts (configurable): Alt+N collapse, Alt+I import, Alt+M mode,
  Alt+. / Alt+, width, Alt+S settings, Alt+P jump into panel, Alt+W save as template
- typing in the panel never triggers Anki review keys (Enter, Space, 1-4);
  Enter = next row, Tab = next cell, Esc = back to the card
- optional "Auto rows" (off by default, toggle with the Auto button or Alt+K):
  rows are taken from the card's legend (user_files/legend_labels.json, made by OCR)
  and points your teacher does NOT want ("NIE: 4, 6, 8" in Personal Notes) get "-"
- optional "Check" (off by default, Check button or Alt+J): Enter or a space at the end
  of your answer checks it against the legend (user_files/legend_answers.json);
  green = correct and jumps to the next row, red = wrong and you stay in the cell
Everything is local, no cloud.
"""

import json
import os
import re
import unicodedata

from aqt import gui_hooks, mw
from aqt.qt import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QAction,
    QCheckBox,
    QColor,
    QComboBox,
    QDesktopServices,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QEvent,
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
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QTabWidget,
    Qt,
    QTimer,
    QUrl,
    QTableWidget,
    QTableWidgetItem,
    QApplication,
    QTextCursor,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import tooltip

ADDON_DIR = os.path.dirname(__file__)
ADDON_KEY = __name__.split(".")[0]
from .common import get_section, write_section

DEFAULTS = {
    "dock_area": "right",
    "dock_width": 320,
    "min_width": 200,
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
    "remember_zoom": True,
    "web_zoom": None,
    "template_dir": "",
    "auto_load_template": True,
    "default_template": "default.txt",
    "tag_rules": [],
    "rules_first_tag_only": False,
    "table_separator": "\t",
    "table_headers": ["Base", "Notes"],
    "table_template_readonly": True,
    "table_empty_rows": 10,
    "table_numbered": True,
    "table_ask_rows": True,
    "smart_rows": False,
    "smart_notes_field": "Personal Notes",
    "smart_dash": "-",
    "check_answers": False,
    "check_ok_color": "#55ff55",
    "check_bad_color": "#ff5555",
    "check_dunno_color": "#55aaff",
    "check_dunno_words": "?, idk, neviem, nwm, nv",
    "check_long_words": 4,
    "check_long_percent": 30,
    # abbreviations accepted by Check (both ways: typing the short form, or the legend using it)
    "check_abbrev": {
        "SIAS": "spina iliaca anterior superior",
        "SIAI": "spina iliaca anterior inferior",
        "SIPS": "spina iliaca posterior superior",
        "SIPI": "spina iliaca posterior inferior",
    },
    "shortcut_collapse": "Alt+N",
    "shortcut_import": "Alt+I",
    "shortcut_mode": "Alt+M",
    "shortcut_wider": "Alt+.",
    "shortcut_narrower": "Alt+,",
    "shortcut_settings": "Alt+S",
    "shortcut_focus": "Alt+P",
    "shortcut_save": "Alt+W",
    "shortcut_smart": "Alt+K",
    "shortcut_check": "Alt+J",
    "shortcut_hint": "Alt+G",
    "hint_word": "hint",
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
    "template_path": None,
    "card": None,
    "shortcuts": [],
    "clash_checked": False,
    "rows_bar": None,
    "rows_box": None,
    "last_rows": None,
    "smart_btn": None,
    "legend_labels": None,
    "legend_answers": None,
    "legend_answers_full": None,
    "check_btn": None,
}


# ----------------------------------------------------------------- config

# shortcuts from older versions that never fired (layout issues / clash with the Tools menu)
OLD_SHORTCUTS = {
    "shortcut_wider": {"Alt+=": "Alt+."},
    "shortcut_narrower": {"Alt+-": "Alt+,"},
    "shortcut_mode": {"Alt+T": "Alt+M"},
}


def cfg() -> dict:
    user = get_section("deep_notes")
    merged = dict(DEFAULTS)
    merged.update(user)
    for key, mapping in OLD_SHORTCUTS.items():
        if merged.get(key) in mapping:
            merged[key] = mapping[merged[key]]
    return merged


def save_cfg(**changes) -> None:
    conf = cfg()
    conf.update(changes)
    write_section("deep_notes", conf)


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
        table.resizeRowsToContents()
        return
    for ln in lines:
        base, _, mine = ln.partition(sep)
        add_row(base.strip(), mine.strip(), locked=conf["table_template_readonly"])
    table.resizeRowsToContents()


def _next_number() -> str:
    """Number for a new row: last numeric value in column 1 + 1."""
    table = state["table"]
    for r in range(table.rowCount() - 1, -1, -1):
        it = table.item(r, 0)
        txt = it.text().strip() if it else ""
        if txt.isdigit():
            return str(int(txt) + 1)
        if txt:
            return ""
    return "1"


def add_row(base=None, mine: str = "", locked: bool = False) -> int:
    """Append a row; without base text and with table_numbered on, column 1 gets the next number."""
    table = state["table"]
    if base is None:
        base = _next_number() if cfg()["table_numbered"] else ""
        locked = bool(base)
    r = table.rowCount()
    table.insertRow(r)
    a = QTableWidgetItem(base)
    if locked and base:
        a.setFlags(a.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(r, 0, a)
    table.setItem(r, 1, QTableWidgetItem(mine))
    return r


def fill_numbered(n: int) -> None:
    """Table with n rows (numbered when table_numbered is on), Notes column empty."""
    table = state["table"]
    table.setRowCount(0)
    for _ in range(max(0, int(n))):
        add_row()
    table.resizeRowsToContents()


def ask_rows() -> None:
    """Show the 'Rows?' bar above the table, pre-filled with the last number used."""
    bar, box = state["rows_bar"], state["rows_box"]
    if not bar:
        return
    last = state.get("last_rows")
    box.setValue(int(last if last is not None else cfg()["table_empty_rows"]))
    bar.show()
    # after Anki has finished showing the question (it focuses the card itself)
    QTimer.singleShot(60, _focus_rows_box)


def _focus_rows_box() -> None:
    bar, box = state["rows_bar"], state["rows_box"]
    if bar and bar.isVisible():
        box.setFocus()
        box.selectAll()


def confirm_rows() -> None:
    """Enter / OK in the 'Rows?' bar: build the rows and jump into the first Notes cell."""
    box = state["rows_box"]
    box.interpretText()
    n = box.value()
    state["last_rows"] = n
    state["rows_bar"].hide()
    fill_numbered(n)
    if cfg()["smart_rows"] and state.get("card"):
        apply_dashes(state["card"])
    focus_panel()


def skip_rows() -> None:
    """Esc in the 'Rows?' bar: keep the current rows, keyboard back to the card."""
    state["rows_bar"].hide()
    focus_reviewer()


# ------------------------------------------------------------- auto rows

def labels_path() -> str:
    return os.path.join(ADDON_DIR, "user_files", "legend_labels.json")


def legend_labels() -> dict:
    """{image file name: [labels in legend order]}; read once, cached."""
    if state["legend_labels"] is None:
        try:
            with open(labels_path(), encoding="utf-8-sig") as fh:
                state["legend_labels"] = json.load(fh)
        except (OSError, ValueError):
            state["legend_labels"] = {}
    return state["legend_labels"]


def labels_for_card(card):
    """Labels of the first image on the note that is in legend_labels.json."""
    known = legend_labels()
    if not known:
        return None
    for value in card.note().values():
        for src in re.findall(r'src="([^"]+)"', value):
            if src in known:
                return list(known[src])
    return None


def _norm_label(s: str) -> str:
    return re.sub(r"\s+", "", s).replace("’", "'").casefold()


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return s.replace("&nbsp;", " ")


def _tokens(text: str) -> list:
    """'1, 3-5, 3 (B), 1b' -> ['1', '3', '4', '5', '3(b)', '1b']"""
    out = []
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        rng = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", part)
        if rng:
            a, b = int(rng.group(1)), int(rng.group(2))
            if a <= b and b - a < 200:
                out += [str(i) for i in range(a, b + 1)]
            continue
        out.append(_norm_label(part))
    return out


def _matches(label: str, token: str, labels_norm: set) -> bool:
    lab = _norm_label(label)
    if lab == token:
        return True
    if token.isdigit():
        # "6" also covers 6a / 6b when the legend has no plain 6 (2' stays its own point)
        if token not in labels_norm and re.fullmatch(re.escape(token) + r"[a-z]'?", lab):
            return True
    return False


def skip_labels(card, labels: list) -> set:
    """Indexes of rows the teacher does not want, read from the notes field.

    "NIE: 4, 6, 8"   -> those get the dash
    "NIE: celá karta" -> every row gets the dash
    "všetky"          -> nothing
    "body 1-10" / "1, 3, 7" (no NIE) -> everything NOT listed gets the dash
    """
    conf = cfg()
    note = card.note()
    field = conf["smart_notes_field"]
    if field not in note.keys():
        return set()
    text = _strip_html(note[field]).strip()
    if not text:
        return set()
    low = text.casefold()
    labels_norm = {_norm_label(x) for x in labels}
    m = re.search(r"\bnie\b\s*:?\s*(.*)", low, re.S)
    if m:
        rest = m.group(1).strip()
        if re.match(r"cel[áa]", rest) or rest.startswith("nic"):
            return set(range(len(labels)))
        toks = _tokens(rest)
        return {i for i, lab in enumerate(labels) if any(_matches(lab, t, labels_norm) for t in toks)}
    if re.search(r"v[šs]etk", low):
        return set()
    after = low.split(":", 1)[1] if ":" in low else low
    after = re.sub(r"^\D*?(?=\d)", "", after)
    toks = _tokens(after)
    if not toks:
        return set()
    return {i for i, lab in enumerate(labels) if not any(_matches(lab, t, labels_norm) for t in toks)}


def apply_dashes(card) -> None:
    """Put the dash into the Notes cell of every row the teacher does not want."""
    t = state["table"]
    labels = []
    for r in range(t.rowCount()):
        it = t.item(r, 0)
        labels.append(it.text().strip() if it else "")
    dash = cfg()["smart_dash"]
    for r in skip_labels(card, labels):
        it = t.item(r, 1)
        if it is None:
            it = QTableWidgetItem("")
            t.setItem(r, 1, it)
        it.setText(dash)
        it.setForeground(QColor("gray"))


def smart_fill(card) -> bool:
    """Auto rows on: rows from the legend + dashes. False = legend unknown."""
    labels = labels_for_card(card)
    if not labels:
        return False
    t = state["table"]
    t.setRowCount(0)
    for lab in labels:
        add_row(lab, "", locked=True)
    apply_dashes(card)
    t.resizeRowsToContents()
    return True


# ----------------------------------------------------------------- check

STOPWORDS = {"a", "et", "na", "do", "s", "se", "v", "ve", "z", "ze", "pro", "jeho", "jako", "k", "ke", "o", "u"}


def legend_answers() -> dict:
    """{image file name: {label: legend text}}; read once, cached."""
    if state["legend_answers"] is None:
        try:
            with open(os.path.join(ADDON_DIR, "user_files", "legend_answers.json"), encoding="utf-8-sig") as fh:
                state["legend_answers"] = json.load(fh)
        except (OSError, ValueError):
            state["legend_answers"] = {}
    return state["legend_answers"]


def legend_answers_full() -> dict:
    """Optional legend_answers_full.json: the complete legend wording. Your answer may match
    either the short practical form (legend_answers.json) or this full one."""
    if state["legend_answers_full"] is None:
        try:
            with open(os.path.join(ADDON_DIR, "user_files", "legend_answers_full.json"), encoding="utf-8-sig") as fh:
                state["legend_answers_full"] = json.load(fh)
        except (OSError, ValueError):
            state["legend_answers_full"] = {}
    return state["legend_answers_full"]


def full_answer_for(card, label: str) -> str:
    known = legend_answers_full()
    if not known or card is None:
        return ""
    for value in card.note().values():
        for src in re.findall(r'src="([^"]+)"', value):
            if src in known:
                return known[src].get(label, "")
    return ""


def answers_for_card(card) -> dict:
    known = legend_answers()
    if not known or card is None:
        return {}
    for value in card.note().values():
        for src in re.findall(r'src="([^"]+)"', value):
            if src in known:
                return known[src]
    return {}


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _words(s: str) -> list:
    return re.findall(r"[a-z0-9]+", _plain(s))


def _close(a: str, b: str) -> bool:
    """One typo allowed in longer words (missing, extra or wrong letter)."""
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]:
            return True  # two swapped letters (corpsu)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 1


_ABBR = {"mtime": None, "map": {}}


def abbreviations() -> dict:
    """user_files/abbreviations.txt: 'tbc = tuberculum', 'v = vertebra, vena'.
    Re-read when the file changes, so edits work without restarting Anki."""
    path = os.path.join(ADDON_DIR, "user_files", "abbreviations.txt")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if mtime != _ABBR["mtime"]:
        mapping = {}
        try:
            with open(path, encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.split("#", 1)[0].strip()
                    if "=" not in line:
                        continue
                    key, _, vals = line.partition("=")
                    key = "".join(_words(key))
                    for v in vals.split(","):
                        w = "".join(_words(v))
                        if key and w:
                            mapping.setdefault(key, set()).add(w)
        except OSError:
            pass
        _ABBR["mtime"], _ABBR["map"] = mtime, mapping
    return _ABBR["map"]


def _same_stem(a: str, b: str) -> bool:
    """anterior ~ anterius, transversus ~ transversarium, vertebra ~ vertebrae."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n == min(len(a), len(b)) or n >= max(4, min(len(a), len(b)) - 3)


def _word_ok(typed: str, real: str) -> bool:
    if real.startswith(typed) or _close(typed, real):
        return True
    return any(_same_stem(full, real) for full in abbreviations().get(typed, ()))


def _covers(typed: list, real: list) -> bool:
    """Every typed word fits the next legend word (abbreviation, full word or one typo);
    only small filler words (a, na, do ...) of the legend may be left out."""
    i = 0
    for w in real:
        if i < len(typed) and _word_ok(typed[i], w):
            i += 1
        elif w in STOPWORDS:
            continue
        else:
            return False
    return i == len(typed)


def _variants(answer: str) -> list:
    """Whole text, text without (brackets), and every part split by , ; or ' a ' / ' et '."""
    out = []
    base = [answer, re.sub(r"\([^)]*\)", " ", answer)]
    for b in base:
        out.append(b)
        out += re.split(r"[,;]| a | et ", b)
    return [v for v in (_words(x) for x in out) if v]


def _expand_abbrev(text: str) -> str:
    ab = cfg().get("check_abbrev") or {}
    for short, full in ab.items():
        text = re.sub(r"(?<!\w)" + re.escape(short) + r"(?!\w)", full, text, flags=re.I)
    return text


def answer_ok(typed: str, answer: str, label: str = "") -> bool:
    typed, answer = _expand_abbrev(typed), _expand_abbrev(answer)
    words = _words(typed)
    if words and label and words[0] == _plain(re.sub(r"\W", "", label)):
        words = words[1:]  # "3b pr transversus" -> label typed in front is fine
    if not words:
        return False
    if any(_covers(words, v) for v in _variants(answer)):
        return True
    if _genitive_ok(words, answer):
        return True
    return _long_ok(words, answer)


# Genitive attribute is optional: "corpus" = "corpus vertebrae", "foramina sacralia" =
# "foramina sacralia ossis sacri" – in both directions (legend has it / you typed it).
# A different genitive is still wrong ("incisura ulnaris radii" ≠ "incisura radialis ulnae").
GEN_ENDINGS = ("ae", "orum", "arum", "ium", "uum", "ei")
GEN_IS = {"ossis", "femoris", "capitis", "pelvis", "corporis", "pectoris", "dentis", "partis",
          "marginis", "tuberis", "foraminis", "cartilaginis", "laminae", "cruris", "pedis",
          "auris", "oris", "nasi", "cordis", "renis", "lienis", "hepatis", "colli", "manus",
          "cranii", "orbitae", "sellae", "processus", "tuberositatis", "arcus", "musculi",
          "nervi", "arteriae", "venae", "ligamenti", "sinus", "canalis", "sulci", "fossae"}


def _gen_start(words: list):
    """Index where a trailing genitive attribute starts (never the first word), else None."""
    for i in range(1, len(words)):
        w = words[i]
        if w in GEN_IS or w.endswith(GEN_ENDINGS) or (len(w) > 3 and w.endswith("i")):
            return i
    return None


def _genitive_ok(words: list, answer: str) -> bool:
    ans_words = _words(answer)
    i = _gen_start(ans_words)
    if i and any(_covers(words, v) for v in _variants(" ".join(ans_words[:i]))):
        return True                       # legend "corpus vertebrae", you typed "corpus"
    j = _gen_start(words)
    if j and any(_covers(words[:j], v) for v in _variants(answer)):
        return True                       # legend "corpus", you typed "corpus vertebrae"
    return False


def _long_ok(typed: list, answer: str) -> bool:
    """Long legend text (more than check_long_words words): enough when more than
    check_long_percent % of its words are in your answer (any order) and every
    word you typed belongs to it."""
    conf = cfg()
    # Czech/Slovak words (with diacritics: část, odpovídající …) don't count – the answer is the Latin
    raw = re.findall(r"\w+", re.sub(r"\([^)]*\)", " ", answer).casefold())
    real = [_plain(w) for w in raw if w.isascii() and _plain(w) not in STOPWORDS]
    if len(real) <= int(conf["check_long_words"]):
        return False
    hit = sum(1 for w in real if any(_word_ok(t, w) for t in typed))
    good = sum(1 for t in typed if any(_word_ok(t, w) for w in real))
    # every word you typed must belong to the legend text (so "longi" never passes for "brevis")
    return hit / len(real) * 100 > float(conf["check_long_percent"]) and good == len(typed)


def check_editor(editor, table, row: int, via_enter: bool) -> bool:
    """Returns True when the key was handled (answer known for this row)."""
    conf = cfg()
    base = table.item(row, 0)
    label = base.text().strip() if base else ""
    answer = answers_for_card(state.get("card")).get(label)
    if not answer:
        return False
    text = editor.text().strip()
    if is_dunno(text):
        reveal_answer(editor, table, row, answer)
        return True
    if via_enter and text and editor.property("dn_wrong") == text:
        # Enter again on the same wrong answer = "I don't know"
        reveal_answer(editor, table, row, answer, tried=text)
        return True
    full = full_answer_for(state.get("card"), label)
    if answer_ok(text, answer, label) or (full and full != answer and answer_ok(text, full, label)):
        item = table.item(row, 1)
        if item is None:
            item = QTableWidgetItem("")
            table.setItem(row, 1, item)
        item.setText(text)
        item.setForeground(QColor(conf["check_ok_color"]))
        item.setToolTip(full or answer)
        editor.setStyleSheet(f"color: {conf['check_ok_color']};")
        table.done_editing(editor)
        QTimer.singleShot(0, table.next_row)
        return True
    editor.setStyleSheet(f"color: {conf['check_bad_color']};")
    # only the editor turns red: touching the cell itself while editing would make Qt
    # reload the cell into the editor and wipe what you typed
    editor.setProperty("dn_wrong", text)  # Enter again (or 2 spaces) = "I don't know"
    return True


def is_dunno(text: str) -> bool:
    words = [w.strip().casefold() for w in str(cfg()["check_dunno_words"]).split(",") if w.strip()]
    return text.strip().casefold() in words


def reveal_answer(editor, table, row: int, answer: str, tried: str = "") -> None:
    """'?' / idk / neviem / second Enter: write the correct answer in blue and go on
    (what you tried is kept in the tooltip)."""
    conf = cfg()
    item = table.item(row, 1)
    if item is None:
        item = QTableWidgetItem("")
        table.setItem(row, 1, item)
    editor.setText(answer)
    item.setText(answer)
    item.setForeground(QColor(conf["check_dunno_color"]))
    full = full_answer_for(state.get("card"), table.item(row, 0).text().strip() if table.item(row, 0) else "")
    tip = full if full and full != answer else ""
    if tried:
        tip = (tip + "\n" if tip else "") + f"you wrote: {tried}"
    item.setToolTip(tip or answer)
    table.done_editing(editor)
    item.setText(answer)
    item.setForeground(QColor(conf["check_dunno_color"]))
    QTimer.singleShot(0, table.next_row)


def _hint_text(current: str, answer: str) -> str:
    """Correct start of the answer + one more letter. What you typed stays if it is a correct
    start (no diacritics / case needed), otherwise the hint starts again from the first letter."""
    n = 0
    while n < len(current) and n < len(answer) and _plain(current[n]) == _plain(answer[n]):
        n += 1
    n += 1
    while n < len(answer) and not answer[n - 1].strip():   # never stop on a space
        n += 1
    return answer[:n]


def apply_hint(editor, strip_word: bool = False) -> bool:
    """One more correct letter in the cell you are writing in."""
    table = state.get("table")
    row = _editor_row(editor, table) if table is not None else None
    if table is None or row is None:
        return False
    base = table.item(int(row), 0)
    label = base.text().strip() if base else ""
    answer = answers_for_card(state.get("card")).get(label)
    if not answer:
        tooltip("Hint: no answer for this row")
        return False
    text = editor.text()
    if strip_word:
        word = re.escape(str(cfg().get("hint_word") or "hint"))
        text = re.sub(r"\s*" + word + r"\s*$", "", text, flags=re.I)
    new = _hint_text(text, answer)
    editor.setText(new)
    editor.setCursorPosition(len(new))
    editor.setProperty("dn_hints", int(editor.property("dn_hints") or 0) + 1)
    editor.setProperty("dn_hint_text", new)     # a space right after a hint must not run Check
    editor.setToolTip(f"hints used: {editor.property('dn_hints')}")
    return True


def hint_now() -> None:
    """Hint button / shortcut: next letter in the open cell, or opens the current (or first empty) row."""
    table = state.get("table")
    if table is None or not table.isVisible():
        return
    fw = QApplication.focusWidget()
    if isinstance(fw, QLineEdit) and table.isAncestorOf(fw):
        apply_hint(fw)
        return
    row = table.currentRow()
    if row < 0 or (table.item(row, 1) and table.item(row, 1).text().strip()):
        row = next((i for i in range(table.rowCount())
                    if not (table.item(i, 1) and table.item(i, 1).text().strip())), max(row, 0))
    if table.item(row, 1) is None:
        table.setItem(row, 1, QTableWidgetItem(""))
    table.setCurrentCell(row, 1)
    table.editItem(table.item(row, 1))

    def later():
        ed = QApplication.focusWidget()
        if isinstance(ed, QLineEdit) and table.isAncestorOf(ed):
            apply_hint(ed)
    QTimer.singleShot(40, later)


def _on_editor_text(editor) -> None:
    """'?', idk, neviem ... reveal the answer as soon as they are typed (no Enter needed).
    Typing the hint word ("hint") at the end gives the next correct letter."""
    word = str(cfg().get("hint_word") or "hint").lower()
    if word and editor.text().lower().rstrip().endswith(word):
        t = editor.text().rstrip()
        if len(t) == len(word) or not t[-len(word) - 1].isalnum():
            apply_hint(editor, strip_word=True)
            return
    if not cfg()["check_answers"] or not is_dunno(editor.text()):
        return
    table = state["table"]
    row = _editor_row(editor, table) if table is not None else None
    if table is None or row is None:
        return
    base = table.item(int(row), 0)
    label = base.text().strip() if base else ""
    answer = answers_for_card(state.get("card")).get(label)
    if answer and not editor.property("dn_done"):
        editor.setProperty("dn_done", True)
        QTimer.singleShot(0, lambda: reveal_answer(editor, table, int(row), answer))


def _editor_row(editor, table):
    """Row the editor really sits in (by its position), falling back to the row it was made for."""
    try:
        idx = table.indexAt(editor.geometry().center())
        if idx.isValid():
            return idx.row()
    except Exception:
        pass
    row = editor.property("dn_row")
    return int(row) if row is not None else None


def _safe_dunno(editor) -> None:
    try:
        if editor.property("dn_done"):
            return
        _on_editor_text(editor)
    except RuntimeError:
        pass  # editor already closed


class CheckDelegate(QStyledItemDelegate):
    """Editor for the Notes column: Enter / space at the end checks the answer."""

    def createEditor(self, parent, option, index):
        ed = super().createEditor(parent, option, index)
        if isinstance(ed, QLineEdit):
            # same font as the finished (green/red) cells
            tbl = state.get("table")
            ed.setFont(tbl.font() if tbl is not None else parent.font())
        if index.column() == 1 and isinstance(ed, QLineEdit):
            ed.installEventFilter(self)
            ed.setProperty("dn_row", index.row())
            ed.textEdited.connect(lambda _t, e=ed: _on_editor_text(e))
        return ed

    def eventFilter(self, obj, ev):
        if (
            ev.type() == QEvent.Type.KeyPress
            and isinstance(obj, QLineEdit)
            and cfg()["check_answers"]
            and not (ev.modifiers() & _REVIEW_MODS)
        ):
            table = state["table"]
            row = _editor_row(obj, table)
            if row is not None and table is not None:
                key = ev.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if check_editor(obj, table, int(row), True):
                        return True
                elif key == Qt.Key.Key_Space and obj.cursorPosition() == len(obj.text()):
                    if obj.property("dn_hint_text") is not None and obj.text() == obj.property("dn_hint_text"):
                        obj.insert(" ")     # space after a hint: just a space, so "hint" can follow
                        return True
                    if obj.text().endswith(" ") and obj.text().strip():
                        # two spaces = "I don't know": show the answer
                        base = table.item(int(row), 0)
                        label = base.text().strip() if base else ""
                        answer = answers_for_card(state.get("card")).get(label)
                        if answer:
                            reveal_answer(obj, table, int(row), answer, tried=obj.text().strip())
                            return True
                    obj.insert(" ")
                    check_editor(obj, table, int(row), False)
                    return True
                else:
                    if obj.styleSheet():
                        obj.setStyleSheet("")  # typing again: back to normal colour
                    # after the key is in the text: '?', idk, neviem ... reveal at once
                    QTimer.singleShot(0, lambda e=obj: _safe_dunno(e))
        return super().eventFilter(obj, ev)


def toggle_check() -> None:
    new = not cfg()["check_answers"]
    save_cfg(check_answers=new)
    update_check_btn()
    tooltip(f"Deep Notes: check {'ON' if new else 'OFF'}")


def update_check_btn() -> None:
    b = state.get("check_btn")
    if b:
        on = bool(cfg()["check_answers"])
        b.setChecked(on)
        b.setText("Check ✓" if on else "Check")


def toggle_smart() -> None:
    new = not cfg()["smart_rows"]
    save_cfg(smart_rows=new)
    update_smart_btn()
    card = mw.reviewer.card if mw.state == "review" else None
    if card and state["dock"]:
        load_for_card(card)
    tooltip(f"Deep Notes: auto rows {'ON' if new else 'OFF'}")


def update_smart_btn() -> None:
    b = state.get("smart_btn")
    if b:
        on = bool(cfg()["smart_rows"])
        b.setChecked(on)
        b.setText("Auto ✓" if on else "Auto")


def _table_has_base() -> bool:
    t = state["table"]
    for r in range(t.rowCount()):
        it = t.item(r, 0)
        if it and it.text().strip():
            return True
    return False


def load_for_card(card) -> None:
    """Fill the panel for a new card.

    Table: a template for this card replaces the Base column; without one the
    Base column you already have stays (first time: numbered rows).
    Text: the template text, or empty.
    """
    state["card"] = card
    path, text = find_template(card) if cfg()["auto_load_template"] else (None, None)
    state["template_path"] = path
    if state["rows_bar"]:
        state["rows_bar"].hide()
    if cfg()["mode"] == "table":
        if path:
            fill_table(text)
        elif cfg()["smart_rows"] and smart_fill(card):
            pass
        else:
            if not _table_has_base():
                fill_table("")
            if cfg()["table_ask_rows"] and state["body"].isVisible():
                ask_rows()
    else:
        fill_text(text)
    set_source(os.path.basename(path) if path else "")


def clear_mine() -> None:
    """After answering: table keeps the Base column and empties Notes; text is emptied."""
    t = state["table"]
    if t:
        for r in range(t.rowCount()):
            it = t.item(r, 1)
            if it:
                it.setText("")
                it.setData(Qt.ItemDataRole.ForegroundRole, None)
        # drop extra rows that are now completely empty (keeps numbered rows)
        for r in range(t.rowCount() - 1, int(cfg()["table_empty_rows"]) - 1, -1):
            base = t.item(r, 0)
            if base is None or not base.text().strip():
                t.removeRow(r)
    if state["text_box"]:
        state["text_box"].clear()
        state["text_box"].setPlaceholderText("Cleared ✓")


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
    if state["rows_bar"] and not table_mode:
        state["rows_bar"].hide()
    if state["mode_btn"]:
        state["mode_btn"].setText("→ Text" if table_mode else "→ Table")
        state["mode_btn"].setToolTip(
            ("Switch to text" if table_mode else "Switch to table")
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
    state["collapse_btn"].setText("«" if cfg()["dock_area"] == "right" else "»")
    save_cfg(collapsed=True)


def expand() -> None:
    dock = state["dock"]
    if not dock or state["body"].isVisible():
        return
    state["body"].show()
    state["tools"].show()
    dock.setMaximumWidth(QT_MAX)
    state["collapse_btn"].setText("»" if cfg()["dock_area"] == "right" else "«")
    save_cfg(collapsed=False)
    set_width(cfg()["dock_width"])


def toggle_collapse() -> None:
    if not state["dock"]:
        return
    if state["body"].isVisible():
        collapse()
    else:
        expand()


def focus_reviewer() -> None:
    """Esc in the panel: give the keyboard back to the card."""
    try:
        mw.web.setFocus()
    except Exception:
        mw.setFocus()


def focus_panel() -> None:
    """Alt+P: jump into the panel (first empty cell of 'Notes' in table mode)."""
    if not state["dock"]:
        return
    expand()
    if cfg()["mode"] == "table":
        t = state["table"]
        if t.rowCount() == 0:
            add_row()
        target = 0
        for r in range(t.rowCount()):
            it = t.item(r, 1)
            if it is None or not it.text().strip():
                target = r
                break
        t.setFocus()
        t.setCurrentCell(target, 1)
        t.editItem(t.item(target, 1))
    else:
        state["text_box"].setFocus()


def _default_template_name(card) -> str:
    rule = rule_file(card) if card else None
    if rule:
        return rule
    tags = card.note().tags if card else []
    if tags:
        return tags[0].replace("::", "__") + ".txt"
    return cfg()["default_template"]


def save_template() -> None:
    """Alt+W: save the panel as the template for this card (column 1 in table mode)."""
    if not state["dock"]:
        return
    path = state.get("template_path")
    if not path:
        folder = template_dir()
        os.makedirs(folder, exist_ok=True)
        name = _default_template_name(state.get("card"))
        path = name if os.path.isabs(name) else os.path.join(folder, name)
    if cfg()["mode"] == "table":
        t = state["table"]
        lines = []
        for r in range(t.rowCount()):
            it = t.item(r, 0)
            txt = it.text().strip() if it else ""
            if txt:
                lines.append(txt)
        content = "\n".join(lines) + ("\n" if lines else "")
    else:
        content = state["text_box"].toPlainText()
    if os.path.isfile(path):
        # keep the previous version, in case Alt+W was pressed by mistake
        try:
            with open(path, encoding="utf-8-sig") as src, open(path + ".bak", "w", encoding="utf-8") as dst:
                dst.write(src.read())
        except OSError:
            pass
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    state["template_path"] = path
    set_source(os.path.basename(path))
    tooltip(f"Deep Notes: saved to {os.path.basename(path)}")


# ------------------------------------------------- keyboard-safe widgets

_REVIEW_MODS = Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ControlModifier


def _eat_shortcut(ev) -> bool:
    """Plain keys typed in the panel must not reach Anki's reviewer shortcuts."""
    if ev.type() == QEvent.Type.ShortcutOverride and not (ev.modifiers() & _REVIEW_MODS):
        ev.accept()
        return True
    return False


class PanelTextEdit(QTextEdit):
    def event(self, ev):
        if _eat_shortcut(ev):
            return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            focus_reviewer()
            return
        super().keyPressEvent(ev)


class PanelTable(QTableWidget):
    """Enter = save cell + next row (adds a row at the end), Tab = next cell,
    Esc = cancel edit / back to the card."""

    def event(self, ev):
        if _eat_shortcut(ev):
            return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        key = ev.key()
        editing = self.state() == QAbstractItemView.State.EditingState
        if key == Qt.Key.Key_Escape and not editing:
            focus_reviewer()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not editing:
            self.next_row()
            return
        super().keyPressEvent(ev)

    def closeEditor(self, editor, hint):
        super().closeEditor(editor, hint)
        if hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            self.next_row()

    def done_editing(self, editor):
        """Close the editor without our own 'Enter = next row' (check moves itself)."""
        self.commitData(editor)
        QAbstractItemView.closeEditor(self, editor, QAbstractItemDelegate.EndEditHint.NoHint)

    def next_row(self):
        r, c = self.currentRow(), max(0, self.currentColumn())
        if cfg()["check_answers"]:
            dash = cfg()["smart_dash"]
            nxt = r + 1
            while nxt < self.rowCount():
                it = self.item(nxt, 1)
                if not (it and dash and it.text().strip() == dash):
                    break
                nxt += 1
            if nxt >= self.rowCount():
                return  # last row done: stay, no extra empty row
            r = nxt - 1
        if r + 1 >= self.rowCount():
            add_row()
        r += 1
        item = self.item(r, c)
        if item is None:
            item = QTableWidgetItem("")
            self.setItem(r, c, item)
        if not (item.flags() & Qt.ItemFlag.ItemIsEditable):
            c = 1
            item = self.item(r, 1)
        self.setCurrentCell(r, c)
        self.scrollToItem(item)
        # open the editor after Qt finished closing the previous one
        QTimer.singleShot(0, lambda it=item: self.editItem(it))


class RowsSpinBox(QSpinBox):
    """'Rows?' box: digits and Enter never reach Anki's review keys.
    Enter = build the rows, Esc = keep the current rows."""

    def event(self, ev):
        if _eat_shortcut(ev):
            return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            confirm_rows()
            return
        if ev.key() == Qt.Key.Key_Escape:
            skip_rows()
            return
        super().keyPressEvent(ev)


# --------------------------------------------------------------------- ui

BTN_STYLE = (
    "QToolButton { padding: 0px 3px; margin: 0px; min-width: 18px; font-size: 13px; }"
)


def _btn(text: str, tip: str, slot) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setStyleSheet(BTN_STYLE)
    b.setFixedHeight(24)
    b.setAutoRaise(False)
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
    collapse_btn = _btn("»", f"Collapse / expand ({conf['shortcut_collapse']})", toggle_collapse)
    top.addWidget(collapse_btn, 0, Qt.AlignmentFlag.AlignTop)
    state["collapse_btn"] = collapse_btn

    tools_w = QWidget()
    tools_rows = QVBoxLayout(tools_w)
    tools_rows.setContentsMargins(0, 0, 0, 0)
    tools_rows.setSpacing(2)

    # row 1: width + settings (+ logo)
    tools = QHBoxLayout()
    tools.setSpacing(2)
    tools.addWidget(_btn("Narrower", f"Narrower panel ({conf['shortcut_narrower']})", narrower))
    tools.addWidget(_btn("Wider", f"Wider panel ({conf['shortcut_wider']})", wider))
    tools.addWidget(_btn("⚙ Settings", f"Settings ({conf['shortcut_settings']})", open_settings))
    tools.addStretch()

    # row 2: content actions
    actions = QHBoxLayout()
    actions.setSpacing(2)
    actions.addWidget(_btn("Load TXT", f"Load a template from a .txt file ({conf['shortcut_import']})", import_txt))
    mode_btn = _btn("→ Table", f"Switch text / table ({conf['shortcut_mode']})", toggle_mode)
    actions.addWidget(mode_btn)
    state["mode_btn"] = mode_btn
    actions.addWidget(_btn("Save template", f"Save as the template for this card ({conf['shortcut_save']})", save_template))
    smart_btn = _btn(
        "Auto",
        "Auto rows from the legend + '-' for points the teacher does not want "
        f"(NIE: … in {conf['smart_notes_field']}). On / off ({conf['shortcut_smart']})",
        toggle_smart,
    )
    smart_btn.setCheckable(True)
    actions.addWidget(smart_btn)
    state["smart_btn"] = smart_btn
    update_smart_btn()
    check_btn = _btn(
        "Check",
        "Enter or a space at the end checks the answer against the legend: "
        f"green = next row, red = stay ({conf['shortcut_check']})",
        toggle_check,
    )
    check_btn.setCheckable(True)
    actions.addWidget(check_btn)
    state["check_btn"] = check_btn
    update_check_btn()
    actions.addWidget(_btn(
        "Hint",
        f"Next correct letter of the answer in the cell you are writing ({conf['shortcut_hint']}). "
        f"Or just type \"{conf.get('hint_word', 'hint')}\" in the cell, again for one more letter.",
        hint_now,
    ))
    actions.addStretch()

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

    tools_rows.addLayout(tools)
    tools_rows.addLayout(actions)

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

    rows_bar = QWidget()
    rows_bar.setObjectName("deepNotesRows")
    rows_bar.setStyleSheet("#deepNotesRows { border: 2px solid #2e6fd8; border-radius: 6px; }")
    rows_row = QHBoxLayout(rows_bar)
    rows_row.setContentsMargins(6, 3, 6, 3)
    rows_row.setSpacing(4)
    rows_lbl = QLabel("Rows?")
    rows_lbl.setStyleSheet("font-weight: bold;")
    rows_box = RowsSpinBox()
    rows_box.setRange(1, 100)
    rows_box.setFixedWidth(64)
    rows_box.setToolTip("Number + Enter = numbered rows, Esc = keep the current rows")
    rows_hint = QLabel("Enter = create · Esc = skip")
    rows_hint.setStyleSheet("font-size: 11px; color: gray;")
    rows_hint.setMinimumWidth(0)
    rows_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    rows_row.addWidget(rows_lbl)
    rows_row.addWidget(rows_box)
    rows_row.addWidget(_btn("OK", "Create the rows (Enter)", confirm_rows))
    rows_row.addWidget(rows_hint, 1)
    rows_bar.hide()
    body_layout.addWidget(rows_bar)
    state["rows_bar"] = rows_bar
    state["rows_box"] = rows_box

    font = QFont(conf["font_family"], int(conf["font_size"]))

    text_box = PanelTextEdit()
    text_box.setFont(font)
    text_box.setPlaceholderText("Write thoughts, reasoning, hypotheses...")
    text_box.setMinimumWidth(60)
    body_layout.addWidget(text_box)
    state["text_box"] = text_box

    table = PanelTable(0, 2)
    table.setFont(font)
    table.setMinimumWidth(60)
    table.setTabKeyNavigation(True)
    headers = list(conf["table_headers"])[:2] + ["", ""]
    table.setHorizontalHeaderLabels(headers[:2])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(True)
    table.setItemDelegate(CheckDelegate(table))
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


SHORTCUT_ACTIONS = [
    ("shortcut_collapse", "Collapse / expand", lambda: toggle_collapse()),
    ("shortcut_import", "Load TXT", lambda: import_txt()),
    ("shortcut_mode", "Text / table", lambda: toggle_mode()),
    ("shortcut_wider", "Wider", lambda: wider()),
    ("shortcut_narrower", "Narrower", lambda: narrower()),
    ("shortcut_settings", "Settings", lambda: open_settings()),
    ("shortcut_focus", "Jump into panel", lambda: focus_panel()),
    ("shortcut_save", "Save template", lambda: save_template()),
    ("shortcut_smart", "Auto rows on / off", lambda: toggle_smart()),
    ("shortcut_check", "Check on / off", lambda: toggle_check()),
    ("shortcut_hint", "Hint: next correct letter", lambda: hint_now()),
]


def _our_shortcuts():
    conf = cfg()
    out = []
    for key, label, fn in SHORTCUT_ACTIONS:
        seq = str(conf.get(key) or "").strip()
        if seq:
            out.append((seq, label, fn))
    return out


def on_state_shortcuts(state_name, shortcuts) -> None:
    """Register through Anki's own review shortcut machinery (same path as Space, 1-4)."""
    if state_name != "review":
        return
    for seq, _label, fn in _our_shortcuts():
        shortcuts.append((seq, fn))


def _norm(seq: str) -> str:
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.PortableText).lower()


def check_shortcut_clashes() -> None:
    """Warn once if one of our shortcuts is also used by a menu, Anki or another add-on."""
    if state.get("clash_checked"):
        return
    state["clash_checked"] = True
    taken = {}
    # menu mnemonics, e.g. "&Tools" -> Alt+T
    try:
        for act in mw.form.menubar.actions():
            text = act.text()
            i = text.find("&")
            if 0 <= i < len(text) - 1 and text[i + 1] != "&":
                taken.setdefault(_norm("Alt+" + text[i + 1]), []).append(f"menu {text.replace('&', '')}")
    except Exception:
        pass
    # menu actions with shortcuts
    for act in mw.findChildren(QAction):
        for ks in act.shortcuts():
            if not ks.isEmpty():
                name = act.text().replace("&", "") or "menu item"
                taken.setdefault(_norm(ks.toString()), []).append(name)
    # every QShortcut in the main window (Anki + add-ons); ours appear once each
    counts = {}
    for sc in mw.findChildren(QShortcut):
        k = _norm(sc.key().toString())
        if k:
            counts[k] = counts.get(k, 0) + 1
    problems = []
    for seq, label, _fn in _our_shortcuts():
        k = _norm(seq)
        users = list(taken.get(k, []))
        if counts.get(k, 0) > 1:
            users.append("another shortcut")
        if users:
            problems.append(f"{seq} ({label}) clashes with {', '.join(users)}")
    if problems:
        tooltip("Deep Notes: " + "; ".join(problems) + ". Change it in ⚙ Settings → Shortcuts.", period=8000)


def add_menu() -> None:
    act = QAction("Deep Notes: collapse / expand panel", mw)
    act.triggered.connect(lambda: (create_dock(), state["dock"].show(), toggle_collapse()))
    mw.form.menuTools.addAction(act)


# --------------------------------------------------------------- settings

SEPARATORS = [("Tab (\\t)", "\t"), ("Semicolon ;", ";"), ("Pipe |", "|"), ("Comma ,", ",")]

# (tab, key, label, kind, extra, help)
SPEC = [
    ("Panel", "dock_area", "Panel side", "choice", ["right", "left"],
     "Right or left. Takes effect after restarting Anki."),
    ("Panel", "dock_width", "Width (px)", "int", (60, 3000),
     "Panel width. Also changed with the Narrower / Wider buttons and shortcuts."),
    ("Panel", "min_width", "Minimum width (px)", "int", (60, 1500),
     "The panel cannot be made narrower than this."),
    ("Panel", "width_step", "Width step (px)", "int", (5, 500),
     "How much Narrower / Wider and their shortcuts change the width."),
    ("Panel", "remember_width", "Remember width", "bool", None,
     "Keep the last width after restarting Anki."),
    ("Panel", "hide_outside_review", "Hide outside review", "bool", None,
     "Hide the panel on the deck list and in the browser."),
    ("Panel", "remember_zoom", "Remember card zoom", "bool", None,
     "Keeps the zoom of the card (View > Zoom, Ctrl + / Ctrl -) after restarting Anki."),
    ("Panel", "show_logo", "Show logo", "bool", None,
     "AnkiMonkey logo in the toolbar. Takes effect after restarting Anki."),
    ("Panel", "logo_height", "Logo height (px)", "int", (12, 200),
     "Takes effect after restarting Anki."),
    ("Writing", "font_family", "Font", "str", None,
     "e.g. Arial, Consolas, Segoe UI."),
    ("Writing", "font_size", "Font size", "int", (6, 72), ""),
    ("Writing", "mode", "Mode", "choice", ["text", "table"],
     "text = free scratchpad, table = Base / Notes table (Alt+M switches)."),
    ("Writing", "clear_after_answer", "Clear after answer", "bool", None,
     "Table: the Notes column is emptied, the Base column stays. "
     "Text: emptied (a template is loaded again for the next card)."),
    ("Writing", "auto_focus", "Cursor into panel", "bool", None,
     "Put the cursor in the panel when a question is shown. Note: Space then types into the panel."),
    ("Templates", "template_dir", "Template folder", "dir", None,
     "Empty = user_files/templates inside the add-on (kept when the add-on updates)."),
    ("Templates", "auto_load_template", "Load template automatically", "bool", None,
     "For every card a template is looked up and loaded (rules → tag → deck → default)."),
    ("Templates", "default_template", "Default template", "str", None,
     "Used when no rule, tag or deck matches."),
    ("Templates", "rules_first_tag_only", "Rules use first tag only", "bool", None,
     "On = only the note's first tag counts (Anki sorts tags alphabetically). "
     "Off = the first rule from the top that matches any tag wins."),
    ("Table", "table_header_1", "Column 1 name", "str", None, "Column from the template."),
    ("Table", "table_header_2", "Column 2 name", "str", None, "Column you fill in."),
    ("Table", "table_separator", "Separator in TXT", "sep", None,
     "Text before the separator goes to column 1, after it to column 2."),
    ("Table", "table_template_readonly", "Lock template column", "bool", None,
     "Column 1 from a template cannot be edited."),
    ("Table", "table_empty_rows", "Rows without template", "int", (0, 100),
     "How many rows the table has when there is no template for the card "
     "(also the first number offered in the 'Rows?' box)."),
    ("Table", "table_numbered", "Number rows 1, 2, 3 …", "bool", None,
     "Without a template column 1 holds the row number (like the numbers on an image). "
     "Enter on the last row adds the next number."),
    ("Table", "table_ask_rows", "Ask for row count", "bool", None,
     "On every card without a template a 'Rows?' box appears above the table: "
     "type a number + Enter. Esc keeps the current rows. It offers the last number you used."),
    ("Table", "smart_rows", "Auto rows from legend", "bool", None,
     "Off = works as before. On = rows come from the card's legend (user_files/legend_labels.json, "
     "every point incl. 3a, 3b, 2' on its own row) and points the teacher does not want get the dash. "
     "Cards not in the file still ask 'Rows?', then get the dashes. Also the Auto button / Alt+K."),
    ("Table", "smart_notes_field", "Field with 'NIE: …'", "str", None,
     "Field read for 'NIE: 4, 6, 8', 'NIE: celá karta' or 'všetky'."),
    ("Table", "smart_dash", "Dash text", "str", None, "What goes into skipped rows."),
    ("Table", "check_answers", "Check answers", "bool", None,
     "Enter or a space at the end of your answer compares it with the legend "
     "(user_files/legend_answers.json). Abbreviations (pr transversus), missing a/na/do "
     "and one typo in longer words are fine. Green = jumps to the next row "
     "(rows with the dash are skipped), red = you stay. Also the Check button / Alt+J."),
    ("Table", "check_ok_color", "Correct colour", "str", None, ""),
    ("Table", "check_bad_color", "Wrong colour", "str", None, ""),
    ("Table", "check_dunno_words", "\"I don't know\" words", "str", None,
     "Typing one of these (comma separated) writes the correct answer in blue straight away "
     "and moves on."),
    ("Table", "check_dunno_color", "\"I don't know\" colour", "str", None,
     "Also used for Enter pressed again on a wrong (red) answer, or two spaces at the end."),
    ("Table", "check_long_words", "Long answer from (words)", "int", (1, 50),
     "Legend text with more words than this counts as long."),
    ("Table", "check_long_percent", "Long answer: % enough", "int", (1, 100),
     "For a long legend text it is enough when more than this % of its words are in your answer."),
    ("Shortcuts", "shortcut_collapse", "Collapse / expand", "str", None,
     "Changes apply the next time you start reviewing. Avoid Alt+F/E/V/T/H (menus) "
     "and keys Anki uses in review (Space, Enter, 1-4, E, R, *, -, =, @, !, Ctrl+1-7)."),
    ("Shortcuts", "shortcut_import", "Load TXT", "str", None, ""),
    ("Shortcuts", "shortcut_mode", "Text / table", "str", None, ""),
    ("Shortcuts", "shortcut_wider", "Wider", "str", None, ""),
    ("Shortcuts", "shortcut_narrower", "Narrower", "str", None, ""),
    ("Shortcuts", "shortcut_settings", "Settings", "str", None, ""),
    ("Shortcuts", "shortcut_focus", "Jump into panel", "str", None,
     "In table mode jumps to the first empty Notes cell. Esc gives the keyboard back to the card."),
    ("Shortcuts", "shortcut_save", "Save as template", "str", None,
     "Saves the Base column (or the text) as the template for this card; the old file is kept as .bak."),
    ("Shortcuts", "shortcut_smart", "Auto rows on / off", "str", None, ""),
    ("Shortcuts", "shortcut_check", "Check on / off", "str", None, ""),
    ("Shortcuts", "shortcut_hint", "Hint: next correct letter", "str", None, ""),
]


def _help_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: gray; font-size: 11px;")
    return lbl


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Deep Notes – settings")
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
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                scroll.setWidget(page)
                tabs.addTab(scroll, tab)
                forms[tab] = form
                if tab == "Templates":
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
        self._fit_to_screen()

    def _fit_to_screen(self):
        # never taller/wider than the monitor -> tabs scroll, Save stays visible
        screen = (self.parent() or mw).screen() if hasattr(self.parent() or mw, "screen") else None
        if screen is None:
            return
        geo = screen.availableGeometry()
        w = min(max(560, int(geo.width() * 0.45)), geo.width() - 40, 760)
        h = min(int(geo.height() * 0.80), 700)
        self.setMaximumHeight(geo.height() - 40)
        self.resize(w, h)
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

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
            open_btn = QPushButton("Open")
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
        path = QFileDialog.getExistingDirectory(self, "Template folder", start)
        if path:
            edit.setText(path)

    def _rules_box(self, form):
        form.addRow(QLabel("<b>Tag rules</b> (the first matching rule from the top wins)"))
        form.addRow("", _help_label(
            "Tag \"Bones\" matches Bones, Bones::UpperLimb, Bones::LowerLimb::femur … "
            "Tag \"Bones::UpperLimb\" matches only that branch. The file is looked up "
            "in the template folder (or give a full path)."
        ))
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Tag", ".txt file"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(140)
        for rule in self.conf.get("tag_rules") or []:
            self._rule_row(table, rule.get("tag", ""), rule.get("file", ""))
        btns = QHBoxLayout()
        add = QPushButton("Add rule")
        add.clicked.connect(lambda: self._rule_row(table, "", ""))
        rem = QPushButton("Remove")
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
        tooltip("Deep Notes: saved")
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
    update_smart_btn()
    update_check_btn()
    if state["body"].isVisible():
        set_width(conf["dock_width"])
    card = mw.reviewer.card if mw.state == "review" else None
    if card:
        load_for_card(card)


# ------------------------------------------------------------------ hooks

def on_show_question(card) -> None:
    if not state.get("zoom_done"):
        state["zoom_done"] = True
        restore_zoom()
    create_dock()
    state["dock"].show()
    QTimer.singleShot(500, check_shortcut_clashes)
    if state["card_id"] != card.id:
        state["card_id"] = card.id
        load_for_card(card)
    asking = state["rows_bar"] is not None and state["rows_bar"].isVisible()
    if cfg()["auto_focus"] and state["body"].isVisible() and not asking:
        target = state["table"] if cfg()["mode"] == "table" else state["text_box"]
        target.setFocus()


def on_answer(reviewer, card, ease) -> None:
    if cfg()["clear_after_answer"]:
        clear_mine()
    state["card_id"] = None


def on_state_change(new_state, old_state) -> None:
    save_zoom()
    if state["dock"] and cfg()["hide_outside_review"] and new_state != "review":
        state["dock"].hide()


# ------------------------------------------------------------------ zoom

def save_zoom() -> None:
    """Remember the card zoom (View > Zoom, Ctrl + / Ctrl -)."""
    if not cfg()["remember_zoom"]:
        return
    try:
        z = round(float(mw.web.zoomFactor()), 2)
    except Exception:
        return
    if z > 0 and z != cfg().get("web_zoom"):
        save_cfg(web_zoom=z)


def restore_zoom() -> None:
    z = cfg().get("web_zoom")
    if not cfg()["remember_zoom"] or not z:
        return
    try:
        if abs(float(mw.web.zoomFactor()) - float(z)) > 0.001:
            mw.web.setZoomFactor(float(z))
    except Exception:
        pass


def on_profile_open() -> None:
    # Anki sets its own zoom while starting; ours goes on top of it
    QTimer.singleShot(800, restore_zoom)
    QTimer.singleShot(2500, restore_zoom)


def on_profile_close() -> None:
    save_zoom()
    dock = state["dock"]
    if dock and state["body"].isVisible() and cfg()["remember_width"]:
        save_cfg(dock_width=dock.width())


gui_hooks.state_shortcuts_will_change.append(on_state_shortcuts)
gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.state_did_change.append(on_state_change)
gui_hooks.profile_will_close.append(on_profile_close)
gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.main_window_did_init.append(add_menu)
