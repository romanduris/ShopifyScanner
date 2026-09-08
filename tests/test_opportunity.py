import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app_analysis
import opportunity

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 9, 8)
URL = "https://apps.shopify.com/example-young-entrant"


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "tests/fixtures/opportunity_evidence.json").read_text())
        self.evidence = self.data["apps"][URL]
        self.app = {"url": URL, "name": "Example Young Entrant", "developer": "Example",
                    "observed_at": "2026-09-08", "launched_at": "2025-01-01", "category_ids": [],
                    "review_count": 9999, "rating": 5, "pricing_model": "freemium", "entry_monthly_usd": 100}

    def result(self, as_of=AS_OF):
        opportunity.validate(self.data, as_of, {URL})
        return opportunity.evaluate(self.app, as_of, self.evidence)

    def test_complete_evidence_qualifies_with_multiplicative_score(self):
        result = self.result()
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["score"], 32)
        self.assertTrue(all(g["status"] == "pass" for g in result["gates"].values()))
        self.assertFalse(result["next_actions"])

    def test_every_required_gate_blocks_qualification_when_evidence_is_missing(self):
        for field, gate in (("payments", "demand"), ("traction", "entry"),
                            ("incumbents", "entry"), ("build", "build"), ("weakness", "weakness")):
            with self.subTest(field=field):
                evidence = copy.deepcopy(self.evidence)
                del evidence[field]
                result = opportunity.evaluate(self.app, AS_OF, evidence)
                self.assertEqual(result["gates"][gate]["status"], "unknown")
                self.assertIsNone(result["score"])
                self.assertEqual(result["status"], "needs_research")

    def test_high_reviews_price_and_simple_profile_cannot_pass_gates(self):
        self.app["name"] = "Simple Trust Badges"
        result = app_analysis.analyze([self.app], AS_OF)["apps"][0]
        self.assertEqual(result["complexity"], 1)
        self.assertGreater(result["success"]["score"], 50)
        self.assertIsNone(result["research_priority"])
        self.assertEqual(result["opportunity"]["status"], "needs_research")

    def test_old_app_cannot_qualify_even_with_complete_evidence(self):
        self.app["launched_at"] = "2019-01-01"
        result = self.result()
        self.assertEqual(result["status"], "established")
        self.assertIsNone(result["score"])

    def test_calendar_launch_boundary_and_leap_day(self):
        self.assertEqual(opportunity.months_before(date(2024, 2, 29), 24), date(2022, 2, 28))
        for launched, state in (("2024-09-08", "pass"), ("2024-09-07", "fail"), (None, "unknown")):
            self.app["launched_at"] = launched
            self.assertEqual(self.result()["gates"]["age"]["status"], state)

    def test_unknown_launch_date_cannot_qualify(self):
        self.app.pop("launched_at")
        result = self.result()
        self.assertEqual(result["status"], "needs_research")
        self.assertIsNone(result["score"])

    def test_review_growth_is_only_a_proxy_even_when_large(self):
        self.evidence["traction"].update(metric="reviews", end_value=10000)
        result = self.result()
        self.assertEqual(result["gates"]["entry"]["status"], "unknown")
        self.assertIsNone(result["score"])
        self.assertIn("proxy", result["gates"]["entry"]["reason"])

    def test_negative_and_small_customer_growth_fail_instead_of_becoming_unknown(self):
        for end in (0, 20, 24):
            self.evidence["traction"]["end_value"] = end
            result = self.result()
            self.assertEqual(result["gates"]["entry"]["status"], "fail")
            self.assertEqual(result["status"], "rejected")

    def test_growth_threshold_is_normalized_by_actual_window(self):
        self.evidence["traction"].update(start_at="2026-06-10", end_value=34)
        self.assertEqual(self.result()["gates"]["entry"]["status"], "fail")
        self.evidence["traction"]["end_value"] = 35
        self.assertEqual(self.result()["gates"]["entry"]["status"], "pass")

    def test_short_incomparable_and_prelaunch_windows_need_research(self):
        for changes in ({"start_at": "2026-09-01"}, {"comparable": False}, {"start_at": "2025-01-01"}):
            evidence = copy.deepcopy(self.evidence)
            evidence["traction"].update(changes)
            self.assertEqual(opportunity.evaluate(self.app, AS_OF, evidence)["gates"]["entry"]["status"], "unknown")
        self.app["launched_at"] = "2026-09-01"
        self.assertEqual(self.result()["gates"]["entry"]["status"], "unknown")

    def test_stale_traction_does_not_become_current_by_rerunning(self):
        result = self.result(AS_OF + timedelta(days=31))
        self.assertEqual(result["gates"]["entry"]["status"], "unknown")
        self.assertIsNone(result["score"])
        self.assertEqual(self.result(AS_OF + timedelta(days=30))["gates"]["entry"]["status"], "pass")

    def test_stale_build_weakness_and_incumbents_need_research(self):
        result = self.result(AS_OF + timedelta(days=91))
        for gate in ("build", "weakness", "entry"):
            self.assertEqual(result["gates"][gate]["status"], "unknown")
        self.assertEqual(result["incumbents"], [])

    def test_republished_old_payment_does_not_prove_current_demand(self):
        self.evidence["payments"][0]["period_end"] = "2020-01-01"
        self.assertEqual(self.result()["gates"]["demand"]["status"], "unknown")
        self.app["revenue_disclosures"] = [{"amount": 100000, "published_at": "2026-09-08",
                                            "source_url": "https://example.org/old-revenue", "evidence_type": "developer_statement"}]
        self.assertEqual(self.result()["gates"]["demand"]["status"], "unknown")

    def test_zero_payment_is_not_proof_that_anyone_pays(self):
        self.evidence["payments"][0]["value"] = 0
        self.assertEqual(self.result()["gates"]["demand"]["status"], "unknown")

    def test_build_budget_limits_are_enforced(self):
        for field, value in (("work_days", 10.1), ("monthly_cost_usd", 51), ("support_hours_monthly", 3),
                             ("core_workflow_covered", False), ("quality_included", False), ("platform_access_verified", False)):
            with self.subTest(field=field):
                evidence = copy.deepcopy(self.evidence)
                evidence["build"][field] = value
                result = opportunity.evaluate(self.app, AS_OF, evidence)
                self.assertEqual(result["gates"]["build"]["status"], "fail")
                self.assertIsNone(result["score"])
        self.evidence["build"].update(work_days=10, monthly_cost_usd=50, support_hours_monthly=2)
        self.assertEqual(self.result()["gates"]["build"]["status"], "pass")

    def test_build_requires_documented_workload_and_all_feasibility_checks(self):
        for field in ("cost_basis", "scope", "validation", "platform_access_verified", "work_days"):
            evidence = copy.deepcopy(self.evidence)
            del evidence["build"][field]
            result = opportunity.evaluate(self.app, AS_OF, evidence)
            self.assertEqual(result["gates"]["build"]["status"], "unknown")

    def test_duplicate_merchant_reports_do_not_establish_recurring_weakness(self):
        self.evidence["weakness"]["reports"][1]["merchant_id"] = " MERCHANT-A "
        self.assertEqual(self.result()["gates"]["weakness"]["status"], "unknown")

    def test_old_reports_and_resolved_weakness_cannot_qualify(self):
        self.evidence["weakness"]["reports"][1]["published_at"] = "2025-01-01"
        self.assertEqual(self.result()["gates"]["weakness"]["status"], "unknown")
        self.evidence["weakness"]["unresolved"] = False
        self.assertEqual(self.result()["gates"]["weakness"]["status"], "fail")

    def test_incumbent_must_precede_entrant_and_be_established(self):
        self.evidence["incumbents"][0]["launched_at"] = "2025-02-01"
        self.assertEqual(self.result()["gates"]["entry"]["status"], "unknown")

    def test_competitor_count_does_not_penalize_proven_entry(self):
        before = self.result()["score"]
        for i in range(20):
            self.evidence["incumbents"].append(dict(self.evidence["incumbents"][0], url=f"https://apps.shopify.com/incumbent-{i}"))
        self.assertEqual(self.result()["score"], before)

    def test_qualified_app_ranks_above_high_review_old_app(self):
        old = dict(self.app, url="https://apps.shopify.com/old-app", launched_at="2010-01-01", review_count=100000)
        self.app["review_count"] = 10
        result = app_analysis.analyze([old, self.app], AS_OF, opportunities=self.data["apps"])
        self.assertEqual(result["apps"][0]["url"], URL)
        self.assertEqual(result["screening_counts"]["qualified"], 1)

    def test_discovery_queue_has_no_review_count_cap(self):
        apps = [dict(self.app, url=f"https://apps.shopify.com/young-{i}", name=f"Size chart {i}", review_count=0) for i in range(25)]
        result = app_analysis.analyze(apps, AS_OF)
        self.assertEqual(len(result["research_queue"]["tasks"]), 25)
        self.assertEqual(len(result["research_queue"]["discovery"]["size_charts"]["young_sample_apps"]), 25)

    def test_real_data_keeps_zigpoll_as_context_and_no_fabricated_qualifications(self):
        apps = json.loads((ROOT / "Data/Sources/apps.json").read_text())["apps"]
        result = app_analysis.analyze(apps, AS_OF)
        self.assertEqual(result["screening_counts"], {"qualified": 0, "needs_research": 7, "rejected": 0, "established": 114})
        zigpoll = next(r for r in result["apps"] if r["url"].endswith("/zigpoll"))
        self.assertEqual(zigpoll["opportunity"]["status"], "established")
        self.assertIsNone(zigpoll["research_priority"])

    def test_malformed_claims_are_rejected(self):
        changes = [
            ("traction", "end_value", True), ("traction", "start_value", -1), ("traction", "metric", "price"),
            ("traction", "end_at", "2026-12-01"), ("traction", "comparable", "yes"),
            ("traction", "start_at", "20260809"), ("traction", "observed_at", "2026-08-01"),
            ("build", "work_days", float("nan")), ("build", "sources", ["javascript:alert(1)"]),
            ("build", "quality_included", 1), ("build", "scope", []),
            ("weakness", "reports", "two"), ("weakness", "sources", []),
        ]
        for field, key, value in changes:
            with self.subTest(field=field, key=key):
                data = copy.deepcopy(self.data)
                data["apps"][URL][field][key] = value
                with self.assertRaises(ValueError):
                    opportunity.validate(data, AS_OF, {URL})

    def test_self_incumbent_unrelated_payment_and_orphan_records_fail(self):
        for case in ("self", "unrelated", "orphan", "duplicate"):
            data = copy.deepcopy(self.data)
            if case == "self":
                data["apps"][URL]["incumbents"][0]["url"] = URL
            elif case == "unrelated":
                data["apps"][URL]["payments"][0]["subject_app_url"] = "https://apps.shopify.com/unrelated"
            elif case == "duplicate":
                data["apps"][URL]["incumbents"] *= 2
            with self.subTest(case=case), self.assertRaises(ValueError):
                opportunity.validate(data, AS_OF, set() if case == "orphan" else {URL})

    def test_invalid_evidence_preserves_existing_page_and_queue(self):
        spec = importlib.util.spec_from_file_location("stats_test_opportunity", ROOT / "1.Stats.py")
        stats = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stats)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "Data/Sources"
            sources.mkdir(parents=True)
            (sources / "market_facts.json").write_bytes((ROOT / "tests/fixtures/market_facts.json").read_bytes())
            (sources / "apps.json").write_text(json.dumps({"schema_version": 1, "apps": [self.app]}))
            evidence_path = sources / "opportunities.json"
            evidence_path.write_text(json.dumps(self.data))
            stats.build(root, AS_OF)
            self.evidence["build"]["work_days"] = 6
            evidence_path.write_text(json.dumps(self.data))
            stats.build(root, AS_OF)
            self.assertEqual(len(list((root / "Data/Stats/history").glob("*.json"))), 1)
            analysis = json.loads((root / "Data/Analysis/latest.json").read_text())
            self.assertEqual(analysis["apps"][0]["opportunity"]["score"], 36)
            self.assertEqual((root / "Data/Analysis/research_queue.json").read_bytes(),
                             (root / "HTML/data/research_queue.json").read_bytes())
            page_path, queue_path = root / "HTML/index.html", root / "Data/Analysis/research_queue.json"
            page, queue = page_path.read_bytes(), queue_path.read_bytes()
            self.evidence["build"]["sources"] = ["javascript:alert(1)"]
            evidence_path.write_text(json.dumps(self.data))
            with self.assertRaises(ValueError):
                stats.build(root, AS_OF)
            self.assertEqual(page_path.read_bytes(), page)
            self.assertEqual(queue_path.read_bytes(), queue)

    def test_new_evidence_text_is_escaped_in_html(self):
        self.evidence["build"]["scope"] = '<img src=x onerror="alert(1)">'
        catalog = app_analysis.analyze([self.app], AS_OF, opportunities=self.data["apps"])
        page = app_analysis.render_catalog(catalog, [self.app], [])
        self.assertIn("&lt;img", page)
        self.assertNotIn("<img", page)


if __name__ == "__main__":
    unittest.main()
