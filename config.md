**Deep Notes – nastavenia**

| Kľúč | Čo robí |
|---|---|
| `dock_area` | `right` / `left` – strana panela |
| `dock_width` | šírka v px (pamätá sa sama, ak `remember_width`) |
| `min_width` | najmenšia šírka v px (pôvodne natvrdo 400) |
| `width_step` | o koľko px menia šírku tlačidlá − / + a skratky |
| `collapsed` | panel zbalený do úzkeho pásika |
| `font_size`, `font_family` | písmo poznámok |
| `show_logo`, `logo_height` | logo AnkiMonkey (výška v px) |
| `mode` | `text` = voľný zápisník, `table` = tabuľka Základ / Moje |
| `clear_after_answer` | po ohodnotení karty vyčistí panel |
| `auto_focus` | po zobrazení otázky skočí kurzor do panela (pozor: potom medzerník píše do panela) |
| `hide_outside_review` | mimo opakovania (decky, browser) panel schová |
| `template_dir` | priečinok s TXT šablónami; prázdne = `user_files/templates` v add-one |
| `auto_load_template` | šablónu načíta sám pri každej karte |
| `default_template` | súbor, keď sa nenájde šablóna pre tag ani deck |
| `table_separator` | oddeľovač v TXT pre tabuľku (predvolený tabulátor) |
| `table_headers` | názvy 2 stĺpcov |
| `table_template_readonly` | stĺpec zo šablóny sa nedá prepísať |
| `table_empty_rows` | počet prázdnych riadkov, keď šablóna nie je |
| `shortcut_*` | klávesové skratky |

**Párovanie šablóny s kartou** (prvá nájdená vyhráva):
1. tagy, najšpecifickejší prvý: `Cihak::scapula` → `Cihak__scapula.txt`, potom `Cihak.txt`
2. deck: `1 PT::anatomia I` → `1 PT__anatomia I.txt`, potom `1 PT.txt`
3. `default.txt`

**TXT pre tabuľku:** jeden riadok = jeden riadok tabuľky. Text pred tabulátorom ide do stĺpca Základ, za ním (voliteľné) do stĺpca Moje.
