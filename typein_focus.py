"""
Anatomia type-in autofocus
--------------------------
After every new question on the Anatomia-type-in-answer note types, give the
keyboard back to the card and put the cursor into the #tc-in box.

Why: the bottom answer bar (mouse click on Again/Hard/Good/Easy) and the
Deep Notes "Rows?" bar (focuses itself ~60 ms after each question) both keep
Qt focus, so JS focus() inside the card can't win on its own.
Deep Notes itself is not touched.
"""

from aqt import gui_hooks, mw
from aqt.qt import QTimer

NOTE_TYPE_PREFIX = "Anatomia-type-in-answer"   # matches both note types
DELAYS_MS = (150, 400)                         # after Deep Notes' 60 ms grab

JS = """
(function () {
  var b = document.getElementById("tc-in");
  if (b && b.offsetParent !== null) { window.focus(); b.focus(); }
})();
"""


def _is_target(card) -> bool:
    try:
        return card.note_type()["name"].startswith(NOTE_TYPE_PREFIX)
    except Exception:
        return False


def _grab(card_id: int) -> None:
    r = mw.reviewer
    if mw.state != "review" or not r.card or r.card.id != card_id:
        return
    if r.state != "question":
        return
    mw.web.setFocus()
    mw.web.eval(JS)


def on_show_question(card) -> None:
    if not _is_target(card):
        return
    for d in DELAYS_MS:
        QTimer.singleShot(d, lambda cid=card.id: _grab(cid))


gui_hooks.reviewer_did_show_question.append(on_show_question)
