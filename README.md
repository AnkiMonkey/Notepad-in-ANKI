<p align="center"><img src="logo2.png" width="200"></p>

# AnkiMonkey 🐒 – Deep Notes · Voice · Ask

One Anki add-on for studying anatomy and medical Latin. **Deep Notes** (the scratchpad panel next to the card) now comes together with Deep Notes Mobile, Latin voice input, a Latin dictionary (Ask) and type-in autofocus. Every module loads on its own, so if one fails the others keep working.

![Deep Notes](1.png)

| Module | What it does | Where |
|---|---|---|
| **Deep Notes** | Notes panel next to the card: free text or a table, TXT templates, *Auto rows* from the legend, *Check* (green / red) | right panel |
| **Deep Notes Mobile** | *Auto rows* + *Check* also on AnkiDroid / AnkiMobile | Tools → Deep Notes Mobile |
| **Voice** | Hold **F2**, say the Latin term, it gets typed for you. Whisper large-v3, 100 % offline | left panel, top |
| **Ask** | Latin dictionary both ways (SK ↔ LA): genitive, gender, declension, plural, example | left panel, bottom |
| **Type-in autofocus** | Cursor goes into the answer box by itself after every card | runs in the background |

---

## Contents

1. [Install / move to another PC](#install--move-to-another-pc)
2. [Deep Notes](#deep-notes)
3. [Voice (F2)](#voice-f2)
4. [Ask (Claude)](#ask-claude)
5. [Type-in autofocus](#type-in-autofocus)
6. [Deep Notes Mobile](#deep-notes-mobile)
7. [Settings](#settings)
8. [Privacy – what leaves your PC](#privacy--what-leaves-your-pc)
9. [Sharing the add-on safely](#sharing-the-add-on-safely)
10. [Files](#files)
11. [Troubleshooting](#troubleshooting)

---

## Install / move to another PC

* **AnkiWeb:** Tools → Add-ons → Get Add-ons → code of *Deep Notes*. Updating from the old Deep Notes keeps all your settings: they move into the `deep_notes` section by themselves.
* **From file:** Tools → Add-ons → Install from file → `ankimonkey.ankiaddon` (build it with `python build.py`).
* **Move to another PC:** close Anki, copy the whole add-on folder from `%APPDATA%\Anki2\addons21\`, start Anki. Settings (`meta.json`), templates, legends, prompts and the Whisper model come with it, so nothing has to be downloaded again.

Needs Anki 23+ (Qt6). **Voice** needs Windows + Anki 25.x/26.x (Python 3.13). The first time you switch 🎤 ON, it downloads its libraries (~90 MB, [GitHub release](https://github.com/AnkiMonkey/Notepad-in-ANKI/releases/tag/voice-libs-1), checksum checked) and the Whisper model (~3 GB). After that it works offline.

> Don't keep the old separate add-ons (Latin Voice Input, Deep Notes Mobile, Anatomia type-in autofocus) next to it. They'd add a second set of panels.

## Deep Notes

Panel on the right of the reviewer.

| Shortcut | Action |
|---|---|
| `Alt+N` | collapse / expand panel |
| `Alt+P` | jump into the panel (`Esc` = back to the card) |
| `Alt+M` | text ↔ table mode |
| `Alt+I` | import a TXT template |
| `Alt+W` | save the current Base column as the template for this card (old file kept as `.bak`) |
| `Alt+.` / `Alt+,` | wider / narrower |
| `Alt+K` | *Auto rows* on/off: rows come from the card's legend |
| `Alt+J` | *Check* on/off: Enter checks the answer, green = jump on, red = stay |
| `Alt+S` | settings window (every option explained) |

* **Templates:** `user_files/templates/`. The file name is the tag or deck with `::` replaced by `__`, e.g. `Anatomy__scapula.txt`. Tag rules (e.g. `Kosti → kosti_notes.txt`) go in Settings.
* **Check** accepts abbreviations, e.g. **SIAS / SIAI / SIPS / SIPI** for the spinae iliacae. Add more in Settings or in `user_files/abbreviations.txt`.
* Typing in the panel never triggers Anki keys (Enter, Space, 1–4).

## Voice (F2)

F2 works on the note types listed in `voice.note_type_prefixes` (default: `Anatomia-type-in-answer…`, `Anatomia-write-all-fields`). Put your own note type names there, plus your answer field in `answer_field`.

1. Start a review. The **Voice · Ask** panel is on the left.
2. 🎤 **ON** (green). The first time it downloads the libraries (~90 MB) and the model (~3 GB), after that it works offline.
3. Wait for **ready**, then **hold F2**, say the term, release.
4. The text lands:
   * type-in cards → in the answer box. Check it and press **Enter**.
   * PT cards with the Deep Notes table → in the open cell. **Enter** runs Check.
5. Wrong? Hold F2 again and the new text replaces the old one.

Why it gets anatomy Latin right: answers from your deck go to Whisper as a spelling hint, and a result ≥ 82 % similar to a known answer gets snapped to the correct spelling. The panel always shows `heard:` so you can see what really came through.

**«** in the panel header pushes the panel to the side (thin strip **» Voice · Ask**). Click the strip to bring it back.

## Ask (Claude)

Type a word (Slovak or Latin) and press **Enter**:

```
caput, -itis, n. (3. deklinácia)
= hlavica (kĺbová hlavica kosti)
pl. capita, capitum
napr. caput femoris
```

* Adjectives are shown as **jednovýchodové / dvojvýchodové / trojvýchodové** with all three forms. The example is always a full term with a noun.
* **Prompts** are plain TXT: `user_files/prompts/`, or any TXT on your PC (*Settings → Add TXT…*). **✎ TXT** edits the selected one right away.
* Placeholders: `{question}`, `{context}` (matching notes from your collection). A first line `@json` = dictionary layout.

### How it talks to Claude (no API key)

Ask uses the **Claude Code** app that is installed on your PC and logged in with your **Claude Pro** account. The add-on just runs `claude -p` in the background, a bit like typing into Claude yourself.

* One-time setup: *Settings → Install Claude Code*, then *Log in*, then *Test* (should say `✓ works`).
* Install by hand if the button gets blocked by your antivirus: download `claude.exe`, run `claude.exe install`, then `claude` and log in.
* The add-on looks for `%USERPROFILE%\.local\bin\claude.exe` (or `claude` on PATH). Another location goes in `claude_path`.

## Type-in autofocus

On note types starting with `Anatomia-type-in-answer` the cursor goes into the `#tc-in` box 150 ms and 400 ms after every question, even after you grade with the mouse. Trade-off: the Deep Notes *Rows?* box doesn't get the cursor on these cards (use `Alt+P`).

## Deep Notes Mobile

Tools → **Deep Notes Mobile → Zapnúť** writes a hidden field `DN Legend` and a small JavaScript block into the card templates. It runs only on the phone/tablet, so on the PC the cards look the same. After you change legends, abbreviations or Check colours, the tablet data updates on the next Anki start (`auto_refresh`). **Vypnúť** removes it again. Backups go to `Documents\DeepNotes_mobile\backup`.

## Settings

| Where | What |
|---|---|
| ⚙ in the Deep Notes panel / `Alt+S` | everything about Deep Notes |
| **Settings** under Ask | prompts, prompt folder, Claude Code install / login / test |
| Tools → Add-ons → AnkiMonkey → **Config** | the raw JSON with three sections: `deep_notes`, `voice`, `mobile` (explained in `config.md`) |

## Privacy – what leaves your PC

| Module | Leaves the PC? |
|---|---|
| Deep Notes, Mobile, autofocus | **No.** Only your collection and `user_files`. Mobile data travels inside your own cards via your normal AnkiWeb sync. |
| Voice | **No.** Recording and recognition run locally. Audio is never saved. Internet only once, to download the model. |
| Ask | **Yes, only what you ask:** the prompt text + your question + up to 6 short matching notes from your collection (`{context}`) go to Claude via Claude Code. Remove `{context}` from the prompt if you don't want that. |

**No secrets in the add-on.** There is no API key, token or password anywhere in the code, the config or `user_files`. The Claude login belongs to Claude Code and stays in `%USERPROFILE%\.claude`, outside the add-on, so copying or sharing the add-on never shares your Claude account. Claude Code is started in the empty folder `user_files/claude_cwd`, in print mode (`-p`), where it only answers and doesn't get permission to touch your files.

## Sharing the add-on safely

Share only the code. **Never** share these:

| Path | Why |
|---|---|
| `user_files/` | your templates, legends, abbreviations, images, prompts, error log, the 3 GB model |
| `meta.json` | your personal settings (Anki creates a new one) |
| `vendor/` | not private, just ~250 MB of libraries (downloaded again automatically) |
| `__pycache__/` | junk |

The receiver needs **their own** Claude Code + Claude login for Ask. Yours is not inside.

## Files

```
ankimonkey/
├── __init__.py        loads the modules (one failing module doesn't stop the others)
├── common.py          shared config helpers (sections)
├── deep_notes.py      Deep Notes panel
├── mobile.py          Deep Notes Mobile  + dn_mobile.js
├── voice.py           Voice panel, F2, Whisper
├── ask.py             Ask panel, prompts, Claude Code bridge
├── typein_focus.py    cursor into the answer box
├── config.json / config.md / manifest.json / logo.png / README.md
├── build.py           builds ankimonkey.ankiaddon (code only, no private files)
├── vendor/            Voice libraries, downloaded on first 🎤 ON (not in git)
└── user_files/        PRIVATE data (see user_files/README.txt)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| A panel is missing | Look at `user_files/error.log` (`module … failed to load`). |
| Two Voice panels | An old add-on is still enabled. Tools → Add-ons → disable/delete it. |
| F2 does nothing | 🎤 must be **ON**, you must be on the **question** side of a supported note type. |
| "mic error" | Windows → Privacy → Microphone → allow desktop apps. |
| Text stays white in the table | Deep Notes checks only on **Enter**. |
| Ask: "Claude Code not found" | *Settings → Install*, or set `claude_path`. |
| Ask: "not logged in" | *Settings → Log in*, log in with your Pro account, then *Test*. |
| Ask is slow the first time | The first answer takes 5–15 s while Claude Code starts. |
