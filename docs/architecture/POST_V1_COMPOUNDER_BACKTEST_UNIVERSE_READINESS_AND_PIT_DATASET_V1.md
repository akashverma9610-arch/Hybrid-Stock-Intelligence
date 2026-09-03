# Compounder Backtest Universe Readiness and PIT Dataset V1

**Status: `RESEARCH_ONLY / NOT_APPROVED / NOT_ACTIVE / NON_EXECUTABLE`.**

## Decision

`BACKTEST_PANEL_NOT_READY`

The existing immutable annual facts and derived-metric receipts are usable
factual inputs, but HSI cannot currently reconstruct a broad, historically
truthful, non-financial company universe at each evaluation date. A current
membership snapshot, a current taxonomy, or today's surviving NSE universe
must never substitute for historical membership or historical company type.

This document is a dataset/readiness artifact, not a backtest, candidate grid,
ranking, qualification, or Compounder policy. It creates no persisted panel,
API, UI, provider request, portfolio access, order path, or execution
authority.

## Required future observation

One future panel observation must be immutable and keyed by:

`canonical instrument + historical universe membership identity + reporting
basis + annual-fact vintage/receipt fingerprints + evaluation as-of +
company-type classification lineage + later-outcome-window identifiers`.

It may associate only the annual facts visible at its supplied as-of, one
exact consolidated or standalone basis, and the derived-metric receipts
calculated from those facts. It cannot attach a candidate qualification,
threshold result, ranking, score, setup, gate, portfolio state, or outcome
value during panel construction.

## Existing contracts that can be reused

- `HistoricalSecurityIdentity`, `UniverseMembership`, and
  `HistoricalCorporateAction` provide the intended immutable identity,
  listing-interval, membership, corporate-action, and PIT guard vocabulary.
- `HistoricalUniverseService` already excludes membership records unknown or
  ineffective at the requested as-of.
- `InstrumentTaxonomyClassification` is PIT-addressable sector/industry
  lineage, but contains no approved bank/NBFC/insurer/non-financial company
  type.
- `FinancialFact`, its approved vintage selector, and
  `CanonicalAnnualFactsReadinessReceipt` are the only annual financial
  observation and PIT-selection paths.
- `CompounderDerivedResearchEvaluation` is the exact deterministic receipt for
  revenue/PAT growth and persistence, ROE variants, CFO/PAT, and cash
  observation. A derived receipt is not a qualification.
- Historical OHLCV, NIFTY 500/NIFTY 50 series, and Historical Integrity
  contracts are available only as future outcome-readiness inputs. Their
  adjustment basis and corporate-action integrity must be verified before any
  label is calculated.

## Survivorship and company-type assessment

| Required property | Current canonical support | Audit finding | Dataset behavior |
| --- | --- | --- | --- |
| Active historical company | Partial | 762 `HISTORICAL_UNIVERSE_MEMBERSHIP` records exist, but every record is first-known/effective `2026-08-30` and `ACTIVE`. | Not historical coverage; exclude for earlier evaluations. |
| Delisted, merged, renamed, failed, or inactive company | No populated evidence | `HISTORICAL_SECURITY_IDENTITY` count is zero; no populated lifecycle/listing-end/symbol-continuity evidence. | Do not silently drop; panel remains unavailable. |
| Listing start/end and tradability interval | Contract exists, data absent | No historical identity records are stored. | Exclude rather than infer from a current master. |
| Historical constituent membership | Contract exists, data insufficient | The 762 memberships are a one-date active snapshot, not dated membership history. | No historical universe reconstruction. |
| Non-financial company type | No canonical contract/data | Taxonomy has sector/industry lineage only; it has no approved bank/NBFC/insurer/company-type field. | `COMPANY_TYPE_UNAVAILABLE`; no keyword/name inference. |

Consequently, the required non-financial filter cannot be applied. Banks,
NBFCs, insurers, unknowns, and non-comparable entities cannot be distinguished
canonically; no provisional inclusion is permitted.

## Current repository coverage receipt

All counts below are read-only, exact-scope observations at the fixed cutoff
`2026-09-03T23:59:59+00:00`, not historical panel rows or research results.

| Item | Observed count / span | Meaning |
| --- | --- | --- |
| Instruments with canonical financial facts | 31 | Not historical eligible universe members. |
| Instruments with any direct annual-input basis observation | 25 | 45 exact-scope observations: 22 consolidated, 23 standalone. |
| Financial-fact period span | 2022-03-31 through 2026-06-30 | Publication timestamps span 2022-05-13 through 2026-08-25. |
| Observations with all five direct input families ready for 3/5 years | 0 / 0 | Direct mappings intentionally lack other required families; this is not an eligibility inference. |
| Revenue/PAT/persistence 3-observation factual receipts | 6 | Exact receipt availability only. |
| Closing + average ROE receipts | 7 | Exact equity/PAT matching only. |
| Annual + cumulative-3 CFO/PAT + cash receipts | 6 | Exact matching annual receipts only. |
| All currently testable metric families, 3-observation form | 6 | Still not a non-financial historical panel. |
| All currently testable metric families, 5-observation form | 6 | Still not a non-financial historical panel. |
| Historical security identities | 0 | Listing lifecycle and renames are unavailable. |
| Historical memberships | 762, all effective/known 2026-08-30 | Current-style active snapshot only. |
| PIT taxonomy classifications | 711, all as-of 2026-08-27 | No company-type discriminator or historical time series. |
| Historical bars | 2,561 instruments; 2023-08-21 through 2026-08-31 | Coverage does not repair universe survivorship. |
| NIFTY 500 benchmark bars | 1,673; 2023-08-21 through 2026-08-30 | Benchmark series is available for later guarded work. |

The six factually complete receipt observations include neither an approved
historical universe definition nor a non-financial classification. They cannot
be treated as empirical coverage, calibration sample, or backtest readiness.

## PIT and basis rules for a later assembler

For each evaluation date, a future assembler must first resolve an immutable
historical membership and security lifecycle record that was both known and
effective at that date. It must then resolve a canonical company type known at
that date and require `NON_FINANCIAL`. Only after those checks may it select
the existing financial vintage at the same as-of and calculate one
exact-scope derived receipt. Consolidated and standalone observations are
separate; no preference, fallback, or mixing is authorized here.

Financial evidence received after the evaluation as-of and later restatements
not then visible remain excluded by the existing selector. Missing,
conflicted, non-comparable, or unavailable metric receipts remain explicit.

## Future outcome readiness, not outcomes

Business outcomes can later reuse subsequent PIT financial vintages for future
revenue, PAT, ROE, CFO/PAT, and loss/profit-deterioration observations, but
only after membership and company-type evidence are repaired. Market outcomes
can later reuse historical bars, NIFTY 500-relative bars, sector lineage, and
integrity assessments. Sector-relative outcomes remain unavailable until
historical sector lineage exists.

Any market-return start must be the first tradable session **after** the
financial evidence became publicly available; fiscal period end is never an
information date. Price adjustment and corporate-action integrity must be
valid for each outcome. No outcome was calculated in this slice.

## Required future validation and trial ledger

Any future candidate research must pre-register chronological development,
validation, and untouched test periods after actual coverage is measured. It
must purge or otherwise exclude forward outcome windows that overlap a later
partition; random IID splits are prohibited.

Every future attempted candidate, including failed variants, must have an
immutable trial ledger containing candidate identity, metric definitions,
thresholds, windows, universe/membership lineage, data vintage, evaluation
period, outcome definitions, and result. This controls multiple testing; it
is not implemented by this readiness artifact.

## Smallest next blocker

Acquire or import an immutable, primary-source historical universe/lifecycle
dataset that includes listing start/end, symbol/ISIN continuity, inactive and
delisted/merged securities, and effective/known historical membership.
Separately establish an approved PIT company-type classification capable of
exactly identifying non-financial entities. Until both exist, a candidate-grid
research harness must not be built.
