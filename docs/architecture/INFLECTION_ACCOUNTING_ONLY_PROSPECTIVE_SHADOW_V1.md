# Inflection Accounting-only Prospective Shadow V1

**Status: `FUNDAMENTAL_INFLECTION_ACCOUNTING_SHADOW = ACTIVE / RESEARCH_SHADOW / WATCH_ONLY / NON_EXECUTABLE / QUALIFICATION_NOT_EVALUATED`.**

`INFLECTION_ACCOUNTING_ONLY_PROSPECTIVE_SHADOW_V1` is a narrow, forward-only
ledger for factual quarterly Revenue and PAT acceleration observations. It
reuses, without changing, canonical issuer/instrument identity, PIT
company-type classification, selected financial fact vintages, financial
observation bundles, and the existing t/t-1/t-4/t-5 derived-metrics receipt.
It does not create an Inflection candidate, score, rank, signal direction,
setup, Six-Gates result, trading instruction, portfolio change, price return,
or market-reaction result.

## Admission and immutable observation

An observation is allowed only at an explicit timezone-aware `as_of` at or
after the fixed prospective activation boundary `2026-09-04T00:00:00+00:00`.
The boundary is a recorded governance datum, not a runtime clock. Thus no
2022–2025 record can be inserted as if HSI had frozen it then. The local
command requires the cutoff explicitly:

```powershell
python -m app.runtime inflection-accounting-prospective-shadow --as-of <UTC-ISO-8601>
```

For each exact `CONSOLIDATED` or `STANDALONE` basis, admission requires a
PIT-valid classified `NON_FINANCIAL` company-type receipt; exact issuer and
instrument lineage; selected reported quarterly Revenue/PAT facts visible by
the cutoff; an exact period identity; no selected-vintage conflict; and at
least one metric that is either `ACCELERATION_OBSERVED` or an explicit
non-comparable accounting state. Revenue and PAT are independently ready: a
Revenue-only or PAT-only observation is valid when its own evidence is exact.
Both are never required merely because both metrics exist.

The immutable observation retains the issuer, canonical security and ISIN
when encoded in the canonical identity, company-type receipt, statement
scope, current-quarter identity, explicit cutoff, the full Revenue/PAT
derived receipts and their four source fact lineages, raw YoY/acceleration
values or special states, proposal and frozen candidate-grid fingerprints,
and deterministic ID/fingerprint. It is only
`ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE` or
`ACCOUNTING_INFLECTION_NON_COMPARABLE`; neither is positive or negative
investment meaning.

Loss-to-profit, profit-to-loss, loss-to-loss, zero-base, near-zero/base,
basis-change, period-alignment, restatement conflict, missing and
non-comparable states remain the source receipt's factual states. No
percentage, normalization, strength, confidence, materiality, expiry,
consensus surprise, guidance, analyst revision, or market reaction is
invented.

## Event-time and candidate-grid limitations

Every record states `EXACT_INTRADAY_EVENT_TIME_UNAVAILABLE` and retains
`MARKET_EVENT_TIME_UNRESOLVED`. A safe accounting cutoff can freeze known
facts; it cannot establish same-day tradability, first tradable session, gap,
return, volume or attribution. Consequently:

- `INFLECTION_QUALIFICATION = NOT_ACTIVE`.
- `INFLECTION_MARKET_REACTION = NOT_ACTIVE`.
- `CANONICAL_CONSENSUS_DATA_MISSING`, `REVISION_DATA_MISSING`, and
  `CANONICAL_GUIDANCE_DATA_MISSING` remain blocked dimensions.

The frozen plan retains the predeclared `ONE_QUARTER`,
`TWO_CONSECUTIVE_QUARTERS`, and `THREE_CONSECUTIVE_QUARTERS` research windows
solely as anti-hindsight lineage. It does not evaluate a confirmation window
or transform one into a candidate.

## Outcomes and persistence

Each inserted observation has a separately immutable linked initial accounting
outcome at the same cutoff with `IMMATURE` maturity and no future fact
lineage. `IMMATURE` is not failure. A later factual outcome must be a new
record with real later metric-receipt fingerprints; it cannot overwrite the
source observation. The contract defines `PARTIALLY_MATURE`, `MATURE`,
`DATA_MISSING`, and `NON_COMPARABLE` for that later bounded work but does not
evaluate them yet.

The existing generic `core_api_snapshots` store has the dedicated
`INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW` family. It writes the frozen plan,
observations, initial outcomes and coverage report insert-only. Identical
replay is `ALREADY_PRESENT`; a changed payload for the same identity fails
closed. New PIT-valid facts, restatements, basis changes, company-type changes
or a changed selected fact vintage can create a new identity. UI requests,
market ticks and unchanged daily runs cannot.

## Non-goals

No historical reconstruction, broad filing-timezone hunt, Compounder change,
Discovery, sell/harvest/rotation work, API/UI activation, scheduler, provider
request, portfolio access, broker/order access, capital authorisation, or
BUY/SELL/HOLD output is in scope.

`FILING_TIMESTAMP_TIMEZONE_COVERAGE = UNAVAILABLE` remains accepted and does
not block this accounting-only ledger.
