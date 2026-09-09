# Canonical 15m Technical Reader Activation V1

**Status:** `IMPLEMENTED_READ_CONTRACT / LIVE_DATA_NOT_READY / RULES_NOT_ACTIVATED / INTERNAL_RADAR_NOT_ACTIVE`

## Purpose and bounded activation

`app.market_data.canonical_fifteen_minute_technical_reader` is the only read boundary added by this slice. It reads persisted canonical prospective `15m` receipts and projects eligible completed OHLCV bars into a provider-neutral, bounded technical-input contract.

```text
immutable canonical 15m receipt store
  -> exact-security, known-at-aware technical reader
  -> CanonicalFifteenMinuteTechnicalInput
  -> future consumer (not implemented by this slice)
```

Activation means only that canonical 15m storage can be read through this contract. It does not activate an indicator, diagnostic Rule, Setup, Six Gates, Internal Radar, alert, signal, UI, provider session, broker, order, or portfolio action.

## Reused architecture

| Concern | Reused contract | Reader rule |
| --- | --- | --- |
| Canonical timeframe | `CanonicalTechnicalInterval(MINUTE, 15)` and `Timeframe.FIFTEEN_MINUTES` | Exact `15m`; no `DHAN_15M` alias. |
| Identity | `CanonicalProspectiveFifteenMinuteReceipt` | Exact canonical security only; no symbol/name/provider-ID lookup. |
| Session | Canonical prospective 15m partition | One approved session partition; full 15-minute interval only. |
| Quality | Receipt `CLOSED` state and no receipt reasons | Incomplete, conflicted, no-trade, malformed, and conflict-artifact evidence cannot enter OHLCV output. |
| PIT knowledge | Immutable receipt `known_at` | Strict read includes only `known_at <= as_of`; no runtime/current clock. |
| Provenance | Canonical bar/derivation/source-lineage fingerprints | All survive in the provider-neutral output. |
| Storage | Immutable Core snapshot repository | Indexed exact-security receipt/conflict reads; no scan across all securities. |

The resulting `CanonicalFifteenMinuteTechnicalBar` contains canonical security, `15m`, session ID, interval, OHLCV, `known_at`, canonical bar fingerprint, derivation-policy ID/version/fingerprint, and source-lineage fingerprint. It contains no provider packet, provider security ID, authenticated data, or raw tick structure.

## Read modes and eligibility

| Mode | `as_of` | Meaning |
| --- | --- | --- |
| `AS_OF_PROSPECTIVE_PIT` | Required, UTC-aware | A bar is visible only if the immutable receipt was known at or before the supplied cutoff. |
| `CURRENT_DESCRIPTIVE` | Prohibited | Returns the latest currently stored eligible receipts. It is expressly not strict historical PIT. |

Eligibility requires exact canonical security identity; a `CLOSED` receipt; an attached canonical bar; zero receipt reasons; matching receipt/bar `known_at`; exact 15-minute session partition; valid tamper-evident snapshot and receipt fingerprints; and no retained conflict artifact known by the same strict cutoff for that receipt. A later conflict cannot rewrite an earlier prospective read. Malformed, duplicate, incomplete, gap-affected, conflicted, residual, and cross-session artifacts fail closed. The derivation contract itself prevents residual shortened intervals from becoming a canonical `15m` receipt.

Lookback is a caller-supplied bounded count (`1..100`), not a strategy minimum. Bars are always returned in ascending canonical interval order. If there are fewer eligible bars, the reader returns the available evidence plus `INSUFFICIENT` and explicit reason codes; it never backfills, interpolates, or forward-fills a price.

## Continuity, no-trade, and conflict semantics

Reader output reports eligible-bar count separately from descriptive continuity metadata. This is intentional: no universal indicator continuity policy is approved.

| Evidence state | Reader treatment |
| --- | --- |
| Fully observed interval with no trade | `NO_TRADE_UNMATERIALIZED`; no OHLCV bar and no prior-close fill. |
| Provider/reconnect/unobserved gap or incomplete source | Excluded; `OBSERVATION_GAP_OR_INCOMPLETE`. |
| Receipt conflict or retained conflict artifact | Excluded; `EVIDENCE_CONFLICTED`. |
| Special-session residual | Not materialized by the upstream full-partition contract. |
| Consumer-specific continuity decision | `CONTINUITY_POLICY_UNSET`; future consumers must select their own approved rule. |

## Technical-input and Rule boundary

`canonical_fifteen_minute_technical_input` can return `CANONICAL_15M_INPUT_AVAILABLE` only for a strict, ready read and a caller-supplied exact canonical `Instrument`. It projects the bars into the existing generic `AsOfSnapshot`/`MarketObservation` technical-input shape. It is a data/readiness adapter, not a second Technical Brain and not a binding to any diagnostic evaluator.

The frozen `RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE` remains unchanged at 61 × 3 = 183 rows. `15m` cannot be relabeled as `30m`, `1H`, or `4H`; daily evidence cannot become `15m`. Rule 14 continues to require genuine timeframe evidence and no Rule becomes ready merely because this reader exists. The existing Daily and Weekly current-descriptive readers are untouched.

## Storage efficiency and present evidence state

The local SQLite snapshot implementation now indexes the existing immutable receipt JSON fields by snapshot family, exact canonical security, and interval; it also indexes conflict receipt IDs. The reader requests at most 100 receipts for one exact canonical security and only the matching conflict IDs. It does not enumerate all 2,287 potential identities or add a table, migration, retention policy, raw-tick store, or write path.

`DHAN_EXACT_IDENTITY_CAPACITY = 2,287` remains a mapping capacity, not live coverage. At the time of this reader implementation, `LIVE_RUNTIME_PROVIDER_PROOF = NOT_EXECUTED_CREDENTIALS_UNAVAILABLE`; actual stored-security, stored-bar, and live-security counts must be reported from a read-only database audit rather than inferred from that capacity.

## Readiness matrix

| Capability | State | Evidence / reason |
| --- | --- | --- |
| Canonical 15m reader implementation | `READY` | Exact canonical persisted-receipt reader with focused storage/PIT tests. |
| Exact security identity | `READY` | Canonical ID only; unknown/no-store result fails closed. |
| Finalized complete filter | `READY` | Closed, conflict-free, full-partition receipts only. |
| Known-at as-of filter | `READY` | Explicit strict cutoff, no current-time lookup. |
| Current-descriptive mode | `READY` | Separate mode with no historical-PIT claim. |
| Continuity metadata | `PARTIAL` | No-trade/gap/conflict are distinct; consumer policy is unset. |
| Canonical 15m technical input | `READY` | Readiness adapter only; no Rule binding. |
| 15m Rule input readiness | `NOT_READY` | Rule-specific policy/data proof is not created here. |
| Internal Radar 15m input contract | `READY` | A future Radar can request exact-security, eligible completed bars with explicit as-of semantics and no provider knowledge. |
| Internal Radar | `NOT_ACTIVE` | Explicitly out of scope. |
| Live 15m data | `NOT_READY` | Credentials/provider-session canary has not been exercised. |
| 30m / 1H / 4H | `NOT_READY` | Their interval policy remains unresolved; no substitution is permitted. |

The next continuation remains a product/governance choice. Deterministic Internal Radar work can use test-only or genuinely stored canonical bars without claiming live production readiness. A live provider canary is the separate prerequisite for any claim of live 15m coverage.
