"""Shared config helpers: one Anki config, one section per module."""
from aqt import mw

PKG = __name__.split(".")[0]
SECTIONS = ("deep_notes", "voice", "mobile")


def _conf() -> dict:
    conf = mw.addonManager.getConfig(PKG) or {}
    # Deep Notes ≤ 2026-10 kept its settings flat at the top level → move them into "deep_notes" once
    flat = {k: v for k, v in conf.items() if k not in SECTIONS}
    if flat:
        dn = dict(flat)
        dn.update(conf.get("deep_notes") or {})
        conf = {k: v for k, v in conf.items() if k in SECTIONS}
        conf["deep_notes"] = dn
        mw.addonManager.writeConfig(PKG, conf)
    return conf


def get_section(name: str) -> dict:
    return dict(_conf().get(name) or {})


def write_section(name: str, values: dict) -> None:
    conf = _conf()
    conf[name] = values
    mw.addonManager.writeConfig(PKG, conf)
