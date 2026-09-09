"""Bounded public JSON adapters. Failed refreshes retain previous observations."""
import copy
import html
import json
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode
from .model import validate_entrant

USER_AGENT = 'OpportunityScanner/1.0 (+https://github.com/romanduris/ShopifyScanner)'
MAX_BYTES = 12_000_000


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Source exceeds adapter response limit')
    return json.loads(raw)


def measurement(value, source, day, note, unit, scope):
    return {'value': value, 'sources': [source], 'date_checked': day.isoformat(), 'kind': 'FACT',
            'confidence': 'HIGH', 'note': note, 'unit': unit, 'scope': scope, 'relation': 'exact'}


def wordpress(day, fetch=get_json):
    base = 'https://api.wordpress.org/plugins/info/1.2/'
    records = {}
    total = None
    count_source = None
    # Small discovery sample, not an exhaustive crawl or a representative cohort.
    queries = [{'request[browse]': 'new', 'request[per_page]': 100},
               {'request[browse]': 'popular', 'request[per_page]': 100}]
    queries += [{'request[search]': term, 'request[per_page]': 40} for term in ('invoice', 'export', 'accessibility', 'table', 'booking')]
    for query in queries:
        source = base + '?' + urlencode({'action': 'query_plugins', **query,
            'request[fields][description]': 0, 'request[fields][sections]': 0})
        data = fetch(source)
        if not isinstance(data.get('plugins'), list) or not data['plugins'] or not isinstance(data.get('info', {}).get('results'), int):
            raise ValueError('Unexpected WordPress API schema or empty result')
        if query.get('request[browse]') == 'new':
            total, count_source = data['info']['results'], source
        for app in data['plugins']:
            slug = app['slug']
            import re
            if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise ValueError('Invalid WordPress plugin slug')
            e = {'name': html.unescape(app['name']), 'url': f'https://wordpress.org/plugins/{slug}/',
                 'source_url': source, 'date_checked': day.isoformat(), 'launched_at': app.get('added'),
                 'launch_basis': 'listing_added', 'reviews': app.get('num_ratings'), 'downloads': app.get('downloaded'),
                 'active_installs': app.get('active_installs'), 'paying_customers': None,
                 'note': 'Official directory added date, not necessarily the first commercial release. Active installs are rounded API buckets; downloads include updates. No payment evidence.',
                 'description': html.unescape(app.get('short_description', ''))}
            validate_entrant(e, day)
            records[slug] = e
    return {'metrics': {'app_count': measurement(total, count_source, day,
            'WordPress API new-browse result total; directory population, not paid plugins or active publishers.', 'plugins', 'wordpress-api-new-browse')},
            'entrants': sorted(records.values(), key=lambda e: e['url']),
            'collection': {'sample_size': len(records), 'method': 'New + popular + five utility searches; bounded, selection-biased sample', 'date_checked': day.isoformat()}}


def obsidian(day, fetch=get_json):
    source = 'https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json'
    data = fetch(source)
    if not isinstance(data, list) or len(data) < 10 or any(not isinstance(r.get('id'), str) for r in data):
        raise ValueError('Unexpected Obsidian registry schema')
    ids = [r['id'] for r in data]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate registry ID')
    return {'metrics': {'app_count': measurement(len(ids), source, day,
            'Entries in the official community plugin registry; not paid plugins, active users or sales.', 'plugins', 'obsidian-official-registry')},
            'collection': {'sample_size': len(ids), 'method': 'Official JSON registry; counts only, no inferred launch dates', 'date_checked': day.isoformat()}}


ADAPTERS = {'wordpress': wordpress, 'obsidian': obsidian}


def refresh(previous, day, adapters=None):
    output = copy.deepcopy(previous or {'schema_version': 1, 'observations': {}})
    report = {'attempted_at': datetime.now(timezone.utc).isoformat(), 'adapters': {}}
    for key, adapter in (ADAPTERS if adapters is None else adapters).items():
        try:
            observation = adapter(day)
            observation['collected_at'] = report['attempted_at']
            output['observations'][key] = observation
            report['adapters'][key] = {'status': 'success', 'date_checked': day.isoformat()}
        except (OSError, ValueError, KeyError, TypeError) as error:
            report['adapters'][key] = {'status': 'failed', 'retained_previous': key in output['observations'], 'error': str(error)[:300]}
    return output, report


def merge(research, observations):
    result = copy.deepcopy(research)
    ids = {r['id'] for r in result['marketplaces']}
    if observations.get('schema_version') != 1 or not isinstance(observations.get('observations'), dict):
        raise ValueError('Invalid observation envelope')
    if set(observations['observations']) - ids:
        raise ValueError('Observation references an unknown marketplace')
    for record in result['marketplaces']:
        observed = observations['observations'].get(record['id'], {})
        for key, metric in observed.get('metrics', {}).items():
            existing = record['metrics'].get(key)
            if existing and existing['value'] is not None and existing.get('date_checked') == metric['date_checked'] and existing['value'] != metric['value']:
                record['conflicts'].append({'metric': key, 'manual': existing, 'automated': metric, 'resolution': 'Display latest direct API measurement; retain both claims here'})
            record['metrics'][key] = metric
        if 'entrants' in observed:
            by_url = {e['url']: e for e in record.get('entrants', [])}
            by_url.update({e['url']: e for e in observed['entrants']})
            record['entrants'] = list(by_url.values())
        if observed:
            record['collection'] = observed.get('collection')
            for metric in observed.get('metrics', {}).values():
                for source in metric['sources']:
                    record['sources'].append({'url': source, 'title': 'Automated public JSON observation', 'date_checked': metric['date_checked'], 'kind': 'primary', 'method': 'Bounded JSON adapter'})
    return result
