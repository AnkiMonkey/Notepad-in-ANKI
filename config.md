**Deep Notes – settings**

Easiest: the ⚙ Settings button in the panel, `Alt+S`, or Tools → Add-ons → Deep Notes → Config (opens the same window, every option explained).

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
| `shortcut_*` | keyboard shortcuts (Alt+N, Alt+I, Alt+M, Alt+., Alt+,, Alt+S, Alt+P, Alt+W); changes apply after restart |

**Template matching** (first found wins):
0. `tag_rules`: tag `Bones` matches `Bones`, `Bones::UpperLimb`, `Bones::LowerLimb::femur` …
1. tags, most specific first: `Anatomy::scapula` → `Anatomy__scapula.txt`, then `Anatomy.txt`
2. deck: `Med::Anatomy I` → `Med__Anatomy I.txt`, then `Med.txt`
3. `default.txt`

**TXT for the table:** one line = one row. Text before the tab goes to column 1, after it (optional) to column 2.

**Typing in the panel:** Anki review keys (Enter, Space, 1–4, letters) never fire while you type in the panel. Table: **Enter** = next row (adds one at the end), **Tab** = next cell, **Esc** = cancel edit / back to the card. **Alt+P** jumps into the panel, **Alt+W** saves the Base column (or the text) as the template for this card (previous file kept as `.bak`).
