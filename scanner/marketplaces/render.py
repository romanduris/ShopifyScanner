"""Static accessible pages sharing the existing Shopify visual language."""
import html
from .model import LABELS, WEIGHTS, AUTOMATION, months_before
from datetime import date


def esc(value):
    return html.escape(str(value), quote=True)


def human(key):
    return key.replace('_', ' ').capitalize()


def show(value):
    if value is None:
        return 'Unknown'
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    if isinstance(value, (int, float)):
        return f'{value:,}'
    if isinstance(value, list):
        return ' · '.join(map(str, value))
    return str(value)


def link(url, label):
    return f'<a href="{esc(url)}">{esc(label)}</a>'


def nav(active='marketplaces', prefix=''):
    links = [('marketplaces', 'index.html', '🌍 Marketplaces'), ('shopify', 'shopify.html', '🛍 Shopify Apps'),
             ('opportunities', 'opportunities.html', '☆ Top Opportunities'), ('changes', 'changes.html', '↗ Changes')]
    items = []
    for key, path, title in links:
        attrs = 'aria-current="page" class="active"' if key == active else ''
        items.append(f'<a {attrs} href="{prefix}{path}">{title}</a>')
    return '<nav aria-label="Main navigation">' + ''.join(items) + '</nav>'


def shell(title, body, as_of, active='marketplaces', prefix=''):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Compare software marketplaces for small solo developer products using sourced evidence, explicit estimates and dated observations.">
<title>{esc(title)} · Opportunity Scanner</title><link rel="stylesheet" href="{prefix}assets/styles.css"><link rel="stylesheet" href="{prefix}assets/marketplaces.css"><script src="{prefix}assets/marketplaces.js" defer></script></head>
<body class="marketplace-site"><a class="skip-link" href="#content">Skip to content</a><header class="topbar"><a class="brand" href="{prefix}index.html"><span class="brand-mark" aria-hidden="true">O</span><span>OPPORTUNITY<span class="brand-accent">SCANNER</span></span></a>{nav(active,prefix)}<span class="scan-status"><i></i>Calculated {as_of}</span></header>
<main id="content">{body}</main><footer><span>Opportunity Scanner · One developer + Codex</span><span>Sourced facts. Explicit estimates. No invented revenue. · {link(prefix+'data/marketplaces.json','JSON')} · {link(prefix+'data/marketplaces.csv','CSV')}</span></footer></body></html>'''


def badge(r):
    return f'<span class="verdict {r["verdict"]}">{LABELS[r["verdict"]]}</span>'


def bar(value, maximum=10, inverse=False):
    if value is None:
        return '<span class="unknown">Unknown</span>'
    return f'<span class="metric-bar {"burden" if inverse else ""}"><b>{value:g}</b><span class="track"><i style="width:{value/maximum*100:.1f}%"></i></span></span>'


def source_note(metric):
    sources = ' · '.join(link(s, f'Source {i+1}') for i, s in enumerate(metric['sources']))
    return f'<small class="evidence-meta">{metric["kind"]} · {metric["confidence"]} · {esc(metric.get("date_checked") or "Not verified")} {sources}</small>'


def metric_card(key, metric):
    return f'<div class="fact-card"><h3>{esc(human(key))}</h3><strong>{esc(show(metric["value"]))}</strong><p>{esc(metric["note"])}</p>{source_note(metric)}</div>'


def shortlist(records, detailed=False):
    cards = []
    for r in records[:3]:
        reason = r.get('deep_dive', {}).get('why_market', r['overview'])
        cards.append(f'''<article class="shortlist-card"><div class="card-heading"><span class="eyebrow">INVESTIGATION {r['rank']:02d}</span>{badge(r)}</div><h3>{link('marketplaces/'+r['id']+'.html',r['name'])}</h3><p>{esc(reason)}</p><div class="card-score"><strong>{r['overall_score']}</strong><span>/100 conservative score<br>Possible range {r['overall_score']}–{r['overall_upper']}</span></div><div class="card-meta"><span>Codex <b>{show(r['codex_advantage'])}/10</b></span><span>Entry evidence <b>{show(r['new_entrant_success']['value'])}</b></span></div>{link('marketplaces/'+r['id']+'.html','Review evidence →')}</article>''')
    return '<div class="shortlist-grid">'+''.join(cards)+'</div>'


COLUMNS = [('rank','Rank'),('name','Marketplace'),('category','Category'),('overall','Overall ↓'),('asymmetry','Asymmetry'),
 ('entry','New entrant'),('saturation','Saturation ↑ worse'),('codex','Codex advantage'),('automation','Automation %'),
 ('distribution','Distribution'),('economics','Economics'),('willingness','Willingness to pay'),('native','Native billing'),
 ('pricing','Typical pricing'),('apps','Apps / plugins'),('users','Users / customers'),('publishing','Publishing ↑ worse'),
 ('support','Support ↑ worse'),('backend','Backend ↑ worse'),('infrastructure','Infrastructure ↑ worse'),
 ('platform','Platform risk ↑ worse'),('legal','Legal risk ↑ worse'),('confidence','Confidence'),('verdict','Verdict')]
FILTERS = [('overall','Overall score','min',100),('asymmetry','Asymmetry','min',100),('entry','New entrant success','min',10),
 ('saturation','Saturation','max',10),('codex','Codex advantage','min',10),('automation','Codex automation %','min',100),
 ('distribution','Distribution','min',10),('economics','Solo economics','min',10),('willingness','Willingness to pay','min',10),
 ('publishing','Publishing friction','max',10),('support','Support burden','max',10),('backend','Backend complexity','max',10)]


def table_row(r):
    s = {k:v['value'] for k,v in r['scores'].items()}
    numbers = dict(rank=r['rank'],overall=r['overall_score'],asymmetry=r['asymmetry_score'],entry=r['new_entrant_success']['value'],
        saturation=s['saturation'],codex=r['codex_advantage'],automation=r['codex_automation_percent'],distribution=s['distribution'],
        economics=s['economics'],willingness=s['willingness_to_pay'],publishing=s['publishing_friction'],support=s['support_burden'],
        backend=s['backend_complexity'],infrastructure=s['infrastructure_complexity'],platform=s['platform_risk'],legal=s['legal_compliance_risk'],
        apps=r['metrics']['app_count']['value'],users=r['metrics']['users']['value'])
    attrs = ' '.join(f'data-{k}="{v if v is not None else ""}"' for k,v in numbers.items())
    attrs += f' data-name="{esc(r["name"].casefold())}" data-search="{esc((r["name"]+" "+r["category"]+" "+r["target_customer"]).casefold())}" data-category="{esc(r["category"])}" data-verdict="{r["verdict"]}" data-confidence="{r["confidence"]}"'
    attrs += f' data-native="{esc(show(r["metrics"]["native_billing"]["value"]))}" data-pricing="{esc(show(r["metrics"]["typical_pricing"]["value"]))}"'
    cells=[]
    for key,label in COLUMNS:
        if key=='name':
            value=f'<a class="market-name" href="marketplaces/{r["id"]}.html">{esc(r["name"])}</a><small>{esc(r["target_customer"])} · {esc(r["last_checked"] or "Unknown date")}</small>'
        elif key=='category':value=esc(r['category'])
        elif key=='overall':value=f'{bar(r["overall_score"],100)}<small>Range {r["overall_score"]}–{r["overall_upper"]}</small>'
        elif key=='asymmetry':value=bar(r['asymmetry_score'],100)
        elif key in ('native','pricing'):
            value=esc(show(r['metrics']['native_billing' if key=='native' else 'typical_pricing']['value']))
        elif key in ('apps','users'):
            m=r['metrics']['app_count' if key=='apps' else 'users'];v=m['value']
            value=esc(('≥' if m.get('relation') in ('at_least','greater_than') else '')+show(v))
            if v is not None:value+=f'<small>{esc(m.get("scope", ""))}</small>'
        elif key=='confidence':value=f'<span class="confidence">{r["confidence"]}</span>'
        elif key=='verdict':value=badge(r)
        elif key=='rank':value=f'{r["rank"]:02d}'
        else:value=bar(numbers.get(key),100 if key=='automation' else 10,key in ('saturation','publishing','support','backend','infrastructure','platform','legal'))
        cells.append(f'<td>{value}</td>')
    return f'<tr class="market-record" {attrs}>'+''.join(cells)+'</tr>'


def methodology():
    weights=''.join(f'<li><span>{human(k)}</span><b>{v}%</b></li>' for k,v in WEIGHTS.items())
    return f'''<section id="methodology" class="panel methodology"><div class="section-header"><div><span class="eyebrow">HOW TO READ THE RANKING</span><h2>Evidence first. Uncertainty stays visible.</h2></div></div><div class="method-grid"><div><p>Overall score uses the requested weights. Marketplace size has no weight. Rows rank by the conservative lower bound, with rejected candidates last. Overlapping ranges do not establish a reliable winner.</p><p>Unknown dimensions retain their full 0–10 range. The lower-bound calculation uses zero contribution for them; this is <strong>not a measured zero</strong>. Scores are research judgments, not probabilities. After 90 days, unreviewed judgments stop contributing.</p><p>Asymmetry = 100 × geometric mean(economics, demand, distribution, entrant success, Codex) / geometric mean(1 + each burden). Each score is scaled to 0–1. Burdens are saturation, development effort, support, infrastructure and publishing. Missing factors keep the score unknown.</p></div><ul class="weight-list">{weights}</ul><div><p><strong>FACT</strong> means an attributed observation. <strong>ESTIMATE</strong> means a scoped cost or workload scenario. <strong>INFERENCE</strong> means an interpretation of evidence.</p><p>New-entrant scores require a launch within 24 calendar months and traction checked within 90 days. Install/review proxies are capped at 6/10. Scores above 6 require paying-customer evidence. Downloads include updates and cannot establish customers.</p><p>Codex automation is the equal-weight mean of nine separate implementation and testing estimates. Host integration, human review and real devices constrain it. It is not a measured model benchmark.</p><p>Strong Opportunity requires an eligible publisher route, at least three paid entrants and a conservative score ≥75. The current shortlist is for manual investigation.</p></div></div></section>'''


def home(dataset):
    records=dataset['marketplaces'];n=len(records)
    verified=sum(r['new_entrant_success']['traction_count']>0 for r in records)
    rejected=sum(r['rejected'] for r in records)
    body=f'''<section class="market-hero"><div><span class="eyebrow">MARKETPLACE OPPORTUNITY SCANNER</span><h1>Find a smaller market.<br><span>Build a useful product.</span></h1><p>Compare {n} ecosystems for one developer + Codex. Prioritize recent entry, paying customers and manageable effort.</p><div class="hero-actions"><a class="primary-button" href="#markets">Explore all marketplaces ↓</a><a class="button" href="#methodology">How scoring works</a></div></div><div class="hero-note"><span class="eyebrow">THE STRATEGY</span><strong>Small products.<br>Repeatable experiments.</strong><p>€100 → €500 → €1,000 / month</p><small>Revenue goals, not forecasts. Find evidence before committing to a build.</small></div></section>
<div class="market-summary"><div><strong>{n}</strong><span>ecosystems compared</span></div><div><strong>{verified}</strong><span>with recent traction proxies</span></div><div><strong>{rejected}</strong><span>rejected, reasons retained</span></div><div><strong>{dataset['snapshot_count']}</strong><span>source snapshots</span></div></div>
<section class="section-lead"><div><span class="eyebrow">START YOUR INVESTIGATION</span><h2>Three markets to look at first</h2></div>{link('opportunities.html','Explore the Top 10 →')}</section>
<p class="research-notice">Provisional research shortlist. Ranking ranges overlap; recent paid success is not yet established for these recommendations. Unknown data is visible in every detail view.</p>
{shortlist(records)}
<section id="markets" class="panel market-catalog"><div class="section-header"><div><span class="eyebrow">THE COMPLETE UNIVERSE</span><h2>Compare marketplaces</h2></div><div class="downloads">{link('data/marketplaces.csv','↓ CSV')} {link('data/marketplaces.json','↓ JSON')}</div></div>
<form id="market-filters" class="market-controls"><div class="market-toolbar"><label class="search-label">Search marketplaces<input id="market-search" type="search" placeholder="Name, category or customer…"></label><label>Category<select id="market-category"><option value="">All categories</option>{''.join(f'<option>{esc(c)}</option>' for c in sorted({r['category'] for r in records}))}</select></label><label>Verdict<select id="market-verdict"><option value="">All verdicts</option>{''.join(f'<option value="{k}">{v}</option>' for k,v in LABELS.items())}</select></label><label>Sort by<select id="market-sort">{''.join(f'<option value="{k}">{esc(label)}</option>' for k,label,_,_ in FILTERS)}<option value="name">Marketplace name</option></select></label><label>Direction<select id="sort-direction"><option value="desc">Highest first</option><option value="asc">Lowest first</option></select></label><button type="reset" class="button">Reset</button></div>
<details class="advanced-filters"><summary>Metric filters <span>Combine Codex ≥8, saturation ≤5 and new-entrant success ≥7</span></summary><div class="metric-filters">{''.join(f'<label>{esc(label)} {"≥" if op=="min" else "≤"}<input type="number" min="0" max="{maxval}" step="0.1" placeholder="Any" data-filter="{key}" data-op="{op}" aria-label="{esc(label)} {"minimum" if op=="min" else "maximum"}"></label>' for key,label,op,maxval in FILTERS)}</div><button id="asymmetric-preset" type="button" class="button">Apply Codex / low competition / entry preset</button><p>Unknown metrics do not satisfy numeric filters. An empty result is a valid research finding.</p></details><div class="result-line"><span id="market-result-count" role="status" aria-live="polite">Showing {n} of {n} marketplaces</span><span>Scores /10 unless marked /100 or %. Burdens: higher is worse. Scroll horizontally for all metrics →</span></div></form>
<div class="table-scroll market-scroll" tabindex="0" role="region" aria-label="Marketplace comparison table"><table class="market-table"><thead><tr>{''.join(f'<th scope="col"><button type="button" data-sort="{key}">{esc(label)}</button></th>' for key,label in COLUMNS)}</tr></thead><tbody id="market-table-body">{''.join(table_row(r) for r in records)}</tbody></table></div><p id="no-market-results" class="empty" hidden>No marketplaces match. Reduce the thresholds or reset filters; unknown entrant evidence cannot pass a minimum.</p></section>{methodology()}'''
    return shell('Marketplaces',body,dataset['as_of'])


def brief(r):
    d=r.get('deep_dive')
    if not d:
        return '<p>Not yet selected for a deep dive. See the research checklist below.</p>'
    fields=('why_market','why_now','recent_entrant_finding','promising_categories','paying_categories','target','avoid','first_customer_target','validation','stop_rule','second_pass')
    body='<div class="brief-grid">'+''.join(f'<div><h3>{human(k)}</h3><p>{esc(d[k])}</p></div>' for k in fields if k in d)+'</div>'
    body+='<h3>Product hypotheses — not validated opportunities</h3><div class="idea-grid">'+''.join(f'<article><span class="eyebrow">HYPOTHESIS</span><h4>{esc(i["name"])}</h4><p>{esc(i["validation"])}</p></article>' for i in d['ideas'])+'</div>'
    for example in d.get('context_examples',[]):body+=f'<p>{link(example["url"],example["name"])}: {esc(example["finding"])}</p>'
    body+='<p class="evidence-meta">Review '+esc(d['reviewed_at'])+' · '+' · '.join(link(s,'Review source') for s in d['sources'])+'</p>'
    return body


def detail(r, dataset):
    fields=''.join(metric_card(k,m) for k,m in r['metrics'].items())
    components=''.join(f'<tr><th>{human(k)}</th><td>{WEIGHTS[k]}%</td><td>{show(v)}</td><td>{show(r["contribution"][k])}</td></tr>' for k,v in r['components'].items())
    scorecards=''.join(metric_card(k,m) for k,m in r['scores'].items())
    auto=''.join(metric_card(k,m) for k,m in r['automation'].items())
    current=date.fromisoformat(dataset['as_of']); recent=[e for e in r.get('entrants',[]) if e.get('launched_at') and months_before(current,24)<=date.fromisoformat(e['launched_at'])<=current]
    recent.sort(key=lambda e:(-(e.get('active_installs') or 0),-(e.get('reviews') or 0),e['name']))
    entries=''.join(f'<tr><td>{link(e["url"],e["name"])}<small>{esc(e.get("description", ""))}</small></td><td>{esc(e["launched_at"])}<small>{esc(e["launch_basis"])}</small></td><td>{show(e.get("active_installs"))}</td><td>{show(e.get("reviews"))}</td><td>{show(e.get("downloads"))}</td><td>{show(e.get("paying_customers"))}</td><td>{link(e["source_url"],e["date_checked"])}<small>{esc(e["note"])}</small></td></tr>' for e in recent[:10])
    entry_body=f'<p>{len(recent)} recent candidates in the collected sample; showing up to 10 by install/review proxy. Sample selection favors discoverable utilities and is not representative.</p><div class="table-scroll"><table><thead><tr><th>Product</th><th>Launch basis</th><th>Active installs</th><th>Reviews</th><th>Downloads</th><th>Paying customers</th><th>Source / checked</th></tr></thead><tbody>{entries}</tbody></table></div>' if recent else '<p class="empty-evidence">No verified launch-plus-traction examples available. This does not mean new entrants cannot succeed; the evidence is missing. Research 5–10 recent listings before selecting a product.</p>'
    dev=r['development']; devhtml=''.join(f'<div><dt>{human(k)}</dt><dd>{esc(show(v))}</dd></div>' for k,v in dev.items())
    econ=r['economics_calculation'];scenario=r['scenario'];goals=''.join(f'<tr><th>€{int(goal):,}/month</th><td>{n:,} {esc(econ["unit"])}</td></tr>' for goal,n in econ['targets'].items())
    sources=''.join(f'<li>{link(s["url"],s["title"])}<small>{esc(s.get("date_checked") or "Unverified")} · {esc(s["method"])}</small></li>' for s in r['sources'])
    body=f'''<p class="breadcrumb">{link('../index.html','← All marketplaces')} / {esc(r['category'])}</p><section class="detail-hero"><div><span class="eyebrow">RANK {r['rank']:02d} · {esc(r['owner'])}</span><h1>{esc(r['name'])}</h1><p>{esc(r['overview'])}</p><div class="hero-actions">{badge(r)}<span class="confidence">{r['confidence']} confidence</span>{link(r['official_url'],'Official marketplace ↗')}</div></div><div class="detail-score"><strong>{r['overall_score']}</strong><span>/100 conservative score</span><b>Range {r['overall_score']}–{r['overall_upper']}</b><small>{r['score_coverage']}% of score dimensions supplied; estimates included.</small></div></section>
<div class="research-notice"><strong>Eligibility: {esc(r['eligibility']['status'])}.</strong> {esc(r['eligibility']['reason'])}</div>
<div class="detail-tabs"><a href="#score">Score explanation</a><a href="#economics">Economics</a><a href="#entrants">Recent entrants</a><a href="#development">Build & test</a><a href="#deep-dive">Product hypotheses</a><a href="#sources">Sources</a></div>
<section id="score" class="panel"><div class="section-header"><h2>Why this score?</h2></div><div class="panel-body"><p>{esc(r['score_note'])}</p><div class="score-layout"><table><thead><tr><th>Dimension</th><th>Weight</th><th>/10</th><th>Contribution /100</th></tr></thead><tbody>{components}</tbody></table><div><h3>Opportunity asymmetry</h3>{bar(r['asymmetry_score'],100)}<p>Potential upper bound: {show(r['asymmetry_upper'])}/100. Missing entrant evidence keeps the point score unknown.</p><h3>Strengths</h3><p>{esc(r['overview'])}</p><h3>Weaknesses / risks</h3><p>Publisher access is conditional. Paid demand, category competition and new-entrant revenue require direct evidence. A small host integration spike is still necessary.</p><p>{link('../index.html#methodology','Full methodology and confidence rules →')}</p></div></div><details><summary>All underlying judgments and provenance</summary><div class="fact-grid">{scorecards}</div></details></div></section>
<section id="economics" class="panel"><div class="section-header"><h2>Solo developer economics</h2><span class="confidence">ESTIMATE · scenario</span></div><div class="panel-body"><div class="score-layout"><div><h3>€{scenario['price_eur']} / {scenario['billing'].replace('_',' ')}</h3><p>This is an illustrative product test price. The typical marketplace price remains {esc(show(r['metrics']['typical_pricing']['value']))}.</p><p>Assumed platform fee {scenario['fee_percent']}%, processing {scenario['processing_percent']}%, infrastructure €{scenario['fixed_cost_eur']}/month.</p><p>{esc(scenario['note'])}</p><p>{esc(econ['note'])}</p></div><table><thead><tr><th>Contribution goal</th><th>Required volume</th></tr></thead><tbody>{goals}</tbody></table></div><p><strong>Are these customer counts realistic?</strong> Unknown until new-entrant acquisition and conversion are measured. Expected support: {show(dev['support_hours_month'])} hours/month; maintenance: {show(dev['maintenance_hours_month'])} hours/month, both scoped estimates.</p></div></section>
<section id="facts" class="panel"><div class="section-header"><h2>Size, monetization and access</h2></div><div class="fact-grid panel-body">{fields}</div></section>
<section id="entrants" class="panel"><div class="section-header"><h2>Can new products succeed?</h2><span>Score: {show(r['new_entrant_success']['value'])}/10</span></div><div class="panel-body"><p>{esc(r['new_entrant_success']['note'])}</p>{entry_body}</div></section>
<section id="development" class="panel"><div class="section-header"><h2>Codex suitability & development</h2><span class="confidence">{show(r['codex_automation_percent'])}% estimated automation</span></div><div class="panel-body"><p>Small MVP: {show(dev['mvp_days'])} working days, including tests and packaging. Marketplace review delays and acquisition are outside the estimate.</p><dl class="development-grid">{devhtml}</dl><details><summary>Nine separate automation estimates</summary><div class="fact-grid">{auto}</div></details></div></section>
<section id="deep-dive" class="panel"><div class="section-header"><h2>Investigation brief & product hypotheses</h2></div><div class="panel-body">{brief(r)}</div></section>
<section class="panel"><div class="section-header"><h2>Next evidence to collect</h2></div><div class="panel-body"><ol>{''.join('<li>'+esc(t)+'</li>' for t in r['research_tasks'])}</ol><p>Direct category counts: Unknown. Incumbent concentration: Unknown. No category is presented as validated low competition.</p></div></section>
<section id="sources" class="panel"><div class="section-header"><h2>Sources & conflicts</h2></div><div class="panel-body"><ul class="source-list">{sources}</ul><p>{esc(show(r['conflicts'])) if r['conflicts'] else 'No conflicting numeric claims recorded. Source access failures are retained in the research log and are not evidence of abandonment.'}</p></div></section>'''
    return shell(r['name'],body,dataset['as_of'],prefix='../')


def opportunities(dataset):
    records=[r for r in dataset['marketplaces'] if not r['rejected']][:10]
    body='<section class="page-intro"><span class="eyebrow">TOP OPPORTUNITIES</span><h1>Choose a market to investigate.</h1><p>The Top 3 and Top 10 are selected from the same scoring model. These are research priorities, not validated product recommendations.</p></section>'+shortlist(records)
    for r in records:
        body+=f'<section id="{r["id"]}" class="panel"><div class="section-header"><div><span class="eyebrow">RANK {r["rank"]:02d} · {r["overall_score"]}–{r["overall_upper"]} /100</span><h2>{link("marketplaces/"+r["id"]+".html",r["name"])}</h2></div>{badge(r)}</div><div class="panel-body">{brief(r)}<p>{link("marketplaces/"+r["id"]+".html","View evidence, prices, build estimates and risks →")}</p></div></section>'
    return shell('Top Opportunities',body,dataset['as_of'],'opportunities')


def history_page(dataset):
    body='<section class="page-intro"><span class="eyebrow">HISTORICAL OBSERVATIONS</span><h1>Track changes, not assumptions.</h1><p>A rerun is not a new market observation. Deltas require matching source scope, units and exact observation dates.</p></section><div class="history-grid">'
    for days,window in dataset['changes'].items():
        body+=f'<section class="panel"><div class="section-header"><h2>{days}-day changes</h2></div><div class="panel-body"><span class="history-icon" aria-hidden="true">↗</span><h3>{window["status"]}</h3><p>{window["matched_metrics"]} comparable measurements.</p>'
        for change in window['changes']:body+=f'<p>{esc(change["marketplace"])} · {human(change["metric"])}: <strong>{change["net_change"]:+,}</strong></p>'
        body+='</div></section>'
    body+=f'</div><section class="panel"><div class="section-header"><h2>Collection coverage</h2></div><div class="panel-body"><p>{dataset["snapshot_count"]} source snapshots preserved. Public JSON adapters refresh WordPress and Obsidian. Other marketplace facts, pricing policies and qualitative judgments require reviewed imports. No scheduled AI research or revenue estimation runs.</p><p>{link("data/marketplace-refresh.json","Latest refresh report")} · {link("data/marketplace-history.json","Historical measurements JSON")}</p><p>New-entrant review and install observations are also retained in snapshots for future cohort analysis; the current 7/30/90-day view compares exact marketplace counts. Lower bounds and changed scopes are excluded.</p></div></section>'
    return shell('Changes',body,dataset['as_of'],'changes')
