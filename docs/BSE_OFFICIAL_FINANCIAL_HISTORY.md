# Official BSE financial-history acquisition

## Current bounded status

The canonical BSE XBRL ingestion boundary is implemented and remains the only
approved BSE route for reported financial facts:

`BSE result metadata -> official XBRL -> exact ISIN + BSE-code identity ->
immutable filing -> immutable FinancialFact`

It preserves statement scope, decimal value, currency, unit, scale, revision
lineage, raw XBRL reference, and point-in-time availability.  It never derives
EBITDA, cash flow, a scale, or a publication time from a period date.

The existing local pilot comprises one consolidated Q1 FY2026-27 filing for
each of `APOLLOHOSP`, `SAFARI`, and `ORIENTTECH`: three filings and 21 direct
official BSE facts.  Local XBRLs whose exchange publication time is not present
are eligible no earlier than the system's real first-observed time.  Their
provenance is `SYSTEM_FIRST_OBSERVED`, not an asserted exchange publication
timestamp.

## #036 acquisition result

On 2026-08-27, the approved existing metadata URL
`https://www.bseindia.com/corporates/Comp_Results.aspx?Code=<BSE code>` was
checked read-only for the APOLLOHOSP BSE code (`508869`).  It returned the
current generic BSE application shell rather than the static result table that
the existing official parser requires.  The response contained no result rows,
financial-year fields, or official XBRL links.  The parser correctly produced
`BSE_PUBLIC_RESULTS_INTERFACE_UNAVAILABLE` and created no filing or fact.

The repository has no separately documented BSE machine-readable financial
result-index contract, and this task does not authorize browser automation,
private/undocumented endpoints, or a manual bulk-XML workflow.  Consequently,
automatic official historical population stops here rather than guessing a new
transport.  A future continuation needs one of the following approved inputs:

1. a documented BSE result-index/XBRL discovery contract that exposes filing
   publication time and official XBRL URLs; or
2. user-supplied official BSE XBRLs plus authoritative filing metadata where
   available.

## Existing evaluator unlock matrix

| Existing diagnostic | Exact current production input | Minimum comparable periods | Current BSE pilot | Remaining official requirement |
| --- | --- | ---: | --- | --- |
| Financial trend / five-year CAGR | annual revenue, EBITDA, PAT, EPS | 6 annual observations | 0 annual | six compatible annual reports, including directly reported EBITDA |
| Return ratios | annual PAT, EBIT, equity, plus configured ROCE capital inputs | 1 annual (2 for average basis) | none | EBIT/equity plus debt/cash for `equity_debt_cash_v1`, or assets/current liabilities for `assets_current_liabilities_v1` |
| Cash flow quality | annual CFO, capex, PAT | 2 annual | none | two annual cash-flow statements with explicit capex sign |
| Leverage | annual debt, equity, cash, EBIT, finance cost | 1 annual | none | directly reported balance-sheet/debt and income metrics |
| Working capital | revenue, receivables; full CCC also needs COGS, inventory, payables | 1 period (2 for average basis) | none | compatible income and balance-sheet facts |
| Earnings acceleration | quarterly revenue | 5 quarterly observations | 1 quarterly | four further comparable quarters |
| Latest-quarter QoQ/YoY | quarterly revenue, EBITDA, PAT, EPS | 5 quarterly observations | 1 quarterly; no EBITDA | four further quarters and direct EBITDA mapping |
| Margin trajectory | quarterly revenue and EBITDA | 5 quarterly observations | 1 quarterly; no EBITDA | four further quarters and directly reported EBITDA |
| Ownership / institutional holdings | shareholding observations | 2 observations | none | separate official shareholding filings; financial results cannot substitute |
| Order-book trend | order book, order inflow, revenue | 1–2 observations | none | explicit order-book disclosure; financial results cannot substitute |
| Valuation enrichments | EPS, shares, EBITDA, equity/debt/cash plus stored market price | latest compatible values | EPS only | separately reported shares/EBITDA/balance-sheet values where present |

The existing BSE mapper intentionally recognizes direct revenue, other income,
PBT, PAT, basic EPS, finance cost, depreciation, total assets, and total
liabilities.  It does not infer EBITDA, EBIT, CFO, capex, debt, equity, shares,
or working-capital values from other concepts.  Those missing direct mappings
remain explicit blockers even after more filing periods are available.

## Boundaries

- Yahoo snapshots remain secondary reconciliation evidence only.  They cannot
  create, fill, scale, date, or make canonical BSE `FinancialFact` values PIT
  eligible.
- Standalone and consolidated facts are selected as a whole scope; they are
  never mixed silently.
- Historical Brain executions consume stored canonical evidence only and make
  zero provider requests.
