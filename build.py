"""Build ankimonkey.ankiaddon for AnkiWeb.

Usage:  python build.py
Packs only the code and the public example files (files at the zip root).
Never packed: meta.json (your settings), vendor/ (downloaded on first 🎤 ON),
and your private user_files (legends, backup images, models, prompts, error log).
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "ankimonkey.ankiaddon")
FILES = ["__init__.py", "common.py", "deep_notes.py", "mobile.py", "dn_mobile.js", "voice.py",
         "ask.py", "typein_focus.py", "config.json", "config.md", "logo.png"]
PUBLIC_USER_FILES = ["README.txt", "abbreviations.txt", "templates"]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in FILES:
        z.write(os.path.join(ROOT, f), f)
    for item in PUBLIC_USER_FILES:
        path = os.path.join(ROOT, "user_files", item)
        if os.path.isfile(path):
            z.write(path, os.path.relpath(path, ROOT))
            continue
        for base, _dirs, names in os.walk(path):
            for n in names:
                if n.endswith((".pyc", ".bak")):
                    continue
                full = os.path.join(base, n)
                z.write(full, os.path.relpath(full, ROOT))
print(OUT, os.path.getsize(OUT), "bytes")
