# Canonical Intraday Timeframe Derivation Policy V1 Candidate

**Status: `CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1_CANDIDATE / DOCUMENTATION_AND_DATA_POLICY_ONLY / NOT_ACTIVE`.**

## Purpose and boundaries

This candidate fixes provider-neutral derivation semantics for `15m`, `30m`,
`1H`, and `4H` from prospective one-minute evidence. It does not derive or
persist a higher intraday bar, activate live capture, modify Daily/Weekly
technical evidence, change any of the canonical 61 Rules, operate Internal
Radar, create a setup/signal/alert, mutate a portfolio, or call a broker/order
interface.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
NO_INDICATOR_EXPANSION = TRUE
LIVE_1M_PRODUCTION_CAPTURE = NOT_READY
HISTORICAL_BACKFILL_PIT = NOT_READY
RAW_TICK_RETENTION_POLICY = UNSET
WHOLE_UNIVERSE_LONG_RETENTION_1M = NOT_APPROVED
```

Canonical horizons remain exactly `SHORT_TERM`, `POSITIONAL`, and `LONG_TERM`.
`MID_TERM` is user-facing wording only. `SETUP_TYPE != HORIZON`. Pre-Breakout,
its thresholds, its setup semantics, and its positional association remain
unchanged.

The companion [machine-readable candidate](CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1_CANDIDATE.json)
is authoritative for fixed vocabulary. Its SHA-256 covers compact UTF-8 JSON
with sorted object keys, retained array order, and only `policy_fingerprint`
excluded:

```text
sha256:488ec1573dd07cfb75f0fe385f9957378767ac85aca2435ef6b42640eec33437
```

`POLICY_READY` means the candidate semantics are determinate. It never means
implementation, capture proof, technical-reader use, historical PIT, or
production activation.

## A. Existing intraday-bar archaeology

| Existing authority | Exact reuse point | Preserved boundary |
| --- | --- | --- |
| `app.market_data.dhan_live_bar` | Exact normalized event; separate immutable `event_time` and `received_at`; completed one-minute receipt; cumulative-volume, gap, no-trade, replay, and conflict semantics. | No feed starts and Dhan is never a canonical timeframe identity. |
| `CanonicalMarketSessionCalendar` | First-party effective-dated trading-day and `REGULAR_CONTINUOUS` phase source. | Dhan status is not exchange-session authority; no historical session is inferred. |
| `TechnicalTradingPeriod` | Venue/segment, session date, start/end, calendar identity/fingerprint, and session-source lineage. | No second session model. |
| `technical_bar_contract` | Typed interval, deterministic identity/fingerprint, completeness, `known_at`, derived parent lineage, and unresolved-4H protection. | No new store, reader, or evaluator binding. |
| Daily temporal and Weekly derivation contracts | Existing current-descriptive Daily/Weekly completeness and PIT semantics. | Daily/Weekly cannot be relabelled as intraday. |
| Rule/Horizon candidate | Frozen `61 × 3 = 183` rows and Rule 14 genuine-MTF protection. | No Rule, indicator, role, score, or horizon changes. |
| Immutable Core snapshot repository | Idempotent append-only evidence and separate conflict payloads. | No derived-bar persistence or retention authorization. |

The existing prospective 1m foundation is implementation-ready only. It does
not prove live market capture or a technical input.

## B. Canonical session anchor

Each future canonical intraday bar must lie in exactly one canonical
`REGULAR_CONTINUOUS` phase and retain session identity, session start/end,
timeframe, interval start/end, and session-source lineage. The exact phase
start is the anchor. Exchange-local boundaries come from the authoritative
calendar; persisted timestamps are UTC. No bar crosses a phase, session,
overnight interval, halt/reopen boundary, or special-session boundary.

The current [NSE market-timings page](https://www.nseindia.com/static/market-data/market-timings)
lists normal/odd-lot capital-market trading from 09:15 to 15:30. That is
reference context only: actual boundaries must come from PIT-visible canonical
phase evidence, not global clock strings or a backward inference.

## C. Standard 375-minute divisibility

| Timeframe | Full intervals | Remainder | Boundary issue | Candidate state |
| --- | ---: | ---: | --- | --- |
| `15m` | 25 | 0m | Session-open partitions exhaust the phase. | `POLICY_READY` |
| `30m` | 12 | 15m | Open anchor leaves a closing tail; close anchor leaves an opening head. | `POLICY_UNSET` |
| `1H` | 6 | 15m | The same tail/head choice is unresolved. | `POLICY_UNSET` |
| `4H` | 1 | 135m | A 135m segment is not another 4H bar. | `NOT_READY` |

For 30m/1H, the open-tail, close-head, heterogeneous-partial, separately
stored-but-excluded, and no-policy alternatives have different comparability,
closing/opening-information, live/historical-PIT, and indicator effects. This
candidate intentionally selects none. For 4H, session-close anchoring, rolling
windows, and cross-session composition are also unselected.

`CROSS_SESSION_INTRADAY_BAR = PROHIBITED`. Overnight information belongs to a
future Opening-Gap/Overnight engine, never a synthetic 4H bar.

## D. 15m derivation policy candidate

`CANONICAL_15M_DERIVATION_POLICY_V1_CANDIDATE` uses exact canonical phase-open
anchoring and fixed full 15-minute partitions. The reference sequence is
conceptually 09:15–09:30 through 15:15–15:30, but no implementation may
hardcode clock strings instead of consuming the calendar phase start.

| Element | Exact policy |
| --- | --- |
| Base evidence | Every one-minute slot must be a closed exact prospective receipt or an explicit proven `NO_TRADE_OBSERVED` receipt. |
| Gap/unobserved evidence | A provider gap, startup mid-window, unobserved minute, unverified receipt, unresolved volume baseline, or conflict yields no complete 15m bar. |
| OHLC | First/max/min/last genuine traded price only. Daily/provider-day H/L, forward fill, and interpolation are prohibited. |
| Volume | Sum valid incremental minute volume only. A proven no-trade minute contributes zero trades; missing baseline/volume is incomplete, never inferred. |
| Entire interval has no trades | Retain descriptive no-trade evidence only; do not materialize a zero-price or previous-close OHLCV bar. |
| Finalization | `known_at` is actual finalization at/after `interval_end` and all supporting known-at values. |
| Late repair / replay | Identical replay is idempotent. New conflicting evidence preserves prior lineage and creates a conflict/revision or fails closed; it never rewrites. |
| Special/short phase | Use exact canonical phase only; create full 15m partitions only and never a partial 15m bar. |
| Halt/reopen | Requires exact canonical phase evidence. Any unobserved required slot fails closed, never becomes no trade. |

The policy is semantically determinate, but current data, live proof, and
production readiness remain `NOT_READY`. The existing base binder has not
admitted special phases, and durable intraday storage/retention is unapproved.

## E. Special sessions, gaps, and no trade

Special/shortened sessions must use their actual PIT-visible canonical phase.
A later phase starts a new partition; no bar bridges a pause. If a phase length
is not divisible by the selected duration, its remainder is descriptive
shortened-interval evidence only and cannot become a homogeneous canonical
bar. The candidate adds no runtime state.

| Evidence fact | Meaning | Candidate result |
| --- | --- | --- |
| Continuous observation proves no trade | `NO_TRADE_OBSERVED` | May satisfy coverage but supplies no fabricated price; an all-no-trade aggregate is not OHLCV. |
| HSI joined mid-window, disconnected, or cannot prove observation | `PROVIDER_GAP_OR_UNOBSERVED_INTERVAL` | Required aggregate coverage fails closed. |
| Late or conflicting source evidence | Immutable evidence conflict/revision | Do not repair or rewrite a finalised bar. |

## F. OHLC, volume, completeness, and prospective PIT

```text
open/high/low/close = first / max / min / last genuine traded price
volume              = sum(valid incremental base volume in the exact window)
complete            = every required minute observed or proven no-trade,
                      with no gap, conflict, startup omission, or baseline failure
known_at            = actual finalisation, never before interval end or a parent known_at
```

A missing stored minute alone does not prove a gap where continuous observation
separately proves no trade; mere absence of events never proves no trade. No
price, volume, completeness, or knowledge time may be inferred.
`PROSPECTIVE_PIT` remains partial until a real captured session; nothing here
upgrades `HISTORICAL_BACKFILL_PIT`.

## G. Immutable lineage, storage, and provider neutrality

Every future derived artifact must retain canonical security, timeframe,
session, interval start/end, base-source/provider lineage, policy ID/version,
quality state, actual `known_at`, deterministic fingerprint, and deterministic
base-evidence lineage summary. It reuses existing canonical technical identity
and immutable conflict conventions, without demanding permanent raw packets.

```text
future transient / short-lived base evidence
  -> future durable canonical derived intraday bars + minimum immutable lineage
```

This is not a retention authorization. The 2,287 exact mappings have a
theoretical ceiling of 857,625 one-minute rows/day; the earlier 5,446-byte
representative receipt was a serialized-payload ceiling, not a SQLite-row-size
promise. No retention duration, deletion, raw archive, full-universe capture,
or database write is chosen.

Canonical IDs are `15m`, `30m`, `1H`, and `4H`, never `DHAN_15M` or
`DHAN_1H`. Provider identity remains lineage so another normalized provider
could support the same canonical contract.

## H. Rule×Horizon and Rule 14 protection

The canonical `61 × 3` matrix is unchanged. A timeframe slot cannot be
satisfied through `Daily -> fake 4H`, `15m -> fake 30m`, `15m -> fake 1H`, or
`1H -> fake 4H`. Only a future distinct completed, policy-approved,
lineage-certified timeframe could enter a genuine MTF reader. Rule 14 and
Pre-Breakout remain unchanged.

## I. Mandatory timeframe matrix

| Field | 15m | 30m | 1H | 4H |
| --- | --- | --- | --- | --- |
| Session divisibility | 25 + 0m | 12 + 15m | 6 + 15m | 1 + 135m |
| Session anchor | Exact phase start | `UNSET` | `UNSET` | `UNSET` |
| Boundary / tail policy | Full fixed intervals / none | `UNSET` | `UNSET` | `UNSET` |
| Special-session policy | Actual phase; full 15m only | `UNSET` | `UNSET` | `UNSET` |
| Base evidence | 15 exact 1m coverage states | Complete 1m if later selected | Complete 1m if later selected | Complete 1m if later selected |
| Gap / no-trade | Gap fail-closed; explicit no-trade only | Fail-closed / no fake OHLCV | Fail-closed / no fake OHLCV | Fail-closed / no fake OHLCV |
| OHLC / volume | Genuine prices / valid increments only | Same if activated | Same if activated | Same if activated |
| Completeness | Exact defined policy | `UNSET` | `UNSET` | `UNSET` |
| Known-at | Actual finalization after close | After close if activated | After close if activated | After close if activated |
| Policy readiness | `POLICY_READY` | `POLICY_UNSET` | `POLICY_UNSET` | `NOT_READY` |
| Data / live proof / production | `NOT_READY` / `NOT_READY` / `NOT_READY` | `NOT_READY` / `NOT_READY` / `NOT_READY` | `NOT_READY` / `NOT_READY` / `NOT_READY` | `NOT_READY` / `NOT_READY` / `NOT_READY` |

## J. Final readiness matrix

| Item | State | Precise reason |
| --- | --- | --- |
| A. Existing archaeology | `READY` | Existing 1m, calendar, technical bar, and immutable conflict contracts are reusable. |
| B. Session anchor | `READY` | Exact source-backed phase boundary is authoritative. |
| C. 375-minute audit | `READY` | Every full interval and remainder is explicit. |
| D. 15m policy | `READY` | Full interval, coverage, no-trade, PIT, and conflict semantics are explicit. |
| E. 30m policy | `PARTIAL` | Common guards exist; remainder boundary policy is unselected. |
| F. 1H policy | `PARTIAL` | Common guards exist; remainder boundary policy is unselected. |
| G. 4H policy | `NOT_READY` | No homogeneous NSE composition is selected. |
| H. Special-session policy | `PARTIAL` | Actual phase requirement is set; base special-session support is absent. |
| I. Gap policy | `READY` | Gap is distinct from no trade and fails closed. |
| J. No-trade policy | `READY` | Explicit observation only; no fake OHLCV. |
| K. OHLC policy | `READY` | Genuine trades only. |
| L. Volume policy | `READY` | Valid increments only. |
| M. Completeness | `READY` | Required base evidence must be complete, conflict-free, and observed. |
| N. Known-at/finalization | `READY` | Actual finalization after close/source knowledge. |
| O. Immutable revision | `READY` | Replay idempotency; conflict/revision otherwise. |
| P. Derivation lineage | `READY` | Security, interval, session, policy, source, quality, timing, and fingerprint are fixed. |
| Q. Storage interaction | `PARTIAL` | Shape is known; retention and durable derived storage are unapproved. |
| R. Provider neutrality | `READY` | HSI interval identity is distinct from provider lineage. |
| S. Rule/Horizon compatibility | `READY` | Canonical 61×3 unchanged. |
| T. Rule 14 protection | `READY` | Genuine interval identity remains mandatory. |
| U. Live proof | `NOT_READY` | No valid Dhan credential or live session proof. |
| V. Dhan identity blockers | `PARTIAL` | 2,287 exact ready; 5 missing provider IDs and 261 class mismatches remain visible. |
| W. Policy versioning | `READY` | Canonical JSON and tamper-evident fingerprint exist. |
| X. Unresolved parameters | `PARTIAL` | 30m/1H boundaries, 4H, special base support, storage, and retention remain `UNSET`. |
| Y. Next dominant blocker | `READY` | 15m is the next internally solvable bounded derivation. |

## Future Internal Radar boundary and continuation

```text
normalized provider event -> prospective base evidence -> completed canonical intraday bars
  -> future Internal Radar -> discovery lead -> 61 diagnostics -> Shared HSI Brain
```

Internal Radar is not implemented. The exact next continuation is:

`CANONICAL_PROSPECTIVE_15M_BAR_DERIVATION_V1`

It must reuse this policy, leave 30m/1H/4H unresolved, and keep retention,
Radar, technical evaluation, setup/trades, portfolio, alerts, and execution
outside scope.
