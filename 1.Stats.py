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
    "free": "Free",
    "freemium": "Freemium",
    "paid": "Paid",
    "free_to_install": "Free to install · other charges may apply",
    "unknown": "Unknown model",
}
TEAMS = {"solo": "Solo · developer statement", "small_team": "Small team · developer statement",
         "company": "Company", "unknown": "Unknown"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def valid_date(value, as_of):
    parsed = date.fromisoformat(value)
    if parsed > as_of:
        raise ValueError(f"Date {value} is after the calculation date {as_of}.")
    return parsed


def safe_url(value):
    if not isinstance(value, str):
        raise ValueError("The source must be an HTTPS URL.")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError(f"Invalid HTTPS URL: {value!r}")
    if any(char.isspace() for char in value):
        raise ValueError("URLs must not contain whitespace.")
    return value


def canonical_app_url(value):
    parts = urlsplit(safe_url(value))
    slug = parts.path.strip("/")
    if parts.netloc != "apps.shopify.com" or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError(f"Expected a direct Shopify App Store URL: {value!r}")
    if slug in {"categories", "partners", "reviews", "search", "stories"}:
        raise ValueError("The URL must identify an app.")
    return f"https://apps.shopify.com/{slug}"


def number(value, minimum=0, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid number: {value!r}")
    if value < minimum or (maximum is not None and value > maximum) or (integer and not isinstance(value, int)):
        raise ValueError(f"Number outside the allowed range: {value!r}")


def validate_inputs(facts, records, as_of):
    if facts.get("schema_version") != 1 or records.get("schema_version") != 1:
        raise ValueError("Unsupported input schema version.")
    valid_date(facts["observed_at"], as_of)
    total = facts["market_total"]
    number(total["value"], integer=True)
    if total["relation"] not in {"exact", "greater_than", "at_least"}:
        raise ValueError("Invalid market total relation.")
    safe_url(total["source_url"])
    ids = [c["id"] for c in facts["categories"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("Categories must have unique IDs.")
    for category in facts["categories"]:
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", category["id"]):
            raise ValueError("Invalid category ID.")
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
            raise ValueError("Missing app name or developer.")
        safe_url(app["developer_url"])
        if not set(app["category_ids"]).issubset(ids):
            raise ValueError(f"Unknown category: {app['name']}")
        app["category_ids"] = sorted(set(app["category_ids"]))
        for source in app.get("category_source_urls", []):
            safe_url(source)
        if app.get("review_count") is not None:
            number(app["review_count"], integer=True)
        if app.get("rating") is not None:
            number(app["rating"], minimum=1, maximum=5)
            if app.get("review_count") == 0:
                raise ValueError("An app without reviews must have a null rating.")
        if app["pricing_model"] not in MODELS:
            raise ValueError("Invalid pricing model.")
        if app.get("entry_monthly_usd") is not None:
            number(app["entry_monthly_usd"], minimum=0.01)
            if app["pricing_model"] == "free":
                raise ValueError("A free app cannot have a paid entry price.")
        if app.get("built_for_shopify") is not None and not isinstance(app["built_for_shopify"], bool):
            raise ValueError("built_for_shopify must be a boolean or null.")
        team = app.get("team", {"status": "unknown"})
        if team["status"] not in TEAMS:
            raise ValueError("Invalid team status.")
        if team["status"] != "unknown":
            safe_url(team["source_url"])
            if team["status"] in {"solo", "small_team"} and team.get("evidence_type") != "developer_statement":
                raise ValueError("Solo or small-team status requires a direct developer statement.")
            if team.get("statement_date"):
                valid_date(team["statement_date"], as_of)
        for revenue in app.get("revenue_disclosures", []):
            if revenue["kind"] not in {"cumulative_revenue", "mrr", "arr"}:
                raise ValueError("Invalid revenue disclosure type.")
            number(revenue["amount"])
            safe_url(revenue["source_url"])
            valid_date(revenue["published_at"], as_of)
            if not re.fullmatch(r"[A-Z]{3}", revenue["currency"]) or not revenue["period_label"].strip():
                raise ValueError("Revenue must include a currency and a period.")
        old = unique.get(app["url"])
        if old and old["observed_at"] == app["observed_at"] and old != app:
            raise ValueError(f"Conflicting records on the same date: {app['url']}")
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
                         "1,000+": sum(n >= 1000 for n in reviews), "Unknown": len(apps) - len(reviews)},
        "new_30d": sum(0 <= (as_of - d).days < 30 for d in launches),
        "new_90d": sum(0 <= (as_of - d).days < 90 for d in launches), "launches_known_count": len(launches),
        "developer_count": len({a["developer_url"].rstrip('/') for a in apps}),
        "solo_claim_count": sum(a.get("team", {}).get("status") == "solo" for a in apps),
        "built_for_shopify_count": sum(a.get("built_for_shopify") is True for a in apps),
        "bfs_known_count": sum(a.get("built_for_shopify") is not None for a in apps),
        "revenue_disclosed_apps": sum(bool(a.get("revenue_disclosures")) for a in apps),
        "revenue_disclosures": disclosures, "categories": categories, "apps": apps,
        "limitations": ["The sample is not representative of the entire market.",
                        "Apps can belong to multiple categories; category counts are not additive.",
                        "A paid plan does not establish revenue or profit.",
                        "Historical team statements may not reflect the current team.",
                        "Processing the same inputs again is not a new market observation."]}


def review_deltas(apps, history, as_of):
    result = {}
    for days in (1, 7, 30):
        target = (as_of - timedelta(days=days)).isoformat()
        prior = {}
        for snapshot in history:
            for app in snapshot.get("apps", []):
                if app["observed_at"] == target and app.get("review_count") is not None:
                    if app["url"] in prior and prior[app["url"]] != app["review_count"]:
                        raise ValueError("History contains conflicting review observations.")
                    prior[app["url"]] = app["review_count"]
        pairs = [a["review_count"] - prior[a["url"]] for a in apps
                 if a["observed_at"] == as_of.isoformat() and a.get("review_count") is not None and a["url"] in prior]
        result[str(days)] = {"net_change": sum(pairs) if pairs else None, "matched_apps": len(pairs)}
    return result


def esc(value):
    return html.escape(str(value), quote=True)


def fmt(value, decimals=0):
    return "—" if value is None else f"{value:,.{decimals}f}"


def money(value):
    return "—" if value is None else f"${fmt(value, 2)}"


def link(url, label):
    return f'<a href="{esc(safe_url(url))}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'


def render_dashboard(stats):
    s = stats
    n = s["sample_size"]
    total = fmt(s["market"]["value"]) + ({"greater_than": "+", "at_least": "+", "exact": ""}[s["market"]["relation"]])
    total_note = {"greater_than": "more than · reported by Shopify", "at_least": "at least · reported by source", "exact": "exact count reported by source"}[s["market"]["relation"]]
    def card(label, value, note, primary=False):
        return f'<article class="stat-card{" primary" if primary else ""}"><span class="stat-label">{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>'
    cards = card("Apps in the marketplace", total, total_note, True)
    cards += card("Main categories", len(s["categories"]), "Shopify taxonomy")
    cards += card("Analyzed apps", n, "manually verified sample")
    cards += card("With a paid plan", s["paid_plan_count"], f"out of {n} sampled apps")
    cards += card("Developers in sample", s["developer_count"], "unique publishers")
    cards += card("Market-wide revenue", "Unknown", "MRR and earning app count unknown")
    category_rows = ""
    max_sample = max((c["sample_count"] for c in s["categories"]), default=0)
    for c in s["categories"]:
        width = 100 * c["sample_count"] / max_sample if max_sample else 0
        market_count = "Unknown" if c.get("market_count") is None else link(c["source_url"], fmt(c["market_count"]))
        category_rows += f'<tr><td><strong>{link("https://apps.shopify.com/categories/" + c["id"], c["name"])}</strong></td><td class="muted">{market_count}</td><td><div class="bar-cell"><span class="bar-track"><span style="width:{width:.2f}%"></span></span><b>{c["sample_count"]}</b></div></td><td class="numeric">{c["paid_plan_count"]}</td></tr>'
    price_rows = ""
    for model, label in MODELS.items():
        count = s["pricing_models"][model]
        percent = 100 * count / n if n else None
        price_rows += f'<div class="distribution-row"><span>{esc(label)}</span><b>{count}</b><small>{fmt(percent)} %</small></div>'
    more_cards = card("Entry paid plan", money(s["entry_monthly_usd_median"]), f"median / month · {s['price_sample_size']} known prices")
    more_cards += card("Without reviews", f"{s['zero_reviews_count']} / {s['reviews_known_count']}", "among apps with known counts")
    more_cards += card("New in 30 / 90 days", f"{s['new_30d']} / {s['new_90d']}", f"{s['launches_known_count']} known launch dates")
    more_cards += card("Documented solo development", s["solo_claim_count"], "historical developer statements")
    more_cards += card("Built for Shopify", f"{s['built_for_shopify_count']} / {s['bfs_known_count']}", "among known statuses in sample")
    more_cards += card("Median rating", fmt(s["rating_median"], 2), f"{s['ratings_known_count']} rated apps")
    app_rows = ""
    for app in s["apps"]:
        team = app.get("team", {"status": "unknown"})
        team_label = TEAMS[team["status"]]
        team_text = link(team["source_url"], team_label) if team.get("source_url") else esc(team_label)
        team_date = team.get("statement_date") or "statement date unknown"
        app_rows += f'<tr><td><strong>{link(app["url"], app["name"])}</strong><small>{esc(app["developer"])}</small></td><td><span class="badge">{esc(MODELS[app["pricing_model"]])}</span></td><td class="numeric">{money(app.get("entry_monthly_usd"))}</td><td class="numeric">{fmt(app.get("rating"), 1)}</td><td class="numeric">{fmt(app.get("review_count"))}</td><td>{team_text}<small>{esc(team_date)}</small></td><td>{esc(app["observed_at"])}</td></tr>'
    if not app_rows:
        app_rows = '<tr><td colspan="7" class="empty">No apps have been imported yet.</td></tr>'
    revenue_rows = ""
    revenue_labels = {"cumulative_revenue": "Total revenue for the period", "mrr": "MRR as of the source date", "arr": "ARR as of the source date"}
    for r in s["revenue_disclosures"]:
        revenue_rows += f'<tr><td><strong>{esc(r["app_name"])}</strong><small>{esc(r["period_label"])}</small></td><td><strong>{fmt(r["amount"], 2)} {esc(r["currency"])}</strong><small>{esc(revenue_labels[r["kind"]])}</small></td><td>{link(r["source_url"], r["published_at"])}</td></tr>'
    if not revenue_rows:
        revenue_rows = '<tr><td colspan="3" class="empty">No sourced revenue disclosures are available yet.</td></tr>'
    histogram = "".join(f'<div class="distribution-row"><span>{esc(band)} reviews</span><b>{count}</b><small>apps</small></div>' for band, count in s["review_bands"].items())
    delta_cards = ""
    for days, delta in s["review_deltas"].items():
        value = fmt(delta["net_change"])
        if delta["net_change"] is not None and delta["net_change"] > 0:
            value = "+" + value
        day_label = "day" if days == "1" else "days"
        delta_cards += f'<div class="trend-stat"><span>{days} {day_label}</span><strong>{value}</strong><small>{delta["matched_apps"]} matched apps</small></div>'
    source_items = "".join(f'<li>{esc(note)}</li>' for note in s["limitations"])
    category_sources = "".join(f'<li>{esc(a["name"])}: {" · ".join(link(u, "Category") for u in a.get("category_source_urls", []))}</li>' for a in s["apps"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Shopify Opportunity Scanner: market overview, pricing models and verified app data.">
<title>Shopify Opportunity Scanner · Market overview</title><link rel="stylesheet" href="assets/styles.css"></head>
<body><header class="topbar"><a class="brand" href="#"><span class="brand-mark" aria-hidden="true">S</span><span>SHOPIFY<span class="brand-accent">SCANNER</span></span></a><nav aria-label="Navigation"><a class="active" href="#market">Market overview</a><a href="#apps">Apps</a><a href="#sources">Sources</a></nav><span class="scan-status"><i aria-hidden="true"></i>Market data: {esc(s['market']['observed_at'])}</span></header>
<main><section id="market" class="intro"><div><span class="eyebrow">SHOPIFY OPPORTUNITY SCANNER</span><h1>Market overview</h1><p>From ecosystem insights to opportunities for a solo developer.</p></div><span class="status-pill">Initial sample · {n} apps</span></section>
<section class="summary-grid" aria-label="Key statistics">{cards}</section>
<p class="context-note"><span class="info-dot">i</span> Market size is reported by Shopify. Pricing, ratings and teams describe our sample only. {link(s['market']['source_url'], 'Market size source')}</p>
<div class="two-columns"><section class="panel categories"><div class="section-header"><div><span class="eyebrow">MARKET MAP</span><h2>Apps by category</h2></div><span class="badge neutral">{len(s['categories'])} main categories</span></div><div class="table-scroll"><table><thead><tr><th>Category</th><th>Entire market</th><th>Our sample</th><th class="numeric">Paid plan*</th></tr></thead><tbody>{category_rows}</tbody></table></div><p class="panel-note">* Within the sample. An app may belong to multiple categories. An unknown count is not zero.</p></section>
<section class="panel"><div class="section-header"><div><span class="eyebrow">MONETIZATION</span><h2>Pricing models</h2></div><span class="badge neutral">Sample: {n}</span></div><div class="panel-body"><div class="pricing-highlight"><strong>{s['paid_plan_count']}<span> / {n}</span></strong><div><b>Apps with a paid plan</b><small>Plan availability, not evidence of paying customers.</small></div></div>{price_rows}</div></section></div>
<div class="subheading"><span class="eyebrow">A CLOSER LOOK</span><h2>What we know about the sampled apps</h2></div><section class="summary-grid secondary" aria-label="Sample statistics">{more_cards}</section>
<div class="two-columns equal"><section class="panel"><div class="section-header"><div><span class="eyebrow">REVENUE</span><h2>Public revenue disclosures</h2></div><span class="badge neutral">Apps with disclosures: {s['revenue_disclosed_apps']}</span></div><div class="table-scroll"><table><thead><tr><th>App / period</th><th>Revenue</th><th>Source published</th></tr></thead><tbody>{revenue_rows}</tbody></table></div><p class="panel-note">Developer statements without independent auditing. Historical revenue is not added to current MRR and does not represent profit.</p></section>
<section class="panel"><div class="section-header"><div><span class="eyebrow">MOMENTUM</span><h2>Review count change</h2></div><span class="badge neutral">Our observations</span></div><div class="trends">{delta_cards}</div><p class="panel-note">Net change for the same apps observed on both dates. It can be negative. Reprocessing inputs does not create a new observation.</p></section></div>
<section id="apps" class="panel"><div class="section-header"><div><span class="eyebrow">STATISTICS INPUTS</span><h2>Analyzed apps</h2></div><span class="badge neutral">{n} verified records</span></div><div class="table-scroll"><table class="apps-table"><thead><tr><th>App / developer</th><th>Pricing model</th><th class="numeric">From / month</th><th class="numeric">Rating</th><th class="numeric">Reviews</th><th>Team · statement source</th><th>Verified</th></tr></thead><tbody>{app_rows}</tbody></table></div></section>
<div class="two-columns equal"><section class="panel"><div class="section-header"><div><span class="eyebrow">USAGE SIGNALS</span><h2>Distribution by review count</h2></div><span class="badge neutral">Sample: {n}</span></div><div class="panel-body">{histogram}</div></section>
<section class="panel next-panel"><div class="section-header"><div><span class="eyebrow">NEXT STEP</span><h2>From statistics to opportunities</h2></div></div><div class="panel-body"><p>First, compare focused categories and add apps with demonstrated demand. Then assess growth, merchant complaints and the complexity of an independent MVP.</p><div class="criteria"><span>Proven demand</span><span>Simple implementation</span><span>Cloudflare</span><span>Automated tests</span></div><small>Opportunity rankings will follow once enough evidence is available.</small></div></section></div>
<details id="sources" class="panel sources"><summary>Sources, methodology and data coverage <span>Show details</span></summary><div class="panel-body"><p>Calculated as of: <b>{esc(s['as_of'])}</b>. App observations: <b>{esc(s['oldest_app_observation'] or 'unknown')} – {esc(s['newest_app_observation'] or 'unknown')}</b>. Distinct input snapshots: <b>{s['snapshot_count']}</b>.</p><ul>{source_items}</ul><p>The price median includes only known positive monthly entry prices in USD. Annual, one-time and usage-based prices are not converted. The rating median is not weighted by review count. New apps launched within the last 30 or 90 calendar days, including the calculation date.</p><p>Developers are counted by publisher URL, not by individual programmers. The top three apps' share of category reviews is available in JSON/CSV and describes the sample, not market share.</p><p>Category sources:</p><ul>{category_sources}</ul><p>Inputs were verified during research or imported. Automated Shopify data collection is not active; {link('https://www.shopify.com/legal/terms', 'access terms, section 1.9')}.</p><p><a href="data/stats.json" download>Download statistics JSON ↓</a> · <a href="data/categories.csv" download>Download categories CSV ↓</a></p></div></details>
</main><footer><span>Shopify Opportunity Scanner · Independent research project</span><span>Public sources · Sourced data · Transparent estimates</span></footer></body></html>'''


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
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root (defaults to the script directory).")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="Calculation date in YYYY-MM-DD format.")
    args = parser.parse_args()
    try:
        stats = build(args.root.resolve(), args.as_of)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        print(f"Input or output error: {exc}", file=sys.stderr)
        return 1
    print(f"Done: {stats['sample_size']} apps, {len(stats['categories'])} categories. HTML: {args.root / 'HTML/index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
