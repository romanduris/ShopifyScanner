# Opportunity evidence imports

Use `Data/Sources/opportunities.json` with an envelope of
`{"schema_version": 1, "apps": {"https://apps.shopify.com/app-slug": {}}}`.
Every keyed app must first exist in `Data/Sources/apps.json`. Keys and app
references use canonical Shopify app URLs without query parameters.

The file starts empty because existing listing metadata cannot substantiate all
the new gates. A missing section is allowed and remains Unknown. A present
section must contain valid evidence; malformed values stop generation before
existing outputs are changed.

A complete **synthetic test example**, never loaded as production evidence, is
in [opportunity_evidence.json](../tests/fixtures/opportunity_evidence.json).
Use its structure and replace all claims, dates, identifiers and sources with
actual research. Do not copy the example's conclusions into production data.

Each evidence object has:

- `observed_at`: the date the claim was actually checked, in `YYYY-MM-DD`.
- `summary`: the claim, its relevance, and any attribution or limitations.
- `sources`: a nonempty list of HTTPS source URLs supporting the claim. Dates
  must not be in the future. Source format validation does not verify truth.

## `incumbents`: direct-competitor evidence

A list with `url`, optional `name`, `launched_at` and the common evidence fields.
The summary must explain why this app solves the same core merchant problem and
is still active. A category page alone does not demonstrate direct competition.
Only incumbents predating the entrant, older than 24 months, and checked within
90 days count. Self references and duplicate incumbent URLs are rejected.

## `payments`: evidence that merchants pay for the problem

A list with the common fields and:

| Field | Values / meaning |
| --- | --- |
| `subject_app_url` | This candidate or one of its documented direct incumbents. |
| `kind` | `paying_customers`, `merchant_payment`, `mrr`, `arr`, `cumulative_revenue`. |
| `value` | A finite non-negative number; customer counts must be integers. Zero cannot pass demand. |
| `currency` | Three-letter uppercase currency code for payment/revenue amounts; unnecessary for customer counts. |
| `period_end` | Actual end of the period represented by the figure, not the article's publication or recheck date. Must be within 365 days to qualify. |
| `evidence_type` | `developer_statement`, `independent_report`, or `merchant_statement`. |

Sources must show actual payment or paying customers. A paid plan, estimated
revenue based on reviews, or a free-install count is not acceptable. No conversion
between cumulative revenue, ARR and MRR is performed. Keep the period and
attribution explicit in `summary`. Incumbent evidence only qualifies when that
incumbent's direct-competition assessment is current.

## `traction`: recent comparable observations

One object with the common fields and `metric` (`paying_customers`,
`active_merchants`, or `reviews`), `start_at`, `end_at`, integer `start_value`,
integer `end_value`, and boolean `comparable`.

The source(s) must substantiate both counts and observation dates for this exact
app. Explain the population definition in `summary`. Accounts across an entire
developer portfolio, lifetime installs, migrated users and changes in metric
definition must not be treated as new active customers. Mark observations
incomparable if their bases cannot be reconciled.

Count windows must span 30–90 days and end within 30 days of calculation.
At least 5 net customers per 30 days are required; zero or negative measured
growth fails the threshold. A window beginning before launch needs research.
Reviews, even numerous recent ones, remain a proxy and cannot pass Proven entry.
The gate also requires a qualifying direct incumbent. Reporting active merchants
does not imply all of them pay; payment is assessed separately by Proven demand.

## `build`: explicit independent implementation assessment

One object with the common fields and:

- `work_days`: positive working-day estimate for one developer, including
  implementation, installation, configuration, necessary billing, isolation,
  error handling and relevant tests. Limit: 10 days.
- `monthly_cost_usd`: non-negative operating-cost estimate. Limit: $50/month.
- `support_hours_monthly`: non-negative maintenance/support estimate. Limit: 2.
- `scope`: core merchant workflow and acceptance criteria.
- `exclusions`: omitted features and non-development lead times.
- `dependencies`: Shopify/external APIs and critical dependencies.
- `validation`: prototype or feasibility checks and relevant test results.
- `cost_basis`: assumed merchant count, traffic, storage, paid APIs and support
  workload. A cost estimate without workload is incomplete.
- `core_workflow_covered`, `quality_included`, `platform_access_verified`:
  booleans. All must be true to pass; absent/null means Unknown, false means Fail.

The textual assessment fields must be nonempty to pass. Cite platform
documentation and accessible prototype/assessment reports. Record the date
constraints were verified. This is an estimate of an independently built useful
product, not copying proprietary code or matching the incumbent feature for
feature. A subset too small to solve the core problem must not be marked covered.

## `weakness`: recurring unmet need and our response

One object with the common fields, `target_segment`, `differentiation`, boolean
`unresolved`, boolean `fits_build_scope`, and a `reports` list.

Each report has `merchant_id`, `published_at`, `summary`, and nonempty `sources`.
Use a stable public merchant identifier, not private personal information. Two
reports by the same merchant count once, ignoring case and surrounding spaces.
At least two independent merchants must report the same need within 180 days.
Their reports cannot postdate the weakness assessment.

Explain the shared problem in the weakness summary, check the current product
and developer responses, and tie the proposed improvement to the build scope.
Do not convert a historical complaint into an assertion of a current defect.
An unverified claim stays Unknown; an explicitly resolved weakness or an
out-of-scope solution fails. The assessment expires after 90 days.

## Outputs and validation

Run `python 1.Stats.py --as-of YYYY-MM-DD` after completing a dated import.
`Data/Analysis/latest.json` and `HTML/data/analysis.json` contain the status,
individual gates, source dates, factors, original evidence and next actions.
`research_queue.json` includes missing-evidence tasks and workflow discovery
links, not automatically collected search results.

Omit sections still under investigation rather than inventing passing claims.
Malformed dates, future observations, invalid URLs, booleans used as counts,
negative/non-finite values, unsupported metric types, and orphan app references
fail validation. Numeric screening and schema checks cannot replace reviewing
the sources and the relevance of their claims.
