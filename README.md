# Shopify Opportunity Scanner

The first module builds statistics and a static dashboard from verified public
facts and JSON imports. It does not scrape Shopify or call an AI API.

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

There is no daily schedule yet: running the same inputs again does not produce
new market observations. The workflow does not modify or commit repository data.

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

`1.Stats.py` orchestrates validation, snapshots and page generation.
`app_analysis.py` separately implements scoring, workflow hypotheses, competition
comparisons and the app table. Both use the standard library and local imports.
`HTML/assets/app.js` adds client-side category filters, search, sorting, peer
comparison and accessible section/row toggles. Collapse preferences stay in the
reader's local browser storage. No backend is needed.

Additional files:

- `Data/Sources/assessments.json`: sourced analyst notes and optional workflow/MVP
  overrides. Complaint evidence currently covers six apps; other complaints
  remain unknown. Historical complaints do not establish current defects.
- `Data/Sources/competition.json`: sourced marketplace category populations.
  These are broader than direct competitors and separate from sample peer counts.
- `Data/Analysis/latest.json` and `HTML/data/analysis.json`: ranked app assessments,
  component scores, evidence coverage, complexity hypotheses and known peers.

The selection uses the 20 highest review counts among apps visible on each of
seven category discovery pages, not the global top 20 in each category. Root
pages include recommendations and overlap. Category buttons therefore represent
**discovery groups**, not verified exclusive app taxonomy membership. The two
original references are also included in their sourced categories.

Review counts and ratings come from discovery cards. Price, developer, launch
and integration metadata comes from separately indexed detail pages, which can
be older. `source_crawled_hint`, `review_source_url` and `source_note` retain that
provenance; the table exposes index age. Short listing excerpts are attributed to
the linked listing. Workflow descriptions and proposed MVPs are our hypotheses.
Recheck a shortlisted app before using its pricing or constraints commercially.

Success weights: demand 35%, satisfaction 15%, observed growth 20%, monetization
20%, age/Built for Shopify 10%. The dashboard explains each normalization.
Missing dimensions are excluded from the displayed score and exposed through
coverage and conservative/optimistic bounds. Without historical observations,
growth is unknown, never an invented zero-growth measurement.

Research priority uses the conservative success bound, estimated MVP complexity
and paid-plan availability. It is a research ordering, not profit, revenue or
proof of a viable business. Complaint severity is not scored until coverage is
sufficient. Complexity estimates describe a limited independent MVP, not feature
parity with the incumbent; validate platform access and a development-store
prototype before committing to a product.

To analyze candidates, open **Apps**, select a discovery category, enable
**Paid plan observed**, and set **Simple · 1–2**. Expand a row for listing evidence,
team statements, source freshness, proposed scope, tests and complaint notes.
**Compare peers** resets other filters and shows the whole known workflow group.
A zero peer count means none identified in this sample, not no competition.
