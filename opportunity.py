"""Evidence gates for young Shopify entrants; no inferred payments or live collection."""

import calendar
import json
import math
import re
from datetime import date
from urllib.parse import quote, urlsplit

OBJECTIVE = (
    "Find Shopify apps launched within approximately the last 24 months that are "
    "currently demonstrating strong traction, despite competing against established "
    "apps, and whose core functionality can be independently rebuilt by a solo "
    "developer with Codex in roughly 1–2 weeks."
)
POLICY = {
    "max_age_months": 24,
    "traction_fresh_days": 30,
    "research_fresh_days": 90,
    "payment_fresh_days": 365,
    "complaint_fresh_days": 180,
    "min_window_days": 30,
    "max_window_days": 90,
    "min_customers_per_30d": 5,
    "max_build_days": 10,
    "max_monthly_cost_usd": 50,
    "max_support_hours_monthly": 2,
}
GATE_LABELS = {
    "age": "Launch window", "demand": "Proven demand", "entry": "Proven entry",
    "build": "Easy build", "weakness": "Exploitable weakness",
}
STATUS_LABELS = {
    "qualified": "Qualified", "needs_research": "Needs research",
    "rejected": "Rejected", "established": "Established app",
}


def months_before(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def source_url(value, app=False):
    if not isinstance(value, str):
        raise ValueError("Evidence URLs must be strings.")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or any(c.isspace() for c in value)):
        raise ValueError("Evidence sources must use HTTPS.")
    if app and (parts.netloc != "apps.shopify.com" or parts.query or parts.fragment
                or not re.fullmatch(r"/[a-z0-9]+(?:-[a-z0-9]+)*", parts.path)
                or parts.path[1:] in {"categories", "search", "partners", "reviews", "stories"}):
        raise ValueError("Evidence must reference a canonical Shopify app URL.")


def validate_date(value, as_of):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Evidence dates must use YYYY-MM-DD.")
    parsed = date.fromisoformat(value)
    if parsed > as_of:
        raise ValueError("Evidence cannot be dated in the future.")
    return parsed


def numeric(value, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("Evidence values must be finite, non-negative numbers.")


def validate_record(record, as_of):
    """Partial assessments are allowed; malformed claims fail before output writes."""
    allowed = {"incumbents", "payments", "traction", "build", "weakness"}
    if not isinstance(record, dict) or set(record) - allowed:
        raise ValueError("Unknown opportunity evidence fields.")

    def evidence(item, dated="observed_at"):
        if not isinstance(item, dict):
            raise ValueError("Evidence must be an object.")
        validate_date(item[dated], as_of)
        if not isinstance(item.get("sources"), list) or not item["sources"]:
            raise ValueError("Evidence requires at least one source.")
        for url in item["sources"]:
            source_url(url)
        if not isinstance(item.get("summary"), str) or not item["summary"].strip():
            raise ValueError("Evidence requires a summary.")

    def flag(item, key):
        if key in item and item[key] is not None and type(item[key]) is not bool:
            raise ValueError(f"{key} must be true, false or null.")

    for field in ("incumbents", "payments"):
        if not isinstance(record.get(field, []), list):
            raise ValueError(f"{field} must be a list.")
    seen = set()
    for item in record.get("incumbents", []):
        evidence(item)
        source_url(item["url"], app=True)
        if item["url"] in seen:
            raise ValueError("Duplicate direct incumbent.")
        seen.add(item["url"])
        if validate_date(item["launched_at"], as_of) > date.fromisoformat(item["observed_at"]):
            raise ValueError("An incumbent cannot be observed before launch.")
    for item in record.get("payments", []):
        evidence(item)
        source_url(item["subject_app_url"], app=True)
        validate_date(item["period_end"], as_of)
        if item["period_end"] > item["observed_at"]:
            raise ValueError("Payment period cannot follow its observation.")
        if item["kind"] not in {"paying_customers", "mrr", "arr", "cumulative_revenue", "merchant_payment"}:
            raise ValueError("A price listing is not payment evidence.")
        if item["evidence_type"] not in {"developer_statement", "independent_report", "merchant_statement"}:
            raise ValueError("Unknown payment evidence type.")
        numeric(item["value"])
        if item["kind"] == "paying_customers" and type(item["value"]) is not int:
            raise ValueError("Customer counts must be integers.")
        if item["kind"] != "paying_customers" and not re.fullmatch(r"[A-Z]{3}", item.get("currency", "")):
            raise ValueError("Payment amounts require a currency; no conversion is inferred.")
    if record.get("traction") is not None:
        item = record["traction"]
        evidence(item)
        if item["metric"] not in {"paying_customers", "active_merchants", "reviews"}:
            raise ValueError("Traction must measure comparable customer or review counts.")
        start, end = validate_date(item["start_at"], as_of), validate_date(item["end_at"], as_of)
        if start >= end or end > date.fromisoformat(item["observed_at"]):
            raise ValueError("Invalid traction observation window.")
        for key in ("start_value", "end_value"):
            numeric(item[key])
            if type(item[key]) is not int:
                raise ValueError("Traction counts must be integers.")
        if type(item.get("comparable")) is not bool:
            raise ValueError("Traction must declare whether observations are comparable.")
    if record.get("build") is not None:
        item = record["build"]
        evidence(item)
        for key in ("work_days", "monthly_cost_usd", "support_hours_monthly"):
            if item.get(key) is not None:
                numeric(item[key], 0.1 if key == "work_days" else 0)
        for key in ("core_workflow_covered", "quality_included", "platform_access_verified"):
            flag(item, key)
        for key in ("scope", "exclusions", "dependencies", "validation", "cost_basis"):
            if key in item and not isinstance(item[key], str):
                raise ValueError(f"Build {key} must be text.")
    if record.get("weakness") is not None:
        item = record["weakness"]
        evidence(item)
        for key in ("unresolved", "fits_build_scope"):
            flag(item, key)
        for key in ("target_segment", "differentiation"):
            if key in item and not isinstance(item[key], str):
                raise ValueError(f"Weakness {key} must be text.")
        if not isinstance(item.get("reports", []), list):
            raise ValueError("Weakness reports must be a list.")
        for report in item.get("reports", []):
            evidence(report, "published_at")
            if report["published_at"] > item["observed_at"]:
                raise ValueError("A weakness report cannot follow its verification.")
            if not isinstance(report.get("merchant_id"), str) or not report["merchant_id"].strip():
                raise ValueError("A weakness report requires a distinct merchant identifier.")


def validate(data, as_of, app_urls):
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or not isinstance(data.get("apps"), dict) or set(data) - {"schema_version", "apps"}):
        raise ValueError("Invalid opportunity evidence schema.")
    for url, record in data["apps"].items():
        source_url(url, app=True)
        if url not in app_urls:
            raise ValueError(f"Import the app listing before its opportunity evidence: {url}")
        validate_record(record, as_of)
        if any(i["url"] == url for i in record.get("incumbents", [])):
            raise ValueError("An app cannot be its own incumbent.")
        subjects = {url} | {i["url"] for i in record.get("incumbents", [])}
        if any(i["subject_app_url"] not in subjects for i in record.get("payments", [])):
            raise ValueError("Payment evidence must concern this app or a documented direct incumbent.")
    return data["apps"]


def load(root, as_of, app_urls):
    path = root / "Data/Sources/opportunities.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1, "apps": {}}
    return validate(data, as_of, app_urls)


def fresh(value, as_of, days):
    return 0 <= (as_of - date.fromisoformat(value)).days <= days


def gate(state, reason, sources=(), observed_at=None, factor=None):
    return {"status": state, "reason": reason, "sources": sorted(set(sources)),
            "observed_at": observed_at, "factor": factor if state == "pass" else None}


def evaluate(app, as_of, evidence, review_growth=None):
    cutoff = months_before(as_of, POLICY["max_age_months"])
    launched = app.get("launched_at")
    gates = {}
    gates["age"] = (gate("pass" if cutoff <= date.fromisoformat(launched) <= as_of else "fail",
                         f"Launched {launched}; eligible from {cutoff.isoformat()} through {as_of.isoformat()}.",
                         [app["url"]], app["observed_at"])
                    if launched else gate("unknown", "Verify the launch date from the app listing."))

    incumbents = [i for i in evidence.get("incumbents", [])
                  if launched and i["launched_at"] < launched and date.fromisoformat(i["launched_at"]) < cutoff
                  and fresh(i["observed_at"], as_of, POLICY["research_fresh_days"])]
    subjects = {app["url"]} | {i["url"] for i in incumbents}
    payments = [p for p in evidence.get("payments", []) if p["value"] > 0
                and p["subject_app_url"] in subjects
                and fresh(p["period_end"], as_of, POLICY["payment_fresh_days"])]
    # Legacy disclosures have publication dates but no machine-readable period end.
    # Import a dated payment record rather than treating republication as fresh revenue.
    gates["demand"] = (gate("pass", "Positive payment evidence for this problem; statements are attributed, not audited.",
                             [s for p in payments for s in p["sources"]], max(p["observed_at"] for p in payments), 1.0)
                       if payments else gate("unknown", "Document actual payments or paying customers for this problem within the last year; a paid plan is insufficient."))

    traction = evidence.get("traction")
    if not traction:
        entry = gate("unknown", "Import comparable customer-count observations spanning 30–90 days, ending within the last 30 days.")
    else:
        days = (date.fromisoformat(traction["end_at"]) - date.fromisoformat(traction["start_at"])).days
        gain = traction["end_value"] - traction["start_value"]
        rate = gain * 30 / days
        sources, observed = traction["sources"], traction["end_at"]
        if not traction["comparable"] or not POLICY["min_window_days"] <= days <= POLICY["max_window_days"]:
            entry = gate("unknown", "Traction needs comparable counts over a 30–90 day window.", sources, observed)
        elif not fresh(traction["end_at"], as_of, POLICY["traction_fresh_days"]):
            entry = gate("unknown", "Traction is stale; obtain a customer-count observation from the last 30 days.", sources, observed)
        elif traction["metric"] == "reviews":
            entry = gate("unknown", f"{gain:+} reviews in {days} days is a proxy; confirm current customer acquisition.", sources, observed)
        elif launched and traction["start_at"] < launched:
            entry = gate("unknown", "Traction window predates launch; verify relaunch or migration history.", sources, observed)
        elif rate < POLICY["min_customers_per_30d"]:
            entry = gate("fail", f"{gain:+} {traction['metric'].replace('_', ' ')} in {days} days: below the screening threshold of 5 net customers per 30 days.", sources, observed)
        elif not incumbents:
            entry = gate("unknown", "Customer growth observed; verify at least one active direct competitor launched before this app and older than 24 months.", sources, observed)
        else:
            entry_factor = min(1.0, rate / 20)
            entry = gate("pass", f"{gain:+} {traction['metric'].replace('_', ' ')} in {days} days alongside {len(incumbents)} documented established competitor(s).",
                         sources + [s for i in incumbents for s in i["sources"]], observed, entry_factor)
    gates["entry"] = entry

    build = evidence.get("build")
    build_fields = ("scope", "exclusions", "dependencies", "validation", "cost_basis")
    if not build:
        gates["build"] = gate("unknown", "Assess core scope, tests, platform access, development days, operating costs and support; a complexity label is insufficient.")
    elif not fresh(build["observed_at"], as_of, POLICY["research_fresh_days"]):
        gates["build"] = gate("unknown", "Refresh the build assessment and platform constraints (older than 90 days).", build["sources"], build["observed_at"])
    else:
        checks = {"work_days": POLICY["max_build_days"], "monthly_cost_usd": POLICY["max_monthly_cost_usd"],
                  "support_hours_monthly": POLICY["max_support_hours_monthly"]}
        over = [k.replace("_", " ") for k, limit in checks.items() if build.get(k) is not None and build[k] > limit]
        flags = ("core_workflow_covered", "quality_included", "platform_access_verified")
        if over or any(build.get(k) is False for k in flags):
            gates["build"] = gate("fail", "Build exceeds budget or a required feasibility check failed: " + ", ".join(over + [k.replace("_", " ") for k in flags if build.get(k) is False]) + ".", build["sources"], build["observed_at"])
        elif any(build.get(k) is None for k in checks) or not all(build.get(k) is True for k in flags) or not all(build.get(k, "").strip() for k in build_fields):
            gates["build"] = gate("unknown", "Complete scope, exclusions, dependency validation, cost assumptions and all feasibility checks.", build["sources"], build["observed_at"])
        else:
            gates["build"] = gate("pass", f"Assessed at {build['work_days']:g} working days including quality checks; ${build['monthly_cost_usd']:g}/month and {build['support_hours_monthly']:g} support hours/month at the documented workload. Estimate, not a delivery guarantee.", build["sources"], build["observed_at"], min(1.0, (15 - build["work_days"]) / 10))

    weakness = evidence.get("weakness")
    if not weakness:
        gates["weakness"] = gate("unknown", "Find a current unmet need reported by at least two independent merchants and a specific improvement within our build scope.")
    else:
        reports = [r for r in weakness.get("reports", []) if fresh(r["published_at"], as_of, POLICY["complaint_fresh_days"])]
        merchants = {r["merchant_id"].strip().casefold() for r in reports}
        sources = weakness["sources"] + [s for r in reports for s in r["sources"]]
        observed = weakness["observed_at"]
        if not fresh(observed, as_of, POLICY["research_fresh_days"]):
            gates["weakness"] = gate("unknown", "Recheck whether the reported weakness is still unresolved (assessment older than 90 days).", sources, observed)
        elif weakness.get("unresolved") is False or weakness.get("fits_build_scope") is False:
            gates["weakness"] = gate("fail", "The weakness is resolved or its solution does not fit the proposed build.", sources, observed)
        elif (len(merchants) < 2 or weakness.get("unresolved") is not True or weakness.get("fits_build_scope") is not True
              or not weakness.get("differentiation", "").strip() or not weakness.get("target_segment", "").strip()):
            gates["weakness"] = gate("unknown", "Require two independent merchant reports within 180 days, current verification, a target segment and a feasible differentiator.", sources, observed)
        else:
            gates["weakness"] = gate("pass", f"{len(merchants)} independent merchants report an unmet need; an in-scope improvement is documented.", sources, observed, min(1.0, len(merchants) / 5))

    states = [g["status"] for g in gates.values()]
    status = ("established" if gates["age"]["status"] == "fail" else "rejected" if "fail" in states
              else "qualified" if all(s == "pass" for s in states) else "needs_research")
    factors = {k: gates[k]["factor"] for k in ("demand", "entry", "build", "weakness")}
    score = round(100 * math.prod(factors.values()), 1) if status == "qualified" else None
    actions = [g["reason"] for g in gates.values() if g["status"] == "unknown"]
    if not incumbents:
        actions.append("Document at least one active direct competitor launched before this entrant and older than 24 months; include sources and a same-problem assessment.")
    return {"status": status, "score": score, "gates": gates, "factors": factors,
            "launch_cutoff": cutoff.isoformat(), "incumbents": incumbents,
            "evidence": evidence, "review_growth_proxy": ({**review_growth, "end_at": app["observed_at"],
                "fresh": fresh(app["observed_at"], as_of, POLICY["traction_fresh_days"])} if review_growth else None),
            "next_actions": actions}


def research_queue(results, as_of):
    """Separate new-entrant discovery from a backlog of missing evidence."""
    tasks = [{"url": r["url"], "name": r["name"], "group": r["group"],
              "actions": r["opportunity"]["next_actions"]}
             for r in results if r["opportunity"]["status"] == "needs_research"]
    groups = {}
    for result in results:
        if result["group"] == "unknown":
            continue
        item = groups.setdefault(result["group"], {"workflow": result["group_name"], "established_sample_apps": [],
                                                  "young_sample_apps": [], "search_url": "https://apps.shopify.com/search?q=" + quote(result["group_name"])})
        if result["opportunity"]["status"] == "established":
            item["established_sample_apps"].append(result["url"])
        elif result["opportunity"]["gates"]["age"]["status"] == "pass":
            item["young_sample_apps"].append(result["url"])
    return {"schema_version": 1, "as_of": as_of.isoformat(), "objective": OBJECTIVE,
            "launch_cutoff": months_before(as_of, POLICY["max_age_months"]).isoformat(),
            "collection_status": "Local imports only; search links are research starting points, not completed observations.",
            "discovery_method": "Search focused workflows and direct alternatives; inspect launch dates before shortlisting. Import all verified young entrants without a lifetime-review top-N cap. Record direct competition and comparable recent customer counts. Sample classifications are hypotheses until verified.",
            "tasks": tasks, "discovery": groups}
