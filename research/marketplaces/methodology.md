# Marketplace research and implementation record

Research baseline: September 9, 2026. This is a **provisional comparison**, not a
validated claim of profitable opportunities. The 66-market universe includes the
18 requested ecosystems, specialized creator/developer tools, CAD, education,
wearables, smart home, NAS, networking, office and enterprise software.

## Integration plan and repository inspection

The original repository uses Python standard-library modules `1.Stats.py`,
`app_analysis.py`, and `opportunity.py`. It validates sourced Shopify imports,
maintains content-addressed listing snapshots, evaluates strict opportunity
gates, and renders a static HTML catalog. Its original input schema and scoring
remain unchanged. Existing CSS, JavaScript, source files, tests, README and Pages
workflow were inspected before implementation.

The implementation plan was to retain Shopify as a specialized module, add an
independent marketplace model/collector/renderer, stage the complete build, and
extend the existing Pages workflow. No application backend is introduced.
`build_site.py` publishes a unified landing page and `shopify.html`; the original
Shopify command is still available for its standalone build.

The first-pass candidate list is `candidates.tsv`. The authoritative, editable
research input is `Data/Marketplaces/sources/research.json`. The TSV is a record
of discovery priors, not a second source of current scores.

## Collection and realistic availability

| Data | Collection method | Limitation |
| --- | --- | --- |
| Identity, publishing route, SDK references | Official developer pages and marketplaces | A reachable page does not verify every policy or EU payout eligibility. |
| Billing and revenue share | Manual review of official policy pages | Terms vary by product, date, threshold and agreement; unverified rates stay unknown. |
| WordPress count and listing observations | Official public Plugins API, new/popular/five utility searches | Bounded selection-biased sample; downloads include updates; install counts are buckets. |
| Obsidian plugin count | Official public JSON registry | No paid adoption or revenue inference; registry entries need not equal active plugins. |
| Shopify recent listing proxies | Existing sourced Shopify import | Established-app-biased sample; first-party listings excluded from entrant scoring. |
| Other entrant success | Reviewed listing or publisher evidence imports | No fabricated launch dates, customers or revenue. Many ecosystems remain unknown. |
| Category saturation and distribution | Explicit low-confidence research priors | No representative category census or observed conversion rate. |
| Development, support, infrastructure | Scoped workload estimates | No host SDK spike has been performed. These are not measured Codex benchmarks. |
| Slovak/EU publisher access | Conditional eligibility by default | Buyer availability does not prove developer merchant access; actual onboarding is untested. |
| Historical changes | Exact dated, comparable observations | No interpolation, extrapolation, or growth before a baseline. |

Automatic refresh is deliberately limited to public JSON sources. It does not
crawl all 66 marketplaces or run an AI research service. Other facts are reviewed
imports with persistent check dates. Direct source availability results (including
403s and replaced URLs) are recorded in `source-checks.json`. A blocked fetch does
not mean that a marketplace is abandoned or closed to developers.

## Evidence and confidence

Every important measurement has `value`, `sources`, `date_checked`, `kind`,
`confidence`, and an explanation. `null` means unknown. `FACT` is an attributed
observation, not an audit of the publisher. `ESTIMATE` is a scoped scenario;
`INFERENCE` is interpretation. Platform user totals are explicitly scoped and
lower-bounded where the source says “more than”; they are not app buyers.

All composite rankings are LOW confidence unless at least three recent traction
examples and all weighted dimensions are available; then they can be MEDIUM.
This implementation deliberately does not automatically issue HIGH composite
confidence. Manual judgments older than 90 days stop contributing to the score.
Rerunning the scanner never changes their verification dates.

## Scores and missing values

The requested 20/15/15/15/10/10/5/5/5 weights are preserved. Low friction averages
publishing, support, platform and legal/compliance burden. Marketplace size has
zero direct weight. Scores are research rubrics, never success probabilities.

Unknown weighted dimensions retain their 0–10 interval. The visible overall
number is the conservative lower bound, with the upper bound displayed beside
it. Known dimensions are not renormalized. Ranking by lower bound favors markets
with more evidence: **coverage bias is unavoidable and is disclosed**. Overlapping
ranges cannot establish a statistically reliable winner. Rejected markets retain
all scores but are sorted after non-rejected ones. Interactive sorting can inspect
the raw dimensions independently of the default eligibility ordering.

Codex automation percent = 10 × mean of the nine separate 0–10 estimates. Codex
Advantage is the same mean, rounded to one decimal. The unit/integration/UI tests,
local simulation, debugging, packaging, deployment and documentation are all part
of the estimate, not only source generation. Device and editor tests still need
human involvement. Profiles describe a narrow MVP, not every app in the ecosystem.

A recent entrant must have a documented launch within the last 24 calendar months
and traction checked within 90 days. A directory `added` date is labeled as such;
it may differ from the first commercial release. Each qualifying third-party
example with at least 100 active installs or 10 reviews contributes 1.5 points,
capped at 6. With actual evidence of at least 5 paying customers per example,
the score can rise to 7–10. Downloads alone never qualify. Without qualifying
examples the value is unknown, not zero. This is an intentionally modest proxy
rubric, not a validated measurement of entrant success probabilities.

Asymmetry = 100 × geometric mean of normalized economics, demand, distribution,
entrant success, Codex / geometric mean of (1 + normalized saturation,
development effort, support, infrastructure, publishing burden). Inputs are
0–10 and divided by 10 first. Missing factors keep the point score null; the
potential upper bound assumes entrant success of 10 and is not a forecast.

Strong Opportunity requires score ≥75, an eligible publication route, at least
three recent paid entrant examples and non-LOW confidence. A conditional route
or review/install proxies alone cannot qualify.

## Economics

The scenario price is a **hypothetical test price**, not typical market pricing.
Marketplace median prices stay unknown until a defensible sample is collected.
Targets use `ceil((monthly contribution goal + fixed infrastructure cost) /
net unit contribution)`. Annual prices are divided by 12. One-time licenses use
new sales per month and are never presented as MRR. Fees, tax, refunds, churn,
manual support and other exclusions are shown. No exchange rates are invented.
The Xero rejection explicitly records the mandatory AUD-denominated tier cost;
a generic EUR scenario must not be read as including that fee.

## Second-pass review and Top 10

`scoring-review.json` retains the first-pass shortlist and the source-driven
adjustments. Review increased Bubble competition, Odoo support and Atlassian
platform risk; reduced the assumption of marketplace-only monday distribution;
and withheld the Superhive native-billing score pending readable seller terms.
The existing Shopify and live WordPress entrant proxies then enter the same
formula as every other market. No named ecosystem has a bonus.

Top 10 and Top 3 are automatically selected from the final scores. Their pages
include investigation briefs, product hypotheses, risks, workload, fees and
validation steps. There are **not** five to ten proven recent paid entrants for
every Top 10 ecosystem. Missing evidence is stated in each brief; the WordPress
and Shopify pages show actual sampled recent listings. The monday/Pioneera story
is portfolio-level, historically dated, and involved community marketing and
agency resources; it is context, not proof of current solo marketplace-only entry.
Generated product ideas never count as demand validation.

## History, reliability and deployment

Source fingerprints exclude calculation time. A new source observation can
create a new snapshot; an identical rerun cannot fabricate daily history. Exact
7/30/90-day deltas require matching scopes, units and exact-count relations at
both dates. Lower bounds and different dataset populations cannot be subtracted.
All raw entrant observations remain in source snapshots; the initial trends view
compares marketplace counts, not inferred revenues or ranking improvements.

The build validates all inputs, renders every page and verifies local links in a
temporary directory before replacing local outputs. A failed adapter preserves
its previous successful observations; complete collection failure stops a refresh.
A failed build never reaches the single Pages deploy job. The last successful
GitHub Pages artifact remains public. The daily and manually dispatched workflow
persists successful observations and snapshots with a normal non-force push;
it fails if main advanced during the build.

GitHub Pages serves only static HTML, CSS, JavaScript and downloadable JSON/CSV.
Pages use embedded server-generated content, so no Codespace, fetch endpoint,
API credential, browser session or local server is required to read them.
