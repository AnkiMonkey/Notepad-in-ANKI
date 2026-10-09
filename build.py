"""Build deep_notes.ankiaddon for AnkiWeb.

Usage:  python build.py
Packs only what Anki needs (files at the zip root, no README images, no caches).
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "deep_notes.ankiaddon")
FILES = ["__init__.py", "config.json", "config.md", "logo.png"]
DIRS = ["user_files"]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in FILES:
        z.write(os.path.join(ROOT, f), f)
    for d in DIRS:
        for base, _, names in os.walk(os.path.join(ROOT, d)):
            for n in names:
                if n.endswith((".pyc", ".bak")) or n == "meta.json":
                    continue
                full = os.path.join(base, n)
                z.write(full, os.path.relpath(full, ROOT))
print(OUT, os.path.getsize(OUT), "bytes")
