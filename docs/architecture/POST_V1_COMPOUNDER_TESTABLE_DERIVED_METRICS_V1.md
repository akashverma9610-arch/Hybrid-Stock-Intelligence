# Compounder Testable Derived Metrics V1

**Status: `RESEARCH ONLY / PROPOSED / NOT APPROVED / NOT ACTIVE / NON EXECUTABLE`.**

## Purpose and boundary

This is a pure, deterministic, on-demand research receipt over the existing
canonical annual-fact readiness contract. It uses only selected, reported,
point-in-time-valid annual `FinancialFact` observations for one supplied
canonical instrument, exact statement scope, and supplied `as_of`. It does
not retrieve data, write a repository, create a migration, rank a company,
qualify a Compounder, or change any Core V1 policy.

Every receipt is fixed to `WATCH_ONLY / NON_EXECUTABLE / RESEARCH_ONLY`. It
has no API, UI, portfolio, price, return, broker, order, provider,
runtime-clock, scoring, threshold, candidate-grid, or activation dependency.
It is evidence observation, not an investment recommendation.

## Canonical input and PIT contract

The module first reuses `CanonicalAnnualFactsReadinessReceipt` and the
approved financial vintage selector without reimplementing either. It admits
only the selected exact-scope facts for the direct existing canonical metrics:
`REVENUE`, `PAT`, `CFO`, `TOTAL_EQUITY`, and `CASH_AND_EQUIVALENTS`.

Facts with `available_at > as_of`, ambiguous revisions, conflicting lineage,
wrong scope, non-annual flow basis, or non-point-in-time stock basis remain
excluded by that upstream contract. Each result preserves source fact IDs,
semantic fact fingerprints, source coverage fingerprints, fiscal ends, scope,
and the supplied as-of in a deterministic receipt fingerprint. Conflict and
insufficient-evidence states are explicit; no missing input becomes zero.

## Exact deterministic observations

| Family | Observation | Formula / rule | Unavailable or non-comparable behavior |
| --- | --- | --- | --- |
| Revenue | Annual YoY | `(current - prior) / prior` only for consecutive fiscal years and `prior > 0`. | Missing/non-consecutive periods are non-comparable; zero or negative bases do not produce a percentage. |
| Revenue | 3/5-observation CAGR | `(last / first)^(1 / elapsed_fiscal_intervals) - 1`; requires 3 or 5 consecutive annual observations and positive first value. | Missing window, non-consecutive periods, or non-positive first value is explicit. No synthetic period count. |
| PAT | Annual YoY and 3/5-observation CAGR | Same arithmetic only where all required denominators are positive. | `LOSS_TO_PROFIT`, `PROFIT_TO_LOSS`, and `LOSS_TO_LOSS` are descriptive non-comparable states, never percentages. |
| Growth persistence | Descriptive interval count | Counts comparable positive, negative, and non-comparable YoY intervals across the available annual series. | It is not a threshold, quality verdict, or qualification. |
| ROE | Closing and average equity variants | Closing: `PAT / closing TOTAL_EQUITY`; average: `PAT / ((opening TOTAL_EQUITY + closing TOTAL_EQUITY) / 2)`. Both use exact fiscal-year matches and positive required equity. | Missing opening equity affects only the average variant. No equity substitute is allowed. |
| ROE summary | 3/5 closing-equity receipt | Deterministic minimum, median, maximum and valid-period count over the last 3 or 5 available closing-equity ratios. | A missing count is `DATA_INSUFFICIENT`, not a score or quality label. |
| Cash conversion | Annual CFO/PAT | `CFO / PAT` only where matching annual PAT is positive. Negative CFO is retained factually. | Missing CFO/PAT match or non-positive PAT is explicit; it is not normalized away. |
| Cash conversion | Cumulative 3/5 observations | `sum(CFO) / sum(PAT)` over matching consecutive annual years, only where cumulative PAT is positive. | Missing window, discontinuity, or non-positive cumulative PAT is explicit. |
| Cash | Trajectory observation | Retains annual cash values and adjacent deltas, with only `INCREASING`, `DECREASING`, `FLAT`, `MIXED`, or `SINGLE_PERIOD` sequence observation. | No liquidity, cash-quality, or business-quality meaning is inferred. |

The 3/5 labels refer to observation counts. The exponent always uses actual
fiscal-year intervals, so three observations use two elapsed intervals and
five observations use four when the years are consecutive.

## Fixed non-goals and unavailable domains

This V1 deliberately does not calculate EBITDA/EBIT, margins, FCF, leverage,
valuation, growth-adjusted valuation, normalized returns, sector comparisons,
bank/NBFC/insurer-specific ratios, forecasts, target prices, strength,
confidence, materiality, or an expiry. It makes no determination of
`SHADOW_CANDIDATE`, `SHADOW_NOT_QUALIFIED`, BUY, SELL, HOLD, ADD, TRIM, EXIT,
or ROTATE. It neither defines a Compounder policy nor supplies any parameter
for one.

## Determinism and auditability

Collections are canonically ordered and duplicates are not silently collapsed
into a selected source series: upstream canonical vintage selection remains
the conflict authority. Receipt and evaluation fingerprints cover all
serialized fields other than their own fingerprint; serialization is stable,
UTC-normalized, locale independent, and has no wall-clock input. Tampered
source readiness or a changed result fingerprint is rejected.

## Activation boundary

The research receipt is useful only as factual input to a later, separately
approved candidate-grid *design* or research policy. Such a later proposal
must define business-type applicability, comparability, thresholds,
calibration, positive/negative semantics, validation, and governance. No
candidate grid, ranking, backtest, policy activation, or external acquisition
is authorized by this document.
