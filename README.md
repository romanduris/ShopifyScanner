# Opportunity Scanner

Compare **66 software marketplaces** for a solo developer building small products
with Codex, alongside the existing Shopify app opportunity scanner.

Public dashboard: https://romanduris.github.io/ShopifyScanner/

```bash
# Build both modules from the last successful inputs (no network required)
python3 build_site.py

# Refresh WordPress/Obsidian public JSON adapters and build both modules
python3 build_site.py --refresh

python3 -m unittest discover -s tests -v
```

The site includes **Marketplaces**, **Shopify Apps**, **Top Opportunities** and
**Changes**. Search, category/verdict filters, combined numeric thresholds and
sortable columns work in static JavaScript; each marketplace has a permanent
detail page. CSV/JSON exports include provenance. Pages also remain readable
without JavaScript and with Codespaces stopped.

Market rankings are **provisional**: facts, estimates and inferences are labeled,
unknown entrant evidence stays unknown, and overall scores show conservative
bounds. Small-product prices are hypothetical scenarios, not marketplace medians.
Top 3/10 entries are investigation priorities, not validated opportunities.
The baseline does not establish five to ten paid recent entrants per ecosystem.

The existing `pages.yml` workflow now builds both modules on pushes/PRs. A daily
05:17 UTC schedule and `workflow_dispatch` refresh the two public JSON adapters,
preserve observations/snapshots and deploy the latest successful build. Other
marketplace policies and judgments require reviewed research imports; the schedule
does not automatically research every marketplace or fabricate fresh check dates.
Complete collection failure or build failure prevents deployment and retains the
last public version. No competing deployment workflow or production backend exists.

- `scanner/marketplaces/`: model, validation, adapters, scoring and static renderer.
- `Data/Marketplaces/sources/research.json`: editable, sourced research and scoped estimates.
- `Data/Marketplaces/sources/observations.json`: last successful automatic observations.
- `Data/Marketplaces/history/`: source snapshots, with no invented baseline growth.
- `research/marketplaces/`: candidate universe, source checks, methodology and review record.
- `HTML/index.html`: marketplace comparison; `HTML/shopify.html`: original Shopify module.

See [marketplace methodology](research/marketplaces/methodology.md) for collection
coverage, scoring formulas, rejection reasons, confidence and research limitations.

## Existing Shopify module

The Shopify-specific documentation below remains applicable to the standalone
`1.Stats.py` command. That command generates the Shopify page at `HTML/index.html`;
run `build_site.py` to regenerate the unified production site before publishing.
The unified workflow supersedes the former Shopify-only deployment behavior.

Find Shopify apps launched within approximately the last 24 months that are
currently demonstrating strong traction, despite competing against established
apps, and whose core functionality can be independently rebuilt by a solo
developer with Codex in roughly 1–2 weeks.

The scanner applies **Proven demand → Proven entry → Easy build**, then requires
a documented weakness we can address. It builds a static dashboard from sourced
JSON imports. It does not scrape Shopify or call an AI API.

## Run locally

Python 3.10+; only the standard library is required.

```bash
python3 1.Stats.py
```

This reads `Data/Sources/`, calculates statistics, saves results in `Data/Stats/` and `Data/Analysis/`
and generates `HTML/index.html`. It does not run tests, commit, push or publish
the website. It processes existing inputs; it does not collect new market data.

To test and preview the generated website:

```bash
python3 -m unittest discover -s tests -v
python3 -m http.server 8000 --directory HTML
```

Open http://localhost:8000. `HTML/index.html` also works directly from the filesystem.
GitHub Pages URL: https://romanduris.github.io/ShopifyScanner/

For a reproducible calculation date:

```bash
python3 1.Stats.py --as-of 2026-09-08
```

Default paths are relative to the script location, not the current working
directory. Use `--root /path/to/project` to process another input dataset.

## Run the GitHub workflow

The workflow validates the code, runs tests, builds the dashboard and publishes
it when GitHub Pages is configured. It runs automatically on pushes to `main`.
Pull requests run checks without publishing.

To run it manually:

1. Open the repository's **Actions** tab.
2. Select **Validate and publish dashboard**.
3. Click **Run workflow**, select **main**, then confirm **Run workflow**.

Alternatively, from an authenticated GitHub CLI in this repository:

```bash
gh workflow run pages.yml --ref main
gh run watch
```

The remote workflow uses files already pushed to GitHub. Local edits must be
committed and pushed before the workflow can use them. Running `1.Stats.py`
on its own does not trigger GitHub Actions.

For initial deployment, select **Settings → Pages → Build and deployment →
Source → GitHub Actions**. If Pages is not configured, the workflow completes
validation, uploads the `github-pages` artifact and skips deployment. After
configuring Pages, rerun the workflow. Only `HTML/` is published.

The Shopify module still processes reviewed imports; its data is not scraped on
a schedule. The unified workflow refreshes supported marketplace adapters and
persists their successful observations, as described above.

## Data

- `Data/Sources/market_facts.json`: published market size, main categories,
  source URLs and observation dates. Unknown market-wide counts are `null`.
- `Data/Sources/apps.json`: versioned envelope `{"schema_version": 1, "apps": [...]}`;
  20 discovery-page selections per main category: 140 slots, 119 unique apps,
  plus two original references (121 unique apps). This is not a representative sample.
- `Data/Stats/latest.json`: calculated statistics and underlying app records.
- `Data/Stats/categories.csv`: category counts; an empty cell means unknown.
  Category counts can sum to more than the number of unique apps.
- `Data/Stats/history/`: a snapshot when source data changes. Identical inputs
  do not create extra snapshots or fabricated daily growth.
- `Data/Sources/opportunities.json`: dated payment, customer growth, direct
  competitor, build and weakness evidence. Empty until research is imported;
  missing evidence never qualifies an app.
- `Data/Analysis/research_queue.json`: missing-evidence tasks and workflow search
  links for discovering young entrants, also downloadable from the dashboard.
- `HTML/`: the website, CSS and downloadable JSON/CSV copies.

Each app requires a direct App Store URL, name and developer,
observation date, `category_ids` and `pricing_model`. Examples also include
optional `rating`, `review_count`, `entry_monthly_usd`, `launched_at`,
`built_for_shopify`, category sources, team evidence and revenue disclosures.
Publisher URLs are optional; publisher names do not establish team size.
Use `null` for unknown numeric values, not zero.

Supported pricing models: `free`, `freemium`, `paid`, `free_to_install`, `unknown`.
`entry_monthly_usd` is the lowest positive recurring monthly price in USD;
annual, one-time and usage-based prices do not belong in this field. Plan
availability is not evidence of revenue. Disclosures distinguish `mrr`, `arr`
and `cumulative_revenue`, including source, currency, period and publication
date. Figures from different periods are not added together.

Duplicate app URLs are normalized by removing query parameters and trailing
slashes; the newest observation wins. Conflicting records from the same day
cause an error. Review deltas over 1/7/30 days require observations on both
exact dates. Negative net changes are valid. Missing days are not interpolated;
`matched_apps` reports coverage. Changing the calculation date does not update
source observation dates. Change `observed_at` only after a new verification.

## Collaboration

Keep the website, source code, comments, messages, data annotations and
documentation in English. Chat with the user in Slovak by default, or in English
when appropriate to their message.

After completing and verifying a task, commit and push its changes to `main`
and provide a verified website link. The personal `spolupraca-sk` skill is stored
outside this repository at `/home/codespace/.codex/skills/spolupraca-sk/SKILL.md`.

## Source availability

On September 8, 2026, the [Shopify App Store](https://apps.shopify.com/) reported
more than 16,000 apps. This is a published lower bound, not an exact inventory
of active apps. Market-wide category counts and total revenue are not verified.

[Shopify's terms](https://www.shopify.com/legal/terms), section 1.9, restrict
automated access and monitoring. A permitted source must be secured before
introducing scheduled collection. This version uses local inputs only;
technical accessibility or robots.txt alone does not establish permission
for automated collection.

## Opportunity analysis

`1.Stats.py` validates inputs, saves snapshots and generates the page.
`opportunity.py` validates evidence, evaluates the gates and builds the research
queue. `app_analysis.py` keeps the historical success proxy and renders the
opportunity table. All use the Python standard library and local imports.

The default view shows young candidates and apps with an unknown launch date.
Each row has a status and four evidence checks. Expand it for reasons, sources,
dates, estimates and missing research. The **Show** filter separates qualified
opportunities, research tasks, rejected candidates and established competitors.
Build estimates and filters use documented working days; missing assessments
stay Unknown. The original complexity profiles remain in the expanded context.
**Compare peers** includes established apps and resets other filters. Section
collapse preferences remain in the reader's browser; the page needs no backend.
The initial candidate view also works without JavaScript.

### Gates and thresholds

These are explicit initial screening rules, not calibrated predictions:

| Check | Required evidence |
| --- | --- |
| Launch window | Listing launch date from 24 calendar months before the calculation date through that date, inclusive. Unknown dates need research; older apps remain comparison context. |
| Proven demand | A positive payment or paying-customer claim for the entrant or a documented direct incumbent, with a payment period ending within 365 days. Statements are attributed, not audited. A price, free-plan usage or review count is insufficient. |
| Proven entry | Comparable paying-customer or active-merchant counts spanning 30–90 days and ending within 30 days. At least 5 net customers per 30 days. At least one active direct competitor must predate the entrant and be older than 24 months. Reviews are only a proxy. |
| Easy build | An explicit independent core scope, exclusions, dependencies, validation and workload/cost assumptions. At most 10 working days including quality checks, $50/month operating costs and 2 support hours/month. Core workflow coverage, quality checks and platform access must be verified. Publishing/review delays are outside development effort. |
| Exploitable weakness | At least two independent merchant reports within 180 days about the same unmet need. Current verification that it remains unresolved, a target segment and a differentiator that fits the proposed build. |

Direct-incumbent, build and weakness assessments expire after 90 days. Merely
rerunning the scanner never refreshes observations. Thresholds live in
`opportunity.POLICY` and are exported with every analysis.

`Pass`, `Fail` and `Unknown` are distinct. Missing evidence yields **Needs
research**, a documented failed gate yields **Rejected**, and older listings are
**Established app** regardless of their other signals. Only all-pass candidates
are **Qualified**. An empty qualified list is a valid outcome.

### Opportunity score

`Opportunity = 100 × Demand × New-entrant traction × Buildability × Weakness`

All factors are on a 0–1 scale:

- Demand: 1 after actual payment is evidenced; no currency conversion or revenue
  extrapolation is used.
- Entry: `min(1, net customers per 30 days / 20)`.
- Build: `min(1, (15 − working days) / 10)`.
- Weakness: `min(1, independent recent merchant reports / 5)`.

The score is `null` until every check passes. Missing factors are never dropped
from the product or renormalized. The weights are a transparent research rubric,
not a probability or projected return. Strong new-entrant growth can qualify in
a crowded category; a large category count is not an automatic penalty.

The former Success score is retained only in expanded historical context and an
optional context sort. Its weights remain demand 35%, satisfaction 15%, observed
review growth 20%, monetization 20%, age/Built for Shopify 10%, with missing
dimensions shown through coverage and bounds. It no longer contributes to
Opportunity. A simple profile cannot pass Easy build.

Analysis output schema is now **2**. `research_priority` remains a compatibility
alias for the new opportunity score (usually `null` without evidence). Consumers
must use `opportunity.status`, `opportunity.gates` and `opportunity.score` rather
than interpreting it as the old complexity-weighted success score. Source and
statistics schemas remain version 1.

### Research and discovery workflow

1. Open **Discover more young entrants** or download `research_queue.json`.
   Search focused workflows and direct alternatives. Verify launch dates before
   selection; do not select only the highest lifetime review counts.
2. Import each verified listing into `Data/Sources/apps.json`. All imported apps
   are evaluated, with no top-N cap. Record provenance and actual observation
   dates. Unknown classification remains a hypothesis until assessed.
3. Follow the candidate's missing-evidence tasks. Record comparable customer
   counts, payment evidence and direct competition; then assess scope and a
   current exploitable weakness in `Data/Sources/opportunities.json`.
4. Run the scanner and inspect the gate reasons. New dated app observations
   generate listing snapshots; evidence-only edits update analysis without
   fabricating a market snapshot.

The original sample selected up to 20 high-review apps from each of seven
discovery pages. It contains 121 unique apps, only 7 in the launch window as of
September 8, 2026. It is biased toward established apps. The discovery queue is
an actionable research plan, not a claim that new listings have already been
collected. Automated collection is not active. The first gate-based run has
7 apps needing research, 114 established apps and no qualified opportunities.

`Data/Sources/competition.json` holds broad sourced category populations,
including 156 survey-category apps observed September 8, 2026. These populations
include adjacent products and do not count direct competitors. Zero sample
peers also does not mean no competition. Zigpoll remains established comparison
context, rather than a young candidate.

Existing `assessments.json` provides optional workflow classifications and
historical complaint notes. Those notes do not automatically satisfy the new
weakness gate. Existing revenue disclosures without a structured `period_end`
must be mapped to payment evidence after verifying their actual period; a fresh
publication date must not make old revenue appear current.

See [the evidence format](docs/opportunity-evidence.md) for fields and a complete
synthetic example. Review counts on category cards and separately indexed detail
pages can disagree; `source_crawled_hint`, `review_source_url` and `source_note`
preserve that provenance. Cached counts cannot establish current customer growth.
