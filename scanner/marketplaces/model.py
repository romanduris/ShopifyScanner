"""Validation and scoring. Scores are research judgments, never probabilities."""
import calendar
import copy
import math
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

WEIGHTS = {'new_entrant_success': 20, 'codex_advantage': 15, 'distribution': 15,
           'economics': 15, 'willingness_to_pay': 10, 'low_competition': 10,
           'native_monetization': 5, 'low_infrastructure': 5, 'low_friction': 5}
AUTOMATION = ('code_generation', 'unit_testing', 'integration_testing', 'ui_testing',
              'local_simulation', 'debugging', 'packaging', 'deployment_automation', 'documentation')
RISKS = ('publishing_friction', 'support_burden', 'platform_risk', 'legal_compliance_risk',
         'infrastructure_complexity', 'backend_complexity', 'development_effort')
REQUIRED_SCORES = ('saturation', 'distribution', 'economics', 'willingness_to_pay', 'demand', 'native_monetization') + RISKS
LABELS = {'strong': '🔥 Strong opportunity', 'investigate': '🟢 Investigate', 'maybe': '🟡 Maybe',
          'poor': '🔴 Poor fit', 'reject': '❌ Reject'}


def url(value):
    if not isinstance(value, str):
        raise ValueError('Expected an HTTPS URL')
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or any(c.isspace() for c in value):
        raise ValueError('Invalid source URL')
    return value


def numeric(value, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError('Invalid numeric measurement')


def checked(value, as_of):
    if date.fromisoformat(value) > as_of:
        raise ValueError('Future observation')


def validate_metric(metric, as_of, maximum=None):
    if metric['kind'] not in ('FACT', 'ESTIMATE', 'INFERENCE') or metric['confidence'] not in ('HIGH', 'MEDIUM', 'LOW'):
        raise ValueError('Invalid evidence classification')
    if not metric.get('note'):
        raise ValueError('Every metric needs an explanation')
    if metric.get('date_checked'):
        checked(metric['date_checked'], as_of)
    for source in metric['sources']:
        url(source)
    if metric['value'] is not None:
        if not metric.get('date_checked') or not metric['sources']:
            raise ValueError('Known values need a source and check date')
        if maximum is not None:
            numeric(metric['value'], maximum)


def validate(data, as_of):
    if data.get('schema_version') != 1 or not isinstance(data.get('marketplaces'), list) or not data['marketplaces']:
        raise ValueError('Invalid marketplace dataset')
    def validate_links(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('url', 'source_url', 'official_url') and child is not None:
                    url(child)
                elif key == 'sources' and isinstance(child, list):
                    for source in child:
                        if isinstance(source, str): url(source)
                        else: validate_links(source)
                else: validate_links(child)
        elif isinstance(value, list):
            for child in value: validate_links(child)
    validate_links(data)
    seen = set()
    for record in data['marketplaces']:
        key = record['id']
        if key in seen or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', key):
            raise ValueError('Duplicate or invalid marketplace ID')
        seen.add(key)
        if not record['name'] or not record['category']:
            raise ValueError('Missing identity')
        url(record['official_url'])
        if record['eligibility']['status'] not in ('eligible', 'conditional', 'rejected'):
            raise ValueError('Invalid eligibility')
        if not record['eligibility']['reason']:
            raise ValueError('Eligibility requires a rationale')
        if type(record['rejected']) is not bool or record['rejected'] != (record['eligibility']['status'] == 'rejected'):
            raise ValueError('Inconsistent rejection state')
        if record['rejected'] and not record['rejection_reason']:
            raise ValueError('Rejected candidates must retain their reason')
        for key, metric in record['metrics'].items():
            validate_metric(metric, as_of)
            if key in ('app_count', 'users', 'publishers') and metric['value'] is not None:
                numeric(metric['value'])
        for key in REQUIRED_SCORES:
            validate_metric(record['scores'][key], as_of, 10)
        for key in AUTOMATION:
            validate_metric(record['automation'][key], as_of, 10)
        entrant_urls = set()
        for entrant in record.get('entrants', []):
            validate_entrant(entrant, as_of)
            if entrant['url'] in entrant_urls:
                raise ValueError('Duplicate entrant URL')
            entrant_urls.add(entrant['url'])
        for source in record['sources']:
            url(source['url'])
            if source.get('date_checked'):
                checked(source['date_checked'], as_of)
        scenario = record['scenario']
        numeric(scenario['price_eur'], 10000)
        if scenario['price_eur'] <= 0 or scenario['billing'] not in ('monthly', 'annual', 'one_time'):
            raise ValueError('Invalid economics scenario')
        numeric(scenario['fee_percent'], 99.9)
        numeric(scenario['processing_percent'], 99.9)
        numeric(scenario['fixed_cost_eur'])
        if scenario['fee_percent'] + scenario['processing_percent'] >= 100:
            raise ValueError('Fees leave no contribution')
    return data


def validate_entrant(entrant, as_of):
    url(entrant['url'])
    url(entrant['source_url'])
    checked(entrant['date_checked'], as_of)
    if entrant.get('launched_at'):
        checked(entrant['launched_at'], date.fromisoformat(entrant['date_checked']))
    if entrant['launch_basis'] not in ('listing_added', 'first_release', 'publisher_statement', 'unknown'):
        raise ValueError('Invalid launch provenance')
    for key in ('reviews', 'downloads', 'active_installs', 'paying_customers'):
        if entrant.get(key) is not None:
            numeric(entrant[key])


def months_before(day, months):
    n = day.year * 12 + day.month - 1 - months
    year, month = divmod(n, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def entrant_score(entrants, as_of):
    entrants = list({e['url']: e for e in sorted(entrants, key=lambda e: e['date_checked'])}.values())
    recent = [e for e in entrants if not e.get('first_party') and e.get('launched_at') and e['launch_basis'] != 'unknown'
              and months_before(as_of, 24) <= date.fromisoformat(e['launched_at']) <= as_of
              and 0 <= (as_of - date.fromisoformat(e['date_checked'])).days <= 90]
    traction = [e for e in recent if (e.get('active_installs') or 0) >= 100
                or (e.get('reviews') or 0) >= 10 or (e.get('paying_customers') or 0) >= 5]
    paid = [e for e in traction if (e.get('paying_customers') or 0) >= 5]
    # Downloads include updates; a listing price is not payment evidence.
    score = min(6, len(traction) * 1.5) if traction else None
    if paid:
        score = min(10, 6 + len(paid))
    return {'value': score, 'kind': 'INFERENCE', 'confidence': 'MEDIUM' if traction else 'LOW',
            'sources': sorted({e['source_url'] for e in traction}),
            'date_checked': max((e['date_checked'] for e in traction), default=None),
            'recent_count': len(recent), 'traction_count': len(traction), 'paid_count': len(paid),
            'note': 'Up to 6/10 for dated entrants with >=100 active installs or >=10 reviews; 7–10 requires >=5 paying customers per example. Selection-biased proxies; not proof of profitability. No qualifying evidence stays unknown, not zero.'}


def interval(components):
    low = sum(WEIGHTS[k] * v / 10 for k, v in components.items() if v is not None)
    unknown = sum(WEIGHTS[k] for k, v in components.items() if v is None)
    return round(low, 1), round(low + unknown, 1), 100 - unknown


def economics(scenario):
    price = scenario['price_eur'] / (12 if scenario['billing'] == 'annual' else 1)
    unit = price * (1 - (scenario['fee_percent'] + scenario['processing_percent']) / 100)
    return {'unit_net_eur': round(unit, 2), 'unit': 'new sales each month' if scenario['billing'] == 'one_time' else 'active paying customers',
            'targets': {str(goal): math.ceil((goal + scenario['fixed_cost_eur']) / unit) for goal in (100, 500, 1000, 5000)},
            'note': 'Scenario contribution after assumed platform/processing fees and fixed infrastructure; before tax, refunds, churn and labor. One-time sales are not MRR. Not a demand forecast.'}


def score_marketplace(original, as_of):
    r = copy.deepcopy(original)
    scores = {k: v['value'] for k, v in r['scores'].items()}
    auto = [r['automation'][k]['value'] for k in AUTOMATION]
    codex = round(sum(auto) / len(auto), 1) if all(v is not None for v in auto) else None
    entry = entrant_score(r.get('entrants', []), as_of)
    invert = lambda value: 10 - value if value is not None else None
    friction = [scores[k] for k in ('publishing_friction', 'support_burden', 'platform_risk', 'legal_compliance_risk')]
    components = {'new_entrant_success': entry['value'], 'codex_advantage': codex,
                  'distribution': scores['distribution'], 'economics': scores['economics'],
                  'willingness_to_pay': scores['willingness_to_pay'], 'low_competition': invert(scores['saturation']),
                  'native_monetization': scores['native_monetization'], 'low_infrastructure': invert(scores['infrastructure_complexity']),
                  'low_friction': 10 - sum(friction) / 4 if all(v is not None for v in friction) else None}
    # After 90 days, a rerun cannot make old judgments current.
    stale = any(v.get('date_checked') and (as_of - date.fromisoformat(v['date_checked'])).days > 90
                for v in list(r['scores'].values()) + list(r['automation'].values()))
    if stale:
        components = {k: v if k == 'new_entrant_success' else None for k, v in components.items()}
    low, high, coverage = interval(components)
    # Bounded product of benefit and inverse cost factors. Size never enters either score.
    benefits = [scores['economics'], scores['demand'], scores['distribution'], entry['value'], codex]
    costs = [scores[k] for k in ('saturation', 'development_effort', 'support_burden', 'infrastructure_complexity', 'publishing_friction')]
    known = all(v is not None for v in benefits + costs) and not stale
    def asymmetry(entry_value):
        b = [scores['economics'], scores['demand'], scores['distribution'], entry_value, codex]
        if any(v is None for v in b + costs):
            return None
        numerator = math.prod(v / 10 for v in b) ** (1 / 5)
        denominator = math.prod(1 + v / 10 for v in costs) ** (1 / 5)
        return round(100 * numerator / denominator, 1)
    asym = asymmetry(entry['value']) if known else None
    confidence = 'LOW'
    if not stale and entry['traction_count'] >= 3 and coverage == 100:
        confidence = 'MEDIUM'
    verdict = 'reject' if r['rejected'] else ('poor' if high < 45 else 'maybe')
    if not r['rejected'] and low >= 55 and not stale:
        verdict = 'investigate'
    if not r['rejected'] and r['eligibility']['status'] == 'eligible' and low >= 75 and entry['paid_count'] >= 3 and confidence != 'LOW':
        verdict = 'strong'
    r.update(overall_score=low, overall_upper=high, score_coverage=coverage, components=components,
             asymmetry_score=asym, asymmetry_upper=asymmetry(10) if not stale else None,
             codex_advantage=codex, codex_automation_percent=round(codex * 10) if codex is not None else None,
             new_entrant_success=entry, confidence=confidence, verdict=verdict, stale=stale,
             contribution={k: round(WEIGHTS[k] * v / 10, 2) if v is not None else None for k, v in components.items()},
             economics_calculation=economics(r['scenario']))
    r['last_checked'] = max((s['date_checked'] for s in r['sources'] if s.get('date_checked')), default=None)
    r['score_note'] = 'Conservative lower bound; missing dimensions are 0–10 uncertainty, not measured zero. Other scores are explicit research estimates.'
    return r


def rank(data, as_of):
    validate(data, as_of)
    records = [score_marketplace(r, as_of) for r in data['marketplaces']]
    records.sort(key=lambda r: (r['rejected'], -r['overall_score'], -(r['asymmetry_score'] or 0), r['name'].casefold()))
    for position, r in enumerate(records, 1):
        r['rank'] = position
    return records


def changes(records, history, as_of):
    result = {}
    for days in (7, 30, 90):
        target = (as_of - timedelta(days=days)).isoformat()
        prior = {}
        # Snapshots are ordered by collected_at; newest real check on a day wins.
        for snapshot in sorted(history, key=lambda s: s.get('collected_at', '')):
            for record in snapshot['marketplaces']:
                for key in ('app_count', 'users', 'publishers'):
                    metric = record['metrics'].get(key, {})
                    if metric.get('date_checked') == target and metric.get('value') is not None:
                        prior[(record['id'], key)] = metric
        rows = []
        for record in records:
            for key in ('app_count', 'users', 'publishers'):
                metric = record['metrics'].get(key, {})
                old = prior.get((record['id'], key))
                comparable = old and old.get('unit') == metric.get('unit') and old.get('scope') == metric.get('scope') and old.get('relation', 'exact') == metric.get('relation', 'exact') == 'exact'
                if comparable and metric.get('date_checked') == as_of.isoformat() and metric.get('value') is not None:
                    rows.append({'id': record['id'], 'marketplace': record['name'], 'metric': key, 'net_change': metric['value'] - old['value']})
        result[str(days)] = {'status': 'Observed changes' if rows else 'Baseline — insufficient historical data', 'matched_metrics': len(rows), 'changes': rows}
    return result
