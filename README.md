# Shopify Opportunity Scanner

The first module builds statistics and a static dashboard from verified public
facts and JSON imports. It does not scrape Shopify or call an AI API.

## Run locally

Python 3.10+; only the standard library is required.

```bash
python3 1.Stats.py
```

This reads `Data/Sources/`, calculates statistics, saves results in `Data/Stats/`
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
  currently two real, manually selected apps, not a representative market sample.
- `Data/Stats/latest.json`: calculated statistics and underlying app records.
- `Data/Stats/categories.csv`: category counts; an empty cell means unknown.
  Category counts can sum to more than the number of unique apps.
- `Data/Stats/history/`: a snapshot when source data changes. Identical inputs
  do not create extra snapshots or fabricated daily growth.
- `HTML/`: the website, CSS and downloadable JSON/CSV copies.

Each app requires a direct App Store URL, name, developer and publisher URL,
observation date, `category_ids` and `pricing_model`. Examples also include
optional `rating`, `review_count`, `entry_monthly_usd`, `launched_at`,
`built_for_shopify`, category sources, team evidence and revenue disclosures.
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
