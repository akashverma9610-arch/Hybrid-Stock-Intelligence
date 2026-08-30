# Canonical fundamentals

`app.fundamentals` normalizes already structured financial-result inputs into immutable `FinancialFact` records. It is not a PDF/OCR/XBRL parser, a consensus-provider adapter, an investment score, or a trading service.

Reported facts retain exact Decimal values, currency/unit/scale (`UNITS`, thousands, lakhs, crores, or millions), filing ID, source/attachment reference, publication time, receipt time, scope, basis, and normalization version. A reported fact cannot be orphaned from a financial-results filing. `REPORTED`, `DERIVED`, `GUIDANCE`, and `CONSENSUS_ESTIMATE` are distinct kinds; this phase produces only reported and derived facts. Estimates are never treated as actual results.

Queries require both `published_at <= as_of` and `received_at <= as_of`; period end is not availability. Standalone and consolidated series are never merged. Quarterly, annual, TTM, and point-in-time balance-sheet facts retain an explicit `QUARTER_ONLY`, `YEAR_TO_DATE`, `FULL_YEAR`, or `UNKNOWN` basis.

The small deterministic derivation service can produce a Q4 from FY minus compatible 9M YTD, a TTM from four compatible reported quarter-only observations, growth rates, margins, selected balance-sheet ratios, and FCF only where the CAPEX sign is explicit. Derived facts/metrics retain all parent fact IDs and are not replacements for reported history. Missing coverage, bad denominators, mixed scope/basis/currency, or ambiguous CAPEX produce no guessed value.

`FundamentalSnapshot` is a low-volume factual summary boundary for future stock-analysis use. It does not change decision-score formulas. Read-only API endpoints are `/api/v1/fundamentals/{symbol}?as_of=...` and `/api/v1/fundamentals/{symbol}/series`; neither retrieves providers or writes records.

SQLite is the local/test normalized store; PostgreSQL uses NUMERIC-compatible persisted payloads and the same immutable contract. Live fundamental providers, full XBRL/PDF parsing, consensus estimates, and a stock-analysis formula adapter remain deferred.

## Existing-engine wiring

`FundamentalsEngineAdapter` is the single bridge from eligible stored reported facts and primary filings to the pre-existing `AsOfSnapshot`/`FinancialObservation` contract used by the fundamental diagnostics. It does not add a second analysis engine or formulas. It selects one statement scope for the full input (consolidated when available, otherwise explicit standalone fallback), preserves factual filing context, and excludes unresolved same-period conflicts. A later explicit revision is used only after its publication and receipt time; historical snapshots retain the original fact.

The runtime stock stage is opt-in: with the adapter plus an existing stock-analysis builder supplied, it publishes that builder's existing analysis result. Default runtime behavior remains unchanged. Missing/partial fundamentals are visible as incomplete adapter input, never as zero values. Score weights, diagnostics, and gates are unchanged.

Recognized local NSE XBRL-converted exports can add structured reported facts. Unknown taxonomies are rejected rather than inferred; no document text is parsed.

Yahoo Finance secondary-research statement tables are stored separately as
immutable raw snapshots. They carry `OBSERVED_AT_FETCH_ONLY` availability and
can support human reconciliation research, but they are not `FinancialFact`
records, cannot replace official BSE/NSE filings, and cannot make a fundamental
diagnostic complete.

For the current official BSE XBRL ingestion status, including the conservative
historical-acquisition blocker and the production evaluator period matrix, see
[Official BSE financial-history acquisition](BSE_OFFICIAL_FINANCIAL_HISTORY.md).
