# Long-Term Compounder Canonical Annual Facts V1

**Status: `IMPLEMENTED / DATA-CONTRACT ONLY / NOT ACTIVE`.**

## Purpose and boundary

This is the factual prerequisite for later non-financial Compounder research.
It adds a deterministic, on-demand coverage receipt over the existing immutable
`FinancialFact` store.  It can answer, at a supplied historical as-of:

> Which directly mapped annual reported facts were legitimately visible for
> this instrument and exact statement scope?

It does not ingest a provider, create a second financial database, change an
existing `FinancialFact`, promote Upstox reconciliation observations, derive a
metric, assess business quality, rank an instrument, or qualify a Compounder.
The existing `FinancialFact` / `FinancialFactStore` persistence and
`select_financial_fact_vintages` PIT selector remain the only fact storage and
vintage-selection paths.

The receipt is factual only.  It cannot emit `SHADOW_CANDIDATE` or
`SHADOW_NOT_QUALIFIED`, a score, a setup, a Six-Gates result, a portfolio
action, or any BUY/SELL/HOLD/ADD/TRIM/EXIT/ROTATE instruction.  It has no
portfolio, broker, order, API, UI, database-write, provider, or runtime-clock
dependency.

## Existing canonical fact contract

`FinancialFact` already retains the immutable reported observation needed for
this layer:

- exact canonical instrument and `FinancialMetric`;
- Decimal value, currency, unit, and scale;
- annual/quarterly/point-in-time type and value basis;
- period start/end, fiscal year/quarter, and exact standalone/consolidated
  scope;
- reported versus derived kind, filing/source/source-reference provenance;
- publication and receipt timestamps, with `available_at =
  max(published_at, received_at)`;
- normalization version, parent and revision-of-fact lineage, and quality
  flags; and
- deterministic source fact IDs plus immutable JSON storage and insert-only
  conflict handling.

`FinancialFactNormalizationService` derives a reported fact ID from the
source, filing, canonical instrument, metric, period, scope, basis, and source
reference.  `SQLiteFinancialFactStore` and `PostgreSQLFinancialFactStore` save
an identical fact idempotently and reject a changed fact with that id or the
same immutable source context.  This slice creates no new table or migration.

The annual readiness receipt references source fact IDs; its own deterministic
fingerprints cover every result field and a canonical source-fact semantic
fingerprint.  It therefore does not duplicate numerical facts as a parallel
source of truth.

## Direct reported measure admission

The `CompounderAnnualMeasureFamily` receipt always reports all families below.
An entry is admitted only when the existing fact is `REPORTED`, `ANNUAL`,
`FULL_YEAR`, the exact requested scope, and the family has an exact direct
canonical mapping.

| Candidate family | Existing direct metric admitted in V1 | Statement family | Current rule |
| --- | --- | --- | --- |
| Revenue | `REVENUE` | Income statement | Direct reported fact only. |
| EBIT and/or EBITDA | None | Income statement | `DEFINITION_MAPPING_UNAVAILABLE`: V1 never substitutes EBIT, operating profit, EBITDA, depreciation, or any combination. |
| Profit after tax | `PAT` | Income statement | Direct reported fact only. |
| Cash flow from operations | `CFO` | Cash flow | Direct reported fact only. |
| Capital expenditure | `CAPEX` | Cash flow | Direct reported fact only; no balance-sheet inference or sign interpretation. |
| Debt / borrowings | `TOTAL_DEBT` | Balance sheet | Direct reported fact only; no arbitrary borrowing-line aggregation. |
| Shareholders' equity | `TOTAL_EQUITY` | Balance sheet | Direct reported fact only; no net-worth substitution. |
| Cash and cash equivalents | `CASH_AND_EQUIVALENTS` | Balance sheet | Direct reported fact only; no liquidity-line substitution. |
| Period-end shares outstanding | None | Share capital | `DEFINITION_MAPPING_UNAVAILABLE`: existing generic `SHARES_OUTSTANDING` cannot establish period-end rather than weighted-average basic/diluted shares or corporate-action treatment. |

An unavailable mapping is not a zero, neutral observation, or adverse company
finding.  It is a fail-closed data-contract state.  Later source-mapping work
must establish exact reported concepts before it can change this table.

## PIT and vintage rules

The receipt passes only already-loaded facts to the existing frozen
`financial-fact-vintage-selection-policy/v1-approved`.  It never performs a
repository "latest" query.  The selector:

1. accepts a fact only when `available_at <= as_of`;
2. excludes future observations;
3. groups facts by the full semantic key, including period, basis, scope,
   representation, metric, source contract, and normalization version;
4. preserves original and revision observations rather than overwriting them;
5. requires an explicit valid, acyclic, same-semantic revision chain for a
   revised vintage to supersede an earlier one; and
6. fails closed on conflict, missing revision parent, branch conflict, cycle,
   invalid chronology, or insufficient semantic identity.

Thus a historical as-of before a restatement selects the original visible
reported fact.  A later as-of can select its valid later revision.  Database
insertion time is never used as a substitute for availability.  Where an
existing ingestion contract explicitly defines first observation as the
availability boundary when publication time is unknown, that established fact
semantic is retained rather than reinterpreted by this module.

## Comparability and basis parity

The caller supplies one exact `StatementScope`; the receipt never changes,
prefers, or converts scope.  Annual `YEAR_TO_DATE`, `QUARTER_ONLY`, unknown
basis, standalone when consolidated was requested, and consolidated when
standalone was requested are not admitted.  They become `BASIS_MISMATCH` with
the applicable `FULL_YEAR_BASIS_REQUIRED` and/or `EXACT_SCOPE_REQUIRED`
reason.

Raw annual depth counts selected annual period ends.  Comparable annual depth
is stricter: a selected fact must also carry period start, period end, fiscal
year, and `period_start < period_end`.  A missing start does not cause fact
loss, but it creates `PERIOD_IDENTITY_INCOMPLETE` and does not count toward a
two-period comparison, three-year research, or five-year research.  No annual
duration, fiscal adjacency, percentage growth, CAGR, margin, ratio, or other
derived inference is calculated here.

## Receipt vocabulary

Each family returns one immutable `CanonicalAnnualFactCoverage` and the outer
`CanonicalAnnualFactsReadinessReceipt` has a stable fingerprint and explicit
serialization.  Permitted statuses are:

- `PIT_READY` — direct selected facts exist; this is availability, not
  Compounder eligibility.
- `CANONICAL_DATA_MISSING` — no exact direct reported canonical fact exists.
- `PIT_UNAVAILABLE` — supplied matching facts are not visible at the as-of.
- `EVIDENCE_CONFLICTED` or `INVALID_LINEAGE` — the existing selector failed
  closed.
- `BASIS_MISMATCH` or `PERIOD_IDENTITY_INCOMPLETE` — exact comparison parity
  is unavailable.
- `DEFINITION_MAPPING_UNAVAILABLE` — a required source concept has no
  approved exact mapping.

The receipt reports selected fact IDs, selected annual ends, source fact
fingerprints, future exclusions, conflicts, raw and comparable annual depth,
and factual two/three/five-period readiness flags.  A readiness flag cannot
be a threshold, a durability score, or a strategy state.

## Revision and share-count safety

Historical originals and later restatements remain immutable `FinancialFact`
observations.  Existing revision lineage is selector-verified; no current
receipt silently replaces historical knowledge.

No share-count fact is admitted yet.  Future work must retain distinct
period-end shares, weighted-average basic shares, weighted-average diluted
shares, issued share capital, and provider-adjusted market-data shares.  It
must also link a reported share observation to the applicable corporate-action
lineage (split, bonus, consolidation, rights issue, QIP, ESOP, acquisition
issuance, or buyback) before a future dilution-normalization policy is
proposed.  This V1 contract creates no dilution classification or linkage.

## Explicit exclusions and next dependency

This slice does **not** calculate EBIT/EBITDA, ROCE/ROIC/ROE, CFO/PAT, FCF,
net debt, debt/equity, interest coverage, dilution, margin durability,
reinvestment, incremental return, a Compounder score, a candidate grid, or a
backtest.  It does not create a data provider or turn Upstox fetch-time
fundamentals into canonical PIT facts.

Current stored facts can now be audited through one deterministic readiness
contract.  The next evidence-led step is a bounded primary-source canonical
ingestion and mapping proposal for missing direct non-financial annual facts,
including period-identity and share-count/corporate-action semantics.  Only
after adequate immutable history is actually populated may derived-metric
definition contracts be proposed.
