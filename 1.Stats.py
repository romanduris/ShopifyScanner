#!/usr/bin/env python3
"""Build market statistics from sourced JSON imports; no network access required."""

import argparse
import csv
import hashlib
import html
import io
import json
import math
import re
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
MODELS = {
    "free": "Bezplatné",
    "freemium": "Freemium",
    "paid": "Platené",
    "free_to_install": "Inštalácia zdarma · ďalšie poplatky možné",
    "unknown": "Neznámy model",
}
TEAMS = {"solo": "Sólo · tvrdenie autora", "small_team": "Malý tím · tvrdenie autora",
         "company": "Firma", "unknown": "Nezistené"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def valid_date(value, as_of):
    parsed = date.fromisoformat(value)
    if parsed > as_of:
        raise ValueError(f"Dátum {value} je po dátume výpočtu {as_of}.")
    return parsed


def safe_url(value):
    if not isinstance(value, str):
        raise ValueError("Zdroj musí byť HTTPS URL.")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError(f"Neplatná HTTPS URL: {value!r}")
    if any(char.isspace() for char in value):
        raise ValueError("URL nesmie obsahovať medzery.")
    return value


def canonical_app_url(value):
    parts = urlsplit(safe_url(value))
    slug = parts.path.strip("/")
    if parts.netloc != "apps.shopify.com" or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError(f"Očakávaná priama Shopify App Store URL: {value!r}")
    if slug in {"categories", "partners", "reviews", "search", "stories"}:
        raise ValueError("URL musí identifikovať aplikáciu.")
    return f"https://apps.shopify.com/{slug}"


def number(value, minimum=0, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Neplatné číslo: {value!r}")
    if value < minimum or (maximum is not None and value > maximum) or (integer and not isinstance(value, int)):
        raise ValueError(f"Číslo mimo povoleného rozsahu: {value!r}")


def validate_inputs(facts, records, as_of):
    if facts.get("schema_version") != 1 or records.get("schema_version") != 1:
        raise ValueError("Nepodporovaná verzia vstupov.")
    valid_date(facts["observed_at"], as_of)
    total = facts["market_total"]
    number(total["value"], integer=True)
    if total["relation"] not in {"exact", "greater_than", "at_least"}:
        raise ValueError("Neplatný typ celkového počtu.")
    safe_url(total["source_url"])
    ids = [c["id"] for c in facts["categories"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("Kategórie musia mať unikátne ID.")
    for category in facts["categories"]:
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", category["id"]):
            raise ValueError("Neplatné ID kategórie.")
        if category.get("market_count") is not None:
            number(category["market_count"], integer=True)
            safe_url(category["source_url"])
            valid_date(category["observed_at"], as_of)
    unique = {}
    for original in records["apps"]:
        app = dict(original)
        app["url"] = canonical_app_url(app["url"])
        valid_date(app["observed_at"], as_of)
        if app.get("launched_at"):
            valid_date(app["launched_at"], date.fromisoformat(app["observed_at"]))
        if not app["name"].strip() or not app["developer"].strip():
            raise ValueError("Chýba názov alebo vývojár.")
        safe_url(app["developer_url"])
        if not set(app["category_ids"]).issubset(ids):
            raise ValueError(f"Neznáma kategória: {app['name']}")
        app["category_ids"] = sorted(set(app["category_ids"]))
        for source in app.get("category_source_urls", []):
            safe_url(source)
        if app.get("review_count") is not None:
            number(app["review_count"], integer=True)
        if app.get("rating") is not None:
            number(app["rating"], minimum=1, maximum=5)
            if app.get("review_count") == 0:
                raise ValueError("Aplikácia bez recenzií musí mať rating null.")
        if app["pricing_model"] not in MODELS:
            raise ValueError("Neplatný cenový model.")
        if app.get("entry_monthly_usd") is not None:
            number(app["entry_monthly_usd"], minimum=0.01)
            if app["pricing_model"] == "free":
                raise ValueError("Bezplatná aplikácia nemôže mať platenú vstupnú cenu.")
        if app.get("built_for_shopify") is not None and not isinstance(app["built_for_shopify"], bool):
            raise ValueError("built_for_shopify musí byť boolean alebo null.")
        team = app.get("team", {"status": "unknown"})
        if team["status"] not in TEAMS:
            raise ValueError("Neplatný stav tímu.")
        if team["status"] != "unknown":
            safe_url(team["source_url"])
            if team["status"] in {"solo", "small_team"} and team.get("evidence_type") != "developer_statement":
                raise ValueError("Sólo alebo malý tím vyžaduje priame vyjadrenie vývojára.")
            if team.get("statement_date"):
                valid_date(team["statement_date"], as_of)
        for revenue in app.get("revenue_disclosures", []):
            if revenue["kind"] not in {"cumulative_revenue", "mrr", "arr"}:
                raise ValueError("Neplatný typ zverejnených príjmov.")
            number(revenue["amount"])
            safe_url(revenue["source_url"])
            valid_date(revenue["published_at"], as_of)
            if not re.fullmatch(r"[A-Z]{3}", revenue["currency"]) or not revenue["period_label"].strip():
                raise ValueError("Príjem musí mať menu a obdobie.")
        old = unique.get(app["url"])
        if old and old["observed_at"] == app["observed_at"] and old != app:
            raise ValueError(f"Konfliktné záznamy v rovnaký deň: {app['url']}")
        if not old or app["observed_at"] > old["observed_at"]:
            unique[app["url"]] = app
    return sorted(unique.values(), key=lambda app: app["url"])


def has_paid_plan(app):
    return app["pricing_model"] in {"paid", "freemium"} or app.get("entry_monthly_usd") is not None


def summarize(facts, apps, as_of):
    prices = [a["entry_monthly_usd"] for a in apps if a.get("entry_monthly_usd") is not None]
    reviews = [a["review_count"] for a in apps if a.get("review_count") is not None]
    ratings = [a["rating"] for a in apps if a.get("rating") is not None]
    launches = [date.fromisoformat(a["launched_at"]) for a in apps if a.get("launched_at")]
    models = Counter(a["pricing_model"] for a in apps)
    categories = []
    for category in facts["categories"]:
        members = [a for a in apps if category["id"] in a["category_ids"]]
        counts = sorted([a["review_count"] for a in members if a.get("review_count") is not None], reverse=True)
        categories.append({**category, "sample_count": len(members),
                           "paid_plan_count": sum(has_paid_plan(a) for a in members),
                           "reviews_known_count": len(counts),
                           "top3_review_share": round(sum(counts[:3]) / sum(counts), 4) if sum(counts) else None})
    disclosures = [{**r, "app_name": a["name"], "app_url": a["url"]}
                   for a in apps for r in a.get("revenue_disclosures", [])]
    return {
        "schema_version": 1, "as_of": as_of.isoformat(),
        "market": {**facts["market_total"], "observed_at": facts["observed_at"],
                   "earning_apps": None, "total_mrr_usd": None},
        "scope": "curated_sample", "sample_size": len(apps),
        "oldest_app_observation": min((a["observed_at"] for a in apps), default=None),
        "newest_app_observation": max((a["observed_at"] for a in apps), default=None),
        "pricing_models": {key: models[key] for key in MODELS},
        "paid_plan_count": sum(has_paid_plan(a) for a in apps),
        "entry_monthly_usd_median": round(statistics.median(prices), 2) if prices else None,
        "price_sample_size": len(prices),
        "review_count_total": sum(reviews) if reviews else None,
        "reviews_known_count": len(reviews), "zero_reviews_count": reviews.count(0),
        "rating_median": statistics.median(ratings) if ratings else None, "ratings_known_count": len(ratings),
        "review_bands": {"0": sum(n == 0 for n in reviews), "1–9": sum(1 <= n < 10 for n in reviews),
                         "10–99": sum(10 <= n < 100 for n in reviews), "100–999": sum(100 <= n < 1000 for n in reviews),
                         "1 000+": sum(n >= 1000 for n in reviews), "Nezistené": len(apps) - len(reviews)},
        "new_30d": sum(0 <= (as_of - d).days < 30 for d in launches),
        "new_90d": sum(0 <= (as_of - d).days < 90 for d in launches), "launches_known_count": len(launches),
        "developer_count": len({a["developer_url"].rstrip('/') for a in apps}),
        "solo_claim_count": sum(a.get("team", {}).get("status") == "solo" for a in apps),
        "built_for_shopify_count": sum(a.get("built_for_shopify") is True for a in apps),
        "bfs_known_count": sum(a.get("built_for_shopify") is not None for a in apps),
        "revenue_disclosed_apps": sum(bool(a.get("revenue_disclosures")) for a in apps),
        "revenue_disclosures": disclosures, "categories": categories, "apps": apps,
        "limitations": ["Vzorka nie je reprezentatívna pre celý trh.",
                        "Aplikácie môžu patriť do viacerých kategórií; počty sa nesčítavajú.",
                        "Platený plán nepreukazuje príjmy ani zisk.",
                        "Historické vyjadrenia o tíme nemusia opisovať dnešný stav.",
                        "Opakované spracovanie rovnakých vstupov nie je nové meranie trhu."]}


def review_deltas(apps, history, as_of):
    result = {}
    for days in (1, 7, 30):
        target = (as_of - timedelta(days=days)).isoformat()
        prior = {}
        for snapshot in history:
            for app in snapshot.get("apps", []):
                if app["observed_at"] == target and app.get("review_count") is not None:
                    if app["url"] in prior and prior[app["url"]] != app["review_count"]:
                        raise ValueError("História obsahuje konfliktné merania recenzií.")
                    prior[app["url"]] = app["review_count"]
        pairs = [a["review_count"] - prior[a["url"]] for a in apps
                 if a["observed_at"] == as_of.isoformat() and a.get("review_count") is not None and a["url"] in prior]
        result[str(days)] = {"net_change": sum(pairs) if pairs else None, "matched_apps": len(pairs)}
    return result


def esc(value):
    return html.escape(str(value), quote=True)


def fmt(value, decimals=0):
    return "—" if value is None else f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def money(value):
    return "—" if value is None else f"${fmt(value, 2)}"


def link(url, label):
    return f'<a href="{esc(safe_url(url))}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'


def render_dashboard(stats):
    s = stats
    n = s["sample_size"]
    total = fmt(s["market"]["value"]) + ({"greater_than": "+", "at_least": "+", "exact": ""}[s["market"]["relation"]])
    total_note = {"greater_than": "viac než · údaj Shopify", "at_least": "aspoň · údaj zdroja", "exact": "presný počet podľa zdroja"}[s["market"]["relation"]]
    def card(label, value, note, primary=False):
        return f'<article class="stat-card{" primary" if primary else ""}"><span class="stat-label">{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>'
    cards = card("Aplikácie na trhu", total, total_note, True)
    cards += card("Hlavné kategórie", len(s["categories"]), "taxonómia Shopify")
    cards += card("Analyzované aplikácie", n, "ručne overená vzorka")
    cards += card("S plateným plánom", s["paid_plan_count"], f"z {n} aplikácií vo vzorke")
    cards += card("Vývojári vo vzorke", s["developer_count"], "unikátni vydavatelia")
    cards += card("Príjmy celého trhu", "Nezistené", "MRR ani počet zarábajúcich")
    category_rows = ""
    max_sample = max((c["sample_count"] for c in s["categories"]), default=0)
    for c in s["categories"]:
        width = 100 * c["sample_count"] / max_sample if max_sample else 0
        market_count = "Nezistené" if c.get("market_count") is None else link(c["source_url"], fmt(c["market_count"]))
        category_rows += f'<tr><td><strong>{link("https://apps.shopify.com/categories/" + c["id"], c["name"])}</strong><small>{esc(c["name_en"])}</small></td><td class="muted">{market_count}</td><td><div class="bar-cell"><span class="bar-track"><span style="width:{width:.2f}%"></span></span><b>{c["sample_count"]}</b></div></td><td class="numeric">{c["paid_plan_count"]}</td></tr>'
    price_rows = ""
    for model, label in MODELS.items():
        count = s["pricing_models"][model]
        percent = 100 * count / n if n else None
        price_rows += f'<div class="distribution-row"><span>{esc(label)}</span><b>{count}</b><small>{fmt(percent)} %</small></div>'
    more_cards = card("Vstupný platený plán", money(s["entry_monthly_usd_median"]), f"medián / mesiac · {s['price_sample_size']} známych cien")
    more_cards += card("Bez recenzií", f"{s['zero_reviews_count']} / {s['reviews_known_count']}", "z aplikácií so známym počtom")
    more_cards += card("Nové za 30 / 90 dní", f"{s['new_30d']} / {s['new_90d']}", f"{s['launches_known_count']} známych dátumov uvedenia")
    more_cards += card("Doložený sólo vývoj", s["solo_claim_count"], "historické tvrdenia autorov")
    more_cards += card("Built for Shopify", f"{s['built_for_shopify_count']} / {s['bfs_known_count']}", "zo známych stavov vo vzorke")
    more_cards += card("Medián hodnotenia", fmt(s["rating_median"], 2), f"{s['ratings_known_count']} hodnotených aplikácií")
    app_rows = ""
    for app in s["apps"]:
        team = app.get("team", {"status": "unknown"})
        team_label = TEAMS[team["status"]]
        team_text = link(team["source_url"], team_label) if team.get("source_url") else esc(team_label)
        team_date = team.get("statement_date") or "dátum tvrdenia nezistený"
        app_rows += f'<tr><td><strong>{link(app["url"], app["name"])}</strong><small>{esc(app["developer"])}</small></td><td><span class="badge">{esc(MODELS[app["pricing_model"]])}</span></td><td class="numeric">{money(app.get("entry_monthly_usd"))}</td><td class="numeric">{fmt(app.get("rating"), 1)}</td><td class="numeric">{fmt(app.get("review_count"))}</td><td>{team_text}<small>{esc(team_date)}</small></td><td>{esc(app["observed_at"])}</td></tr>'
    if not app_rows:
        app_rows = '<tr><td colspan="7" class="empty">Zatiaľ nie sú importované žiadne aplikácie.</td></tr>'
    revenue_rows = ""
    revenue_labels = {"cumulative_revenue": "Celkové príjmy za obdobie", "mrr": "MRR k dátumu zdroja", "arr": "ARR k dátumu zdroja"}
    for r in s["revenue_disclosures"]:
        revenue_rows += f'<tr><td><strong>{esc(r["app_name"])}</strong><small>{esc(r["period_label"])}</small></td><td><strong>{fmt(r["amount"], 2)} {esc(r["currency"])}</strong><small>{esc(revenue_labels[r["kind"]])}</small></td><td>{link(r["source_url"], r["published_at"])}</td></tr>'
    if not revenue_rows:
        revenue_rows = '<tr><td colspan="3" class="empty">Zatiaľ nemáme doložené vyjadrenia o príjmoch.</td></tr>'
    histogram = "".join(f'<div class="distribution-row"><span>{esc(band)} recenzií</span><b>{count}</b><small>aplikácií</small></div>' for band, count in s["review_bands"].items())
    delta_cards = ""
    for days, delta in s["review_deltas"].items():
        value = fmt(delta["net_change"])
        if delta["net_change"] is not None and delta["net_change"] > 0:
            value = "+" + value
        delta_cards += f'<div class="trend-stat"><span>{days} dní</span><strong>{value}</strong><small>{delta["matched_apps"]} porovnateľných aplikácií</small></div>'
    source_items = "".join(f'<li>{esc(note)}</li>' for note in s["limitations"])
    category_sources = "".join(f'<li>{esc(a["name"])}: {" · ".join(link(u, "Kategória") for u in a.get("category_source_urls", []))}</li>' for a in s["apps"])
    return f'''<!doctype html>
<html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Shopify Opportunity Scanner: prehľad trhu, cenových modelov a overených údajov o aplikáciách.">
<title>Shopify Opportunity Scanner · Prehľad trhu</title><link rel="stylesheet" href="assets/styles.css"></head>
<body><header class="topbar"><a class="brand" href="#"><span class="brand-mark" aria-hidden="true">S</span><span>SHOPIFY<span class="brand-accent">SCANNER</span></span></a><nav aria-label="Navigácia"><a class="active" href="#market">Prehľad trhu</a><a href="#apps">Aplikácie</a><a href="#sources">Zdroje</a></nav><span class="scan-status"><i aria-hidden="true"></i>Údaje trhu: {esc(s['market']['observed_at'])}</span></header>
<main><section id="market" class="intro"><div><span class="eyebrow">SHOPIFY OPPORTUNITY SCANNER</span><h1>Prehľad trhu</h1><p>Od prehľadu ekosystému k príležitosti pre jedného vývojára.</p></div><span class="status-pill">Prvá vzorka · {n} aplikácie</span></section>
<section class="summary-grid" aria-label="Hlavné štatistiky">{cards}</section>
<p class="context-note"><span class="info-dot">i</span> Veľkosť trhu je údaj Shopify. Cenové modely, hodnotenia a tímy opisujú iba našu vzorku. {link(s['market']['source_url'], 'Zdroj celkového počtu')}</p>
<div class="two-columns"><section class="panel categories"><div class="section-header"><div><span class="eyebrow">MAPA TRHU</span><h2>Aplikácie podľa kategórie</h2></div><span class="badge neutral">{len(s['categories'])} hlavných kategórií</span></div><div class="table-scroll"><table><thead><tr><th>Kategória</th><th>Celý trh</th><th>Naša vzorka</th><th class="numeric">Platený plán*</th></tr></thead><tbody>{category_rows}</tbody></table></div><p class="panel-note">* Vo vzorke. Jedna aplikácia môže patriť do viacerých kategórií. Nezistený počet nie je nula.</p></section>
<section class="panel"><div class="section-header"><div><span class="eyebrow">MONETIZÁCIA</span><h2>Cenové modely</h2></div><span class="badge neutral">Vzorka: {n}</span></div><div class="panel-body"><div class="pricing-highlight"><strong>{s['paid_plan_count']}<span> / {n}</span></strong><div><b>Aplikácie s plateným plánom</b><small>Údaj o ponuke, nie o platiacich zákazníkoch.</small></div></div>{price_rows}</div></section></div>
<div class="subheading"><span class="eyebrow">BLIŽŠÍ POHĽAD</span><h2>Čo vieme o analyzovaných aplikáciách</h2></div><section class="summary-grid secondary" aria-label="Štatistiky vzorky">{more_cards}</section>
<div class="two-columns equal"><section class="panel"><div class="section-header"><div><span class="eyebrow">PRÍJMY</span><h2>Verejne zverejnené údaje</h2></div><span class="badge neutral">{s['revenue_disclosed_apps']} aplikácia s údajmi</span></div><div class="table-scroll"><table><thead><tr><th>Aplikácia / obdobie</th><th>Príjmy</th><th>Zdroj publikovaný</th></tr></thead><tbody>{revenue_rows}</tbody></table></div><p class="panel-note">Tvrdenia autorov bez nezávislého auditu. Historické príjmy nesčítavame do aktuálneho MRR; nejde o zisk.</p></section>
<section class="panel"><div class="section-header"><div><span class="eyebrow">MOMENTUM</span><h2>Zmena počtu recenzií</h2></div><span class="badge neutral">Vlastné merania</span></div><div class="trends">{delta_cards}</div><p class="panel-note">Čistá zmena na rovnakých aplikáciách s meraním v oboch dňoch. Môže byť záporná. Opakované spracovanie vstupov nevytvára nové meranie.</p></section></div>
<section id="apps" class="panel"><div class="section-header"><div><span class="eyebrow">PODKLADY PRE ŠTATISTIKY</span><h2>Analyzované aplikácie</h2></div><span class="badge neutral">{n} overené záznamy</span></div><div class="table-scroll"><table class="apps-table"><thead><tr><th>Aplikácia / vývojár</th><th>Cenový model</th><th class="numeric">Od / mesiac</th><th class="numeric">Hodnotenie</th><th class="numeric">Recenzie</th><th>Tím · zdroj tvrdenia</th><th>Overené</th></tr></thead><tbody>{app_rows}</tbody></table></div></section>
<div class="two-columns equal"><section class="panel"><div class="section-header"><div><span class="eyebrow">DÔKAZY POUŽÍVANIA</span><h2>Rozdelenie podľa recenzií</h2></div><span class="badge neutral">Vzorka: {n}</span></div><div class="panel-body">{histogram}</div></section>
<section class="panel next-panel"><div class="section-header"><div><span class="eyebrow">ĎALŠÍ KROK</span><h2>Od štatistík k príležitostiam</h2></div></div><div class="panel-body"><p>Najprv porovnáme úzke kategórie a doplníme aplikácie s preukázaným dopytom. Potom pridáme rast, sťažnosti obchodníkov a náročnosť vlastného MVP.</p><div class="criteria"><span>Preukázaný dopyt</span><span>Jednoduchý vývoj</span><span>Cloudflare</span><span>Automatické testy</span></div><small>Poradie príležitostí pribudne po získaní dostatočných podkladov.</small></div></section></div>
<details id="sources" class="panel sources"><summary>Zdroje, metodika a pokrytie dát <span>Rozbaliť podrobnosti</span></summary><div class="panel-body"><p>Výpočet k dátumu: <b>{esc(s['as_of'])}</b>. Údaje o aplikáciách: <b>{esc(s['oldest_app_observation'] or 'nezistené')} – {esc(s['newest_app_observation'] or 'nezistené')}</b>. Počet odlišných snímok vstupov: <b>{s['snapshot_count']}</b>.</p><ul>{source_items}</ul><p>Medián cien zahŕňa iba známe kladné mesačné vstupné ceny v USD. Ročné, jednorazové a variabilné ceny neprepočítavame. Medián hodnotení nie je vážený počtom recenzií. Nové aplikácie sú aplikácie uvedené v posledných 30 alebo 90 kalendárnych dňoch vrátane dátumu výpočtu.</p><p>Počet vývojárov používame podľa URL vydavateľa; nepredstavuje počet jednotlivých programátorov. Podiel recenzií top 3 aplikácií v kategórii je dostupný v JSON/CSV a opisuje len vzorku, nie trhový podiel.</p><p>Zdroje kategorizácie:</p><ul>{category_sources}</ul><p>Vstupy boli overené pri prieskume alebo importované. Automatizovaný zber zo Shopify nie je aktívny; {link('https://www.shopify.com/legal/terms', 'podmienky prístupu, bod 1.9')}.</p><p><a href="data/stats.json" download>Stiahnuť štatistiky JSON ↓</a> · <a href="data/categories.csv" download>Stiahnuť kategórie CSV ↓</a></p></div></details>
</main><footer><span>Shopify Opportunity Scanner · Nezávislý výskumný projekt</span><span>Verejné zdroje · Doložené údaje · Transparentné odhady</span></footer></body></html>'''


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content.encode("utf-8"):
        return
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def csv_text(categories):
    output = io.StringIO(newline="")
    fields = ["id", "name", "market_count", "sample_count", "paid_plan_count", "reviews_known_count", "top3_review_share"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for category in categories:
        row = dict(category)
        for key in fields:
            if isinstance(row.get(key), str) and row[key].startswith(("=", "+", "-", "@", "\t", "\r")):
                row[key] = "'" + row[key]
        writer.writerow(row)
    return output.getvalue()


def build(root, as_of):
    facts = read_json(root / "Data/Sources/market_facts.json")
    records = read_json(root / "Data/Sources/apps.json")
    apps = validate_inputs(facts, records, as_of)
    digest = hashlib.sha256(encode_json({"facts": facts, "apps": apps}).encode()).hexdigest()
    history_dir = root / "Data/Stats/history"
    history = [read_json(path) for path in sorted(history_dir.glob("*.json"))]
    stats = summarize(facts, apps, as_of)
    stats["source_fingerprint"] = digest
    stats["review_deltas"] = review_deltas(apps, history, as_of)
    new_snapshot = not any(h.get("source_fingerprint") == digest for h in history)
    stats["snapshot_count"] = len(history) + int(new_snapshot)
    page = render_dashboard(stats)
    json_output = encode_json(stats)
    category_csv = csv_text(stats["categories"])
    # All validation, calculations and rendering complete before writing outputs.
    if new_snapshot:
        write_text(history_dir / f"{as_of.isoformat()}-{digest[:12]}.json", json_output)
    write_text(root / "Data/Stats/latest.json", json_output)
    write_text(root / "Data/Stats/categories.csv", category_csv)
    write_text(root / "HTML/index.html", page)
    write_text(root / "HTML/data/stats.json", json_output)
    write_text(root / "HTML/data/categories.csv", category_csv)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Koreň projektu (predvolene umiestnenie skriptu).")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="Dátum výpočtu YYYY-MM-DD.")
    args = parser.parse_args()
    try:
        stats = build(args.root.resolve(), args.as_of)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        print(f"Chyba vstupov alebo výstupu: {exc}", file=sys.stderr)
        return 1
    print(f"Hotovo: {stats['sample_size']} aplikácie, {len(stats['categories'])} kategórií. HTML: {args.root / 'HTML/index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
