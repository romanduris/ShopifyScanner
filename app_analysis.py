"""Transparent, provisional app scoring and an accessible research table."""

import json
import html
import math
from datetime import date
from urllib.parse import urlsplit

WEIGHTS = {"demand": 35, "satisfaction": 15, "growth": 20, "monetization": 20, "credibility": 10}

# These profiles describe an independently built MVP, not the incumbent's stack.
# Complexity estimates are research hypotheses that still need a development-store spike.
PROFILES = {
    "barcodes": ("SKU and barcode tools", 2, "Generate product identifiers and printable labels from merchant-defined rules.", "SKU generation, collision detection and a printable label template.", "Product API access; preview changes before saving; printer layout testing.", "Strong", "Rule tests, duplicate detection and label rendering snapshots."),
    "size_charts": ("Size charts", 2, "Display reusable sizing information on product pages.", "Reusable size tables, product assignment and unit conversion.", "Theme app extension; configuration storage; theme compatibility.", "Strong", "Unit conversion, assignment rules and storefront rendering."),
    "terms": ("Terms acceptance", 2, "Request customer acknowledgement before checkout.", "Configurable terms checkbox and an order acknowledgement record.", "Theme integration; checkout-path coverage; no promise of legal compliance.", "Strong", "Checkbox behavior and all supported paths to checkout."),
    "badges": ("Trust badges", 1, "Display configured trust or payment icons on the storefront.", "A theme extension with an icon library and placement settings.", "Theme compatibility; use only properly licensed graphics.", "Strong", "Configuration persistence, responsive rendering and accessibility."),
    "currency": ("Currency display", 3, "Display product prices in a shopper-selected currency.", "Currency display using Shopify-supported pricing data.", "Markets configuration; display versus checkout currency; rounding rules.", "Conditional", "Rounding, market selection and checkout currency consistency."),
    "invoicing": ("Invoices and order documents", 3, "Generate printable documents from order data.", "A limited invoice or packing-slip template for one clearly defined workflow.", "Protected customer data; order access; PDF generation; jurisdiction-specific requirements.", "Conditional", "Document totals, taxes from Shopify data, pagination and access control."),
    "bulk_edit": ("Bulk product management", 3, "Apply changes to product data in batches.", "One type of bulk edit with a preview, audit log and recovery path.", "API limits; large catalogs; resumable jobs; accidental data changes.", "Strong", "Dry runs, idempotence, partial failure and recovery."),
    "wishlist": ("Wishlists", 3, "Save products for shoppers to revisit later.", "Storefront save buttons and a basic customer wishlist.", "Identity and guest merging; storage; privacy and deletion handling.", "Strong", "Guest-to-customer merge, isolation and storefront interactions."),
    "booking": ("Appointment booking", 4, "Reserve capacity or time slots for products and services.", "Single-calendar reservations with explicit capacity rules.", "Time zones; concurrency; overselling; cancellations; calendar dependencies.", "Conditional", "Concurrent reservations, daylight saving transitions and cancellation races."),
    "page_builder": ("Page and theme builders", 4, "Create storefront pages or sections through a visual editor.", "A small library of configurable theme sections instead of a full visual editor.", "Theme compatibility; editor state; asset handling; performance and support.", "Conditional", "Theme fixtures, visual regression and editor persistence."),
    "feeds": ("Product feeds", 4, "Export and synchronize product data with advertising or sales channels.", "A feed for one channel with validation and scheduled updates.", "External channel specifications; API changes; catalog scale; synchronization.", "Conditional", "Feed fixtures, field mapping, retries and incremental updates."),
    "marketplaces": ("Marketplace integrations", 5, "Synchronize listings, inventory and orders with external marketplaces.", "One narrow integration; validate partner access before development.", "Multiple external APIs; inventory conflicts; order correctness; ongoing support.", "Weak", "Partner sandboxes, synchronization conflicts and duplicate event handling."),
    "dropshipping": ("Sourcing and dropshipping", 5, "Source products and coordinate fulfillment with suppliers.", "A limited supplier integration, subject to supplier API access.", "Supplier networks; external APIs; stock changes; fulfillment disputes.", "Weak", "Supplier sandbox tests, stock reconciliation and fulfillment failures."),
    "print_on_demand": ("Print on demand", 5, "Connect personalized products to manufacturing and fulfillment.", "A narrow connector to an existing fulfillment provider.", "Manufacturing dependencies; artwork processing; shipping and support.", "Weak", "Provider integration, artwork validation and order lifecycle tests."),
    "wholesale": ("B2B and wholesale", 4, "Offer customer-specific catalog access and wholesale pricing.", "One access or pricing rule for a defined merchant segment.", "B2B plan restrictions; customer identity; price correctness; checkout constraints.", "Conditional", "Customer permissions, price rules and supported Shopify plans."),
    "subscriptions": ("Subscriptions and memberships", 5, "Manage recurring purchases or membership billing.", "A narrow subscription workflow after validating platform eligibility.", "Subscription APIs; payment lifecycle; migrations; cancellations and billing support.", "Weak", "Billing lifecycle, payment failures and subscription migrations."),
    "product_options": ("Product options and personalization", 3, "Collect product choices or customization inputs.", "Simple text and choice fields with order-line metadata.", "Variant and pricing rules; theme support; file uploads if offered.", "Strong", "Required fields, variants, cart persistence and order-line data."),
    "reviews": ("Product review platforms", 4, "Collect and publish customer product reviews.", "A narrowly scoped review display or collection workflow.", "Review imports; moderation; email delivery; spam and support.", "Conditional", "Moderation, imports, storefront rendering and email workflows."),
    "loyalty": ("Loyalty and rewards", 4, "Track customer rewards and redemption rules.", "One earning rule and one redemption workflow.", "Order events; refunds; fraud; customer identity and accounting-like balances.", "Conditional", "Ledger consistency, refunds, duplicate events and redemption races."),
    "seo": ("SEO utilities", 3, "Inspect and improve storefront metadata or structured information.", "A deterministic metadata audit and one controlled bulk correction.", "Theme compatibility; API access; avoid unsupported ranking guarantees.", "Strong", "Metadata fixtures, structured data validation and rollback."),
    "consent": ("Privacy and consent", 4, "Manage storefront tracking choices and consent records.", "A narrowly scoped consent UI integrated with supported Shopify APIs.", "Regional requirements; tracking integrations; consent correctness and evidence.", "Conditional", "Consent states, blocked tracking and regional configurations."),
    "email": ("Messaging and marketing automation", 5, "Send and automate customer marketing messages.", "One event-driven notification using an existing delivery provider.", "Deliverability; consent; external providers; automation state; support.", "Weak", "Provider integration, consent, suppression and duplicate sends."),
    "translation": ("Store translation", 4, "Translate and manage localized storefront content.", "A limited translation-management workflow for selected content types.", "Markets; theme text; external translation APIs; content synchronization.", "Conditional", "Locale fallback, content updates and translated storefront fixtures."),
    "tracking": ("Shipment tracking", 4, "Collect carrier events and display delivery progress.", "A tracking page backed by one supported provider.", "Carrier APIs; event normalization; background polling and customer notifications.", "Conditional", "Carrier fixtures, out-of-order events and delivery state transitions."),
    "shipping": ("Shipping operations", 5, "Coordinate shipping labels, rates and fulfillment workflows.", "One carrier workflow after verifying its API and billing requirements.", "Carrier contracts; label purchases; rates; fulfillment correctness.", "Weak", "Carrier sandboxes, rate calculation and label purchase retries."),
    "returns": ("Returns and cancellations", 4, "Manage return requests, exchanges or cancellation workflows.", "A request form and merchant review queue before automated financial actions.", "Order permissions; refunds; inventory; regional rules and support.", "Conditional", "Permissions, duplicate requests and refund state transitions."),
    "digital_downloads": ("Digital downloads", 3, "Deliver digital files to customers after purchase.", "Secure expiring downloads with a basic merchant file manager.", "Order webhooks; object storage; download authorization; bandwidth costs.", "Strong", "Download permissions, expiry, webhook retries and refund access."),
    "chat": ("Support and chat", 4, "Manage customer conversations or automated support.", "A limited contact widget and inbox integration.", "Messaging providers; real-time delivery; AI costs if used; personal data.", "Conditional", "Message ordering, customer isolation and provider failures."),
    "analytics": ("Session analytics", 5, "Collect and analyze shopper behavior or session recordings.", "A small aggregate event dashboard without session video capture.", "Privacy; event volume; retention; high-write storage and tracking accuracy.", "Weak", "Consent, event ingestion, aggregation and retention policies."),
    "surveys": ("Customer surveys", 2, "Collect structured feedback from shoppers.", "A short survey with response storage and CSV export.", "Extension placement eligibility; consent; response storage and export.", "Strong", "Branching questions, duplicate submissions and data export."),
    "backups": ("Store backups", 4, "Back up merchant data and restore selected records.", "A read-only export for one resource type before offering restoration.", "Data retention; bulk APIs; restoration correctness and merchant trust.", "Conditional", "Backup integrity, versioning and restoration fixtures."),
    "bundles": ("Bundles and upsells", 4, "Offer grouped products or additional purchases.", "A narrow bundle presentation using supported Shopify primitives.", "Cart and pricing constraints; inventory; discounts and checkout support.", "Conditional", "Cart combinations, inventory and discount interactions."),
    "stock_alerts": ("Preorders and stock alerts", 4, "Collect stock notifications or manage preorder availability.", "A simple interest list for out-of-stock products.", "Inventory events; notification delivery; preorder payment and fulfillment rules.", "Conditional", "Stock transitions, duplicate notifications and consent."),
    "affiliate": ("Affiliate marketing", 4, "Attribute referred orders and manage affiliate rewards.", "Basic referral attribution before automated payouts.", "Tracking accuracy; fraud; refunds; payouts and reconciliation.", "Conditional", "Attribution windows, refunds and commission consistency."),
    "order_limits": ("Order quantity rules", 3, "Apply minimum or maximum purchase quantities.", "One quantity rule with clear supported checkout paths.", "Checkout restrictions; accelerated checkout; cart rule enforcement.", "Conditional", "Boundary quantities, cart changes and checkout paths."),
    "store_locator": ("Store locators", 2, "Show retail locations with search and filtering.", "A searchable location list with an optional map.", "Map provider costs if used; geocoding; location data maintenance.", "Strong", "Distance calculations, filters and accessible list rendering."),
    "unknown": ("Unclassified workflow", None, "The primary job-to-be-done needs a focused review.", "Define a specific merchant problem before estimating an MVP.", "Platform requirements and external dependencies have not been assessed.", "Unknown", "A development-store spike is required before planning tests."),
}

# First match wins. Classification is deliberately visible as a heuristic.
RULES = [
    ("size_charts", ("size chart", "size guide")),
    ("barcodes", ("barcode", "skugen")),
    ("terms", ("terms and conditions",)),
    ("badges", ("trust badges",)),
    ("order_limits", ("order limit", "minimum order", "quantity")),
    ("invoicing", ("invoice", "order printer")),
    ("bulk_edit", ("bulk product", "matrixify", "stock sync")),
    ("store_locator", ("store locator", "mappy")),
    ("surveys", ("zigpoll",)),
    ("stock_alerts", ("preorder", "back in stock")),
    ("backups", ("backup", "duplify", "rewind")),
    ("returns", ("returns", "withdrawal", "revoq")),
    ("digital_downloads", ("digital download", "filemonk")),
    ("tracking", ("order tracking", "trackingmore", "track123")),
    ("shipping", ("shipstation", "easyship", "ezlabel", "australia post")),
    ("currency", ("currency converter",)),
    ("translation", ("translate", "langify", "gtranslate")),
    ("consent", ("gdpr", "consent", "pandectes")),
    ("seo", ("seo",)),
    ("loyalty", ("loyalty", "smile:")),
    ("reviews", ("product reviews", "judge.me")),
    ("print_on_demand", ("print on demand", "printful", "printify")),
    ("dropshipping", ("dropship", "dsers", "eprolo", "cjdrop", "syncee", "zopi")),
    ("wholesale", ("wholesale", "b2b", "collective", "faire:")),
    ("subscriptions", ("subscription", "membership", "recharge")),
    ("product_options", ("product options", "product opt", "personalizer", "swatch", "variant")),
    ("booking", ("booking", "appointment", "cowlendar")),
    ("wishlist", ("wishlist",)),
    ("page_builder", ("page builder", "theme sections", "theme access")),
    ("social_feed", ("instafeed",)),
    ("feeds", ("feed", "simprosys")),
    ("bundles", ("bundle", "upsell", "discounty")),
    ("affiliate", ("affiliate", "uppromote")),
    ("analytics", ("clarity", "replay", "heatmap")),
    ("popups", ("popconvert",)),
    ("email", ("email", "omnisend", "klaviyo", "pushowl", "whatsapp marketing", "popup", "pop up")),
    ("chat", ("chat", "gorgias", "tidio", "whatsapp")),
    ("marketplaces", ("tiktok", "facebook", "instagram", "google & youtube", "pinterest", "amazon", "litcommerce")),
]


PROFILES["social_feed"] = ("Social feed widgets", 3, "Display social content on the storefront.", "One feed widget with caching and a supported provider connection.", "External API permissions, token renewal, content rights and theme compatibility.", "Conditional", "Provider failures, token expiry, caching and storefront layout.")
PROFILES["popups"] = ("Storefront popups", 2, "Display targeted storefront messages or opt-in forms.", "One configurable popup with frequency limits and CSV export.", "Theme integration, consent, accessible dialogs and shopper state.", "Strong", "Targeting rules, keyboard access, frequency limits and export.")


def load_research(root, as_of):
    """Load optional analyst evidence; validate before generating any outputs."""
    outputs = []
    for filename, field in (("assessments.json", "apps"), ("competition.json", "groups")):
        path = root / "Data/Sources" / filename
        data = json.loads(path.read_text()) if path.exists() else {"schema_version": 1, field: {}}
        if data.get("schema_version") != 1 or not isinstance(data.get(field), dict):
            raise ValueError("Invalid research schema.")
        for key, record in data[field].items():
            def source(url):
                parts = urlsplit(url)
                if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or any(c.isspace() for c in url):
                    raise ValueError("Research sources must be HTTPS URLs.")
            if field == "apps":
                source(key)
                if record.get("group", "unknown") not in PROFILES:
                    raise ValueError("Unknown workflow profile.")
                complexity = record.get("complexity")
                if complexity is not None and (type(complexity) is not int or not 1 <= complexity <= 5):
                    raise ValueError("Complexity must be an integer from 1 to 5.")
                for complaint in record.get("complaints", []):
                    source(complaint["source_url"])
                    if not complaint["summary"].strip():
                        raise ValueError("Complaint summaries cannot be empty.")
                for url in record.get("sources", []):
                    source(url)
            else:
                if key not in PROFILES or type(record["app_count"]) is not int or record["app_count"] < 0:
                    raise ValueError("Invalid marketplace category count.")
                source(record["source_url"])
                if date.fromisoformat(record["observed_at"]) > as_of:
                    raise ValueError("Future competition observation.")
        outputs.append(data[field])
    return outputs


def classify(app):
    name = app["name"].casefold()
    return next((group for group, terms in RULES if any(term in name for term in terms)), "unknown")


def success_score(app, as_of, growth=None):
    reviews = app.get("review_count")
    rating = app.get("rating")
    price = app.get("entry_monthly_usd")
    model = app.get("pricing_model", "unknown")
    demand = min(100, 100 * math.log10(1 + reviews) / math.log10(10001)) if reviews is not None else None
    # A modest prior reduces the influence of a handful of perfect reviews.
    satisfaction = 20 * (rating * reviews + 4 * 20) / (reviews + 20) if rating is not None and reviews is not None else None
    if price is not None:
        monetization = min(100, 65 + 10 * math.log2(1 + price))
    elif model in {"paid", "freemium"}:
        monetization = 65
    elif model == "free":
        monetization = 0
    else:
        monetization = None
    credibility_parts = []
    if app.get("launched_at"):
        age = max(0, (as_of - date.fromisoformat(app["launched_at"])).days)
        credibility_parts.append((70, min(100, age / 1095 * 100)))
    if app.get("built_for_shopify") is not None:
        credibility_parts.append((30, 100 if app["built_for_shopify"] else 0))
    credibility = sum(w * value for w, value in credibility_parts) / sum(w for w, _ in credibility_parts) if credibility_parts else None
    components = {"demand": demand, "satisfaction": satisfaction, "growth": growth,
                  "monetization": monetization, "credibility": credibility}
    coverage = sum(WEIGHTS[key] for key, value in components.items() if value is not None)
    earned = sum(WEIGHTS[key] * value / 100 for key, value in components.items() if value is not None)
    return {"score": round(earned / coverage * 100, 1) if coverage else None,
            "coverage": coverage, "lower_bound": round(earned, 1),
            "upper_bound": round(earned + 100 - coverage, 1),
            "components": {key: round(value, 1) if value is not None else None for key, value in components.items()},
            "missing": [key for key, value in components.items() if value is None]}


def app_growth(app, history):
    from datetime import timedelta
    current_date = date.fromisoformat(app["observed_at"])
    for days in (30, 7):
        target = (current_date - timedelta(days=days)).isoformat()
        previous = [a for snapshot in history for a in snapshot.get("apps", [])
                    if a["url"] == app["url"] and a["observed_at"] == target and a.get("review_count") is not None]
        if previous and app.get("review_count") is not None:
            if len({a["review_count"] for a in previous}) != 1:
                raise ValueError("History contains conflicting review observations.")
            net = app["review_count"] - previous[-1]["review_count"]
            score = min(100, max(0, net / days / 2 * 100))
            return {"days": days, "net_change": net, "score": round(score, 1)}
    return None


def analyze(apps, as_of, history=None, assessments=None, competition=None):
    history, assessments, competition = history or [], assessments or {}, competition or {}
    results = []
    for app in apps:
        group = classify(app)
        profile = PROFILES[group]
        manual = assessments.get(app["url"], {})
        if manual.get("group"):
            group = manual["group"]
            profile = PROFILES[group]
        growth = app_growth(app, history)
        success = success_score(app, as_of, growth["score"] if growth else None)
        complexity = manual.get("complexity", profile[1])
        paid = app["pricing_model"] in {"paid", "freemium"} or app.get("entry_monthly_usd") is not None
        # Research priority rewards a simpler MVP, not unverified claims of incumbent weakness.
        priority = round(success["lower_bound"] * (6 - complexity) / 5 * (1 if paid else .35), 1) if complexity is not None else None
        results.append({"url": app["url"], "name": app["name"], "category_ids": app["category_ids"],
                        "group": group, "group_name": profile[0], "classification": "name-based hypothesis" if not manual.get("group") else "analyst assessment",
                        "success": success, "growth": growth, "complexity": complexity,
                        "complexity_confidence": "preliminary", "feature_summary": profile[2],
                        "proposed_mvp": manual.get("proposed_mvp", profile[3]), "technical_notes": manual.get("technical_notes", profile[4]),
                        "cloudflare_fit": profile[5], "test_plan": profile[6], "research_priority": priority,
                        "paid_plan": paid, "complaints": manual.get("complaints", []),
                        "complaint_status": manual.get("complaint_status", "Not researched; no weakness inferred."),
                        "market_competition": competition.get(group), "sources": manual.get("sources", [])})
    for result in results:
        peers = [r for r in results if r["group"] == result["group"] and r["url"] != result["url"]] if result["group"] != "unknown" else []
        result["sample_peer_count"] = len(peers) if result["group"] != "unknown" else None
        result["sample_peers"] = [{"name": p["name"], "url": p["url"]} for p in peers]
    results.sort(key=lambda r: (r["research_priority"] is not None, r["research_priority"] or 0, r["success"]["lower_bound"]), reverse=True)
    return {"schema_version": 1, "as_of": as_of.isoformat(), "weights": WEIGHTS, "apps": results,
            "methodology": "Success is a proxy, not revenue. Missing dimensions are excluded from the displayed score and shown in coverage and bounds. Research priority uses the conservative score bound, estimated MVP complexity and observed paid-plan availability. Similarity groups and complexity are hypotheses, not audits of incumbent architecture."}


def esc(value):
    return html.escape(str(value), quote=True)


def render_catalog(catalog, apps, categories):
    lookup = {a["url"]: a for a in apps}
    buttons = '<button type="button" class="category-filter active" data-category="all" aria-pressed="true">All apps <span>' + str(len(apps)) + '</span></button>'
    for c in categories:
        count = sum(c["id"] in a["category_ids"] for a in apps)
        buttons += f'<button type="button" class="category-filter" data-category="{esc(c["id"])}" aria-pressed="false">{esc(c["name"])} <span>{count}</span></button>'
    rows = ""
    for index, result in enumerate(catalog["apps"]):
        app = lookup[result["url"]]
        success = result["success"]
        score = "Unknown" if success["score"] is None else f'{success["score"]:.1f}'
        priority = "—" if result["research_priority"] is None else f'{result["research_priority"]:.1f}'
        complexity = result["complexity"]
        complexity_label = "Unknown" if complexity is None else f'{complexity} / 5'
        peer_count = "Unknown" if result["sample_peer_count"] is None else str(result["sample_peer_count"])
        price = "Unknown" if app.get("entry_monthly_usd") is None else f'${app["entry_monthly_usd"]:,.2f}'
        model_label = {"free": "Free", "freemium": "Freemium", "paid": "Paid", "free_to_install": "Free to install", "unknown": "Unknown"}[app["pricing_model"]]
        reviews = "—" if app.get("review_count") is None else f'{app["review_count"]:,}'
        rating = "—" if app.get("rating") is None else f'{app["rating"]:.1f}'
        details_id = f'app-detail-{index}'
        categories_attr = esc(" ".join(app["category_ids"]))
        search = esc(" ".join([app["name"], app.get("developer") or "", result["group_name"], result["feature_summary"]]).lower())
        rows += f'<tbody class="app-record" data-categories="{categories_attr}" data-search="{search}" data-group="{esc(result["group"])}" data-priority="{result["research_priority"] if result["research_priority"] is not None else -1}" data-success="{success["lower_bound"]}" data-complexity="{complexity if complexity is not None else 99}" data-reviews="{app.get("review_count") if app.get("review_count") is not None else -1}" data-peers="{result["sample_peer_count"] if result["sample_peer_count"] is not None else 9999}" data-paid="{str(result["paid_plan"]).lower()}"><tr class="app-summary"><td><button type="button" class="row-toggle" aria-expanded="false" aria-controls="{details_id}" aria-label="Show details for {esc(app["name"])}"><span aria-hidden="true">›</span></button></td><td><strong><a href="{esc(app["url"])}" target="_blank" rel="noopener noreferrer">{esc(app["name"])} ↗</a></strong><small>{esc(app.get("developer") or "Developer not verified")} · {esc(result["group_name"])}</small></td><td class="numeric"><b class="score-pill">{priority}</b></td><td class="numeric"><strong>{score}</strong><small>{success["coverage"]}% evidence coverage</small></td><td class="numeric"><strong>{complexity_label}</strong><small>preliminary MVP</small></td><td class="numeric">{reviews}<small>{rating} / 5 rating</small></td><td class="numeric">{price}<small>{model_label}</small></td><td class="numeric">{peer_count}<small>known sample peers</small></td><td><button class="group-filter" type="button" data-group="{esc(result["group"])}">Compare peers</button></td></tr>'
        components = "".join(f'<li><span>{key.title()} ({WEIGHTS[key]}%)</span><b>{"Unknown" if value is None else f"{value:.1f} / 100"}</b></li>' for key, value in success["components"].items())
        integrations = app.get("integrations")
        integration_text = ", ".join(integrations) if integrations else "Not verified from the listing."
        complaints = "".join(f'<li>{esc(c["summary"])} <a href="{esc(c["source_url"])}" target="_blank" rel="noopener noreferrer">Source ↗</a><small>{esc(c.get("status", "Needs verification"))}</small></li>' for c in result["complaints"])
        peer_links = " · ".join(f'<a href="{esc(p["url"])}" target="_blank" rel="noopener noreferrer">{esc(p["name"])} ↗</a>' for p in result["sample_peers"])
        market = result["market_competition"]
        market_text = f'<a href="{esc(market["source_url"])}" target="_blank" rel="noopener noreferrer">{market["app_count"]:,} apps in {esc(market["category_name"])} ↗</a><small>Observed {esc(market["observed_at"])}. Category population, not an exact direct-competitor count.</small>' if market else 'Marketplace-wide alternatives: <b>Unknown</b>. A complete, sourced count is not available.'
        listing = esc(app.get("listing_excerpt") or "No listing excerpt imported; inspect the source.")
        team = app.get("team", {"status": "unknown"})
        team_text = esc(team["status"].replace("_", " ").title())
        if team.get("source_url"):
            team_text = f'<a href="{esc(team["source_url"])}" target="_blank" rel="noopener noreferrer">{team_text} · statement source ↗</a>'
        team_text += " · Statement date: " + esc(team.get("statement_date") or "Unknown")
        team_text += " · " + esc(team.get("note", "Team size cannot be inferred from a publisher name."))
        freshness = esc(app.get("source_crawled_hint") or "Not reported")
        review_source = esc(app.get("review_source_url") or app["url"])
        launched = app.get("launched_at") or "Unknown"
        bfs = "Yes" if app.get("built_for_shopify") is True else "No" if app.get("built_for_shopify") is False else "Unknown"
        rows += f'<tr id="{details_id}" class="app-detail" hidden><td colspan="9"><div class="detail-grid"><section><h3>Listing and independent MVP</h3><p>“{listing}” <a href="{esc(app["url"])}" target="_blank" rel="noopener noreferrer">Listing ↗</a></p><h4>Workflow hypothesis</h4><p>{esc(result["feature_summary"])}</p><h4>Our proposed scope</h4><p>{esc(result["proposed_mvp"])}</p><small>Workflow classification: {esc(result["classification"])}. Verify actual features in the listing.</small><h4>Publisher team</h4><p>{team_text}</p><h4>Listed integrations</h4><p>{esc(integration_text)}</p></section><section><h3>Buildability · {complexity_label}</h3><p>{esc(result["technical_notes"])}</p><h4>Cloudflare fit: {esc(result["cloudflare_fit"])}</h4><p>{esc(result["test_plan"])}</p><small>This estimates our MVP, not the current app’s infrastructure. Validate API eligibility and platform constraints before implementation.</small></section><section><h3>Success score and evidence</h3><ul class="score-components">{components}</ul><p>Possible full-score range: <b>{success["lower_bound"]:.1f}–{success["upper_bound"]:.1f}</b>. Displayed score uses known dimensions only.</p><small>Launched: {esc(launched)} · Built for Shopify: {bfs}<br>Research date: {esc(app["observed_at"])}<br>Detail source index age at research: {freshness}<br><a href="{review_source}" target="_blank" rel="noopener noreferrer">Review-count source ↗</a>. Indexed pages may be stale or disagree.</small></section><section><h3>Merchant complaints</h3><p>{esc(result["complaint_status"])}</p><ul>{complaints}</ul><a href="{esc(app["url"])}/reviews?ratings%5B%5D=1" target="_blank" rel="noopener noreferrer">Inspect one-star reviews ↗</a><h4>Competition</h4><p>{market_text}</p><small>Known peers are grouped by a similar workflow within our sample. They are candidates for comparison, not a verified exhaustive list of direct competitors.</small></section></div><details class="peer-links"><summary>Known alternatives in our sample ({peer_count})</summary><p>{peer_links or "No classified peers in this sample yet."}</p></details></td></tr></tbody>'
    return f'''<section id="apps" class="panel catalog-panel"><div class="section-header"><div><span class="eyebrow">OPPORTUNITY RESEARCH</span><h2>App analysis workspace</h2></div><span class="badge neutral">{len(apps)} unique apps</span></div>
<div class="catalog-controls"><div class="category-filters" role="group" aria-label="Filter apps by discovery category">{buttons}</div><div class="filter-toolbar"><label>Search apps or workflows<input id="app-search" type="search" placeholder="App, developer or problem…"></label><label>Sort by<select id="app-sort"><option value="priority">Research priority</option><option value="success">Success · conservative bound</option><option value="reviews">Review count</option><option value="complexity">Simplest MVP first</option><option value="peers">Fewest known peers</option></select></label><label>MVP complexity<select id="complexity-filter"><option value="all">All estimates</option><option value="2">Simple · 1–2</option><option value="3">Up to medium · 1–3</option><option value="unknown">Not assessed</option></select></label><label>Minimum reviews<input id="min-reviews" type="number" min="0" value="0"></label><label class="checkbox-filter"><input id="paid-only" type="checkbox">Paid plan observed</label><button id="reset-app-filters" class="button" type="button">Reset filters</button></div><div class="filter-result"><span id="app-result-count" role="status" aria-live="polite">Showing {len(apps)} apps</span><span id="active-peer-filter" hidden></span></div></div>
<p class="panel-note">Complaint evidence is available for {sum(bool(r["complaints"]) for r in catalog["apps"])} / {len(apps)} apps; unresearched complaints are unknown. Start with successful apps, then narrow the MVP. Scores are provisional signals, not revenue estimates. Category buttons show discovery-page selections; an app may appear in multiple groups. Expand a row to inspect assumptions and sources.</p><div class="table-scroll"><table id="analysis-table" class="analysis-table"><thead><tr><th aria-label="Expand details"></th><th>App / workflow</th><th class="numeric">Priority</th><th class="numeric">Success</th><th class="numeric">MVP effort</th><th class="numeric">Reviews / rating</th><th class="numeric">From / month</th><th class="numeric">Similar apps*</th><th>Compare</th></tr></thead>{rows}</table></div><p id="no-app-results" class="empty" hidden>No apps match these filters. Try a broader category or reset the filters.</p>
<details class="analysis-methodology"><summary>Scoring, selection and competition methodology</summary><div class="panel-body"><p>Success weights: demand 35%, satisfaction 15%, measured review growth 20%, monetization 20%, age and Built for Shopify 10%. Demand uses a logarithmic review-count scale capped at 10,000 reviews. Satisfaction uses a 20-review prior at 4.0 stars. Growth reaches 100 at two net reviews per day over an observed 7- or 30-day period; negative growth scores zero. Paid-plan availability scores 65 before the known-price adjustment; free-to-install alone is not evidence of monetization. Credibility combines age (70%, capped at three years) and Built for Shopify (30%); missing sub-signals are excluded.</p><p>Unknown dimensions are excluded from the displayed score and reported as missing coverage. Bounds show the possible full score if unknown dimensions scored 0 or 100. Research priority = conservative success bound × (6 − estimated complexity) / 5 × paid-plan factor (1 if observed, otherwise 0.35). It prioritizes research; it does not establish that a competitor is weak or that our alternative will sell.</p><p>Complexity 1–2 means a small proposed MVP; 3 means moderate scope; 4–5 involves substantial integrations, state management or platform constraints. Estimates come from explicit workflow profiles and name-based classification unless an analyst assessment is available. They are not estimates of the incumbent’s actual architecture or promises about development time.</p><p>Sampling selects up to 20 apps with the most reviews among the apps observed on each of seven category discovery pages. Those pages contain recommendations and overlap; this is not the global top 20 or a complete market census. App details can differ from cached category cards. Index freshness can bias future deltas; verify consistent fresh sources before interpreting daily growth. Similar-app counts exclude the current app and count only classified peers in our sample. Marketplace category totals, where sourced, are separate and can include apps solving other problems.</p><p><a href="data/analysis.json" download>Download app analysis JSON ↓</a></p></div></details></section>'''
