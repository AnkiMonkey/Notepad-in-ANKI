"""AnkiMonkey – Deep Notes · Deep Notes Mobile · Latin Voice Input · Ask (Claude) · type-in autofocus.

One add-on, five modules. Each module loads on its own: if one fails, the others still work
and the error goes to user_files/error.log.
"""
import importlib
import os
import traceback

MODULES = ("deep_notes", "mobile", "voice", "typein_focus")
_DIR = os.path.dirname(os.path.abspath(__file__))

for _m in MODULES:
    try:
        importlib.import_module(f"{__name__}.{_m}")
    except Exception:
        try:
            os.makedirs(os.path.join(_DIR, "user_files"), exist_ok=True)
            with open(os.path.join(_DIR, "user_files", "error.log"), "a", encoding="utf8") as _f:
                _f.write(f"\n--- module {_m} failed to load ---\n" + traceback.format_exc())
        except Exception:
            pass
