import copy
import csv
import io
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import build_site
from scanner.marketplaces import model, collect, build, render

ROOT=Path(__file__).resolve().parents[1]
DAY=date(2026,9,9)


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'Data/Marketplaces/sources/research.json').read_text())
        def fix_dates(value):
            if isinstance(value,dict):
                for key,child in value.items():
                    if key=='date_checked' and child is not None:value[key]=DAY.isoformat()
                    else:fix_dates(child)
            elif isinstance(value,list):
                for child in value:fix_dates(child)
        fix_dates(self.data)
        self.record=copy.deepcopy(self.data['marketplaces'][0])

    def prepare_root(self,root):
        source=root/'Data/Sources';source.mkdir(parents=True)
        for name in ('apps.json','market_facts.json'):
            shutil.copyfile(ROOT/'tests/fixtures'/name,source/name)
        markets=root/'Data/Marketplaces/sources';markets.mkdir(parents=True)
        (markets/'research.json').write_text(json.dumps(self.data))
        shutil.copytree(ROOT/'HTML/assets',root/'HTML/assets')

    def entrant(self, **values):
        e={'name':'Example utility','url':'https://example.org/plugin','source_url':'https://example.org/evidence',
           'date_checked':DAY.isoformat(),'launched_at':'2025-01-01','launch_basis':'listing_added',
           'reviews':20,'downloads':500,'active_installs':100,'paying_customers':None,'note':'Synthetic test fixture'}
        return dict(e,**values)

    def test_at_least_50_unique_candidates_and_all_required_markets(self):
        self.assertGreaterEqual(len(model.validate(self.data,DAY)['marketplaces']),50)
        required={'shopify','connect-iq','atlassian','jetbrains','vscode','chrome','google-workspace','appsource','teams',
                  'salesforce','wordpress','woocommerce','samsung','google-play','canva','figma','quickbooks','xero'}
        self.assertTrue(required <= {r['id'] for r in self.data['marketplaces']})

    def test_unknown_entry_preserves_bounds_and_asymmetry_unknown(self):
        r=model.score_marketplace(self.record,DAY)
        self.assertIsNone(r['new_entrant_success']['value'])
        self.assertIsNone(r['asymmetry_score'])
        self.assertGreaterEqual(round(r['overall_upper']-r['overall_score'],1),20)
        self.assertNotEqual(r['verdict'],'strong')

    def test_no_size_advantage(self):
        a=model.score_marketplace(self.record,DAY)
        self.record['metrics']['users']['value']=1000000000
        self.record['metrics']['app_count']['value']=1
        b=model.score_marketplace(self.record,DAY)
        self.assertEqual(a['overall_score'],b['overall_score'])
        self.assertEqual(a['asymmetry_upper'],b['asymmetry_upper'])

    def test_entrant_launch_boundary_and_stale_evidence(self):
        self.assertIsNotNone(model.entrant_score([self.entrant(launched_at='2024-09-09')],DAY)['value'])
        self.assertIsNone(model.entrant_score([self.entrant(launched_at='2024-09-08')],DAY)['value'])
        self.assertIsNone(model.entrant_score([self.entrant(date_checked='2026-01-01')],DAY)['value'])
        self.assertIsNone(model.entrant_score([self.entrant(launched_at=None)],DAY)['value'])

    def test_downloads_and_first_party_do_not_prove_entry(self):
        self.assertIsNone(model.entrant_score([self.entrant(reviews=0,active_installs=0,downloads=1000000)],DAY)['value'])
        self.assertIsNone(model.entrant_score([self.entrant(first_party=True)],DAY)['value'])

    def test_install_proxies_cannot_pass_payment_threshold(self):
        r=model.entrant_score([self.entrant(url=f'https://example.org/plugin/{i}') for i in range(10)],DAY)
        self.assertEqual(r['value'],6)
        self.assertEqual(r['paid_count'],0)
        r=model.entrant_score([self.entrant(url=f'https://example.org/plugin/{i}',paying_customers=5) for i in range(3)],DAY)
        self.assertEqual(r['value'],9)

    def test_duplicate_entrants_cannot_inflate_success(self):
        result=model.entrant_score([self.entrant() for _ in range(10)],DAY)
        self.assertEqual(result['traction_count'],1)
        self.assertEqual(result['value'],1.5)

    def test_friction_and_saturation_have_correct_direction(self):
        self.record['entrants']=[self.entrant()]
        a=model.score_marketplace(self.record,DAY)
        for key in ('publishing_friction','saturation','support_burden','infrastructure_complexity'):
            modified=copy.deepcopy(self.record);modified['scores'][key]['value']=10
            b=model.score_marketplace(modified,DAY)
            self.assertLessEqual(b['overall_score'],a['overall_score'])
            self.assertLessEqual(b['asymmetry_score'],a['asymmetry_score'])

    def test_stale_judgments_are_not_refreshed_by_rerun(self):
        r=model.score_marketplace(self.record,DAY+timedelta(days=91))
        self.assertTrue(r['stale']);self.assertEqual(r['overall_score'],0)
        self.assertEqual(r['overall_upper'],100)
        self.assertIsNone(r['asymmetry_score'])

    def test_invalid_scores_dates_and_sources_fail(self):
        for value in (-1,11,True,float('nan'),float('inf')):
            data=copy.deepcopy(self.data);data['marketplaces'][0]['scores']['saturation']['value']=value
            with self.assertRaises(ValueError):model.validate(data,DAY)
        for group,key,field,value in [('metrics','app_count','date_checked','2099-01-01'),('scores','saturation','sources',['javascript:alert(1)'])]:
            data=copy.deepcopy(self.data);data['marketplaces'][0][group][key][field]=value
            with self.assertRaises(ValueError):model.validate(data,DAY)

    def test_rejected_candidates_retain_reason_and_sort_last(self):
        ranked=model.rank(self.data,DAY)
        first=next(i for i,r in enumerate(ranked) if r['rejected'])
        self.assertTrue(all(r['rejected'] and r['rejection_reason'] for r in ranked[first:]))
        data=copy.deepcopy(self.data);r=next(r for r in data['marketplaces'] if r['rejected']);r['rejection_reason']=''
        with self.assertRaises(ValueError):model.validate(data,DAY)

    def test_economics_recurring_vs_one_time_and_rounding(self):
        scenario={'price_eur':120,'fee_percent':0,'processing_percent':0,'fixed_cost_eur':0,'billing':'annual'}
        annual=model.economics(scenario);self.assertEqual(annual['targets']['100'],10)
        scenario['billing']='one_time'
        one=model.economics(scenario);self.assertEqual(one['targets']['100'],1)
        self.assertEqual(one['unit'],'new sales each month')
        scenario.update(price_eur=10,fee_percent=15,fixed_cost_eur=15,billing='monthly')
        self.assertEqual(model.economics(scenario)['targets']['100'],14)

    def test_history_requires_exact_dates_scope_and_not_lower_bounds(self):
        r=copy.deepcopy(self.record)
        metric={'value':90,'date_checked':'2026-09-02','scope':'directory','unit':'apps','relation':'exact'}
        old=copy.deepcopy(r);old['metrics']['app_count']=metric
        r['metrics']['app_count']=dict(metric,value=80,date_checked='2026-09-09')
        history=[{'collected_at':'2026-09-02','marketplaces':[old]}]
        result=model.changes([r],history,DAY)
        self.assertEqual(result['7']['changes'][0]['net_change'],-10)
        self.assertEqual(result['30']['matched_metrics'],0)
        for field,value in [('scope','different'),('relation','at_least'),('date_checked','2026-09-08')]:
            modified=copy.deepcopy(r);modified['metrics']['app_count'][field]=value
            self.assertEqual(model.changes([modified],history,DAY)['7']['matched_metrics'],0)

    def test_failed_adapter_retains_previous_and_success_is_independent(self):
        previous={'schema_version':1,'observations':{'bad':{'metrics':{'old':True}}}}
        def failed(day):raise ValueError('Missing field')
        result,report=collect.refresh(previous,DAY,{'bad':failed,'good':lambda day:{'metrics':{}}})
        self.assertEqual(result['observations']['bad'],previous['observations']['bad'])
        self.assertTrue(report['adapters']['bad']['retained_previous'])
        self.assertEqual(report['adapters']['good']['status'],'success')
        self.assertNotIn('good',previous['observations'])

    def test_collector_does_not_accept_empty_or_broken_api(self):
        with self.assertRaises(ValueError):collect.wordpress(DAY,lambda url:{'plugins':[],'info':{'results':0}})
        with self.assertRaises(ValueError):collect.obsidian(DAY,lambda url:[{'id':'same'}]*12)

    def test_wordpress_adapter_preserves_zero_and_launch_provenance(self):
        item={'name':'Example','slug':'example','added':'2025-01-01','num_ratings':0,'downloaded':0,'active_installs':0}
        result=collect.wordpress(DAY,lambda url:{'plugins':[item],'info':{'results':42}})
        self.assertEqual(result['metrics']['app_count']['value'],42)
        self.assertEqual(len(result['entrants']),1)
        self.assertEqual(result['entrants'][0]['reviews'],0)
        self.assertEqual(result['entrants'][0]['launch_basis'],'listing_added')
        self.assertIsNone(result['entrants'][0]['paying_customers'])

    def test_exports_escape_html_and_spreadsheet_formulas(self):
        self.record['name']='=HYPERLINK("bad")'
        r=model.score_marketplace(self.record,DAY);r['rank']=1
        row=next(csv.DictReader(io.StringIO(build.csv_export([r]))))
        self.assertTrue(row['Marketplace'].startswith("'="))
        r['name']='<script>alert(1)</script>'
        page=render.detail(r,{'as_of':DAY.isoformat()})
        self.assertNotIn('<script>alert(1)',page)
        self.assertIn('&lt;script&gt;',page)

    def test_whole_build_idempotence_and_validation_failure_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.prepare_root(root)
            a=build_site.build(root,DAY);b=build_site.build(root,DAY)
            self.assertEqual(a,b)
            original=(root/'HTML/index.html').read_bytes()
            source=root/'Data/Marketplaces/sources/research.json';source.write_text('{"schema_version":99}')
            with self.assertRaises(ValueError):build_site.build(root,DAY)
            self.assertEqual((root/'HTML/index.html').read_bytes(),original)
            self.assertTrue((root/'HTML/shopify.html').exists())

    def test_all_adapters_failing_does_not_write_new_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.prepare_root(root)
            build_site.build(root,DAY)
            before=(root/'HTML/index.html').read_bytes()
            def fail(day):raise OSError('Source unavailable')
            with patch.dict(collect.ADAPTERS,{'broken':fail},clear=True):
                with self.assertRaises(ValueError):build_site.build(root,DAY,refresh=True)
            self.assertEqual((root/'HTML/index.html').read_bytes(),before)


if __name__=='__main__':unittest.main()
