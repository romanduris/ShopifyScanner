# Shopify Opportunity Scanner

Prvý modul vytvára štatistiky a statický dashboard z overených verejných údajov
a JSON importov. Nevykonáva automatizovaný zber zo Shopify ani nevolá AI API.

## Spustenie

Python 3.10+; modul používa iba štandardnú knižnicu, bez inštalácie závislostí.

```bash
python3 1.Stats.py
python3 -m unittest discover -s tests -v
python3 -m http.server 8000 --directory HTML
```

Lokálna stránka: http://localhost:8000. `HTML/index.html` funguje aj priamo zo súboru.
Adresa po zapnutí GitHub Pages: https://romanduris.github.io/ShopifyScanner/

Na reprodukovateľný výpočet k určitému dátumu:

```bash
python3 1.Stats.py --as-of 2026-09-08
```

Predvolené cesty sa určujú podľa umiestnenia skriptu. `--root /cesta/k/projektu`
umožňuje spracovať inú sadu vstupov.

## Dáta

- `Data/Sources/market_facts.json`: publikovaná veľkosť trhu, hlavné kategórie,
  zdroje a dátum overenia. Neznáme celotrhové počty sú `null`.
- `Data/Sources/apps.json`: verzovaný obal `{"schema_version": 1, "apps": [...]}`;
  aktuálne dve skutočné, ručne vybrané aplikácie. Nejde o reprezentatívnu vzorku.
- `Data/Stats/latest.json`: kompletné vypočítané štatistiky a podkladové záznamy.
- `Data/Stats/categories.csv`: počty podľa kategórií; prázdna hodnota znamená
  nezistený počet. Súčet kategórií môže prekročiť počet unikátnych aplikácií.
- `Data/Stats/history/`: snímka pri zmene zdrojových údajov. Rovnaké vstupy
  nevytvoria ďalšiu snímku ani predstieraný denný rast.
- `HTML/`: stránka, vlastné CSS a kópie JSON/CSV pre stiahnutie z webu.

Záznam aplikácie musí mať priamu App Store URL, názov, vývojára a jeho URL,
dátum overenia, `category_ids` a `pricing_model`. Príklady obsahujú voliteľné
údaje: `rating`, `review_count`, `entry_monthly_usd`, `launched_at`,
`built_for_shopify`, zdroje kategórií, dôkazy o tíme a zverejnené príjmy.
Nezistené číselné údaje zadávaj ako `null`, nikdy ako nulu.

Podporované cenové modely: `free`, `freemium`, `paid`, `free_to_install`, `unknown`.
`entry_monthly_usd` je najnižší kladný pravidelný mesačný plán v USD; ročné,
jednorazové alebo variabilné ceny sem nepatria. Cena nepreukazuje tržby.
História rozlišuje `mrr`, `arr` a `cumulative_revenue` so zdrojom, menou,
obdobím a dátumom publikácie. Údaje z rôznych období sa nesčítavajú.

Duplicitné URL sa normalizujú (bez query parametrov a koncovej lomky); vyhrá
najnovšie meranie. Konfliktné údaje z rovnakého dňa spôsobia chybu.
Zmeny počtu recenzií za 1/7/30 dní používajú len aplikácie s meraním presne
v oboch porovnávaných dňoch. Záporná čistá zmena je platná. Zmeškané dni
sa neinterpolujú; `matched_apps` udáva pokrytie. Aktualizácia dátumu výpočtu
nemení dátum zdroja. Dátum `observed_at` zmeň iba pri novom overení.

## Publikovanie a spolupráca

Workflow `.github/workflows/pages.yml` pri pushi do `main` skontroluje syntax,
spustí testy, vytvorí HTML a publikuje iba priečinok `HTML/` cez GitHub Pages.
Najprv musí vlastník v **Settings → Pages → Build and deployment → Source**
zvoliť **GitHub Actions**. Ak Pages nie je zapnutý, workflow dokončí kontroly,
uloží HTML ako artefakt `github-pages` a nasadenie označí ako preskočené.
Po zapnutí Pages spusti workflow ručne cez **Actions → Validate and publish
dashboard → Run workflow** alebo pushni ďalšiu overenú zmenu na `main`.
Pri pull requeste vykoná kontroly bez publikovania. Denný cron zatiaľ nie je
zapnutý: nové spustenie bez nového dátového zdroja by neprinieslo nové údaje.

Po dokončení a úspešnom overení zmeny commitujeme a pushujeme na `main`
a odovzdávame overený odkaz na stránku. Osobný skill `spolupraca-sk` je uložený
mimo repozitára v `/home/codespace/.codex/skills/spolupraca-sk/SKILL.md`.

## Dostupnosť zdrojov

Shopify 8. 9. 2026 na [App Store](https://apps.shopify.com/) uvádzal viac než
16 000 aplikácií. Ide o publikovanú hranicu, nie presný súpis aktívnych aplikácií.
Presné celotrhové počty podľa kategórií ani celkové príjmy zatiaľ nie sú overené.

[Podmienky Shopify](https://www.shopify.com/legal/terms), bod 1.9, uvádzajú
obmedzenie automatizovaného prístupu a monitorovania. Pred zavedením
pravidelného zberu treba zabezpečiť zdroj s povoleným prístupom. Táto verzia
pracuje výlučne s lokálnymi vstupmi; technicky dostupná stránka ani robots.txt
samostatne nepreukazujú oprávnenie na automatizovaný zber.
