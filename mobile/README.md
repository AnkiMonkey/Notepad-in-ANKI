# Deep Notes – mobile (AnkiDroid / AnkiMobile)

AnkiDroid can't run Python add-ons, so **Auto rows** and **Check** run here as JavaScript inside the card template.
The script runs **only on a phone or tablet**; on the PC it does nothing and the add-on works exactly as before.

## What you get on the tablet

- A table under the card: legend points as rows, the ones your notes field skips (`NIE: …`) get `-`
- Check with the same rules as the add-on: Enter or space at the end checks your answer.
  Green means correct and jumps to the next row. Red stays, and Enter again reveals the answer.
  `?` / `idk` / `neviem` or two spaces reveal the answer in blue. Abbreviations come from `abbreviations.txt`.
- Score `correct / revealed / total`; tap a finished row to see the full legend text
- Hardware keyboard: `Alt+K` Auto, `Alt+J` Check, `Alt+P` jump into the first empty row, `Esc` leaves the row
- What you type survives flipping to the back side; a new card starts empty

## Install (once, on the PC)

1. Put `dn_mobile.js` and `dn_mobile_setup.py` into `Documents\DeepNotes_mobile\`.
2. In Anki, open Tools → Debug Console (`Ctrl+Shift+;`), paste this line and press `Ctrl+Enter`:
   ```python
   exec(open(r"C:\Users\timon\Documents\DeepNotes_mobile\dn_mobile_setup.py", encoding="utf-8").read())
   ```
3. Confirm the prompts. The script then:
   - makes a backup (`.colpkg` and the original templates as JSON) in `DeepNotes_mobile\backup\`
   - adds a hidden field `DN Legend`, which is a schema change and needs one full sync
   - appends the JS block between the `DN-MOBILE START/END` markers
4. Sync the PC and choose **Upload** when asked about a full sync. Then sync the tablet and choose **Download**.

Run it again after you change the legends or `abbreviations.txt`. It replaces the old block, so nothing gets doubled.

## Remove

```python
DN_MODE = "remove"; exec(open(r"C:\Users\timon\Documents\DeepNotes_mobile\dn_mobile_setup.py", encoding="utf-8").read())
```

This strips the templates back and deletes the field, which needs a full sync again.

## Data

Legend text lives only in your own collection (`DN Legend` field) and never goes into this repo.
To test the JS on the PC, run `localStorage.setItem("dn_force","1")` in the card's dev tools.
