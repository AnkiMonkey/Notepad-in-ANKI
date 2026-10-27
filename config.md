**AnkiMonkey – settings**

One config with three sections: `deep_notes`, `voice`, `mobile`. Easiest is the buttons in the panels.

### `deep_notes` – the right panel

Easiest: the ⚙ Settings button in the panel, `Alt+S`, opens a window where every option is explained.

| Key | What it does |
|---|---|
| `dock_area` | `right` / `left` – panel side |
| `dock_width` | width in px (remembered automatically when `remember_width` is on) |
| `min_width` | narrowest allowed width in px |
| `width_step` | how much Narrower / Wider and their shortcuts change the width |
| `collapsed` | panel collapsed to a thin strip |
| `font_size`, `font_family` | font of your notes |
| `show_logo`, `logo_height` | AnkiMonkey logo (height in px) |
| `mode` | `text` = free scratchpad, `table` = Base / Notes table |
| `clear_after_answer` | table: Notes column emptied, Base column kept; text: emptied |
| `auto_focus` | cursor jumps into the panel when a question is shown (Space then types into the panel) |
| `hide_outside_review` | hide the panel outside review (deck list, browser) |
| `template_dir` | folder with TXT templates; empty = `user_files/templates` in the add-on |
| `auto_load_template` | load a template for every card automatically |
| `default_template` | file used when no rule, tag or deck matches |
| `tag_rules` | tag → file rules, e.g. `[{"tag": "Bones", "file": "bones_notes.txt"}]`; first match from the top wins |
| `rules_first_tag_only` | rules look only at the note's first tag (Anki sorts tags alphabetically) |
| `table_separator` | separator in the TXT for the table (default tab) |
| `table_headers` | names of the 2 columns |
| `table_template_readonly` | template column cannot be edited |
| `table_empty_rows` | number of rows when there is no template (default 10) |
| `table_numbered` | without a template, column 1 is numbered 1, 2, 3 …; Enter on the last row adds the next number |
| `table_ask_rows` | on every card without a template a **Rows?** box asks how many rows you want (number + Enter, Esc = keep current rows); offers the last number used |
| `remember_zoom` | keep the card zoom (View → Zoom, Ctrl + / Ctrl −) after restarting Anki |
| `smart_rows` | **Auto rows** (off by default, `Alt+K` or the Auto button): rows come from the card's legend in `user_files/legend_labels.json` (every point incl. 3a, 3b, 2' on its own row); points your teacher does not want get the dash |
| `smart_notes_field` | field read for `NIE: 4, 6, 8` (dash on those), `NIE: celá karta` (dash on all), `všetky` (none), or a plain list like `1, 3, 7` / `body 1-10` (dash on the rest) |
| `smart_dash` | text put into skipped rows (default `-`) |
| `check_answers` | **Check** (off by default, `Alt+J` or the Check button): Enter or a space at the end of your answer compares it with `user_files/legend_answers.json`; green = jumps to the next row (dash rows skipped), red = you stay |
| `check_ok_color`, `check_bad_color` | colours for correct / wrong (default `#55ff55` / `#ff5555`) |
| `check_dunno_words`, `check_dunno_color` | typing one of these (`?, idk, neviem, nwm, nv`) writes the correct answer in blue (`#55aaff`) straight away and moves on |
| `check_long_words`, `check_long_percent` | legend text longer than 4 words: more than 30 % of its words in your answer is enough (any order, at least half of what you typed must fit) |
| wrong answer | stays red and stays in the cell; **Enter again** or **two spaces** = "I don't know" → correct answer in blue, your try kept in the tooltip |
| `shortcut_*` | keyboard shortcuts (Alt+N, Alt+I, Alt+M, Alt+., Alt+,, Alt+S, Alt+P, Alt+W, Alt+K, Alt+J); changes apply after restart |

**Template matching** (first found wins):
0. `tag_rules`: tag `Bones` matches `Bones`, `Bones::UpperLimb`, `Bones::LowerLimb::femur` …
1. tags, most specific first: `Anatomy::scapula` → `Anatomy__scapula.txt`, then `Anatomy.txt`
2. deck: `Med::Anatomy I` → `Med__Anatomy I.txt`, then `Med.txt`
3. `default.txt`

**TXT for the table:** one line = one row. Text before the tab goes to column 1, after it (optional) to column 2.

**Typing in the panel:** Anki review keys (Enter, Space, 1–4, letters) never fire while you type in the panel. Table: **Enter** = next row (adds one at the end), **Tab** = next cell, **Esc** = cancel edit / back to the card. **Alt+P** jumps into the panel, **Alt+W** saves the Base column (or the text) as the template for this card (previous file kept as `.bak`).

**Check – what counts as correct:** the genitive attribute is optional both ways (`corpus` = `corpus vertebrae`, `foramina sacralia` = `foramina sacralia ossis sacri`; a different genitive is still wrong), abbreviations and word starts (`pr transversus`, `tub ant`), the row label typed in front (`3b pr t`), small filler words left out (a, na, do …), one typo in longer words (`corpsu vertebrae`), no diacritics needed. If the legend lists several terms (`processus …, facies …`) one of them is enough. Abbreviations that are not a word start (`tbc`, `ligg`, `mm`) come from `user_files/abbreviations.txt` (`skratka = slovo`, several meanings separated by commas; edits work from the next card).

**Data files for Auto / Check** (`user_files/`, kept on add-on updates, not shipped):
- `legend_labels.json` – `{"image_legenda.jpg": ["1", "2", "3a", "3b", …]}`
- `legend_answers.json` – `{"image_legenda.jpg": {"1": "corpus vertebrae", …}}`
- `legend_answers_full.json` (optional) – same shape with the complete legend wording; `legend_answers.json` then holds the short practical form. An answer matching either one is green, the reveal shows the short form, the tooltip the full one.
The image is found by its file name in any field of the note (e.g. the Back image).

### `voice` – the left panel (Voice · Ask).
- `enabled` – 🎤 ON/OFF (saved by the button) · `hotkey` – hold-to-talk key (`F2`)
- `note_type_prefixes` – note types where F2 works · `answer_field` – answer field for the spelling hint (`Rub`)
- `model` – `large-v3` (best) / `large-v3-turbo` (faster) / `medium` / `small` · `device` `cpu`/`cuda` · `compute_type` `int8`/`float16`
- `language` `la` · `beam_size` · `use_deck_hint` · `snap_to_vocab` + `snap_cutoff` (0–1) · `lowercase`
- `dock_width`, `ask_width`, `collapsed` (panel pushed to the side with «), `hide_outside_review`
- Ask: `ask_enabled`, `ask_prompt_path`, `ask_extra_prompts` (TXT from anywhere), `claude_path` (empty = found automatically), `claude_model` (empty = your Claude Code default)

### `mobile` – Tools → Deep Notes Mobile. `enabled` is set by the menu; `auto_refresh`; `backup_dir` (empty = Documents\DeepNotes_mobile\backup); `last_signature` internal.

Changes in this JSON apply after an Anki restart.
