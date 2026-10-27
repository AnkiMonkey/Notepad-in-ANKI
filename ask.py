"""Ask panel (Claude via Claude Code, Pro login) – part of AnkiMonkey.

Prompts
  * .txt files. Built-in folder:  <addon>/user_files/prompts/
  * plus any .txt anywhere on the PC, added with Settings → "Add TXT…"
  * the full path of the active prompt is always shown (tooltip + Settings).
  * placeholders: {question} = what you ask, {context} = matching notes from your collection
  * a first line "@json" = the model must answer in JSON; the add-on formats it
    (used by the dictionary prompt so the format is always complete).

Answers come from Claude through the Claude Code app (your own Pro login, no API key).
Nothing about the login is stored in this add-on; Claude Code keeps it in ~/.claude.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading

from aqt import mw
from aqt.qt import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QEvent, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QTextBrowser, QVBoxLayout, Qt,
)
from aqt.utils import openFolder, tooltip

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(ADDON_DIR, "user_files", "prompts")
GREEN, RED, BG = "#55ff55", "#ff5555", "#222"
DICT_NAME = "latinsky_slovnik.txt"

DICT_PROMPT = """@json
Si slovník LEKÁRSKEJ latinskej terminológie (anatómia, fyziológia, klinika) pre slovenského študenta fyzioterapie.
Vždy význam v medicíne, nie všeobecná latinčina.

Funguje OBOMA smermi:
- SK → LA: vstup je slovenské slovo → nájdi latinský lekársky termín.
- LA → SK: vstup je latinské slovo (aj v inom páde či čísle) → urči jeho slovníkový tvar a slovenský význam.
Najprv rozhodni, v akom jazyku je vstup.

Vráť IBA JSON objekt s týmito kľúčmi:

{
  "smer": "SK→LA" | "LA→SK",
  "druh": "podstatné meno" | "prídavné meno" | "sloveso" | "spojenie",
  "lemma": "nominatív singuláru",
  "gen_sg": "genitív singuláru (celý tvar)",
  "rod": "m." | "f." | "n.",
  "deklinacia": "1." | "2." | "3." | "4." | "5.",
  "nom_pl": "nominatív plurálu",
  "gen_pl": "genitív plurálu",
  "pridavne_tvary": "len pri prídavnom mene: tvary pre m./f./n., napr. longus, -a, -um",
  "vychodovost": "len pri prídavnom mene: jednovýchodové | dvojvýchodové | trojvýchodové",
  "sk": "slovenský význam v medicíne",
  "priklad": "1 skutočný, gramaticky správny anatomický termín s týmto slovom (celý, s podstatným menom)",
  "istota": "vysoká" | "nízka"
}

Pravidlá:
- Pri podstatnom mene VŽDY vyplň gen_sg, rod, deklinacia, nom_pl, gen_pl.
- Prídavné meno zaraďuj IBA ako jednovýchodové / dvojvýchodové / trojvýchodové, deklináciu pri ňom nepíš.
- PRÍKLAD musí byť skutočný anatomický termín (ako v učebnici/Terminologia Anatomica), gramaticky správny:
  * prídavné meno NIKDY nestojí samo ako podstatné meno – vždy pri ňom je podstatné meno, s ktorým sa zhoduje v rode, čísle a páde
    správne: musculus longus capitis, ligamentum longitudinale anterius, os longum
    ZLE: longus capitis, longum, brevis pollicis
  * podstatné meno v príklade nezamieňaj za prídavné meno a naopak
  * ak si nie si istý skutočným termínom, nechaj "priklad" prázdny ""
- Kľúče, ktoré sa nehodia, nechaj prázdne "".
- Žiadny text mimo JSON.

Príklady:
vstup: hlava → {"smer":"SK→LA","druh":"podstatné meno","lemma":"caput","gen_sg":"capitis","rod":"n.","deklinacia":"3.","nom_pl":"capita","gen_pl":"capitum","pridavne_tvary":"","vychodovost":"","sk":"hlava","priklad":"caput humeri","istota":"vysoká"}
vstup: venae → {"smer":"LA→SK","druh":"podstatné meno","lemma":"vena","gen_sg":"venae","rod":"f.","deklinacia":"1.","nom_pl":"venae","gen_pl":"venarum","pridavne_tvary":"","vychodovost":"","sk":"žila","priklad":"vena cava superior","istota":"vysoká"}
vstup: krátky → {"smer":"SK→LA","druh":"prídavné meno","lemma":"brevis","gen_sg":"brevis","rod":"","deklinacia":"","nom_pl":"breves","gen_pl":"brevium","pridavne_tvary":"brevis, -e","vychodovost":"dvojvýchodové","sk":"krátky","priklad":"musculus fibularis brevis","istota":"vysoká"}
vstup: dlhý → {"smer":"SK→LA","druh":"prídavné meno","lemma":"longus","gen_sg":"longi","rod":"","deklinacia":"","nom_pl":"longi","gen_pl":"longorum","pridavne_tvary":"longus, -a, -um","vychodovost":"trojvýchodové","sk":"dlhý","priklad":"musculus longus capitis","istota":"vysoká"}

Z mojej zbierky (ak nie je prázdne, je to hlavný zdroj):
{context}

vstup: {question}
"""

ui = {"box": None, "answer": None, "combo": None, "status": None, "busy": False}


def cfg():
    from .voice import cfg as _cfg
    return _cfg()


def save_cfg(**kw):
    from .voice import save_cfg as _s
    _s(**kw)


# ------------------------------------------------------------------ prompts

def ensure_prompts() -> None:
    os.makedirs(PROMPT_DIR, exist_ok=True)
    p = os.path.join(PROMPT_DIR, DICT_NAME)
    old = open(p, encoding="utf8").read() if os.path.exists(p) else ""
    if not old or "Formát odpovede" in old or ("Si slovník LEKÁRSKEJ" in old and "NIKDY nestojí samo" not in old):   # upgrade old built-in versions
        with open(p, "w", encoding="utf8") as f:
            f.write(DICT_PROMPT)


def prompt_paths() -> list[str]:
    """Full paths: built-in folder first, then TXT files added from anywhere."""
    ensure_prompts()
    out = [os.path.join(PROMPT_DIR, f) for f in sorted(os.listdir(PROMPT_DIR)) if f.lower().endswith(".txt")]
    for p in cfg().get("ask_extra_prompts") or []:
        if os.path.isfile(p) and p not in out:
            out.append(p)
    return out


def current_path() -> str:
    c = ui["combo"]
    return c.currentData() if c is not None and c.currentData() else os.path.join(PROMPT_DIR, DICT_NAME)


def read_prompt(path: str) -> str:
    with open(path, encoding="utf8") as f:
        return f.read()


# ------------------------------------------------------------------ Claude (Claude Code, Pro login, no API key)

def claude_exe() -> str:
    p = (cfg().get("claude_path") or "").strip()
    if p and os.path.isfile(p):
        return p
    import shutil
    cands = [os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"),
             os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
             shutil.which("claude") or ""]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise RuntimeError("Claude Code not found – install it (Settings → Claude → Install) or set its path")


def ask_claude(prompt: str) -> str:
    import subprocess
    exe = claude_exe()
    work = os.path.join(ADDON_DIR, "user_files", "claude_cwd")   # empty folder: no project files for Claude to read
    os.makedirs(work, exist_ok=True)
    args = [exe, "-p", "--output-format", "text"]
    m = (cfg().get("claude_model") or "").strip()
    if m:
        args += ["--model", m]
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf8",
                       cwd=work, timeout=180, creationflags=flags)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        err = (r.stderr or out or "no output").strip()
        if "login" in err.lower() or "auth" in err.lower():
            err = "Claude Code is not logged in – Settings → Claude → Log in"
        raise RuntimeError(err[:400])
    return out


def claude_install() -> None:
    """Official installer from claude.ai, in a visible PowerShell window."""
    import subprocess
    subprocess.Popen(["cmd", "/c", "start", "Install Claude Code", "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-NoExit", "-Command", "irm https://claude.ai/install.ps1 | iex"])


def claude_login() -> None:
    """Opens Claude Code in its own window – log in there once with your Pro account, then close it."""
    import subprocess
    exe = claude_exe()
    work = os.path.join(ADDON_DIR, "user_files", "claude_cwd")
    os.makedirs(work, exist_ok=True)
    subprocess.Popen(["cmd", "/c", "start", "Claude Code login", "/D", work, exe])


def collection_context(q: str, limit: int = 6) -> str:
    q = q.strip()
    if not q or mw.col is None:
        return ""
    words = re.sub(r"[\"*_:()]", " ", q).split()
    if not words:
        return ""
    w = words[0]
    out: list[str] = []
    try:
        for query in (f'"note:Latina Terminologia*" "{w}*"', f'"{w}*" -"note:Latina Terminologia*"'):
            for nid in mw.col.find_notes(query)[:limit]:
                n = mw.col.get_note(nid)
                txt = " | ".join(re.sub(r"<[^>]+>", " ", html.unescape(v)).strip()
                                 for k, v in n.items() if v and "<img" not in v and k != "DN Legend")
                txt = re.sub(r"\s+", " ", txt)[:300]
                if txt and txt not in out:
                    out.append(txt)
            if len(out) >= limit:
                break
    except Exception:
        pass
    return "\n".join("- " + t for t in out[:limit])


def ask(question: str) -> None:
    question = question.strip()
    if ui["busy"] or not question:
        return
    path = current_path()
    try:
        template = read_prompt(path)
    except Exception as e:
        set_answer(f"<span style='color:{RED}'>cannot read {html.escape(path)}: {html.escape(str(e))}</span>")
        return
    as_json = template.lstrip().lower().startswith("@json")
    if as_json:
        template = template.lstrip()[5:].lstrip("\n")
    ctx = collection_context(question)
    prompt = template.replace("{question}", question).replace("{context}", ctx or "(nič)")
    if "{question}" not in template:
        prompt += "\n\n" + question
    ui["busy"] = True
    set_status("thinking…", "#ddd")
    set_answer("")

    def work():
        text = ""
        try:
            mw.taskman.run_on_main(lambda: set_status("… Claude", "#888"))
            text = ask_claude(prompt + ("\n\nOdpovedz IBA platným JSON objektom, bez ```." if as_json else ""))
            final = render_json(text) if as_json else render(text)
            mw.taskman.run_on_main(lambda: (set_answer(final), set_status("✓ Claude", GREEN)))
        except Exception as e:
            msg = str(e)
            mw.taskman.run_on_main(lambda m=msg: (set_status("error", RED),
                                                 set_answer(f"<span style='color:{RED}'>{html.escape(m)}</span>")))
        finally:
            ui["busy"] = False

    threading.Thread(target=work, daemon=True).start()


def render(t: str) -> str:
    t = re.sub(r"<think>.*?(</think>|$)", "", t, flags=re.S)
    t = html.escape(t.strip())
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")


def _ending(lemma: str, form: str) -> str:
    """'capitis' with lemma 'caput' -> '-itis' (common prefix cut, dictionary style)."""
    if not form or not lemma or form == lemma:
        return form
    i = 0
    while i < min(len(lemma), len(form)) and lemma[i] == form[i]:
        i += 1
    i = max(1, min(i, len(lemma) - 1))
    return "-" + form[i:] if i >= 2 else form


def render_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, flags=re.S)
    try:
        d = json.loads(m.group(0) if m else text)
    except Exception:
        return render(text)
    g = lambda k: (d.get(k) or "").strip() if isinstance(d.get(k), str) else str(d.get(k) or "")
    e = html.escape
    lemma, druh = g("lemma"), g("druh").lower()
    lines = []
    adj = "prídav" in druh or "pridav" in druh
    if adj:
        head = g("pridavne_tvary") or lemma
        v = g("vychodovost")
        lines.append(f"<b>{e(head)}</b>" + (f" <span style='color:#aaa'>({e(v)})</span>" if v else ""))
    else:
        gen, rod, dek = g("gen_sg"), g("rod"), g("deklinacia")
        fixed_dek, fixed_rod = check_noun(lemma, gen, rod, dek)
        corrected = (fixed_dek and fixed_dek != dek.rstrip(".")) or (fixed_rod and fixed_rod != rod)
        dek = fixed_dek or dek
        rod = fixed_rod or rod
        head = f"<b>{e(lemma)}</b>"
        if gen:
            head += f", {e(_ending(lemma, gen))}"
        if rod:
            head += f", {e(rod)}"
        if dek:
            head += f" <span style='color:#aaa'>({e(dek.rstrip('.'))}. deklinácia)</span>"
        lines.append(head)
    if g("sk"):
        lines.append(f"= {e(g('sk'))}")
    npl, gpl = g("nom_pl"), g("gen_pl")
    if npl or gpl:
        lines.append(f"<span style='color:#9cf'>pl.</span> {e(npl)}" + (f", {e(gpl)}" if gpl else ""))
    ex = g("priklad")
    if ex and adj:
        # an adjective example must contain a noun before the adjective (musculus longus capitis, not longus capitis)
        forms = {f.strip(" -").lower() for f in re.split(r"[,\s]+", g("pridavne_tvary") or lemma) if f.strip(" -")}
        first = ex.split()[0].lower() if ex.split() else ""
        if first == lemma.lower() or first in forms:
            ex = ""
    if ex:
        lines.append(f"<i style='color:#bbb'>napr. {e(ex)}</i>")
    if not adj and corrected:
        lines.append("<span style='color:#ffb74d'>rod/deklináciu som opravil podľa koncoviek – model sa pomýlil</span>")
    if g("istota").lower().startswith("n"):
        lines.append(f"<span style='color:{RED}'>neistá odpoveď – over v učebnici</span>")
    return "<br>".join(lines)


def check_noun(lemma: str, gen: str, rod: str, dek: str):
    """Declension (and gender where it is regular) from the endings – small models mix this up.
    Returns (declension, gender) or ("", "") when the endings say nothing sure."""
    L, G = lemma.lower().strip(), gen.lower().strip()
    if not L or not G:
        return "", ""
    r = rod.strip().lower()
    if G.endswith("ae") and L.endswith("a"):
        return "1", ("" if r in ("m.",) else "f.")          # poeta, -ae m. stays m.
    if G.endswith("ei") and L.endswith("es"):
        return "5", "f."
    if G.endswith("us") and L.endswith("us") and G == L:
        return "4", ("m." if r != "f." else "f.")            # manus, -us f.
    if G.endswith("u") and L.endswith("u"):
        return "4", "n."                                     # cornu, -us n.
    if G.endswith("i") and not G.endswith("ei"):
        if L.endswith("um") or L.endswith("on"):
            return "2", "n."
        if L.endswith("us") or L.endswith("er"):
            return "2", ("f." if r == "f." else "m.")        # a few -us are f. (humus), keep if model said f.
    if G.endswith("is"):
        return "3", ""                                       # 3rd: gender not predictable from endings
    return "", ""


# ------------------------------------------------------------------ UI

class AskBox(QLineEdit):
    """Enter/Space/… typed here must not reach the reviewer (no card flip)."""

    def event(self, ev):
        if ev.type() == QEvent.Type.ShortcutOverride:
            ev.accept()
            return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            ask(self.text())
            ev.accept()
            return
        if ev.key() == Qt.Key.Key_Escape:
            mw.web.setFocus()
            return
        super().keyPressEvent(ev)


def set_status(t, col="#ddd"):
    if ui["status"]:
        ui["status"].setText(t)
        ui["status"].setStyleSheet(f"color:{col}; font-size:10px;")


def set_answer(h):
    if ui["answer"]:
        ui["answer"].setHtml(f"<div style='color:#eee; font-size:13px'>{h}</div>")


def reload_combo(select: str | None = None):
    c = ui["combo"]
    if c is None:
        return
    c.blockSignals(True)
    c.clear()
    for p in prompt_paths():
        name = os.path.basename(p)
        if os.path.dirname(p) != PROMPT_DIR:
            name += "  (ext.)"
        c.addItem(name, p)
        c.setItemData(c.count() - 1, p, Qt.ItemDataRole.ToolTipRole)
    want = select or cfg().get("ask_prompt_path") or os.path.join(PROMPT_DIR, DICT_NAME)
    i = c.findData(want)
    c.setCurrentIndex(i if i >= 0 else 0)
    c.setToolTip(current_path())
    c.blockSignals(False)


def _on_combo(_i):
    p = current_path()
    ui["combo"].setToolTip(p)
    save_cfg(ask_prompt_path=p)


def build(lay) -> None:
    ensure_prompts()
    lay.addWidget(QLabel("<hr>"))
    title = QLabel("<b>Ask</b> <span style='color:#888'>(Claude)</span>")
    title.setStyleSheet("color:#ddd;")
    lay.addWidget(title)

    row = QHBoxLayout()
    combo = QComboBox()
    combo.currentIndexChanged.connect(_on_combo)
    edit = QPushButton("✎ TXT")
    edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    edit.setToolTip("Edit the selected prompt TXT right now")
    edit.setStyleSheet("QPushButton{background:#333; color:#ffd54f; border:1px solid #555; border-radius:4px; padding:2px 6px;}")
    edit.clicked.connect(open_quick_edit)
    row.addWidget(combo, 1)
    row.addWidget(edit)
    lay.addLayout(row)

    sett = QPushButton("Settings")
    sett.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    sett.setToolTip("Prompts (TXT from anywhere), model, folder")
    sett.setStyleSheet("QPushButton{background:#333; color:#ddd; border:1px solid #555; border-radius:4px; padding:3px;}")
    sett.clicked.connect(open_settings)
    lay.addWidget(sett)

    box = AskBox()
    box.setPlaceholderText("slovo / word … Enter")
    box.setStyleSheet("background:#333; color:#eee; padding:4px;")
    lay.addWidget(box)

    btn = QPushButton("Ask")
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setStyleSheet(f"QPushButton{{background:{BG}; color:{GREEN}; border:1px solid {GREEN}; border-radius:6px; padding:4px;}}")
    btn.clicked.connect(lambda: ask(box.text()))
    lay.addWidget(btn)

    status = QLabel("")
    status.setWordWrap(True)
    lay.addWidget(status)

    ans = QTextBrowser()
    ans.setStyleSheet("background:#1b1b1b; color:#eee; border:1px solid #444;")
    ans.setMinimumHeight(160)
    lay.addWidget(ans, 2)

    ui.update(box=box, answer=ans, combo=combo, status=status)
    reload_combo()


# ------------------------------------------------------------------ settings

class Settings(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("Ask (Claude) – settings")
        scr = mw.screen().availableGeometry()
        self.resize(min(760, int(scr.width() * 0.85)), min(600, int(scr.height() * 0.8)))
        v = QVBoxLayout(self)

        # --- prompt file
        row = QHBoxLayout()
        self.combo = QComboBox()
        row.addWidget(self.combo, 1)
        for text, fn in (("Add TXT…", self.add_txt), ("New…", self.new), ("Remove from list", self.remove)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row)

        self.path = QLineEdit(); self.path.setReadOnly(True)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("File:")); prow.addWidget(self.path, 1)
        for text, fn in (("Copy path", self.copy_path), ("Open folder", self.open_folder), ("Open in Notepad", self.open_external)):
            b = QPushButton(text); b.clicked.connect(fn); prow.addWidget(b)
        v.addLayout(prow)

        v.addWidget(QLabel("Placeholders: {question} = what you ask · {context} = matching notes from your collection · "
                           "first line @json = answer as JSON (dictionary layout)"))
        self.edit = QPlainTextEdit()
        v.addWidget(self.edit, 1)

        # --- model
        form = QFormLayout()
        crow = QHBoxLayout()
        for text, fn in (("Install Claude Code", claude_install), ("Log in", self._login), ("Test", self._test)):
            b = QPushButton(text); b.clicked.connect(fn); crow.addWidget(b)
        try:
            found = claude_exe()
        except Exception:
            found = "not installed yet"
        self.cl_state = QLabel(found)
        crow.addWidget(self.cl_state, 1)
        form.addRow("Claude:", crow)
        form.addRow("Built-in prompt folder:", QLabel(f"<code>{html.escape(PROMPT_DIR)}</code>"))
        v.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        self.combo.currentIndexChanged.connect(self.load)
        self.fill(current_path())

    def fill(self, select):
        self.combo.blockSignals(True)
        self.combo.clear()
        for p in prompt_paths():
            self.combo.addItem(os.path.basename(p) + ("" if os.path.dirname(p) == PROMPT_DIR else "  (ext.)"), p)
        i = self.combo.findData(select)
        self.combo.setCurrentIndex(max(i, 0))
        self.combo.blockSignals(False)
        self.load()

    def cur(self):
        return self.combo.currentData() or ""

    def _login(self):
        try:
            claude_login()
            self.cl_state.setText("login window opened – log in there, then press Test")
        except Exception as e:
            self.cl_state.setText(str(e))

    def _test(self):
        self.cl_state.setText("testing…")
        QApplication.processEvents()
        try:
            out = ask_claude("Odpovedz iba slovom: OK")
            self.cl_state.setText("✓ works: " + out[:40])
        except Exception as e:
            self.cl_state.setText("✗ " + str(e)[:200])

    def load(self, *_):
        p = self.cur()
        self.path.setText(p)
        try:
            self.edit.setPlainText(read_prompt(p) if p else "")
        except Exception as e:
            self.edit.setPlainText(f"(cannot read: {e})")

    def add_txt(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose a prompt TXT", os.path.expanduser("~"), "Text (*.txt)")
        if p:
            p = os.path.normpath(p)
            extra = list(cfg().get("ask_extra_prompts") or [])
            if os.path.dirname(p) != PROMPT_DIR and p not in extra:
                extra.append(p)
                save_cfg(ask_extra_prompts=extra)
            self.fill(p)

    def new(self):
        name, ok = QInputDialog.getText(self, "New prompt", "File name (saved in the built-in folder):")
        if ok and name.strip():
            name = re.sub(r"[^\w\-. ]", "_", name.strip())
            if not name.lower().endswith(".txt"):
                name += ".txt"
            p = os.path.join(PROMPT_DIR, name)
            if not os.path.exists(p):
                with open(p, "w", encoding="utf8") as f:
                    f.write("{context}\n\n{question}\n")
            self.fill(p)

    def remove(self):
        p = self.cur()
        extra = [x for x in (cfg().get("ask_extra_prompts") or []) if x != p]
        save_cfg(ask_extra_prompts=extra)
        if os.path.dirname(p) == PROMPT_DIR:
            tooltip("Built-in prompts stay – delete the file in the folder if you really want it gone.")
        self.fill(current_path())

    def copy_path(self):
        QApplication.clipboard().setText(self.cur())
        tooltip("Path copied")

    def open_folder(self):
        openFolder(os.path.dirname(self.cur()) or PROMPT_DIR)

    def open_external(self):
        p = self.cur()
        if p:
            os.startfile(p) if hasattr(os, "startfile") else openFolder(p)

    def save(self):
        p = self.cur()
        if p:
            with open(p, "w", encoding="utf8") as f:
                f.write(self.edit.toPlainText())
        save_cfg(ask_backend="claude", ask_prompt_path=p)
        reload_combo(p)
        tooltip("Saved")


class QuickEdit(QDialog):
    """Small editor for the prompt that is selected in the panel."""

    def __init__(self):
        super().__init__(mw)
        self.p = current_path()
        self.setWindowTitle("Edit prompt – " + os.path.basename(self.p))
        scr = mw.screen().availableGeometry()
        self.resize(min(640, int(scr.width() * 0.7)), min(520, int(scr.height() * 0.7)))
        v = QVBoxLayout(self)
        lab = QLineEdit(self.p); lab.setReadOnly(True)
        v.addWidget(lab)
        self.edit = QPlainTextEdit(read_prompt(self.p))
        v.addWidget(self.edit, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.save); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def save(self):
        with open(self.p, "w", encoding="utf8") as f:
            f.write(self.edit.toPlainText())
        tooltip("Prompt saved")
        self.accept()


def open_quick_edit():
    QuickEdit().exec()


def open_settings():
    Settings().exec()
