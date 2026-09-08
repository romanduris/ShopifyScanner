import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import app_analysis as analysis

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 9, 8)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.apps = json.loads((ROOT / 'tests/fixtures/apps.json').read_text())['apps']

    def test_missing_growth_is_unknown_and_has_bounds(self):
        score = analysis.success_score(self.apps[0], AS_OF)
        self.assertEqual(sum(analysis.WEIGHTS.values()), 100)
        self.assertEqual(score['coverage'], 80)
        self.assertIsNone(score['components']['growth'])
        self.assertAlmostEqual(score['upper_bound'] - score['lower_bound'], 20)
        self.assertLessEqual(score['lower_bound'], score['score'])
        self.assertLessEqual(score['score'], score['upper_bound'])

    def test_unknown_is_not_a_zero_success_score(self):
        score = analysis.success_score({}, AS_OF)
        self.assertIsNone(score['score'])
        self.assertEqual(score['coverage'], 0)
        self.assertEqual((score['lower_bound'], score['upper_bound']), (0, 100))

    def test_small_perfect_rating_gets_less_weight(self):
        small = analysis.success_score({'rating': 5, 'review_count': 1}, AS_OF)
        large = analysis.success_score({'rating': 5, 'review_count': 1000}, AS_OF)
        self.assertLess(small['components']['satisfaction'], large['components']['satisfaction'])

    def test_growth_requires_matching_dates_and_preserves_negative_net(self):
        app = self.apps[0]
        old = dict(app, observed_at='2026-09-01', review_count=app['review_count'] + 7)
        growth = analysis.app_growth(app, [{'apps': [old]}])
        self.assertEqual(growth, {'days': 7, 'net_change': -7, 'score': 0})
        old['observed_at'] = '2026-09-02'
        self.assertIsNone(analysis.app_growth(app, [{'apps': [old]}]))
        self.assertIsNone(analysis.app_growth(app, [{'apps': [app]}]))

    def test_conflicting_history_fails(self):
        app = self.apps[0]
        a = dict(app, observed_at='2026-09-01', review_count=1)
        b = dict(a, review_count=2)
        with self.assertRaises(ValueError):
            analysis.app_growth(app, [{'apps': [a]}, {'apps': [b]}])

    def test_free_install_is_not_evidence_of_a_paid_plan(self):
        app = dict(self.apps[0], pricing_model='free_to_install', entry_monthly_usd=None)
        result = analysis.analyze([app], AS_OF)['apps'][0]
        self.assertFalse(result['paid_plan'])
        self.assertIsNone(result['success']['components']['monetization'])

    def test_peer_count_excludes_self_and_unknown_does_not_mean_zero(self):
        a = dict(self.apps[0], name='Example Size Chart')
        b = dict(self.apps[1], name='Other Size Chart')
        result = analysis.analyze([a, b], AS_OF)['apps']
        self.assertTrue(all(r['sample_peer_count'] == 1 for r in result))
        self.assertTrue(all(r['sample_peers'][0]['url'] != r['url'] for r in result))
        a['name'] = 'Unclassified'
        unknown = next(r for r in analysis.analyze([a, b], AS_OF)['apps'] if r['url'] == a['url'])
        self.assertIsNone(unknown['sample_peer_count'])
        self.assertIsNone(unknown['research_priority'])
        self.assertEqual(unknown['complaints'], [])

    def test_selection_has_twenty_slots_per_category_without_duplicate_urls(self):
        apps = json.loads((ROOT / 'Data/Sources/apps.json').read_text())['apps']
        selected = [a for a in apps if a.get('category_assignment') == 'discovery_page']
        categories = json.loads((ROOT / 'Data/Sources/market_facts.json').read_text())['categories']
        self.assertEqual(len(selected), 119)
        self.assertEqual(len({a['url'] for a in apps}), len(apps))
        for category in categories:
            self.assertEqual(sum(category['id'] in a['category_ids'] for a in selected), 20)

    def test_unverified_complaints_never_increase_priority(self):
        before = analysis.analyze(self.apps, AS_OF)
        after = analysis.analyze(self.apps, AS_OF, assessments={self.apps[0]['url']: {'complaints': [{'summary': 'A claim'}]}})
        self.assertEqual([a['research_priority'] for a in before['apps']], [a['research_priority'] for a in after['apps']])

    def test_sources_and_complexity_are_validated_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Data/Sources/assessments.json'
            path.parent.mkdir(parents=True)
            for record in ({'complexity': 0}, {'complexity': True}, {'group': 'bogus'},
                           {'complaints': [{'summary': 'Claim', 'source_url': 'javascript:alert(1)'}]}):
                path.write_text(json.dumps({'schema_version': 1, 'apps': {self.apps[0]['url']: record}}))
                with self.assertRaises(ValueError):
                    analysis.load_research(root, AS_OF)

    def test_source_counts_are_separate_from_sample_peers(self):
        assessments, competition = analysis.load_research(ROOT, AS_OF)
        app = dict(self.apps[0], name='Barcode Example')
        result = analysis.analyze([app], AS_OF, competition=competition)['apps'][0]
        self.assertEqual(result['sample_peer_count'], 0)
        self.assertEqual(result['market_competition']['app_count'], 90)

    def test_catalog_escapes_untrusted_text(self):
        apps = copy.deepcopy(self.apps)
        apps[0]['name'] = '<img src=x onerror=alert(1)>'
        apps[0]['listing_excerpt'] = '<script>unsafe</script>'
        page = analysis.render_catalog(analysis.analyze(apps, AS_OF), apps, [])
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('<script>unsafe', page)
        self.assertIn('&lt;script&gt;', page)


if __name__ == '__main__':
    unittest.main()
