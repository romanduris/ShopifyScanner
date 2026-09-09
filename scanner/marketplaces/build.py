"""Build market data and pages within the caller's staging directory."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from . import collect, model, render


def encode(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def csv_export(records):
    rows=[]
    for r in records:
        row={'Rank':r['rank'],'Marketplace':r['name'],'Category':r['category'],'Official URL':r['official_url'],
             'Target Customer':r['target_customer'],'Overall Opportunity Score':r['overall_score'],
             'Overall Upper Bound':r['overall_upper'],'Opportunity Asymmetry Score':r['asymmetry_score'],
             'New Entrant Success':r['new_entrant_success']['value'],'Codex Advantage':r['codex_advantage'],
             'Codex Automation %':r['codex_automation_percent'],'Confidence':r['confidence'],
             'Verdict':render.LABELS[r['verdict']],'Rejected':r['rejected'],'Rejection Reason':r['rejection_reason'],
             'Last Checked':r['last_checked'],'Eligibility':r['eligibility']['status']}
        row.update({render.human(k):m['value'] for k,m in r['metrics'].items()})
        row.update({render.human(k):m['value'] for k,m in r['scores'].items()})
        # Flat export has provenance for every measurement; JSON retains the full record.
        for group in ('metrics','scores','automation'):
            for key,m in r[group].items():
                for field in ('kind','confidence','date_checked','note','sources'):
                    row[f'{group}.{key}.{field}']=' | '.join(m[field]) if field=='sources' else m.get(field)
        for key,value in row.items():
            if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r','\n')):
                row[key]="'"+value
        rows.append(row)
    output=io.StringIO(newline='')
    fields=list(dict.fromkeys(key for row in rows for key in row))
    writer=csv.DictWriter(output,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return output.getvalue()


def build(root, as_of, refresh=False):
    source=root/'Data/Marketplaces/sources'
    research=read(source/'research.json')
    model.validate(research,as_of)
    observation_path=source/'observations.json'
    observations=read(observation_path) if observation_path.exists() else {'schema_version':1,'observations':{}}
    refresh_path=root/'Data/Marketplaces/refresh.json'
    report=read(refresh_path) if refresh_path.exists() else {'adapters':{},'note':'No live refresh attempted'}
    if refresh:
        observations,report=collect.refresh(observations,as_of)
        if not any(r['status']=='success' for r in report['adapters'].values()):
            raise ValueError('All marketplace adapters failed; last successful website and observations are preserved. '+encode(report))
    merged=collect.merge(research,observations)
    shopify_data=root/'Data/Sources/apps.json'
    if shopify_data.exists():
        for record in merged['marketplaces']:
            if record['id'] == 'shopify':
                record['entrants'] = [
                    {'name':a['name'], 'url':a['url'], 'source_url':a.get('review_source_url') or a['url'],
                     'date_checked':a['observed_at'], 'launched_at':a.get('launched_at'), 'launch_basis':'listing_added',
                     'reviews':a.get('review_count'), 'downloads':None, 'active_installs':None, 'paying_customers':None,
                     'first_party':a.get('developer') in ('Shopify', 'Microsoft', 'Meta'),
                     'note':'Existing curated Shopify import; review proxy only, not paying customers. First-party apps do not contribute to entrant scoring.'}
                    for a in read(shopify_data)['apps'] if a.get('launched_at')]
    records=model.rank(merged,as_of)
    if len(records)<50:
        raise ValueError('Production candidate universe must contain at least 50 marketplaces')
    # Fingerprint source evidence, not calculation time or adapter execution timestamps.
    canonical={'schema_version':1,'marketplaces':merged['marketplaces']}
    digest=hashlib.sha256(encode(canonical).encode()).hexdigest()
    history_path=root/'Data/Marketplaces/history'
    snapshots=[read(p) for p in sorted(history_path.glob('*.json'))]
    for snapshot in snapshots:
        model.validate(snapshot,as_of)
    fresh=not any(s['source_fingerprint']==digest for s in snapshots)
    snapshot={**canonical,'source_fingerprint':digest,'collected_at':datetime.now(timezone.utc).isoformat()}
    history=snapshots+[snapshot] if fresh else snapshots
    payload={'schema_version':1,'as_of':as_of.isoformat(),'weights':model.WEIGHTS,'snapshot_count':len(history),
             'source_fingerprint':digest,'marketplaces':records,'changes':model.changes(records,history,as_of),
             'limitations':['Rankings are provisional, not probabilities or earnings predictions.',
                            'Only WordPress and Obsidian have live public JSON adapters.',
                            'Other facts and qualitative assessments require reviewed research imports.',
                            'No claims of validated recent paid entrants without payment evidence.'],
             'top10':[r['id'] for r in records if not r['rejected']][:10],
             'top3':[r['id'] for r in records if not r['rejected']][:3]}
    pages={'index.html':render.home(payload),'opportunities.html':render.opportunities(payload),'changes.html':render.history_page(payload)}
    pages.update({f'marketplaces/{r["id"]}.html':render.detail(r,payload) for r in records})
    # Serialize and render everything before writing even to the isolated staging tree.
    encoded=encode(payload);csv_text=csv_export(records)
    if fresh:write(history_path/f'{as_of}-{digest[:12]}.json',encode(snapshot))
    if refresh:
        write(observation_path,encode(observations));write(refresh_path,encode(report))
    write(root/'Data/Marketplaces/latest.json',encoded)
    write(root/'Data/Marketplaces/marketplaces.csv',csv_text)
    write(root/'HTML/data/marketplaces.json',encoded)
    write(root/'HTML/data/marketplaces.csv',csv_text)
    write(root/'HTML/data/marketplace-refresh.json',encode(report))
    # Compact count history is enough for exported trend analysis; source snapshots retain entrants.
    write(root/'HTML/data/marketplace-history.json',encode([{'collected_at':s['collected_at'],'source_fingerprint':s['source_fingerprint'],
        'marketplaces':[{'id':r['id'],'metrics':{k:r['metrics'][k] for k in ('app_count','users','publishers')}} for r in s['marketplaces']]} for s in history]))
    for name,content in pages.items():write(root/'HTML'/name,content)
    return payload
