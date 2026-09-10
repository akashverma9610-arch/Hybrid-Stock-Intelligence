# Canonical financial diagnostic input comparability closure V1

Human-approved scope: **16, 17, 18, 19, 20, 24, 25, 26, 29 only**.
Baseline: `cab9304d1498bba64cb000223c568a5ff16505cb`.
No acquisition, persisted diagnostic run, new registry, formula calibration,
score, gate, trading authority, or downstream operationalization is authorized.

## Existing semantics, before repair

Names remain owned by the [canonical registry](../../app/registry/canonical.py).
The [runner](../../app/universe_analysis/service.py) calls the existing
[wrappers](../../app/diagnostics/evaluators.py),
[financial evaluators](../../app/analysis/fundamentals.py), and
[valuation evaluator](../../app/analysis/valuation_trade.py).

| Rule | Existing evaluator / payload | Period / history and exact existing calculation | Existing limitation / fallback |
| --- | --- | --- | --- |
| 16 | `five_year_trend`: revenue, ebitda, pat, eps | Last six annual rows; positive first/last values; `(last/first)^(1/5)-1` for each metric | Rows were date-sorted, not fiscal-continuity certified; all four metrics mandatory; five dates are insufficient |
| 17 | `return_ratios`: pat, ebit, total_equity, total_debt, cash | Latest annual PAT / mean beginning/end equity; EBIT / mean capital employed; default capital = equity + debt - cash | Existing ending-only fallback when prior denominator unavailable; optional assets-current-liabilities method not selected by runner; no financial-company branch |
| 18 | `cash_flow`: operating_cash_flow, capex, pat | Available last one/two annual rows must contain all three; latest FCF = CFO - CAPEX; CFO/PAT | Missing CAPEX blocks; canonical derivation service instead accepts negative outflow CAPEX and adds it: sign bridge is not governed; zero PAT would divide by zero |
| 19 | `leverage`: total_debt, total_equity, cash, ebit, interest_expense | Latest annual; debt/equity, debt-cash, EBIT/interest; positive equity and interest | No bank/NBFC/insurer branch; no missing-debt zero in this evaluator |
| 20 | `working_capital`: revenue, receivables; optional cogs, inventory, payables | Annual 365-day DSO; average beginning/end balances or explicit ending fallback; CCC = DSO + DIO - DPO | Missing COGS/inventory/payables gives partial, not full CCC; only explicit `not_applicable_working_capital` gives N/A; canonical COGS metric absent |
| 24 | `earnings_acceleration`: revenue | Last five quarter rows; latest/row-five-back minus one, positive endpoints | One YoY observation, not successive growth acceleration; organic/one-off attribution explicitly unassessed |
| 25 | `latest_quarter`: revenue, ebitda, pat, eps | Last five quarter rows; latest/prior minus one and latest/year-ago minus one for each positive available triple | Missing metrics skipped; one available metric can make wrapper eligible, not full rule ready |
| 26 | `margins`: revenue, ebitda | Last five quarter rows; latest EBITDA/revenue and difference from prior-year quarter | No gross-margin computation; PAT margin is not a substitute |
| 29 | `valuation`: dated close + eps; forward_eps, configured_growth_rate, shares_outstanding, ebitda, total_equity, total_debt, cash | Annual EPS P/E; forward P/E; PEG = P/E / (growth*100); EV = price*shares + debt - cash; EV/EBITDA; P/B = price*shares/equity | P/E drives classification even when other multiples unavailable; legacy EV defaults missing debt/cash to zero, so canonical bridge must prevent that path; no authoritative forward/share-count mapping |

The runner's existing thresholds remain unchanged: growth `0.1/-0.1`, return
ratio `0.1`, debt/equity `1.5`, interest coverage `2`, margin change `0.02`,
P/E `15/35`. Legacy evaluator units are anonymous floats; their canonical
adapter must establish economic compatibility before conversion.

## Canonical archaeology and reuse

- [FinancialFact](../../app/fundamentals/models.py) remains the sole fact model;
  exact instrument, metric, scope, dimension, currency/unit/scale, fiscal
  identity, publication/receipt, revision parent and filing identity survive.
- [FinancialFactStore](../../app/fundamentals/store.py) remains the sole store.
  SQLite writes are immutable/idempotent; queries have a 500-per-metric cap.
  Canonical diagnostic intake must fail closed when completeness is unproven.
- [Filing normalization](../../app/fundamentals/service.py) binds the exact
  financial-results filing/instrument and equal publication/receipt timestamps.
  The Q4/TTM helper exists, but its date/known-at/contiguity guarantees do not
  certify this bridge. `QUARTER_FROM_YTD_DERIVATION_POLICY = UNSET` here.
- The frozen [vintage selector](../../app/fundamentals/financial_fact_vintage_selector.py)
  and [approved policy](../../app/fundamentals/financial_fact_vintage_selection_policy.py)
  select only explicit, non-conflicted PIT lineage. No latest-row/max/average
  shortcut and no policy flag mutation.
- The existing [metric materializer](../../app/fundamentals/financial_metric_observation_materializer.py)
  and [schema](../../app/fundamentals/financial_metric_observation_schema.py)
  already preserve values, periods, fingerprints and source/selection lineage.
  They are reused, not replaced by another fact model.
- [Annual readiness](../../app/fundamentals/compounder_canonical_annual_facts.py)
  establishes exact full-year flows and same-end point-in-time balances;
  shares' period-end versus weighted-average semantics remain unavailable.
- [BSE ingestion](../../app/fundamentals/bse_official.py) stores direct XBRL raw
  units, preserving source rounding metadata. No magnitude-based scaling.
- The [legacy adapter](../../app/fundamentals/adapter.py) prefers consolidated,
  otherwise standalone. It groups by end/type, loses start/basis/scale, aliases
  operating profit to EBITDA and net worth to equity, and ignores point balances.
  Its unrelated consumers are not rewritten. A separate **certification path
  over these same facts**, not another source, supplies only the approved rules.

## Approved boundary decisions

Same series requires exact metric, scope, period type/basis, currency, unit,
scale and normalization version. No scale conversion or FX conversion is
introduced. Unknown representation fails closed. EPS used with INR price must
be raw INR units; no statement-wide multiplier is applied to per-share data.
Quarter-only and YTD remain distinct even in Q1. No TTM derivation is activated.
Fiscal YoY/QoQ requires explicit year/quarter and exact contiguous fiscal periods,
not nearest dates. Missing recent periods cannot cause retreat to an older
apparently complete window. Calendar month-boundary periods are provable here;
52/53-week or other accounting calendars require a separate canonical contract.

Balances join only on exact annual end and fiscal year. No arbitrary closing
balance substitution. Existing average/ending fallback semantics are retained
only where those exact boundaries can be demonstrated. Cross-metric monetary
representation must also match. CAPEX sign interpretation and specialized
financial-company ratio applicability are not invented; `POLICY_DEFINITION_MISSING`
is different from `NOT_APPLICABLE`. Company type is never guessed from a symbol,
sector label, or absence from a regulator list.

PIT cutoff is caller-supplied and timezone-aware. Visibility is bounded by both
fact and filing publication/receipt and period end. Later revisions cannot
alter earlier eligible values. Source receipt limits historical coverage: an
old reporting period is not proof of old knowability. Price and fundamentals
must both be visible at the same explicit valuation cutoff; an older close is
reported with its date, never described as live/current.

## Stable-candidate measured coverage

Read-only audit cutoff: `2026-09-10T00:00:00+00:00`. Historical comparison
cutoff: `2025-12-31T23:59:59+00:00`. Financial-source denominator: **31**
companies, not the complete 2,553-security universe from the accepted audit.
The refreshed production counts are **4,067 facts / 362 filings**, unchanged.
The existing selector yields **3,730 SELECTED / 120 CONFLICTED** semantic groups;
these are groups, not a count of imported facts. No conflict was resolved by
this slice and no stored facts were modified.

| Period / basis | Facts |
| --- | ---: |
| ANNUAL / FULL_YEAR | 787 |
| POINT_IN_TIME / UNKNOWN | 480 |
| QUARTERLY / QUARTER_ONLY | 2214 |
| QUARTERLY / YEAR_TO_DATE | 586 |

`READY` below means the whole certified input contract is satisfied. `PARTIAL`
is useful but incomplete descriptive evidence. Wrapper eligibility is reported
separately; it must not be promoted to full-rule certification. Each row sums
to 31. `NOT_APPLICABLE = 0` for every row; missing branch policies are not N/A.

| Rule | Ready | Partial | Insufficient | Conflicted | Policy blocked | Wrapper eligible before → after | Prospective/as-of input usable | Strict historical usable |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 16 | 0 | 0 | 28 | 3 | 0 | 0 → 0 | 0 | 0 |
| 17 | 0 | 0 | 0 | 3 | 28 | 0 → 0 | 0 | 0 |
| 18 | 0 | 0 | 0 | 3 | 28 | 0 → 0 | 0 | 0 |
| 19 | 0 | 0 | 0 | 3 | 28 | 0 → 0 | 0 | 0 |
| 20 | 0 | 0 | 0 | 3 | 28 | 0 → 0 | 0 | 0 |
| 24 | 0 | 18 | 9 | 4 | 0 | 5 → 18 | 18 | 0 |
| 25 | 0 | 18 | 9 | 4 | 0 | 5 → 18 | 18 | 0 |
| 26 | 0 | 0 | 0 | 4 | 27 | 0 → 0 | 0 | 0 |
| 29 | 0 | 20 | 8 | 3 | 0 | 22 → 20 | 0 | 0 |

The same-cutoff financial-only inputs for Rules 24/25 are prospectively
replayable for 18 companies. This is not a pre-acquisition backtest or proof of
all future sessions. The historical cutoff predates all stored financial
receipts; all nine rules have **0/31** usable historical inputs there.
Rule 29 uses existing **CURRENT_DESCRIPTIVE** certified daily price evidence;
that source's strict-historical limitation is retained, so the audit does not
promote its 20 partial P/E results to prospective/historical certification.
Every company's exact price date/known-at is in the artifact. Prices are dated
close observations, not live quotations.

### Metric-level facts and comparable series

Raw row counts include both scopes; distinct-company counts do not sum across
scopes. Comparable counts use the existing consolidated-else-standalone
preference and concern the whole observed series, **not required rule depth**.
Exact standalone/consolidated counts and all missing periods are also retained
in the machine artifact. The final rule inputs assess only the exact requested
window: an unrelated older gap cannot poison the last five complete quarters.
All older evidence, including conflicts, remains in the parent lineage.

| Metric | Annual rows / companies / comparable preferred-scope series | Quarter-only rows / companies / comparable series | Point-balance rows / companies / comparable series |
| --- | --- | --- | --- |
| Revenue | 96 / 25 / 21 | 310 / 29 / 21 | 0 |
| PAT | 96 / 25 / 21 | 310 / 29 / 21 | 0 |
| Basic EPS | 96 / 25 / 21 | 310 / 29 / 21 | 0 |
| Finance cost / interest | 96 / 25 / 21 | 310 / 29 / 21 | 0 |
| CFO | 36 / 4 / 3 | 0 | 0 |
| Total equity / book-value component | 0 | 0 | 36 / 4 / 4 |
| Cash and equivalents | 0 | 0 | 36 / 4 / 4 |
| Direct EBITDA, EBIT, CAPEX, total debt | 0 each | 0 each | 0 each |
| Receivables, inventory, payables, shares | 0 each | 0 each | 0 each |
| Net worth (not silently aliased to equity) | 0 | 0 | 0 |

Revenue/PAT/EPS/finance-cost YTD each have **83 rows / 20 companies**.
Those cumulative-duration observations are retained separately; no YTD-to-quarter
conversion or sequential quarter comparison is admitted. Six-point comparable
annual revenue, EBITDA, PAT and EPS coverage is **0/31 for each metric**;
maximum annual dates remain five. Direct monetary components do not authorize
synthetic EBITDA, EBIT, debt, CAPEX, COGS, or shares.

### Exact rule blockers and next requirements

| Rule | Actual safe evidence and contract state | Remaining requirement for human review |
| --- | --- | --- |
| 16 | Revenue/PAT/EPS exist; no six-point annual set; EBITDA absent. Input semantics READY; security readiness NOT_READY | Six fiscal-comparable annual endpoints and direct governed EBITDA; resolve three companies' relevant conflicts |
| 17 | Some PAT/equity/cash facts; exact balance-end alignment implemented. Formula unchanged. NOT_READY | Direct EBIT/debt; exact-as-of company-type intake and specialized financial-sector policy; positive capital denominator |
| 18 | CFO is factual partial evidence (4 source companies); CAPEX absent. NOT_READY | Direct CAPEX, explicit diagnostic-vs-derivation CAPEX sign bridge, nonzero PAT, applicability policy |
| 19 | Equity/cash/finance cost partly available; direct debt/EBIT absent. NOT_READY | Direct debt and EBIT, exact aligned balances, specialized bank/NBFC/insurer policy |
| 20 | No receivables/inventory/payables; canonical COGS metric absent. NOT_READY | Direct working-capital facts, governed COGS taxonomy and applicability; no arbitrary N/A label |
| 24 | 18/31 comparable five-quarter revenue windows; PARTIAL | Exact organic/one-off attribution; four conflicted companies and nine insufficient companies retained; no inferred organic growth |
| 25 | At least one positive comparable metric triple for 18/31: revenue 18, PAT 15, EPS 15, EBITDA 0; PARTIAL | Direct EBITDA, remaining valid fiscal windows; no quarter/YTD substitution |
| 26 | Direct EBITDA absent; gross-margin mapping absent; NOT_READY | Direct operating inputs, gross-profit/COGS taxonomy, branch applicability; no PAT-margin substitute |
| 29 | 20/31 partial P/E, **0** forward P/E, PEG, EV/EBITDA and P/B | Forward-EPS/configured-growth policies, period-end-share semantics, direct EBITDA/debt, aligned book value; current/strict-price distinction |

Three annual-conflicted companies are CRAFTSMAN, TEGA and ONESOURCE.
Quarter-window conflicts additionally include SIEMENS. Conflicts refer to
existing immutable vintage evidence; there is no new majority/latest-value
resolution. APARINDS, GLAND, GENUSPOWER and DEEPINDS have quarter-only-labelled
September/December facts with six-/nine-month period starts. They fail
`EXACT_FISCAL_PERIOD_REQUIRED`, rather than receiving a rewritten period or
inferred quarter value. Resolving those source-context inconsistencies is a
separate human-reviewed data correction, not authorized fact mutation here.

Existing company-type infrastructure is implemented, not unavailable: stored
classification receipts have cutoffs `2026-08-31T23:59:59+00:00` and
`2026-09-04T19:30:59.533938+00:00`, including 168 non-financial classifications
at each and seven banks at the latter. No exact September 10 receipt was
supplied. The adapter does not rerun that classifier, extrapolate its cutoff,
or invent rule-specific bank/NBFC/insurer policies. Typed exact-as-of receipts
can be injected; tests exercise all four branches. Source fiscal labels are
retained as stored; this is not a newly certified issuer fiscal-calendar map.

### Per-company current-descriptive inputs

| Symbol | Facts | Rule 24 | Rule 25 | Rule 29 |
| --- | ---: | --- | --- | --- |
| RELIANCE | 88 | PARTIAL | PARTIAL | PARTIAL |
| SJVN | 136 | PARTIAL | PARTIAL | PARTIAL |
| MGL | 145 | PARTIAL | PARTIAL | PARTIAL |
| SIEMENS | 101 | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED | PARTIAL |
| ASTRAL | 136 | PARTIAL | PARTIAL | PARTIAL |
| CRISIL | 89 | PARTIAL | PARTIAL | INSUFFICIENT_DATA |
| IDBI | 23 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| INFY | 136 | PARTIAL | PARTIAL | PARTIAL |
| BIKAJI | 136 | PARTIAL | PARTIAL | PARTIAL |
| ACUTAAS | 136 | PARTIAL | PARTIAL | PARTIAL |
| SWIGGY | 136 | PARTIAL | PARTIAL | INSUFFICIENT_DATA |
| CRAFTSMAN | 143 | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED |
| DALBHARAT | 136 | PARTIAL | PARTIAL | PARTIAL |
| AFFLE | 136 | PARTIAL | PARTIAL | PARTIAL |
| ZYDUSLIFE | 136 | PARTIAL | PARTIAL | PARTIAL |
| TEJASNET | 136 | PARTIAL | PARTIAL | INSUFFICIENT_DATA |
| LTTS | 113 | PARTIAL | PARTIAL | PARTIAL |
| TEGA | 136 | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED |
| ACC | 136 | PARTIAL | PARTIAL | PARTIAL |
| ONESOURCE | 150 | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED | EVIDENCE_CONFLICTED |
| DABUR | 136 | PARTIAL | PARTIAL | PARTIAL |
| GESHIP | 136 | PARTIAL | PARTIAL | PARTIAL |
| LT | 145 | PARTIAL | PARTIAL | PARTIAL |
| GLAND | 300 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | PARTIAL |
| ICICIBANK | 23 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| DEEPINDS | 198 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | PARTIAL |
| ORIENTTECH | 7 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| APARINDS | 324 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | PARTIAL |
| SAFARI | 7 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| APOLLOHOSP | 7 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| GENUSPOWER | 300 | INSUFFICIENT_DATA | INSUFFICIENT_DATA | PARTIAL |

## Final readiness matrix

| Item | State | Evidence / boundary |
| --- | --- | --- |
| A FINANCIAL_FACT_ARCHAEOLOGY | READY | Sole fact/store/filing/selector/materializer contracts audited; 4,067/362/31 remeasured |
| B PERIOD_TAXONOMY | READY | Full-year, quarter-only, YTD and point balances distinct; TTM not derived |
| C FISCAL_PERIOD_IDENTITY | PARTIAL | Exact stored fiscal year/quarter/start/end checks implemented; malformed and non-calendar periods rejected |
| D SCOPE_COMPARABILITY | READY | Whole-series scope fixed; exact-scope coverage measured separately |
| E UNIT_CURRENCY_COMPARABILITY | READY | Exact INR/unit/scale/version; no invented multiplier or FX; unknown fails closed |
| F VINTAGE_SELECTION | READY | Existing frozen policy unchanged; 3,730 selected / 120 conflicted groups |
| G PIT_AS_OF_SELECTION | READY | Both fact/filing known-at and period end checked at explicit cutoff |
| H CONFLICT_PRESERVATION | READY | Conflicts reject affected inputs; all immutable lineage retained |
| I COMPARABLE_SERIES_CONTRACT | READY | Deterministic, source-bound, period-window-aware, no new fact store |
| J RULE_16_INPUT_READINESS | NOT_READY | 0/31; six annual endpoints and EBITDA missing |
| K RULE_17_INPUT_READINESS | NOT_READY | 0/31; denominator data/applicability missing |
| L RULE_18_INPUT_READINESS | NOT_READY | 0/31; CAPEX and sign policy missing |
| M RULE_19_INPUT_READINESS | NOT_READY | 0/31; debt/EBIT and applicability missing |
| N RULE_20_INPUT_READINESS | NOT_READY | 0/31; working-capital facts/COGS/applicability missing |
| O RULE_24_INPUT_READINESS | PARTIAL | 18/31; organic attribution unavailable |
| P RULE_25_INPUT_READINESS | PARTIAL | 18/31; EBITDA unavailable |
| Q RULE_26_INPUT_READINESS | NOT_READY | 0/31; EBITDA/gross-margin/applicability gaps |
| R RULE_29_INPUT_READINESS | PARTIAL | 20/31 P/E only; no full valuation-ready company |
| S CURRENT_DESCRIPTIVE_COVERAGE | PARTIAL | Explicit 31-company denominator and per-rule count table above |
| T PROSPECTIVE_PIT_COVERAGE | PARTIAL | Rules 24/25: 18/31 at audited cutoff; no source-historical claim |
| U STRICT_HISTORICAL_PIT_COVERAGE | NOT_READY | 0/31 for all nine at historical cutoff; old fiscal date is not known-at |
| V FINANCIAL_SECTOR_APPLICABILITY | PARTIAL | Existing type model reused; missing exact-as-of intake/branch policy is not N/A |
| W INTERNAL_REPAIRS | READY | Certified path bypasses lossy aliases/basis collapse; existing formulas unchanged |
| X MISSING_CANONICAL_METRICS | NOT_READY | Direct gaps above; no zeros/derived substitutes |
| Y EXTERNAL_DATA_REQUIREMENTS | PARTIAL | Exact missing direct metrics/history/context evidence listed; no acquisition performed |
| Z MACHINE_READABLE_ARTIFACT | READY | Deterministic linked artifact; not a second registry |
| AA NEXT_HUMAN_DECISION | PARTIAL | Review financial-period corrections, missing data and interpretation policies before selecting another group |

## Implementation and audit reproducibility

- [Comparability assembler](../../app/fundamentals/diagnostic_comparability.py):
  references existing immutable facts, filing fingerprints, selected vintages
  and materialized observations. No scale, fiscal-calendar or metric invention.
- [Diagnostic input bridge](../../app/fundamentals/diagnostic_input.py): only the
  approved nine rules; no prices/forward/share defaults. Regenerates the legacy
  snapshot with fact/filing/selection/source fingerprints in each observation.
- Existing adapter exposes `diagnostic_input`; existing stored-data source
  forwards it; `StockDiagnosticInputAssembler` checks instrument/as-of and the
  canonical runner uses it only for these nine rules. Uncertified canonical
  legacy observations cannot silently become certified input. Generic legacy
  consumers and other rule groups are unchanged.
- [Read-only audit](../../scripts/audit_financial_diagnostic_comparability.py)
  reads only stored financial data and one latest existing weekly artifact per
  financial-source company for certified daily prices. No universe rebuild,
  source fetch, raw re-ingestion, or diagnostic persistence.
- [Focused comparability tests](../../tests/unit/test_financial_diagnostic_comparability.py)
  and [audit regression](../../tests/unit/test_financial_comparability_audit.py)
  cover all required boundaries, isolation, deterministic replay and windowing.
- [Machine-readable audit](CANONICAL_FINANCIAL_DIAGNOSTIC_INPUT_COMPARABILITY_V1.json)
  fingerprint: `sha256:8fa3b3a39f70f0eccb9025d87f725014d04c64ae10feff78431b09de40e2d870`.

Example read-only reproduction (choose a new ignored output path):

```powershell
& $PythonPath scripts/audit_financial_diagnostic_comparability.py --database data/nse_stock_manager.db --as-of 2026-09-10T00:00:00+00:00 --historical-as-of 2025-12-31T23:59:59+00:00 --output .tmp/financial-comparability-reproduction.json
```

## Final validation and defensive review

- Focused comparability/audit tests: **42 passed / 0 failed**.
- Affected financial/vintage/materialization/PIT/diagnostic/Brain regressions:
  **147 passed / 0 failed / 2 warnings**.
- Final completed backend regression: **3,318 passed / 0 failed / 6 skipped /
  2 warnings**, 275.13 seconds. The warnings concern existing Starlette/httpx
  and AnyIO test infrastructure deprecations, not a weakened assertion.
- Defensive review found that an unrelated older fiscal gap could incorrectly
  block an otherwise complete latest-five-quarter window. A reproducing test
  preceded the bounded fix. Exact requested-window comparability now retains
  all original evidence in parent lineage without poisoning unrelated windows;
  focused, affected and the complete final suite were rerun after that fix.
- SQLite read-only `quick_check = ok`, `integrity_check = ok`, FK violations
  **0**. Financial-fact content, accepted table counts, protected-table content
  and snapshot-family counts match the pre-slice audit. Portfolio snapshots
  **1**, cash **UNKNOWN**, paper trades **0**, trade plans **0**, generic
  strategy versions/results **0/0**, canonical strategy definitions **1** and
  canonical diagnostic results **2,074** remain unchanged. Canonical 15-minute
  snapshot rows remain **0**; no broker/order table or record was introduced.
- Local Markdown links, whitespace, targeted credential/private-file scan and
  `git diff --check` pass. The artifact is deterministic, its fingerprint is
  verified, and it matches the final read-only audit output. No production
  dataset, private portfolio payload, credential, runtime log or test output
  is included in the release files.

No provider runtime, API/UI, schema, investment thresholds, Rule registry,
Decision Score, Six Gates, technical policy, portfolio or order state changed.
No next rule group is authorized by this result. **STOP for semantic/human review.**
