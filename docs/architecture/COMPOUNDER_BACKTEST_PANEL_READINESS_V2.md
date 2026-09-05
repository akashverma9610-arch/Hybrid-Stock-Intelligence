# Compounder Backtest Panel Readiness V2

**Status: `RESEARCH_READINESS_AUDIT / DECISION_COMPLETE / NON_EXECUTABLE`.**

## Decision

`BACKTEST_PANEL_NOT_READY`

This is the final bounded historical-panel decision for
`COMPOUNDER_TESTABLE_SUBSET_V1`. It is a read-only audit of the canonical
production SQLite evidence at the fixed audit cutoff
`2026-09-04T19:30:59.533938Z`. It does not run a candidate grid, qualify an
issuer, select a threshold, calculate an outcome, create a panel row, or
change any policy, source, database record, portfolio, API, UI, provider, or
execution boundary.

The active PIT company-type policy improves the prospective starting point;
it does not make the earlier sparse security, issuer, membership, or taxonomy
evidence continuous. The first complete testable financial subset was not
PIT-visible until after the only current company-type/session anchor. There
is therefore no broad, temporally truthful cross-sectional historical panel,
and no completed forward business or market horizon. Software can calculate a
receipt; that is not empirical backtest readiness.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` remains explicit: immutable
primary records are facts, the existing PIT receipts and exact selectors are
data, this document is a readiness interpretation, and it creates no
Compounder inference.

## Audit method and scope

The audit used only the existing read-only canonical contracts and their
lineage:

- `NseSessionPointIdentity` for exact same-session NSE security facts;
- the approved ISIN-to-CIN anchor/forward-continuity receipts for exact issuer
  observations;
- `pit-company-type-classification-policy / v1` receipts and reports;
- `FinancialFact`, the frozen fact-vintage selector, and
  `CanonicalAnnualFactsReadinessReceipt`;
- `CompounderDerivedResearchEvaluation` for factual, non-qualifying metrics;
- stored historical bars, benchmark bars, taxonomy, and existing historical
  integrity contracts; and
- immutable core-snapshot and financial-fact source, policy, and fingerprint
  lineage.

All financial figures below were re-evaluated at the stated cutoff with the
existing fact-vintage selector. A fact was admitted only when both publication
and receipt visibility were at or before that cutoff. Consolidated and
standalone observations are counted independently; no scope fallback or mix
was made.

## Future observation contract — conceptual only

One future candidate-grid research observation must be keyed by and retain:

```text
canonical security
+ exact issuer/CIN identity
+ authoritative PIT company type
+ evaluation/as-of timestamp
+ one reporting basis
+ PIT-visible annual FinancialFact IDs and fingerprints
+ derived Compounder receipt fingerprints
+ historical security and universe-membership lineage
+ future business-outcome horizon identifiers
+ optional market-outcome horizon identifiers
+ all source/policy/selector versions
```

It may say that a required fact or derived metric is missing, conflicted, or
non-comparable. It may not contain a candidate-grid result, threshold result,
rank, score, setup, gate, trade instruction, portfolio field, or outcome value
at construction time.

Entry into a future `NON_FINANCIAL` panel requires all of the following at the
same evaluation boundary: exact session/lifecycle security evidence, exact
issuer evidence, a final active `NON_FINANCIAL` receipt, one comparable annual
reporting basis, PIT-selected annual facts, and the requested factual metric
receipt or its explicit unavailable state. A current fact, current company
type, or surviving membership may never be projected backwards.

## Coverage timeline

| Date or exact cutoff | Security evidence | Issuer/CIN evidence | Company type | Financial / metric evidence | Panel consequence |
| --- | --- | --- | --- | --- | --- |
| `2024-02-05` | 24,693 exact NSE session-point rows; 11,295 ISINs. No `HistoricalSecurityIdentity` interval. | No active final issuer-forward observation for this anchor. | 0 final receipts. | No annual facts were PIT-visible. | 0 observations; cannot be reconstructed from later facts. |
| `2024-04-05` | No matching stored session point beyond the February anchor. | Earliest exact BRSR-to-MII issuer anchor is known. It is an anchor, not an uninterrupted security/issuer interval. | No final company type. | No annual-fact observation can be joined to an authorised panel session. | Not an eligible evaluation date. |
| `2026-08-31T23:59:59Z` | 37,155 exact session-point rows; 16,520 ISINs. Still no interval/lifecycle identity. | 335 forward observations for 332 issuers, each tied to this exact later session. | 335 final receipts: 168 `NON_FINANCIAL`, 33 unsupported financial, 133 data-insufficient, 1 non-comparable. | 8 scope observations have all five direct inputs, but none has 3 or 5 comparable annual periods; all CAGR, ROE-summary, and cumulative-CFO/PAT windows are unavailable. | No complete metric subset and no historical membership/lifecycle panel. |
| `2026-09-03T17:40:00.665780Z` | No new exact NSE session point. | No new continuous issuer/security identity. | No new same-session type evidence. | First complete-input availability for every currently testable 3/5-observation metric family appears in current receipts. | Financial depth alone cannot create an evaluation date. |
| `2026-09-04T19:30:59.533938Z` | No exact security session point for this cutoff; `HistoricalSecurityIdentity` remains empty. | Same limited forward-observation population. | 335 final receipts: 168 `NON_FINANCIAL`, 7 banks, 28 unsupported financial, 131 data-insufficient, 1 non-comparable. | 6 instrument/scope cells have every testable-subset metric. | A current factual intersection exists, not a survivorship-safe historical backtest panel. |

Earliest non-zero evidence is therefore distinct from a valid joined panel:

| Dependency | Earliest stored PIT-safe point | Limitation |
| --- | --- | --- |
| Exact session security identity | `2024-02-05` | Session-point-only; no listing/tradability interval, continuity, or historical membership. |
| Exact issuer/CIN anchor | `2024-04-05T15:36:27Z` | Anchor-only; the approved forward security observation begins at the separate `2026-08-31` session. |
| Final active company type | `2026-08-31T23:59:59Z` | First genuine coverage is current-era only; no historical company type is inferred. |
| Any annual fact visible to the selector | `2026-08-31T16:19:29.491183Z` | No three- or five-period direct-input depth at the first type boundary. |
| First current receipt with every testable-subset metric | `2026-09-03T17:40:00.665780Z` | No matching later session identity, historical membership, post-input prices, or completed horizon. |
| Complete historical research observation | none | No date satisfies every required join. |

## Panel breadth and survivorship

The audit found **zero** valid company-evaluation observations, hence zero
valid panel issuers, securities, sectors, and evaluation dates. This is not a
claim that no data exists; it is a result of applying all required joins.

The latest limited factual intersections illustrate why a handful of examples
is not a research universe:

| Latest factual intersection, not a panel | Count | Scope |
| --- | ---: | --- |
| Final `NON_FINANCIAL` issuers at the 2026-09-04 cutoff | 168 | Exact final type receipt only. |
| `NON_FINANCIAL` securities with any current fact | 10 | 19 separate reporting-scope cells; 9 present taxonomy-sector labels. |
| Sectors among that financial intersection | 9 | Current taxonomy only, not a historical peer set. |
| Securities with all current testable-subset metrics | 3 | 6 scope cells; one is not `NON_FINANCIAL`. |
| `NON_FINANCIAL` securities with all current testable-subset metrics | 2 | APARINDS and GLAND, counted as four separate scope cells; not broad empirical coverage. |
| Exact historical company-evaluation observations | 0 | No lifecycle/membership/identity/metric/outcome-complete row. |

Survivorship is not repaired by descriptive lifecycle material:

- 762 `HISTORICAL_UNIVERSE_MEMBERSHIP` records are a single active snapshot,
  all known/effective at `2026-08-30T05:11:19.551869Z`.
- `HISTORICAL_SECURITY_IDENTITY` has zero interval records.
- 1,337 BSE compulsory-delisted PDF rows and three BSE lifecycle notices are
  retained as descriptive primary evidence. They are not exact NSE historical
  membership, listing intervals, or issuer/security joins.
- The two NSE session snapshots prove only their own 2024 and 2026 sessions;
  they cannot identify securities that later disappeared or prove that a
  current survivor was eligible throughout an interval.

Accordingly, current active securities, inactive/delisted securities, later
disappeared securities, and a non-survivor historical population cannot be
represented together for the contemplated evaluation dates.

## Financial-fact and basis coverage

There are 4,067 canonical `FinancialFact` rows for 31 instruments. Of those,
787 are reported annual rows for 27 instruments, with fiscal period ends from
`2022-03-31` through `2026-03-31`. The audit evaluated 59
instrument-and-scope cells: 27 instruments have consolidated annual facts and
26 have standalone annual facts. Those are separate factual views, not 53
comparable companies.

At `2026-09-04T19:30:59.533938Z`, direct input coverage is:

| Exact direct family | PIT-ready scope cells | >=3 comparable periods | >=5 comparable periods |
| --- | ---: | ---: | ---: |
| Revenue | 45 | 7 | 6 |
| PAT | 45 | 7 | 6 |
| CFO | 8 | 7 | 6 |
| Total equity | 8 | 7 | 6 |
| Cash and cash equivalents | 8 | 7 | 6 |
| All five currently testable direct families, same scope | 8 | 7 (4 instruments) | 6 (3 instruments) |

The direct families intentionally remain unavailable for EBIT/EBITDA selection,
period-end share-count semantics, debt, and capex where their canonical mapping
or source facts are absent. That limitation is preserved; it is not filled by
an adjacent financial metric.

## Derived metric readiness

The following are factual-receipt distributions generated from the same 59
exact-scope cells at the audit cutoff. Annual-interval rows can produce more
than one receipt per cell. They apply no candidate threshold.

| Derived receipt | Available | Data insufficient | Evidence conflicted | Non-comparable |
| --- | ---: | ---: | ---: | ---: |
| Revenue CAGR, 3 observations | 6 | 48 | 4 | 1 |
| Revenue CAGR, 5 observations | 6 | 49 | 4 | 0 |
| PAT CAGR, 3 observations | 6 | 48 | 4 | 1 |
| PAT CAGR, 5 observations | 6 | 49 | 4 | 0 |
| Revenue persistence | 20 | 35 | 4 | 0 |
| PAT persistence | 20 | 35 | 4 | 0 |
| Closing-equity ROE annual observation | 35 | 47 | 4 | 0 |
| Average-equity ROE annual observation | 25 | 57 | 4 | 0 |
| ROE summary, 3 observations | 7 | 48 | 4 | 0 |
| ROE summary, 5 observations | 6 | 49 | 4 | 0 |
| Cumulative CFO/PAT, 3 observations | 6 | 52 | 0 | 1 |
| Cumulative CFO/PAT, 5 observations | 6 | 53 | 0 | 0 |
| Cash trajectory observation | 8 | 51 | 0 | 0 |

Only six instrument/scope cells expose every current testable-subset metric;
four of those cells correspond to the two `NON_FINANCIAL` instruments above.
This is factual coverage, not a candidate result or an acceptable calibration
sample.

The audit continues to exclude the following dimensions from
`COMPOUNDER_TESTABLE_SUBSET_V1`: ROCE, ROIC, FCF conversion, margin durability,
debt quality, dilution, reinvestment quality, and incremental ROIC. Their
formulae, source semantics, applicability, or canonical inputs remain
unavailable. A future study using the narrower subset must never describe
itself as a complete Compounder policy.

## Outcome-label readiness

### Business outcomes

Subsequent revenue, PAT, ROE, CFO/PAT, and loss/profit-deterioration labels
could later reuse selected annual facts, but not at the first valid
company-type boundary. The 2026-08-31 boundary has no completed later annual
business horizon; the 2026-09-04 factual intersection is even later.

| Completed forward business horizon | Available observations | PIT-safe completed label | Reason |
| --- | ---: | --- | --- |
| 1 year | 0 | no | No type-and-metric eligible observation has one later completed annual horizon. |
| 3 years | 0 | no | The first possible input boundary is in 2026. |
| 5 years | 0 | no | The first possible input boundary is in 2026. |

### Market outcomes

Historical bars exist for 2,561 instruments from
`2023-08-21T18:30:00Z` through `2026-08-31T18:30:00Z`. NIFTY 500 has 1,673
bars over that span; NIFTY 50 has 746 bars from `2023-08-27T18:30:00Z` through
`2026-08-30T18:30:00Z`. These stored series do not produce labels here:

- NIFTY 50 is `UNKNOWN` adjustment basis; NIFTY 500 contains `RAW` and
  `UNKNOWN` bases.
- no `HISTORICAL_PRICE_INTEGRITY` assessment is stored;
- the first complete factual metric receipt is after the last stored session,
  so there is no first tradable session **after** the evidence was known;
- current sector taxonomy and sector-index data do not establish a historical
  PIT peer universe or comparable sector-return basis.

Therefore forward stock return, benchmark-relative return, sector-relative
return, and maximum drawdown all have zero completed eligible observations for
1-, 3-, and 5-year horizons. Fiscal period end is not used as a proxy for the
information date.

## Chronological validation and trial governance

There is no time range with a valid joined population and completed labels,
so no development, validation, and untouched test partitions can be formed.
Random splits are prohibited, and a chronological split would also need to
purge outcome windows that overlap a later partition.

The repository supplies useful immutable backtest/governance patterns, but it
does not contain a Compounder candidate-trial ledger: `backtest_runs`,
historical analytical snapshot/evaluation tables, and
`CALIBRATION_OBSERVATION` snapshots are all empty, and no stored contract
captures the required candidate ID, grid cell, universe, source/policy
versions, temporal partition, outcome definition, and non-selection result.
A small future immutable ledger harness is feasible without changing this
readiness decision. It must be proposed before candidate research begins; it
does not make the absent historical panel ready.

The pre-registered research-only grid remains frozen and unexecuted:

| Dimension | Frozen candidate values |
| --- | --- |
| Revenue CAGR | 5%, 8%, 10%, 12%, 15% |
| PAT CAGR | 8%, 10%, 12%, 15%, 20% |
| Median ROE | 12%, 15%, 18%, 20% |
| Cumulative CFO/PAT | 0.70, 0.80, 0.90, 1.00 |
| Persistence | 50%, 75%, 100% |
| Annual windows | 3 observations, 5 observations |

No value in this table is selected, scored, or compared against an issuer.

## Readiness dimensions

| Dimension | State | Exact reason |
| --- | --- | --- |
| `SECURITY_IDENTITY` | `PARTIAL` | Two exact NSE session-point populations exist, but no historical interval identity and no exact session after financial-subset availability. |
| `ISSUER_IDENTITY` | `PARTIAL` | Exact BRSR anchors and 335 forward observations exist; they are not a continuous historical issuer/security population. |
| `COMPANY_TYPE` | `PARTIAL` | Active final type receipts begin only at 2026-08-31; 168 are non-financial, but historical classification is unavailable. |
| `FINANCIAL_FACTS` | `PARTIAL` | Seven scope cells have all direct inputs for three periods and six for five, but they were first complete in September 2026 and are not a broad joined universe. |
| `DERIVED_METRICS` | `PARTIAL` | Six scope cells have all testable-subset receipts; conflict, insufficiency, basis separation, and limited breadth remain explicit. |
| `SURVIVORSHIP` | `NOT_READY` | No historical security intervals or historical membership series; descriptive delisting evidence cannot substitute. |
| `BUSINESS_OUTCOMES` | `NOT_READY` | No completed 1-, 3-, or 5-year business horizons from an eligible observation. |
| `MARKET_OUTCOMES` | `NOT_READY` | No post-input tradable session, price-integrity assessment, coherent return basis, or completed horizon. |
| `CHRONOLOGICAL_VALIDATION` | `NOT_READY` | No valid labelled period for development/validation/test, and no way to purge overlapping forward windows. |
| `TRIAL_GOVERNANCE` | `PARTIAL` | Immutable governance patterns exist, but no Compounder trial-ledger contract or stored trial is present. |

## Permitted follow-on and stopped work

Historical taxonomy, lifecycle, membership, and company-type reconstruction
stops here. No further broad archive hunt is authorised by this result. A
limited `DESCRIPTIVE_RETROSPECTIVE_SANITY_CHECK` could later describe the
two-to-three current examples with fully preserved limitations, but it must not
be called a backtest, select a grid value, or be used for threshold selection.

The appropriate next research path is:

`COMPOUNDER_PROSPECTIVE_SHADOW_VALIDATION_V1`

That future, separately approved slice should begin only from newly captured
genuine PIT boundaries; retain exact `NON_FINANCIAL` type, issuer, security,
scope, financial-vintage, and metric lineage; and wait for completed business
and market horizons. It is **partially** supported today by active
non-financial type receipts and deterministic derived facts, but it needs a
new exact session/membership capture, coherent price-integrity assessment, a
trial ledger, and elapsed future time before it can form outcome labels. No
prospective implementation is authorised here.

## Non-goals

This decision creates no historical reconstruction, candidate-grid execution,
threshold evaluation, company qualification, research-shadow outcome,
portfolio mutation, discovery change, API/UI change, provider call, score,
setup, Six-Gates authorisation, broker/order path, or trade vocabulary.

`BACKTEST_PANEL_NOT_READY`
