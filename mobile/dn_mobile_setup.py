"""Deep Notes – mobile setup (AnkiDroid / AnkiMobile).

Puts Auto rows + Check into the card templates as JavaScript that runs ONLY on a
phone/tablet. The Deep Notes add-on on the PC is not touched; on the PC the script
does nothing at all.

What it does (install):
  1. backup of the collection + a JSON copy of the original templates
  2. adds a hidden field "DN Legend" to the note types that have legend cards
     (one-time full sync needed after this)
  3. fills that field from user_files/legend_*.json (+ abbreviations.txt, your config)
  4. appends a block between DN-MOBILE START / END markers to the templates

Run it in Anki on the PC: Tools > Debug Console (Ctrl+Shift+;), paste, Ctrl+Enter:

    exec(open(r"C:\\Users\\timon\\Documents\\DeepNotes_mobile\\dn_mobile_setup.py", encoding="utf-8").read())

Undo everything (templates back + field removed):

    DN_MODE = "remove"; exec(open(r"...\\dn_mobile_setup.py", encoding="utf-8").read())

Running install again is safe: it replaces the old block and refreshes the field
(do it after you change legends or abbreviations.txt).
dn_mobile.js must sit in the same folder as this script (default Documents\\DeepNotes_mobile,
or set DN_DIR = r"..." before exec).
"""

import html
import json
import os
import re
import time
import unicodedata

from aqt import mw
from aqt.utils import askUser, showInfo

DN_ADDON_ID = "558080023"
DN_FIELD = "DN Legend"
DN_START = "<!-- DN-MOBILE START: Deep Notes for phone/tablet. Do not edit by hand - re-run dn_mobile_setup.py -->"
DN_END = "<!-- DN-MOBILE END -->"
DN_BLOCK_RE = re.compile(r"\n?<!-- DN-MOBILE START.*?<!-- DN-MOBILE END -->", re.S)


def _dn_plain(s):
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _dn_words(s):
    return re.findall(r"[a-z0-9]+", _dn_plain(s))


def _dn_addon_dir():
    addons = mw.addonManager.addonsFolder()
    cands = [os.path.join(addons, DN_ADDON_ID)]
    cands += [os.path.join(addons, d) for d in sorted(os.listdir(addons))]
    for d in cands:
        if os.path.isfile(os.path.join(d, "user_files", "legend_labels.json")):
            return d
    return None


def _dn_json(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _dn_abbreviations(path):
    """Same parsing as the add-on: 'tbc = tuberculum', 'v = vertebra, vena'."""
    mapping = {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if "=" not in line:
                    continue
                key, _, vals = line.partition("=")
                key = "".join(_dn_words(key))
                for v in vals.split(","):
                    w = "".join(_dn_words(v))
                    if key and w:
                        mapping.setdefault(key, [])
                        if w not in mapping[key]:
                            mapping[key].append(w)
    except OSError:
        pass
    return mapping


def _dn_strip(tmpl):
    return DN_BLOCK_RE.sub("", tmpl or "").rstrip()


def _dn_no_braces(text, allowed):
    """Anki reads {{...}} as a field – only our own field references may be in the block."""
    rest = text
    for a in allowed:
        rest = rest.replace(a, "")
    return "{{" not in rest and "}}" not in rest


def _dn_payload(note, labels, answers, full):
    for value in note.values():
        for src in re.findall(r'src="([^"]+)"', value):
            if src in labels:
                data = {
                    "img": src,
                    "labels": list(labels[src]),
                    "answers": answers.get(src, {}),
                    "full": full.get(src, {}),
                }
                return html.escape(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return ""


def _dn_remove():
    changed, removed_field = [], []
    for nt in mw.col.models.all():
        has_block = any(DN_START in (t["qfmt"] + t["afmt"]) for t in nt["tmpls"])
        has_field = DN_FIELD in mw.col.models.field_names(nt)
        if not has_block and not has_field:
            continue
        if has_block:
            for t in nt["tmpls"]:
                t["qfmt"] = _dn_strip(t["qfmt"])
                t["afmt"] = _dn_strip(t["afmt"])
            changed.append(nt["name"])
        if has_field:
            mw.col.mod_schema(check=True)
            fld = next(f for f in nt["flds"] if f["name"] == DN_FIELD)
            mw.col.models.remove_field(nt, fld)
            removed_field.append(nt["name"])
        mw.col.models.update_dict(nt)
    showInfo(
        "Deep Notes mobile: odstránené.\n\n"
        f"Šablóny vyčistené: {', '.join(changed) or '-'}\n"
        f"Pole '{DN_FIELD}' zmazané: {', '.join(removed_field) or '-'}"
    )


def _dn_install(here):
    addon_dir = _dn_addon_dir()
    if not addon_dir:
        showInfo("Deep Notes mobile: nenašiel som add-on s user_files/legend_labels.json.\n"
                 "Najprv tam musia byť legendy (rovnako ako pre Auto rows na PC).")
        return
    uf = os.path.join(addon_dir, "user_files")
    labels = _dn_json(os.path.join(uf, "legend_labels.json"))
    answers = _dn_json(os.path.join(uf, "legend_answers.json"))
    full = _dn_json(os.path.join(uf, "legend_answers_full.json"))
    abbr = _dn_abbreviations(os.path.join(uf, "abbreviations.txt"))
    conf = mw.addonManager.getConfig(os.path.basename(addon_dir)) or {}

    js_path = os.path.join(here, "dn_mobile.js")
    try:
        with open(js_path, encoding="utf-8") as fh:
            js = fh.read()
    except OSError:
        showInfo(f"Deep Notes mobile: chýba {js_path}\nDaj dn_mobile.js do rovnakého priečinka ako tento skript.")
        return

    # which notes have a legend image, and in which note types
    payloads, nt_ids = {}, set()
    for nid in mw.col.find_notes(""):
        note = mw.col.get_note(nid)
        p = _dn_payload(note, labels, answers, full)
        if p:
            payloads[nid] = p
            nt_ids.add(note.mid)
    if not payloads:
        showInfo("Deep Notes mobile: žiadna karta nemá obrázok z legend_labels.json.")
        return
    nts = [mw.col.models.get(mid) for mid in nt_ids]
    names = ", ".join(nt["name"] for nt in nts)
    need_field = [nt for nt in nts if DN_FIELD not in mw.col.models.field_names(nt)]

    msg = (f"Deep Notes mobile\n\nKarty s legendou: {len(payloads)}\nNote typy: {names}\n\n"
           "Urobím zálohu, pridám JS do šablón (beží len na mobile/tablete) "
           f"a naplním pole '{DN_FIELD}'.")
    if need_field:
        msg += "\n\nPridanie poľa = zmena schémy: po tomto raz treba plný sync (Upload z PC)."
    if not askUser(msg + "\n\nPokračovať?"):
        return

    # 1) backups
    bdir = os.path.join(here, "backup")
    os.makedirs(bdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(bdir, f"templates_{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({nt["name"]: nt["tmpls"] for nt in nts}, fh, ensure_ascii=False, indent=1)
    try:
        made = mw.col.create_backup(backup_folder=bdir, force=True, wait_for_completion=True)
        backup_msg = "nová záloha kolekcie v " + bdir if made else \
            "Anki novú zálohu nespravilo (od poslednej žiadna zmena) – posledná je v Anki backups"
    except Exception as e:  # noqa: BLE001 – never stop on the backup step silently
        if not askUser(f"Záloha kolekcie zlyhala: {e}\n\nŠablóny sú zálohované v {bdir}. Pokračovať aj tak?"):
            return
        backup_msg = "záloha kolekcie zlyhala, šablóny zálohované"

    # 2) the block for the templates
    cfg_keys = ["smart_dash", "check_ok_color", "check_bad_color", "check_dunno_color",
                "check_dunno_words", "check_long_words", "check_long_percent"]
    dn_cfg = {k: conf[k] for k in cfg_keys if k in conf}
    notes_field = conf.get("smart_notes_field", "Personal Notes")

    def front_block(nt):
        fields = mw.col.models.field_names(nt)
        parts = [DN_START,
                 '<div id="dn-legend" style="display:none">{{' + DN_FIELD + '}}</div>']
        if notes_field in fields:
            parts.append('<div id="dn-pnotes" style="display:none">{{' + notes_field + '}}</div>')
        parts += ['<div id="dn-root"></div>',
                  "<script>window.DN_CFG = " + json.dumps(dn_cfg, ensure_ascii=False) +
                  ";\nwindow.DN_ABBR = " + json.dumps(abbr, ensure_ascii=False) + ";</script>",
                  "<script>\n" + js + "\n</script>",
                  DN_END]
        return "\n".join(parts)

    back_only = DN_START + '\n<span id="dn-back" style="display:none"></span>\n' + DN_END

    # 3) field + templates
    for nt in nts:
        if DN_FIELD not in mw.col.models.field_names(nt):
            mw.col.mod_schema(check=True)
            fld = mw.col.models.new_field(DN_FIELD)
            if "collapsed" in fld:
                fld["collapsed"] = True
            if "excludeFromSearch" in fld:
                fld["excludeFromSearch"] = True
            mw.col.models.add_field(nt, fld)
            mw.col.models.update_dict(nt)
        nt = mw.col.models.get(nt["id"])
        fb = front_block(nt)
        allowed = ["{{" + DN_FIELD + "}}", "{{" + notes_field + "}}"]
        if not _dn_no_braces(fb, allowed):
            showInfo("Deep Notes mobile: v dn_mobile.js / abbreviations sú dve zložené zátvorky vedľa seba – "
                     "Anki by ich bral ako pole. Nič som nezmenil v šablónach.")
            return
        for t in nt["tmpls"]:
            t["qfmt"] = _dn_strip(t["qfmt"]) + "\n\n" + fb
            a = _dn_strip(t["afmt"])
            if "{{FrontSide}}" in a:
                t["afmt"] = a + "\n\n" + back_only
            else:
                t["afmt"] = a + "\n\n" + back_only + "\n" + fb
        mw.col.models.update_dict(nt)

    # 4) fill the field (and empty it on notes that no longer have a legend image)
    changed = []
    for mid in nt_ids:
        for nid in mw.col.models.nids(mid):
            note = mw.col.get_note(nid)
            want = payloads.get(nid, "")
            if note[DN_FIELD] != want:
                note[DN_FIELD] = want
                changed.append(note)
    if changed:
        mw.col.update_notes(changed)

    try:
        mw.reset()
    except Exception:  # noqa: BLE001
        pass
    showInfo(
        "Deep Notes mobile: hotovo.\n\n"
        f"Note typy: {names}\nKarty s legendou: {len(payloads)} (zmenených poznámok: {len(changed)})\n"
        f"Záloha: {backup_msg}\n\n"
        "Teraz Sync na PC (pri otázke na plný sync daj Upload), potom Sync na tablete (Download).\n"
        "Na PC sa nič nemení – add-on robí Auto/Check ako doteraz."
    )


def _dn_main():
    mode = str(globals().pop("DN_MODE", "install")).lower()
    here = globals().get("DN_DIR") or os.path.join(os.path.expanduser("~"), "Documents", "DeepNotes_mobile")
    if mode == "remove":
        if askUser("Deep Notes mobile: odstrániť JS zo šablón a zmazať pole 'DN Legend'?\n"
                   "(zmena schémy – potom plný sync)"):
            _dn_remove()
    else:
        _dn_install(here)


try:
    _dn_main()
except Exception as _dn_err:  # noqa: BLE001 – e.g. full-sync question answered "No"
    import traceback
    showInfo("Deep Notes mobile: zastavené.\n\n" + "".join(traceback.format_exception_only(type(_dn_err), _dn_err)))
