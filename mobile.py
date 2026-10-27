"""Deep Notes Mobile – Auto rows + Check on AnkiDroid / AnkiMobile.

Part of AnkiMonkey (module "mobile"). The Deep Notes module itself is never touched.
On the PC it only does the setup (Tools > Deep Notes Mobile > Zapnúť): it writes a hidden
field "DN Legend" and a small JavaScript block into the card templates. That JS runs only
on a phone/tablet, so on the PC everything looks and works exactly as before.

Legends, abbreviations and colours are read from user_files and the deep_notes config section.
"""

import hashlib
import html
import json
import os
import re
import time
import unicodedata

from aqt import gui_hooks, mw
from aqt.qt import QAction, QMenu
from aqt.utils import askUser, showInfo, tooltip

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_KEY = __name__.split(".")[0]
from .common import get_section, write_section
FIELD = "DN Legend"
START = "<!-- DN-MOBILE START: Deep Notes Mobile add-on. Do not edit by hand - Tools > Deep Notes Mobile -->"
END = "<!-- DN-MOBILE END -->"
TABLET_KEYS = ["smart_dash", "check_ok_color", "check_bad_color", "check_dunno_color",
               "check_dunno_words", "check_long_words", "check_long_percent"]
BLOCK_RE = re.compile(r"\n?<!-- DN-MOBILE START.*?<!-- DN-MOBILE END -->", re.S)

DEFAULTS = {
    "enabled": False,
    "auto_refresh": True,
    "backup_dir": "",
    "last_signature": "",
}


# ---------------------------------------------------------------- config

def cfg() -> dict:
    conf = dict(DEFAULTS)
    conf.update(get_section("mobile"))
    return conf


def save_cfg(**changes) -> None:
    conf = cfg()
    conf.update(changes)
    write_section("mobile", conf)


def backup_dir() -> str:
    custom = str(cfg()["backup_dir"]).strip()
    if custom:
        return os.path.expandvars(os.path.expanduser(custom))
    return os.path.join(os.path.expanduser("~"), "Documents", "DeepNotes_mobile", "backup")


# ---------------------------------------------------------------- inputs

def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _words(s: str) -> list:
    return re.findall(r"[a-z0-9]+", _plain(s))


def deep_notes_dir():
    """Deep Notes lives in this same add-on now."""
    if os.path.isfile(os.path.join(ADDON_DIR, "user_files", "legend_labels.json")):
        return ADDON_DIR
    return None


def _json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def abbreviations(path: str) -> dict:
    """Same parsing as Deep Notes: 'tbc = tuberculum', 'v = vertebra, vena'."""
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
                        mapping.setdefault(key, [])
                        if w not in mapping[key]:
                            mapping[key].append(w)
    except OSError:
        pass
    return mapping


def _source_files(dn_dir: str) -> list:
    uf = os.path.join(dn_dir, "user_files")
    return [os.path.join(uf, n) for n in
            ("legend_labels.json", "legend_answers.json", "legend_answers_full.json", "abbreviations.txt")] + \
           [os.path.join(ADDON_DIR, "dn_mobile.js")]


def signature(dn_dir: str) -> str:
    """Changes when legends, abbreviations, Deep Notes settings or the JS change."""
    h = hashlib.sha1()
    for p in _source_files(dn_dir):
        try:
            with open(p, "rb") as fh:
                h.update(fh.read())
        except OSError:
            h.update(b"-")
    dn_conf = get_section("deep_notes")
    # only what ends up on the tablet – not width/zoom that Deep Notes saves on every close
    h.update(json.dumps({k: dn_conf.get(k) for k in TABLET_KEYS + ["smart_notes_field"]}, sort_keys=True).encode())
    return h.hexdigest()


def load_sources(dn_dir: str) -> dict:
    uf = os.path.join(dn_dir, "user_files")
    with open(os.path.join(ADDON_DIR, "dn_mobile.js"), encoding="utf-8") as fh:
        js = fh.read()
    return {
        "labels": _json(os.path.join(uf, "legend_labels.json")),
        "answers": _json(os.path.join(uf, "legend_answers.json")),
        "full": _json(os.path.join(uf, "legend_answers_full.json")),
        "abbr": abbreviations(os.path.join(uf, "abbreviations.txt")),
        "conf": get_section("deep_notes"),
        "js": js,
    }


# ---------------------------------------------------------------- building

def strip_block(tmpl: str) -> str:
    return BLOCK_RE.sub("", tmpl or "").rstrip()


def payload(note, src_data: dict) -> str:
    labels = src_data["labels"]
    for value in note.values():
        for src in re.findall(r'src="([^"]+)"', value):
            if src in labels:
                data = {
                    "img": src,
                    "labels": list(labels[src]),
                    "answers": src_data["answers"].get(src, {}),
                    "full": src_data["full"].get(src, {}),
                }
                return html.escape(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return ""


def front_block(nt, src_data: dict):
    """The block for the front template, or None when it would break the template."""
    conf = src_data["conf"]
    dn_cfg = {k: conf[k] for k in TABLET_KEYS if k in conf}
    notes_field = conf.get("smart_notes_field", "Personal Notes")
    parts = [START, '<div id="dn-legend" style="display:none">{{' + FIELD + '}}</div>']
    allowed = ["{{" + FIELD + "}}"]
    if notes_field in mw.col.models.field_names(nt):
        parts.append('<div id="dn-pnotes" style="display:none">{{' + notes_field + '}}</div>')
        allowed.append("{{" + notes_field + "}}")
    parts += ['<div id="dn-root"></div>',
              "<script>window.DN_CFG = " + json.dumps(dn_cfg, ensure_ascii=False) +
              ";\nwindow.DN_ABBR = " + json.dumps(src_data["abbr"], ensure_ascii=False) + ";</script>",
              "<script>\n" + src_data["js"] + "\n</script>",
              END]
    block = "\n".join(parts)
    rest = block
    for a in allowed:
        rest = rest.replace(a, "")
    if "{{" in rest or "}}" in rest:
        return None  # Anki would read it as a field
    return block


BACK_BLOCK = START + '\n<span id="dn-back" style="display:none"></span>\n' + END


def scan(src_data: dict):
    """{note id: field value} for notes with a legend image, and their note type ids."""
    payloads, mids = {}, set()
    for nid in mw.col.find_notes(""):
        note = mw.col.get_note(nid)
        p = payload(note, src_data)
        if p:
            payloads[nid] = p
            mids.add(note.mid)
    return payloads, mids


def write_templates(nt, src_data: dict) -> bool:
    fb = front_block(nt, src_data)
    if fb is None:
        return False
    for t in nt["tmpls"]:
        t["qfmt"] = strip_block(t["qfmt"]) + "\n\n" + fb
        a = strip_block(t["afmt"])
        t["afmt"] = a + "\n\n" + BACK_BLOCK if "{{FrontSide}}" in a else a + "\n\n" + BACK_BLOCK + "\n" + fb
    mw.col.models.update_dict(nt)
    return True


def fill_notes(mids, payloads) -> int:
    changed = []
    for mid in mids:
        for nid in mw.col.models.nids(mid):
            note = mw.col.get_note(nid)
            want = payloads.get(nid, "")
            if note[FIELD] != want:
                note[FIELD] = want
                changed.append(note)
    if changed:
        mw.col.update_notes(changed)
    return len(changed)


def _refresh_ui() -> None:
    try:
        mw.reset()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- actions

def turn_on() -> None:
    """Menu: set up / refresh everything (asks before any schema change)."""
    dn_dir = deep_notes_dir()
    if not dn_dir:
        showInfo("Deep Notes Mobile: nenašiel som Deep Notes s user_files/legend_labels.json.\n"
                 "Legendy musia byť najprv v Deep Notes (tie isté ako pre Auto rows na PC).")
        return
    src_data = load_sources(dn_dir)
    payloads, mids = scan(src_data)
    if not payloads:
        showInfo("Deep Notes Mobile: žiadna karta nemá obrázok z legend_labels.json.")
        return
    nts = [mw.col.models.get(m) for m in mids]
    names = ", ".join(nt["name"] for nt in nts)
    need_field = [nt for nt in nts if FIELD not in mw.col.models.field_names(nt)]

    msg = (f"Deep Notes Mobile\n\nKarty s legendou: {len(payloads)}\nNote typy: {names}\n\n"
           "Urobím zálohu, pridám JS do šablón (beží len na tablete/mobile, na PC nič) "
           f"a naplním skryté pole '{FIELD}'.")
    if need_field:
        msg += "\n\nPridanie poľa = zmena schémy: potom raz plný sync (na PC Upload, na tablete Download)."
    if not askUser(msg + "\n\nPokračovať?"):
        return

    bdir = backup_dir()
    os.makedirs(bdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(bdir, f"templates_{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({nt["name"]: nt["tmpls"] for nt in nts}, fh, ensure_ascii=False, indent=1)
    try:
        made = mw.col.create_backup(backup_folder=bdir, force=True, wait_for_completion=True)
        backup_msg = f"v {bdir}" if made else "Anki novú nespravilo (bez zmien od poslednej), šablóny zálohované"
    except Exception as e:  # noqa: BLE001
        if not askUser(f"Záloha kolekcie zlyhala: {e}\n\nŠablóny sú zálohované v {bdir}. Pokračovať aj tak?"):
            return
        backup_msg = "kolekcia zlyhala, šablóny zálohované"

    for nt in need_field:
        mw.col.mod_schema(check=True)
        fld = mw.col.models.new_field(FIELD)
        if "collapsed" in fld:
            fld["collapsed"] = True
        if "excludeFromSearch" in fld:
            fld["excludeFromSearch"] = True
        mw.col.models.add_field(nt, fld)
        mw.col.models.update_dict(nt)
    for mid in mids:
        if not write_templates(mw.col.models.get(mid), src_data):
            showInfo("Deep Notes Mobile: v JS alebo skratkách sú dve zložené zátvorky vedľa seba – "
                     "Anki by ich bral ako pole. Šablóny som nezmenil.")
            return
    n = fill_notes(mids, payloads)
    save_cfg(enabled=True, last_signature=signature(dn_dir))
    _refresh_ui()
    update_menu()
    showInfo(
        "Deep Notes Mobile: zapnuté.\n\n"
        f"Note typy: {names}\nKarty s legendou: {len(payloads)} (zmenených poznámok: {n})\n"
        f"Záloha: {backup_msg}\n\n"
        "Teraz Sync na PC (plný sync = Upload), potom Sync na tablete (Download).\n"
        "Na PC sa nič nemení – Deep Notes robí Auto/Check ako doteraz."
    )


def auto_refresh() -> None:
    """On profile open: legends / abbreviations / colours changed -> update quietly.
    Never changes the schema (only notes + templates that already have the field)."""
    conf = cfg()
    if not (conf["enabled"] and conf["auto_refresh"]) or mw.col is None:
        return
    try:
        dn_dir = deep_notes_dir()
        if not dn_dir:
            return
        sig = signature(dn_dir)
        if sig == conf["last_signature"]:
            return
        src_data = load_sources(dn_dir)
        payloads, mids = scan(src_data)
        ready = [m for m in mids if FIELD in mw.col.models.field_names(mw.col.models.get(m))]
        if len(ready) != len(mids):
            tooltip("Deep Notes Mobile: nové note typy s legendou – daj Nástroje > Deep Notes Mobile > Zapnúť")
            return
        for mid in ready:
            if not write_templates(mw.col.models.get(mid), src_data):
                return
        n = fill_notes(ready, payloads)
        save_cfg(last_signature=sig)
        tooltip(f"Deep Notes Mobile: legendy aktualizované ({n} poznámok)")
    except Exception as e:  # noqa: BLE001 – never break opening the profile
        tooltip(f"Deep Notes Mobile: aktualizácia zlyhala ({e})")


def turn_off() -> None:
    """Menu: remove the block from all templates and delete the field."""
    if not askUser("Deep Notes Mobile: odstrániť JS zo šablón a zmazať pole 'DN Legend'?\n\n"
                   "Zmena schémy – potom plný sync. Deep Notes na PC sa to netýka."):
        return
    cleaned, dropped = [], []
    for nt in mw.col.models.all():
        has_block = any(START[:24] in (t["qfmt"] + t["afmt"]) for t in nt["tmpls"])
        has_field = FIELD in mw.col.models.field_names(nt)
        if not (has_block or has_field):
            continue
        if has_block:
            for t in nt["tmpls"]:
                t["qfmt"] = strip_block(t["qfmt"])
                t["afmt"] = strip_block(t["afmt"])
            cleaned.append(nt["name"])
        if has_field:
            mw.col.mod_schema(check=True)
            mw.col.models.remove_field(nt, next(f for f in nt["flds"] if f["name"] == FIELD))
            dropped.append(nt["name"])
        mw.col.models.update_dict(nt)
    save_cfg(enabled=False, last_signature="")
    _refresh_ui()
    update_menu()
    showInfo("Deep Notes Mobile: vypnuté.\n\n"
             f"Šablóny vyčistené: {', '.join(cleaned) or '-'}\n"
             f"Pole '{FIELD}' zmazané: {', '.join(dropped) or '-'}\n\n"
             "Potom Sync (plný sync = Upload).")


def _safe(fn):
    def run():
        try:
            fn()
        except Exception as e:  # noqa: BLE001 – e.g. full-sync question answered "No"
            showInfo(f"Deep Notes Mobile: zastavené.\n\n{type(e).__name__}: {e}")
    return run


# ---------------------------------------------------------------- menu

_menu = {"on": None, "off": None, "status": None}


def update_menu() -> None:
    on = bool(cfg()["enabled"])
    if _menu["status"]:
        _menu["status"].setText("Stav: zapnuté pre tablet" if on else "Stav: vypnuté")
    if _menu["on"]:
        _menu["on"].setText("Aktualizovať legendy na tablete" if on else "Zapnúť pre tablet / mobil")
    if _menu["off"]:
        _menu["off"].setEnabled(on)


def add_menu() -> None:
    menu = QMenu("Deep Notes Mobile", mw)
    status = QAction("", mw)
    status.setEnabled(False)
    menu.addAction(status)
    menu.addSeparator()
    act_on = QAction("", mw)
    act_on.triggered.connect(_safe(turn_on))
    menu.addAction(act_on)
    act_off = QAction("Vypnúť (odstrániť zo šablón)", mw)
    act_off.triggered.connect(_safe(turn_off))
    menu.addAction(act_off)
    menu.addSeparator()
    act_dir = QAction("Otvoriť priečinok so zálohami", mw)
    act_dir.triggered.connect(lambda: _open_dir(backup_dir()))
    menu.addAction(act_dir)
    mw.form.menuTools.addMenu(menu)
    _menu.update(on=act_on, off=act_off, status=status)
    update_menu()


def _open_dir(path: str) -> None:
    from aqt.utils import openFolder
    os.makedirs(path, exist_ok=True)
    openFolder(path)


gui_hooks.main_window_did_init.append(add_menu)
gui_hooks.profile_did_open.append(auto_refresh)
