"""
Latin Voice Input  (AnkiMonkey)
-------------------------------
Say the Latin answer, it lands in the #tc-in box, you check it, you press Enter.

* Left-side panel with a 🎤 ON/OFF button.
* Hold F2 (configurable) while speaking, release -> offline Whisper transcription.
* Works on the Anatomia-type-in-answer note types (prefix configurable).
* Vocabulary hint: answers (field "Rub") from the current deck are fed to Whisper
  as a prompt, and the result can be snapped to the closest known term.
* 100 % local: faster-whisper (large-v3) runs on your CPU, model stored in user_files/models.
  Internet is needed only once, to download the model.

Libraries are bundled in vendor_parts/ and unpacked to vendor/ on first use.
"""

from __future__ import annotations

import contextlib
import difflib
import hashlib
import json
import shutil
import ssl
import urllib.request
import html
import os
import re
import sys
import threading
import traceback
import zipfile

from aqt import gui_hooks, mw
from aqt.qt import (
    QHBoxLayout,
    QApplication,
    QDockWidget,
    QEvent,
    QKeySequence,
    QLabel,
    QObject,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_KEY = __name__.split(".")[0]
from .common import get_section, write_section
VENDOR_DIR = os.path.join(ADDON_DIR, "vendor")
PARTS_DIR = os.path.join(ADDON_DIR, "vendor_parts")
MODELS_DIR = os.path.join(ADDON_DIR, "user_files", "models")
OK_MARK = os.path.join(VENDOR_DIR, ".unpacked_ok")

DEFAULTS = {
    "enabled": False,
    "hotkey": "F2",
    "note_type_prefix": "Anatomia-type-in-answer",
    "note_type_prefixes": ["Anatomia-type-in-answer", "Anatomia-write-all-fields"],
    "answer_field": "Rub",
    "model": "large-v3",
    "device": "cpu",
    "compute_type": "int8",
    "cpu_threads": 0,
    "language": "la",
    "beam_size": 5,
    "use_deck_hint": True,
    "snap_to_vocab": True,
    "snap_cutoff": 0.82,
    "lowercase": True,
    "dock_width": 130,
    "hide_outside_review": True,
    "collapsed": False,
    "ask_enabled": True,
    "ask_extra_prompts": [],
    "ask_width": 260,
    "ask_prompt": "latinsky_slovnik.txt",
    "claude_path": "",
    "claude_model": "",
}

GREEN = "#55ff55"
RED = "#ff5555"
BG = "#222"

state = {
    "dock": None,
    "btn": None,
    "status": None,
    "heard": None,
    "model": None,
    "model_name": None,
    "loading": False,
    "recording": False,
    "stream": None,
    "frames": [],
    "filter": None,
    "vocab_all": None,     # list of known answers (all target notes)
    "deck_vocab": {},      # did -> list
}


# ----------------------------------------------------------------- config

def cfg() -> dict:
    c = dict(DEFAULTS)
    c.update(get_section("voice"))
    return c


def save_cfg(**kw) -> None:
    c = get_section("voice")
    c.update(kw)
    write_section("voice", c)


# ----------------------------------------------------------------- UI

def set_status(text: str, colour: str = "#ddd") -> None:
    lab = state["status"]
    if lab:
        lab.setText(text)
        lab.setStyleSheet(f"color:{colour}; background:{BG}; padding:4px;")


def set_heard(text: str) -> None:
    lab = state["heard"]
    if lab:
        lab.setText(text)


def style_button() -> None:
    btn = state["btn"]
    if not btn:
        return
    on = cfg()["enabled"]
    if state["recording"]:
        txt, col = "● REC", RED
    else:
        txt, col = ("🎤 ON" if on else "🎤 OFF"), (GREEN if on else RED)
    btn.setText(txt)
    btn.setStyleSheet(
        f"QPushButton {{ background:{BG}; color:{col}; border:2px solid {col};"
        f" border-radius:8px; font-size:16px; font-weight:bold; padding:10px 4px; }}"
    )


def create_dock() -> None:
    if state["dock"]:
        return
    dock = QDockWidget("Voice", mw)
    dock.setObjectName("latin_voice_input_dock")
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
    body = QWidget()
    body.setStyleSheet(f"background:{BG};")
    outer = QVBoxLayout(body)
    outer.setContentsMargins(4, 4, 4, 4)
    outer.setSpacing(4)
    # header bar: title + hide button (expanded) / vertical strip (collapsed)
    header = QWidget()
    hl = QHBoxLayout(header)
    hl.setContentsMargins(4, 2, 2, 2)
    title = QLabel("<b style='color:#55ff55'>Voice</b><span style='color:#777'> · </span><b style='color:#ffd54f'>Ask</b>")
    hl.addWidget(title, 1)
    fold = QPushButton("«")
    fold.setFixedSize(30, 24)
    fold.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    fold.setToolTip("Odsunúť panel do strany")
    fold.setStyleSheet("QPushButton{background:#2d2d2d; color:#55ff55; border:1px solid #55ff55; border-radius:4px; font-weight:bold; font-size:16px; padding:0px;}"
                       "QPushButton:hover{background:#55ff55; color:#111;}")
    hl.addWidget(fold)
    header.setStyleSheet("background:#2a2a2a; border-radius:6px;")
    outer.addWidget(header)

    strip = QPushButton("»\n\nV\no\ni\nc\ne\n\n·\n\nA\ns\nk")
    strip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    strip.setToolTip("Zobraziť panel Voice · Ask")
    strip.setFixedWidth(28)
    strip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    strip.setStyleSheet("QPushButton{background:#2a2a2a; color:#55ff55; border:1px solid #444; border-radius:6px;"
                        " font-weight:bold; font-size:13px; padding:8px 0px 0px 0px; min-width:0px; text-align:top;}"
                        "QPushButton:hover{background:#333; border-color:#55ff55;}")
    outer.addWidget(strip, 1)
    content = QWidget()
    outer.addWidget(content, 1)
    lay = QVBoxLayout(content)
    lay.setContentsMargins(2, 2, 2, 2)
    lay.setSpacing(8)

    btn = QPushButton()
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Turn Latin voice input on/off")
    btn.clicked.connect(toggle)
    lay.addWidget(btn)

    hk = QLabel(f"hold <b>{cfg()['hotkey']}</b><br>and speak")
    hk.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hk.setStyleSheet("color:#aaa;")
    lay.addWidget(hk)

    status = QLabel()
    status.setWordWrap(True)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(status)

    heard = QLabel()
    heard.setWordWrap(True)
    heard.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heard.setStyleSheet("color:#888; font-size:11px;")
    heard.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(heard)
    width = int(cfg()["dock_width"])
    if cfg().get("ask_enabled", True):
        try:
            from . import ask
            ask.build(lay)
            width = max(width, int(cfg().get("ask_width", 260)))
        except Exception:
            _log(traceback.format_exc())
            lay.addStretch(1)
    else:
        lay.addStretch(1)

    body.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def apply_fold(collapsed: bool) -> None:
        content.setVisible(not collapsed)
        header.setVisible(not collapsed)
        strip.setVisible(collapsed)
        body.setFixedWidth(36 if collapsed else width)
        dock.setTitleBarWidget(QWidget())      # our own header replaces the plain "Voice" title

    def toggle_fold() -> None:
        c = not cfg().get("collapsed", False)
        save_cfg(collapsed=c)
        apply_fold(c)

    fold.clicked.connect(toggle_fold)
    strip.clicked.connect(toggle_fold)
    dock.setWidget(body)
    apply_fold(bool(cfg().get("collapsed", False)))
    mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    state.update(dock=dock, btn=btn, status=status, heard=heard)
    style_button()
    if cfg()["enabled"]:
        set_status("starting…")
        prepare_async()
    else:
        set_status("off", "#888")


def toggle() -> None:
    on = not cfg()["enabled"]
    save_cfg(enabled=on)
    style_button()
    if on:
        set_status("starting…")
        prepare_async()
    else:
        stop_recording(discard=True)
        set_status("off", "#888")
    focus_card()


# ----------------------------------------------------------------- vendor libs

def _vendor_ready() -> bool:
    return os.path.exists(OK_MARK)


# Voice libraries (faster-whisper, ctranslate2, numpy, sounddevice …) for Windows + Python 3.13.
# Too big for AnkiWeb, so they are downloaded once from the repo's "voice-libs" branch when 🎤 is switched ON.
LIBS_BASE = "https://raw.githubusercontent.com/AnkiMonkey/Notepad-in-ANKI/voice-libs/"
LIBS_PARTS = ["vendor-win64-py313.zip.part00", "vendor-win64-py313.zip.part01"]
LIBS_TOTAL = 88830281
LIBS_SHA256 = "a8f102b41ce49cf0aac22cb3c6d762730d637db93035f21c263ea622b76bcb76"


def _unpack_vendor(ui=None) -> None:
    """vendor_parts/vendor.zip.part* if present (offline copy), otherwise download LIBS_URL."""
    tmp = os.path.join(ADDON_DIR, "vendor.zip.tmp")
    h = hashlib.sha256()
    parts = sorted(os.path.join(PARTS_DIR, f) for f in os.listdir(PARTS_DIR)
                   if f.startswith("vendor.zip.part")) if os.path.isdir(PARTS_DIR) else []
    if parts:
        want = ""
        want_file = os.path.join(PARTS_DIR, "SHA256")
        if os.path.exists(want_file):
            want = open(want_file).read().strip()
        with open(tmp, "wb") as out:
            for p in parts:
                with open(p, "rb") as f:
                    data = f.read()
                    h.update(data)
                    out.write(data)
    else:
        want = LIBS_SHA256
        if ui:
            ui("downloading libraries<br>(~90 MB, first time only)…")
        got = 0
        last = -1
        with open(tmp, "wb") as out:
            for part in LIBS_PARTS:
                with _get(LIBS_BASE + part, _ssl_ctx()) as r:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        h.update(chunk)
                        got += len(chunk)
                        pct = int(got * 100 / LIBS_TOTAL)
                        if ui and pct != last and pct % 5 == 0:
                            last = pct
                            ui(f"downloading libraries<br>{pct} %")
    if want and h.hexdigest() != want:
        os.remove(tmp)
        raise RuntimeError("voice libraries are corrupted (checksum mismatch) – switch ON again")
    if ui:
        ui("unpacking libraries<br>(first time only)…")
    os.makedirs(VENDOR_DIR, exist_ok=True)
    with zipfile.ZipFile(tmp) as z:
        z.extractall(VENDOR_DIR)
    os.remove(tmp)
    with open(OK_MARK, "w") as f:
        f.write("ok")
    for p in parts:   # free the space, vendor/ now holds everything
        try:
            os.remove(p)
        except OSError:
            pass


def _activate_vendor() -> None:
    # appended (not prepended) so Anki's own packages always win
    if VENDOR_DIR not in sys.path:
        sys.path.append(VENDOR_DIR)
    for sub in ("", "ctranslate2", "av.libs", "numpy.libs", "_sounddevice_data/portaudio-binaries"):
        d = os.path.join(VENDOR_DIR, sub)
        if os.path.isdir(d) and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass
    # keep Hugging Face quiet: anything on stderr becomes an Anki error popup
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


# ----------------------------------------------------------------- model

MODEL_REPOS = {
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
}


def _ssl_ctx():
    try:
        import truststore  # vendored: uses the Windows certificate store
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return ssl.create_default_context()


def _get(url: str, ctx, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "AnkiMonkey-LatinVoice/1.0", **(headers or {})})
    return urllib.request.urlopen(req, context=ctx, timeout=60)


def ensure_model(name: str, ui) -> str:
    """Download the CTranslate2 model once into user_files/models/<name>, return its path."""
    repo = MODEL_REPOS.get(name, name)
    dest = os.path.join(MODELS_DIR, name.replace("/", "__"))
    done = os.path.join(dest, ".complete")
    if os.path.exists(done):
        return dest
    os.makedirs(dest, exist_ok=True)
    ctx = _ssl_ctx()
    with _get(f"https://huggingface.co/api/models/{repo}/tree/main", ctx) as r:
        tree = json.loads(r.read().decode("utf8"))
    files = [(t["path"], int(t.get("size") or 0)) for t in tree
             if t.get("type") == "file" and not t["path"].startswith(".") and t["path"].lower() != "readme.md"]
    total = sum(sz for _, sz in files) or 1
    got_before = 0
    for path, size in files:
        out = os.path.join(dest, path)
        if os.path.exists(out) and (size == 0 or os.path.getsize(out) == size):
            got_before += size
            continue
        part = out + ".part"
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        with _get(f"https://huggingface.co/{repo}/resolve/main/{path}", ctx, headers) as r:
            if have and getattr(r, "status", 200) != 206:
                have = 0   # server ignored Range: start over
            mode = "ab" if have else "wb"
            last = -1
            with open(part, mode) as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    have += len(chunk)
                    pct = int((got_before + have) * 100 / total)
                    if pct != last:
                        last = pct
                        ui(f"downloading “{name}”<br>{pct} %  ({(got_before + have) / 1e9:.2f} / {total / 1e9:.2f} GB)<br>first time only")
        os.replace(part, out)
        got_before += size
    with open(done, "w") as f:
        f.write(repo)
    return dest


def _cleanup_old_hf_cache() -> None:
    # leftovers of the first (Hugging Face cache based) attempt
    for d in os.listdir(MODELS_DIR) if os.path.isdir(MODELS_DIR) else []:
        if d.startswith("models--") or d in (".locks",) or d == "CACHEDIR.TAG":
            p = os.path.join(MODELS_DIR, d)
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            except OSError:
                pass


@contextlib.contextmanager
def _quiet():
    """Anything printed to stderr becomes an Anki error popup -> send it to the log."""
    import warnings
    logf = open(os.path.join(ADDON_DIR, "user_files", "error.log"), "a", encoding="utf8")
    try:
        with warnings.catch_warnings(), contextlib.redirect_stderr(logf), contextlib.redirect_stdout(logf):
            warnings.simplefilter("ignore")
            yield
    finally:
        logf.close()


def prepare_async() -> None:
    c = cfg()
    if state["model"] is not None and state["model_name"] == c["model"]:
        set_status(f"ready<br>hold {c['hotkey']}", GREEN)
        return
    if state["loading"]:
        return
    state["loading"] = True

    def ui(msg, col="#ddd"):
        mw.taskman.run_on_main(lambda: set_status(msg, col))

    def work():
        try:
            with _quiet():
                if not _vendor_ready():
                    _unpack_vendor(ui)
                _activate_vendor()
                os.makedirs(MODELS_DIR, exist_ok=True)
                _cleanup_old_hf_cache()
                path = ensure_model(c["model"], ui)
                ui(f"loading “{c['model']}”<br>into memory…")
                from faster_whisper import WhisperModel  # noqa: E402
                model = WhisperModel(
                    path,
                    device=c["device"],
                    compute_type=c["compute_type"],
                    cpu_threads=int(c["cpu_threads"] or 0),
                )
            state["model"] = model
            state["model_name"] = c["model"]
            ui(f"ready<br>hold {c['hotkey']}", GREEN)
        except Exception as e:  # shown in the panel, never as a popup
            state["model"] = None
            msg = f"{type(e).__name__}: {e}"
            _log(traceback.format_exc())
            ui(f"error:<br>{html.escape(msg)[:300]}", RED)
        finally:
            state["loading"] = False

    threading.Thread(target=work, daemon=True).start()


def _log(text: str) -> None:
    try:
        with open(os.path.join(ADDON_DIR, "user_files", "error.log"), "a", encoding="utf8") as f:
            f.write(text + "\n")
    except Exception:
        pass


# ----------------------------------------------------------------- vocabulary

def _clean_answer(raw: str) -> list[str]:
    raw = re.sub(r"<br\s*/?>|</div>|</p>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw).replace("\xa0", " ")
    out = []
    whole = re.sub(r"\s+", " ", raw).strip()
    if whole:
        out.append(whole)
    for piece in re.split(r"[\n;/,]", raw):
        piece = re.sub(r"\s+", " ", piece).strip(" .")
        if piece and piece not in out:
            out.append(piece)
    return out


def _prefixes() -> tuple:
    c = cfg()
    return tuple(c.get("note_type_prefixes") or [c["note_type_prefix"]])


def _target_models() -> list[dict]:
    return [m for m in mw.col.models.all() if m["name"].startswith(_prefixes())]


def _legend_answers(note) -> list[str]:
    """Deep Notes legend (PT cards): answers stored as JSON in 'DN Legend'."""
    if "DN Legend" not in note.keys():
        return []
    try:
        d = json.loads(html.unescape(note["DN Legend"]))
        return [a for v in (d.get("answers") or {}).values() for a in _clean_answer(str(v))]
    except Exception:
        return []


def _answers_for_query(query: str) -> list[str]:
    field = cfg()["answer_field"]
    words: list[str] = []
    seen = set()
    for nid in mw.col.find_notes(query):
        note = mw.col.get_note(nid)
        items = _clean_answer(note[field]) if field in note.keys() else []
        items += _legend_answers(note)
        for a in items:
            k = a.lower()
            if k not in seen:
                seen.add(k)
                words.append(a)
    return words


def _models_query() -> str:
    names = [m["name"] for m in _target_models()]
    if not names:
        return "nid:0"
    return "(" + " OR ".join(f'"note:{n}"' for n in names) + ")"


def vocab_all() -> list[str]:
    if state["vocab_all"] is None:
        state["vocab_all"] = _answers_for_query(_models_query())
    return state["vocab_all"]


def deck_vocab(did: int) -> list[str]:
    if did not in state["deck_vocab"]:
        state["deck_vocab"][did] = _answers_for_query(f"did:{did} {_models_query()}")
    return state["deck_vocab"][did]


def build_prompt(card) -> str:
    if not cfg()["use_deck_hint"]:
        return ""
    words = deck_vocab(card.odid or card.did)
    out, total = [], 0
    for w in words:   # Whisper prompt ≈ 224 tokens, keep it short
        if total + len(w) > 650:
            break
        out.append(w)
        total += len(w) + 2
    return ", ".join(out)


def snap(text: str) -> str:
    c = cfg()
    if not c["snap_to_vocab"] or not text:
        return text
    vocab = vocab_all()
    low = {v.lower(): v for v in vocab}
    if text.lower() in low:
        return low[text.lower()]
    hit = difflib.get_close_matches(text.lower(), list(low), n=1, cutoff=float(c["snap_cutoff"]))
    return low[hit[0]] if hit else text


# ----------------------------------------------------------------- recording

def is_target_card() -> bool:
    r = mw.reviewer
    if mw.state != "review" or not r.card or r.state != "question":
        return False
    try:
        return r.card.note_type()["name"].startswith(_prefixes())
    except Exception:
        return False


def start_recording() -> None:
    if state["recording"]:
        return
    if state["model"] is None:
        set_status("still loading…" if state["loading"] else "not ready", RED)
        if not state["loading"]:
            prepare_async()
        return
    try:
        import sounddevice as sd
        state["frames"] = []

        def cb(indata, frames, time_info, status):
            state["frames"].append(indata.copy())

        stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=cb)
        stream.start()
        state["stream"] = stream
        state["recording"] = True
        style_button()
        set_status("● listening…", RED)
    except Exception as e:
        _log(traceback.format_exc())
        set_status(f"mic error:<br>{html.escape(str(e))[:200]}", RED)


def stop_recording(discard: bool = False) -> None:
    stream = state["stream"]
    if not state["recording"] or stream is None:
        return
    try:
        stream.stop()
        stream.close()
    except Exception:
        pass
    state["stream"] = None
    state["recording"] = False
    style_button()
    frames = state["frames"]
    state["frames"] = []
    if discard:
        return
    import numpy as np
    if not frames:
        set_status(f"nothing heard<br>hold {cfg()['hotkey']}", "#ddd")
        return
    audio = np.concatenate(frames).flatten()
    if len(audio) < 16000 * 0.3:
        set_status(f"too short<br>hold {cfg()['hotkey']}", "#ddd")
        return
    card = mw.reviewer.card
    prompt = build_prompt(card) if card else ""
    vocab_all()          # build on the main thread (collection access)
    transcribe_async(audio, prompt, card.id if card else None)


def transcribe_async(audio, prompt: str, card_id) -> None:
    set_status("transcribing…", "#ddd")
    c = cfg()
    model = state["model"]

    def work():
        try:
            if True:   # no stderr redirect here: it would swallow other add-ons' errors
                segs, _info = model.transcribe(
                    audio,
                    language=c["language"] or None,
                    beam_size=int(c["beam_size"]),
                    initial_prompt=prompt or None,
                    condition_on_previous_text=False,
                    without_timestamps=True,
                    temperature=0.0,
                    vad_filter=False,
                )
                text = " ".join(s.text for s in segs)
            mw.taskman.run_on_main(lambda: deliver(text, card_id))
        except Exception as e:
            _log(traceback.format_exc())
            msg = html.escape(f"{type(e).__name__}: {e}")[:250]
            mw.taskman.run_on_main(lambda: set_status(f"error:<br>{msg}", RED))

    threading.Thread(target=work, daemon=True).start()


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" .,!?;:\"'„“”…-")
    if cfg()["lowercase"]:
        text = text.lower()
    return text


def deliver(raw: str, card_id) -> None:
    hk = cfg()["hotkey"]
    r = mw.reviewer
    if not r.card or r.card.id != card_id or r.state != "question":
        set_status(f"card changed, dropped<br>hold {hk}", "#ddd")
        return
    heard = tidy(raw)
    final = snap(heard)
    if not final:
        set_status(f"nothing recognised<br>hold {hk}", "#ddd")
        return
    try:
        from . import ask
        if ask.ui["box"] is not None and QApplication.focusWidget() is ask.ui["box"]:
            ask.ui["box"].setText(heard)
            ask.ask(heard)
            set_status(f"asked<br>hold {hk}", GREEN)
            return
    except Exception:
        pass
    set_heard(f"heard: {html.escape(heard)}" + (f"<br>→ {html.escape(final)}" if final != heard else ""))
    set_status(f"check & Enter<br>hold {hk} to redo", GREEN)
    if "DN Legend" in r.card.note().keys():
        deliver_panel(final)
        return
    js = """
(function (t) {
  var b = document.getElementById("tc-in");
  if (!b) return;
  b.value = t;
  b.dispatchEvent(new Event("input", { bubbles: true }));
  window.focus(); b.focus();
  b.setSelectionRange(t.length, t.length);
})(%s);
""" % _js_str(final)
    mw.web.setFocus()
    mw.web.eval(js)


def deliver_panel(text: str) -> None:
    """PT cards: write into the Deep Notes panel (focused editor, or current/next empty Notes row)."""
    from aqt.qt import QLineEdit, QPlainTextEdit, QTextEdit
    fw = QApplication.focusWidget()
    if isinstance(fw, QLineEdit):
        fw.setText(text); fw.end(False); return
    if isinstance(fw, (QPlainTextEdit, QTextEdit)):
        fw.insertPlainText(text); return
    dn = sys.modules.get(ADDON_KEY + ".deep_notes")
    st = getattr(dn, "state", None) if dn else None
    table = st.get("table") if isinstance(st, dict) else None
    if table is not None and table.isVisible() and table.rowCount():
        from aqt.qt import QTableWidgetItem, QTimer
        row = table.currentRow()
        if row < 0 or (table.item(row, 1) and table.item(row, 1).text().strip()):
            row = next((i for i in range(table.rowCount())
                        if not (table.item(i, 1) and table.item(i, 1).text().strip())), max(row, 0))
        it = table.item(row, 1)
        if it is None:
            it = QTableWidgetItem(""); table.setItem(row, 1, it)
        # open the cell editor so Deep Notes' Check runs when YOU press Enter
        table.setFocus()
        table.setCurrentCell(row, 1)
        table.editItem(it)

        def fill():
            ed = QApplication.focusWidget()
            if isinstance(ed, QLineEdit):
                ed.setText(text); ed.end(False)
            else:
                it.setText(text)
        QTimer.singleShot(0, fill)
        return
    box = st.get("text_box") if isinstance(st, dict) else None
    if box is not None:
        box.setFocus(); box.insertPlainText(text + "\n"); return
    set_status("no answer box found", RED)


def _js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def focus_card() -> None:
    if mw.state == "review":
        mw.web.setFocus()
        mw.web.eval(
            'var b=document.getElementById("tc-in");if(b&&b.offsetParent!==null){window.focus();b.focus();}'
        )


# ----------------------------------------------------------------- hotkey

def _hotkey_code() -> int:
    seq = QKeySequence(cfg()["hotkey"])
    if seq.isEmpty():
        return -1
    k = seq[0]
    k = k.key() if hasattr(k, "key") else k
    return int(getattr(k, "value", k))


class HoldToTalk(QObject):
    def eventFilter(self, obj, ev):  # noqa: N802 (Qt API)
        t = ev.type()
        if t not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        try:
            if ev.key() != _hotkey_code():
                return False
        except Exception:
            return False
        if not cfg()["enabled"]:
            return False
        if t == QEvent.Type.KeyPress:
            if not is_target_card() and not state["recording"]:
                return False
            if not ev.isAutoRepeat():
                start_recording()
            return True
        # release
        if ev.isAutoRepeat():
            return True
        if state["recording"]:
            stop_recording()
            return True
        return False


def install_filter() -> None:
    if state["filter"] is None:
        f = HoldToTalk(mw)
        QApplication.instance().installEventFilter(f)
        state["filter"] = f


# ----------------------------------------------------------------- hooks

def on_profile_open() -> None:
    state["vocab_all"] = None
    state["deck_vocab"] = {}
    create_dock()
    install_filter()
    if cfg()["hide_outside_review"] and mw.state != "review":
        state["dock"].hide()


def on_state_change(new_state, old_state) -> None:
    dock = state["dock"]
    if not dock:
        return
    if new_state == "review":
        dock.show()
    elif cfg()["hide_outside_review"]:
        stop_recording(discard=True)
        dock.hide()
    if new_state != "review":
        # notes may have been added/edited in the meantime
        state["vocab_all"] = None
        state["deck_vocab"] = {}


def on_show_answer(card) -> None:
    stop_recording(discard=True)


def on_profile_close() -> None:
    stop_recording(discard=True)


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)
gui_hooks.state_did_change.append(on_state_change)
gui_hooks.reviewer_did_show_answer.append(on_show_answer)
