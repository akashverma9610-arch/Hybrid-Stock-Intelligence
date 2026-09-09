# Canonical Prospective 15m Bar Derivation V1

**Status: `IMPLEMENTED_DOMAIN_AND_BOUNDED_PERSISTENCE / LIVE_DATA_NOT_READY / TECHNICAL_READER_NOT_ACTIVE`.**

This document records the implementation of the accepted
`CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1_CANDIDATE` for `15m` only.
The policy artifact remains unchanged, including fingerprint
`sha256:488ec1573dd07cfb75f0fe385f9957378767ac85aca2435ef6b42640eec33437`.
No 30m, 1H, 4H, technical reader, Internal Radar, diagnostic, setup, signal,
runtime capture, portfolio, broker, or order behavior is activated.

## Implemented bounded contract

`app.market_data.prospective_fifteen_minute_bar` normalizes a completed
one-minute receipt into a provider-neutral minute-evidence contract, derives a
single security/session `15m` receipt, and persists only the compact,
immutable derived result through the existing Core snapshot repository.

```text
normalized provider event
  -> completed / explicit-no-trade one-minute evidence
  -> canonical prospective 15m receipt and, when traded, OHLCV bar
  -> future reader (not active)
```

The canonical bar identity is `15m`, a canonical security, exact session
identity, phase fingerprint, calendar fingerprint, and interval start/end. It
does not contain `DHAN_15M` or any provider identity. Provider families remain
in immutable source lineage so another provider can emit equivalent normalized
minute evidence without creating a different canonical timeframe.

## Session, coverage, and finalization

- The calendar resolves one PIT-visible `REGULAR_CONTINUOUS` phase; its exact
  phase start anchors all partitions. Persisted interval and knowledge times
  are UTC.
- Only complete 15-minute partitions wholly inside that phase exist. A 375
  minute ordinary phase yields exactly 25 partitions. Short/special phases
  yield only `floor(phase_minutes / 15)` full partitions; residual minutes are
  not labeled `15m` and are never merged or crossed into another phase.
- Each receipt requires exactly fifteen one-minute coverage states. A closed
  minute and an explicit observed-no-trade minute are distinct valid coverage
  states. Missing coverage, startup partiality, reconnect/provider gap,
  unverified volume, and source conflict fail closed.
- OHLC uses only the first, maximum, minimum, and last genuine traded prices.
  Observed no-trade contributes no price and zero volume. A fully observed
  no-trade window stores a descriptive `NO_TRADE_OBSERVED` receipt and no
  zero-price or forward-filled OHLCV bar.
- `known_at` is injected by the bounded caller, must be at or after both the
  interval end and every source `known_at`, and is never synthesized from a
  wall clock or a session boundary.

## Immutability and durable scope

The append-only `ProspectiveCanonicalFifteenMinuteStore` uses the existing
immutable Core snapshot store. Exact replay is `ALREADY_PRESENT`; a late
equivalent finalization leaves the stored receipt unchanged; changed evidence
creates a separate conflict artifact and cannot overwrite history. The result
retains canonical security, ISIN, `15m`, session and partition lineage,
provider-family and base-receipt lineage, policy ID/version/fingerprint,
completeness state, actual `known_at`, and tamper-evident fingerprints.

This is not approval for raw tick retention, permanent whole-universe 1m
retention, a background feed, a scheduler, or deletions. The expected ceiling
for the currently exact-ready 2,287 securities is:

| Scope | Theoretical upper bound |
| --- | ---: |
| One ordinary session | 57,175 rows (`2,287 × 25`) |
| 20 trading days | 1,143,500 rows |
| 250 trading days | 14,293,750 rows |

These are capacity ceilings only; they do not assert trading or completed
coverage for every security/interval.

## Current readiness

| Capability | State | Evidence / boundary |
| --- | --- | --- |
| Canonical 15m domain, session partitions, provenance, replay | `READY` | Unit coverage proves ordinary, special, gap, no-trade, conflict, and reopen behavior. |
| Bounded canonical 15m persistence | `READY` | Existing immutable snapshot repository with separate conflict records. |
| 15m live data | `NOT_READY` | No active prospective capture/session proof. |
| 15m technical reader / Internal Radar | `NOT_READY` | Explicitly outside this implementation. |
| 30m / 1H / 4H | `NOT_READY` | Their policy/boundary semantics remain unchanged and unresolved. |
| Rule 14 MTF use | `NOT_READY` | `15m` cannot be relabeled as 30m, 1H, or 4H; no Rule is activated. |
| Dhan whole-market identity | `PARTIAL` | 2,287 exact-ready; 5 missing provider IDs and 261 security-class mismatches remain unmodified. |

The next dominant prerequisite is a shared prospective runtime/capture
coordinator, not an Internal Radar activation:

`PROSPECTIVE_MARKET_DATA_RUNTIME_ORCHESTRATOR_V1`
