# Compounder Prospective Shadow Validation V1

**Status: `COMPOUNDER_RESEARCH_SHADOW_OPERATIONAL / NON_EXECUTABLE / QUALIFICATION_NOT_EVALUATED`.**

## Decision and boundary

`COMPOUNDER_PROSPECTIVE_SHADOW_VALIDATION_V1` is the forward-only research ledger that follows the closed historical-panel assessment. It is not a Compounder policy, candidate evaluator, score, ranking, strategy activation, or product signal. Its purpose is to freeze verified current-or-future fundamental observations and wait for genuine future evidence.

```text
PIT company type + exact session identity + PIT annual facts + derived metrics
    -> immutable prospective observation -> future outcome evidence
```

It never runs the candidate grid. It never emits `COMPOUNDER`, `QUALIFIED`, `NOT_QUALIFIED`, `SHADOW_CANDIDATE`, or `SHADOW_NOT_QUALIFIED`. Every persisted observation carries the fixed posture `WATCH_ONLY / RESEARCH_SHADOW / NON_EXECUTABLE / QUALIFICATION_NOT_EVALUATED`.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` remains explicit. Source facts and exact receipts are facts/data; the prospective ledger makes no Compounder inference.

## Immutable observation contract

An accepted observation retains canonical instrument, ISIN, exact issuer/CIN, issuer-observation ID/fingerprint, one exact NSE session-point identity, one classified `NON_FINANCIAL` company-type receipt, explicit `as_of`, and separate maximum input-known time. It preserves exactly one basis (`CONSOLIDATED` or `STANDALONE`), the full canonical annual-fact readiness receipt, selected direct-fact IDs/fingerprints, raw deterministic derived metric states/values, selector and company-type policy versions, proposal version, candidate-grid plan lineage, and a deterministic ID/fingerprint.

The current direct/derived subset is factual only: revenue/PAT growth and persistence, closing/average-equity ROE summaries, CFO/PAT, and cash trajectory. ROCE, ROIC, FCF, margin durability, debt quality, dilution, reinvestment quality, and incremental ROIC remain unavailable and are not estimated from adjacent measures.

An observation is accepted only where all are true at the same explicit cutoff:

1. One exact NSE session identity exists for the instrument ISIN and cutoff date.
2. A canonical issuer observation and classified `NON_FINANCIAL` type receipt are PIT-valid.
3. The basis is exact; required factual metric receipts are available and comparable.
4. Canonical facts, annual selection, and derived metrics are conflict-free.
5. The cutoff is not earlier than any required input known time.

Every other result is a non-persisted readiness diagnostic: `SECURITY_IDENTITY_UNAVAILABLE`, `ISSUER_EVIDENCE_UNAVAILABLE`, `COMPANY_TYPE_UNAVAILABLE`, `UNSUPPORTED_COMPANY_TYPE`, `FINANCIAL_FACTS_MISSING`, `METRICS_INCOMPLETE`, `METRICS_NON_COMPARABLE`, `EVIDENCE_CONFLICTED`, `BASIS_MISMATCH`, or `INPUT_AFTER_AS_OF`.

New facts, valid revisions, company-type changes, or changed required metric inputs warrant a new immutable observation only after a complete exact PIT join. A page load or market tick does not. Existing observations are never modified.

## Candidate-grid lineage and outcome contracts

The `compounder-candidate-grid` plan freezes the documented research values for annual observation windows, revenue/PAT CAGR, median ROE, cumulative CFO/PAT, and persistence. It is `NOT_APPROVED_NOT_ACTIVE_NON_EXECUTABLE`; the fingerprint is anti-hindsight lineage only. No value is applied, selected, compared, or stored as a result.

Future business outcome horizons are `ONE_YEAR`, `THREE_YEARS`, and `FIVE_YEARS`. An initial observation marks each `IMMATURE`, never failed. A future available outcome requires real later annual-fact IDs. This slice creates no outcome receipt without that evidence.

All market telemetry is `MARKET_OUTCOME_NOT_READY`. Forward return, benchmark/sector relative return, MFE, MAE, and drawdown remain uncalculated while exact post-input price and price-integrity/adjustment-basis contracts are unavailable. This decision does not repair price data.

## Persistence, command, and current baseline

The existing `core_api_snapshots` store has the dedicated `COMPOUNDER_PROSPECTIVE_SHADOW` family. Candidate-grid plan, accepted observations, and the first coverage receipt are insert-only and duplicate-safe. Immediate replay cannot add an equivalent observation; incomplete issuers never create a full observation.

Run only with an explicit cutoff:

```powershell
python -m app.runtime compounder-prospective-shadow --as-of <UTC-ISO-8601>
```

The command performs no network acquisition, scheduling, API/UI activation, portfolio access, provider call, order/broker call, setup/gate creation, or candidate evaluation. It is restart-safe and has no runtime-clock semantic.

At `2026-09-04T19:30:59.533938+00:00`, the generic production run considered 167 currently classified non-financial issuers. It persisted zero observations: 157 reporting-basis evaluations lacked canonical financial facts and 19 otherwise relevant evaluations lacked an exact session identity. This intended fail-closed baseline does not trigger a repair or archive search.

The generic assessment also governs APARINDS, DEEPINDS, GENUSPOWER, GLAND, and ICICIBANK; no named-security exception exists. ICICIBANK remains outside the `NON_FINANCIAL` contract. At this baseline, no target has an accepted prospective observation because exact joined inputs are not simultaneously present.

## Governance and non-goals

Candidate thresholds can be considered only through future human/governance approval after enough prospective empirical evidence. The system cannot self-activate.

No historical reconstruction, discovery, Decision Score, Six Gates, holding review, harvest, sell, rotation, paper trade, API, UI, portfolio mutation, order, broker, capital authorisation, or investment instruction is in scope.

`COMPOUNDER_RESEARCH_SHADOW_OPERATIONAL`

`COMPOUNDER_QUALIFICATION_DEFERRED_PENDING_EMPIRICAL_VALIDATION`

`HISTORICAL_BACKTEST_RECONSTRUCTION_CLOSED`
