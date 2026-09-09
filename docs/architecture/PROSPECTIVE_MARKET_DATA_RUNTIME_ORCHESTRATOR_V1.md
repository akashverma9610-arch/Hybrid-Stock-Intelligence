# Prospective Market-Data Runtime Orchestrator V1

**Status:** `IMPLEMENTED / DISABLED_BY_DEFAULT / OPERATOR_INFRASTRUCTURE_ONLY`

## Purpose and boundary

This V1 coordinator is the single in-process owner for a prospective Dhan
Quote-mode market-data session.  It exists only behind an explicit operator
start and reuses the existing `DHAN_LIVE_MARKET_ENABLED` enablement convention.
An import, FastAPI application startup, page load, API route, or ordinary test
does not create a Dhan connection.

```
one operator-owned runtime
  -> governed Dhan subscription snapshot
  -> documented binary Quote packet parser
  -> normalized prospective event (event_time != received_at)
  -> existing prospective 1m builder
  -> canonical prospective 15m derivation
  -> append-only canonical 15m receipt store
```

It is neither a user-specific socket nor a second market Brain.  It introduces
no technical reader, diagnostic Rule, Internal Radar invocation, signal, setup,
portfolio access, alert, order, broker path, API route, UI surface, raw-tick
archive, or retention policy.

## Reused canonical components

| Concern | Reused component | V1 coordinator role |
|---|---|---|
| Credentials, socket URL, diagnostics | Existing Dhan credential and transport boundary | Intentionally injected outside the coordinator; no credential enters a receipt or health object. |
| Provider limits, subscription JSON, parser | `app.market_data.dhan_live_bar` | Uses the verified Dhan V2 Quote contract: 5,000 instruments/connection and 100 instruments/request. |
| Event normalisation | `DhanProspectiveMarketEvent` | Preserves source `event_time` and original packet `received_at`. |
| Session authority | `CanonicalMarketSessionCalendar` | Admits only canonical `REGULAR_CONTINUOUS` minutes; it does not hard-code ordinary hours. |
| 1m evidence | `ProspectiveDhanOneMinuteBarBuilder` | Preserves late-start, gap, duplicate and incomplete semantics. |
| 15m evidence/persistence | `prospective_fifteen_minute_bar` | Derives only covered partitions and uses the existing append-only snapshot store. |

## Runtime state and ownership

The deterministic state vocabulary is `STOPPED`, `STARTING`, `CONNECTING`,
`SUBSCRIBING`, `RUNNING`, `DEGRADED`, `RECONNECTING`, `STOPPING`, and `FAILED`.
`RUNNING` means an explicit transport was opened, all bounded subscription
messages were submitted, and the 1m builder received a run-specific connection
boundary.  It does not claim a live trade in every security.

A class-level in-process ownership guard prevents two V1 coordinators in one
process.  It is released only on explicit stop or failed start.  Distributed
host leasing is deliberately not invented:

`CROSS_HOST_MARKET_RUNTIME_LEASE = NOT_READY`.

Each explicit start requires a caller-supplied unique `run_id` and a UTC
`started_at`.  Its immutable receipt fingerprints non-secret runtime settings,
the exact universe, provider contract, and calendar evidence.  It never
contains a token, client ID, secret, header, password, authenticated URL, or
raw credential material.

## Subscription snapshot and liveness

The runtime consumes an immutable, governed universe snapshot.  It retains the
selected denominator, exact-ready identities, every blocked identity, and the
sorted blocker distribution.  The current recorded mapping state is 2,287
exact-ready of 2,553 selected, with 266 blockers; V1 does not repair or hide
them.  Batching is recomputed from the snapshot, so 2,287 exact identities
produce 23 requests without exceeding 100 identities per request or creating
an unnecessary second connection.

Provider-message liveness is independent of an individual security trading.
Unsupported but received provider frames can update provider-message liveness;
an illiquid security therefore cannot be misclassified as a dead socket.

## Loss, session, and finalisation safety

- A bounded queue has no unbounded memory mode.  Queue rejection records a
  gap; later affected minute evidence cannot be promoted to complete.
- Malformed, unsupported, wrong-segment, unknown-security, duplicate, and
  non-regular-session frames are isolated and never mutate canonical evidence.
- A disconnect records an unobserved boundary.  Reconnect is explicit, bounded,
  reuses exactly the same universe, and does not repair the lost interval.
- Start late and process restart preserve the 1m builder's mid-interval
  incompleteness semantics.  A restart clears unfinished in-memory windows;
  it cannot join observations across a process boundary.
- Stop clears unprocessed frames, closes the owned transport, releases local
  ownership, and never force-finalizes active 1m or 15m windows.
- Canonical 15m derivation starts only after all fifteen corresponding final
  1m receipts are available.  It activates no 15m reader and no Internal
  Radar.

## Storage and live proof

Only the already-approved append-only canonical 15m receipt/conflict artifacts
are persisted.  No raw tick archive or whole-universe long-retention 1m store
is created.  The health receipt reports the explicit states:

- `WHOLE_UNIVERSE_LONG_RETENTION_1M = NOT_APPROVED`
- `RAW_TICK_RETENTION_POLICY = UNSET`

The coordinator is deterministic-test ready, not an assertion of live capture.
Where secure Dhan credentials are unavailable, its truthful provider proof is
`LIVE_RUNTIME_PROVIDER_PROOF = NOT_EXECUTED_CREDENTIALS_UNAVAILABLE`.
No unattended whole-universe capture or market-hours canary is started by this
implementation.

## Validation and activation state

Focused tests cover disabled import/start behavior, immutable universe and
2,287-style batching, ownership, normalized packet routing, timestamp
preservation, malformed/unknown isolation, liveness, backpressure, session
exclusion, reconnect, restart/shutdown, 1m-to-15m persistence, redaction, and
static no-execution dependencies.  Existing one-minute and 15m suites remain
the regression contract.

| Capability | State |
|---|---|
| Shared prospective runtime coordinator | `READY / DISABLED_BY_DEFAULT` |
| Canonical 15m persistence wiring | `READY` |
| Live provider/session proof | `NOT_EXECUTED_CREDENTIALS_UNAVAILABLE` |
| 15m technical reader | `NOT_ACTIVE` |
| Internal Radar | `NOT_ACTIVE` |
| 30m, 1H, 4H | `NOT_READY` |
| Cross-host runtime lease | `NOT_READY` |
