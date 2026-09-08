import copy
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stats", ROOT / "1.Stats.py")
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)
AS_OF = date(2026, 9, 8)


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.facts = stats.read_json(ROOT / "Data/Sources/market_facts.json")
        self.records = stats.read_json(ROOT / "Data/Sources/apps.json")

    def apps(self):
        return stats.validate_inputs(self.facts, self.records, AS_OF)

    def test_known_sample_and_unknown_market_are_separate(self):
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(result["entry_monthly_usd_median"], 6.49)
        self.assertEqual(result["review_count_total"], 152)
        self.assertEqual(result["paid_plan_count"], 2)
        self.assertIsNone(result["market"]["earning_apps"])
        self.assertIsNone(result["market"]["total_mrr_usd"])
        self.assertTrue(all(c["market_count"] is None for c in result["categories"]))

    def test_categories_overlap_without_inflating_unique_apps(self):
        self.records["apps"][0]["category_ids"] *= 2
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(sum(c["sample_count"] for c in result["categories"]), 3)
        self.assertEqual(result["sample_size"], 2)

    def test_canonical_duplicates_use_newest_observation(self):
        older = copy.deepcopy(self.records["apps"][0])
        older.update(url=older["url"] + "/?locale=sk", observed_at="2026-09-07", review_count=12)
        self.records["apps"].append(older)
        self.assertEqual(len(self.apps()), 2)
        self.assertEqual(next(a for a in self.apps() if "ezinvoices" in a["url"])["review_count"], 13)

    def test_conflicting_same_day_records_fail(self):
        other = copy.deepcopy(self.records["apps"][0])
        other["review_count"] += 1
        self.records["apps"].append(other)
        with self.assertRaises(ValueError):
            self.apps()

    def test_empty_import_is_supported(self):
        self.records["apps"] = []
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(result["sample_size"], 0)
        self.assertIsNone(result["entry_monthly_usd_median"])
        self.assertIsNone(result["rating_median"])
        self.assertIsNone(result["review_count_total"])

    def test_unknown_values_are_not_zero_and_free_install_is_not_paid(self):
        self.records["apps"] = [self.records["apps"][0]]
        self.records["apps"][0].update(review_count=None, rating=None, pricing_model="free_to_install", entry_monthly_usd=None)
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(result["zero_reviews_count"], 0)
        self.assertEqual(result["reviews_known_count"], 0)
        self.assertEqual(result["paid_plan_count"], 0)
        self.assertEqual(result["review_bands"]["Nezistené"], 1)

    def test_historical_revenue_is_not_converted_to_mrr(self):
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(result["revenue_disclosed_apps"], 1)
        revenue = result["revenue_disclosures"][0]
        self.assertEqual(revenue["kind"], "cumulative_revenue")
        self.assertEqual(revenue["amount"], 735.66)
        self.assertIsNone(result["market"]["total_mrr_usd"])

    def test_solo_classification_needs_direct_evidence(self):
        self.records["apps"][0]["team"]["evidence_type"] = "one_app_in_profile"
        with self.assertRaises(ValueError):
            self.apps()

    def test_invalid_numeric_values_fail(self):
        for key, value in (("review_count", -1), ("review_count", 1.5), ("review_count", True),
                           ("rating", 5.1), ("rating", float("nan")), ("entry_monthly_usd", -3)):
            with self.subTest(key=key, value=value):
                records = copy.deepcopy(self.records)
                records["apps"][0][key] = value
                with self.assertRaises(ValueError):
                    stats.validate_inputs(self.facts, records, AS_OF)

    def test_invalid_sources_and_future_dates_fail(self):
        for key, value in (("url", "https://example.com/ezinvoices"),
                           ("developer_url", "javascript:alert(1)"), ("observed_at", "2026-10-01")):
            with self.subTest(key=key):
                records = copy.deepcopy(self.records)
                records["apps"][0][key] = value
                with self.assertRaises(ValueError):
                    stats.validate_inputs(self.facts, records, AS_OF)

    def test_market_category_count_requires_evidence(self):
        self.facts["categories"][0]["market_count"] = 123
        with self.assertRaises(KeyError):
            self.apps()

    def test_badge_is_boolean_not_numeric(self):
        self.records["apps"][0]["built_for_shopify"] = 1
        with self.assertRaises(ValueError):
            self.apps()

    def test_delta_requires_actual_observations_and_can_be_negative(self):
        apps = self.apps()
        prior = copy.deepcopy(apps)
        for app in prior:
            app["observed_at"] = "2026-09-01"
            app["review_count"] += 2
        result = stats.review_deltas(apps, [{"apps": prior}], AS_OF)
        self.assertEqual(result["7"], {"net_change": -4, "matched_apps": 2})
        self.assertIsNone(result["1"]["net_change"])
        stale = stats.review_deltas(prior, [{"apps": prior}], AS_OF)
        self.assertIsNone(stale["7"]["net_change"])

    def test_delta_excludes_new_unmatched_apps(self):
        apps = self.apps()
        prior = copy.deepcopy(apps[:1])
        prior[0].update(observed_at="2026-09-07", review_count=prior[0]["review_count"] - 3)
        result = stats.review_deltas(apps, [{"apps": prior}], AS_OF)
        self.assertEqual(result["1"], {"net_change": 3, "matched_apps": 1})

    def test_rolling_launch_window_boundary(self):
        self.records["apps"][0]["launched_at"] = "2026-08-10"
        self.records["apps"][1]["launched_at"] = "2026-08-09"
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertEqual(result["new_30d"], 1)
        self.assertEqual(result["new_90d"], 2)

    def test_export_escapes_html_and_spreadsheet_formulas(self):
        self.records["apps"][0]["name"] = '<script>alert("x")</script>'
        self.facts["categories"][0]["name"] = "=1+2"
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        result.update(review_deltas=stats.review_deltas(self.apps(), [], AS_OF), snapshot_count=1)
        rendered = stats.render_dashboard(result)
        self.assertNotIn('<script>alert', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        rows = list(csv.DictReader(io.StringIO(stats.csv_text(result["categories"]))))
        self.assertEqual(rows[0]["name"], "'=1+2")
        self.assertEqual(rows[0]["market_count"], "")

    def test_end_to_end_idempotence_and_failure_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "Data/Sources"
            sources.mkdir(parents=True)
            for name, data in (("market_facts.json", self.facts), ("apps.json", self.records)):
                (sources / name).write_text(json.dumps(data), encoding="utf-8")
            first = stats.build(root, AS_OF)
            second = stats.build(root, AS_OF)
            self.assertEqual(first, second)
            self.assertEqual(len(list((root / "Data/Stats/history").glob("*.json"))), 1)
            page = (root / "HTML/index.html").read_text()
            self.assertIn("Prehľad trhu", page)
            self.assertEqual((root / "HTML/data/stats.json").read_bytes(), (root / "Data/Stats/latest.json").read_bytes())
            # Advancing the calculation date without new sources is not a new observation.
            stats.build(root, date(2026, 9, 9))
            self.assertEqual(len(list((root / "Data/Stats/history").glob("*.json"))), 1)
            preserved = (root / "HTML/index.html").read_bytes()
            (sources / "apps.json").write_text('{"schema_version": 99}')
            with self.assertRaises(ValueError):
                stats.build(root, AS_OF)
            self.assertEqual((root / "HTML/index.html").read_bytes(), preserved)

    def test_exports_use_consistent_line_endings(self):
        result = stats.summarize(self.facts, self.apps(), AS_OF)
        self.assertNotIn("\r", stats.csv_text(result["categories"]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.csv"
            path.write_bytes(b"a,b\r\n1,2\r\n")
            stats.write_text(path, "a,b\n1,2\n")
            self.assertEqual(path.read_bytes(), b"a,b\n1,2\n")


if __name__ == "__main__":
    unittest.main()
