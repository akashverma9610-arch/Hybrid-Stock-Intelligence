# Research Metric Directionality Policy v1

**APPROVED — NOT SELECTED — NOT ACTIVE**

`research-metric-directionality-policy / v1-approved` is an immutable passive
policy approved by `human:Akash-Verma`. It requires an already AVAILABLE
`FinancialMetricTrajectory` built under
`financial-metric-trajectory-policy / v1-approved`
(`15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7`).

Policy fingerprint:
`0b4bcb46b00ec04c6c50610be0b5062237e39f2373e6df435ac788617db5a1dc`

It is metric-local orientation metadata, not an interpreter. It does not say a
business, thesis, opportunity, portfolio, or action improved or deteriorated.
Sequential-quarter flow movement remains conservative because seasonality is
not governed. Point-in-time balance-sheet movement remains context-dependent.
The v1 lower-potentially-favorable set is intentionally empty.

| Metric | Sequential quarter | YoY quarter | YoY annual | Point-in-time | Rationale |
| --- | --- | --- | --- | --- | --- |
| REVENUE | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Seasonality; comparable YoY operating orientation |
| OTHER_INCOME | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Non-operating context |
| EBITDA | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Seasonality; comparable YoY operating orientation |
| OPERATING_PROFIT | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Seasonality; comparable YoY operating orientation |
| EBIT | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Seasonality; comparable YoY operating orientation |
| DEPRECIATION | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Accounting component context |
| FINANCE_COST | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Financing context |
| PBT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Pre-tax accounting context |
| TAX | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Tax context |
| PAT | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Comparable YoY earnings orientation only |
| MINORITY_INTEREST | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Ownership/entity context |
| EPS_BASIC | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Comparable per-share orientation only |
| EPS_DILUTED | CONTEXT_DEPENDENT | HIGHER_POTENTIALLY_FAVORABLE | HIGHER_POTENTIALLY_FAVORABLE | NOT_APPLICABLE | Comparable per-share orientation only |
| TOTAL_ASSETS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Balance-sheet context |
| TOTAL_LIABILITIES | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Balance-sheet context |
| TOTAL_EQUITY | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Balance-sheet context |
| NET_WORTH | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Balance-sheet context |
| TOTAL_DEBT | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Capital-structure context |
| CASH_AND_EQUIVALENTS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Funding/use-of-cash context |
| CURRENT_ASSETS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Working-capital context |
| CURRENT_LIABILITIES | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Working-capital context |
| INVENTORY | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Working-capital context |
| RECEIVABLES | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Working-capital context |
| PAYABLES | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | CONTEXT_DEPENDENT | Working-capital context |
| CFO | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Working-capital timing context |
| CFI | NON_DIRECTIONAL | NON_DIRECTIONAL | NON_DIRECTIONAL | NOT_APPLICABLE | Raw investing cash flow |
| CFF | NON_DIRECTIONAL | NON_DIRECTIONAL | NON_DIRECTIONAL | NOT_APPLICABLE | Raw financing cash flow |
| CAPEX | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Capital-allocation context |
| FREE_CASH_FLOW | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | CONTEXT_DEPENDENT | NOT_APPLICABLE | Capex timing/allocation context |
| SHARES_OUTSTANDING | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NON_DIRECTIONAL | Corporate-action/denominator representation |
| FACE_VALUE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NON_DIRECTIONAL | Corporate-action representation |

The code-only policy registry has an explicit rule for every individual canonical
`FinancialMetric × FinancialMetricTrajectoryBasis` pair; grouped rows above
are a readable presentation only. Derived non-canonical metrics remain
unsupported: ROCE, ROE, margins, debt-to-equity, interest coverage, CAGR, and
PEG. A future enum value receives no inherited semantics and requires a new
policy version.

U14D-6B recorded that directionality was blocked before a factual trajectory
existed. U14D-6W, U14D-6X, and U14D-6Y supplied, implemented, and QA-validated
that factual substrate. This policy does not implement directionality runtime
evaluation, materiality, persistence, attribution, aggregation, thesis or
opportunity semantics, alerts, recommendations, or execution.
