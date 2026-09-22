# Pilot source current-EOD acquisition and handoff v1

Status: `BOUNDED_SOURCE_IMPLEMENTATION / NOT_PUBLICLY_DEPLOYED / PARTIAL`

This document belongs only to `PILOT_SOURCE_OWNERSHIP_AND_ACQUISITION`.
Core V1 remains ACTIVE, Execution Gate V2 remains NOT_ACTIVE, and P1 prospective
start remains UNSET with recorder NOT_ACTIVE. No strategy, Brain, portfolio,
Auth0 boundary or price-basis selection is changed.

## Current EOD versus frozen history

[CurrentNseEodRefreshJob](../../app/data_operations/current_nse_eod.py) is separate
from [the historical UDiFF backfill](../../app/market_data/nse_udiff_daily_history.py).
The latter's end remains 2026-08-31. The new job accepts only a later completed
session resolved by the existing [first-party calendar](../../app/historical/nse_capital_market_session_evidence_2022_2026.py).
Unknown calendar days, missing phase timing, future universe context, missing
targets and ambiguous exact identities fail closed. No weekday-only fallback.

The shared target set is the existing canonical universe snapshot, not one
whole-market request per user. Exact ISIN and symbol must match. An absent or
multiple target row is a visible gap, not successful full coverage. An index
is not an equity constituent: the CM bhavcopy does not prove benchmark coverage.

The first official ZIP is retained through the existing snapshot artifact store;
bar parsing, validation and provider-versioned writes reuse existing UDiFF and
historical-store code. Readback is checked before publishing a verified
watermark. A subsequent invocation reads the same immutable archive and retains
its original observation time. A conflicting store result is not overwritten.
This is first-capture acquisition, not an automatic corrected-archive discovery
mechanism; later exchange corrections require explicit reconciliation.

Three time facts must remain separate:

- The bar's raw exchange timestamp is the source's labelled trade-date boundary,
  not an asserted publication or market-close timestamp.
- Archive `observed_at` is first HSI observation. Historical exchange publication
  remains unavailable; current observation cannot be backdated.
- Operations `completed_at` records ingestion completion. The calendar's resolved
  close may describe accepted session coverage, not the first availability of
  the payload. Neither operation health nor its watermark grants P1 eligibility.

Raw source acceptance does **not** certify adjustment compatibility, historical
known-at, complete technical windows, regime, sector, or P1 readiness.

## Source dependency ledger

[The source ledger](../../app/data_operations/source_dependency_ledger.py) is an
immutable, on-demand read result, not a database table or second evidence store.
It identifies consumer/run, canonical subject, family/provider, required versus
optional dependencies, native reference/fingerprint, source time, known-at,
ingestion time, freshness-policy reference and independent blocker states.

An owning reader must verify the complete manifest and native evidence/policy.
Partial lists cannot prove readiness. Missing mandatory data, stale data,
unverified metadata, unavailable known-at, unresolved identity and unavailable
policy are separately preserved as `SOURCE_MISSING`, `SOURCE_STALE`,
`SOURCE_UNVERIFIED`, `KNOWN_AT_INSUFFICIENT`, `IDENTITY_UNRESOLVED` and
`POLICY_UNAVAILABLE`. `READY_TO_EVALUATE` is only source handoff readiness;
it is never a signal, positive strategy finding or authorization.

Exact duplicate references coalesce; conflicting references remain visible and
block. UTC-normalized deterministic serialization includes all manifest and
reference fields. The content fingerprint excludes itself, not provenance.
The reader is backend-owned: it cannot trust a user's freshness or identity claim.
No new freshness duration or policy threshold is introduced.

**Still required:** production adapters that verify complete owning-source
dependencies for every P1 assessment input. The ledger interface and tests do
not imply those adapters exist. Existing P1 canonical readers/reducer/recorder
are unchanged and remain non-active. Regime and sector consumers likewise need
their complete, current-aligned native input manifests, not a successful NEWS
or EOD receipt.

## Worker composition and concurrency

[The bounded worker](../../app/data_operations/pilot_source_worker.py) composes
only current EOD using the existing `DataOperationsService`, durable run receipts,
two-attempt transient retry cap and shared universe. It runs once and exits:

```powershell
& .\.venv\Scripts\python.exe -m app.data_operations.pilot_source_worker --database D:\nse-stock-manager\data\nse_stock_manager.db --once
```

This is an operator command, **not an instruction to enable a timer**. Protect
and verify a current backup before material writes; verify integrity and exact
deltas afterward. The worker requires an existing database.

The additive worker uses a cooperative
[OS acquisition lock](../../app/data_operations/local_source_lease.py), scoped
to the resolved database path. Competing invocations fail before a source job
runs; no lock file is deleted based on age. Process/handle termination releases
ownership. Crash recovery replays canonical idempotent ingestion. This is
single-host cooperation, not distributed locking, a universal database lock,
or protection against unrelated programs ignoring the protocol. PostgreSQL
distributed worker exclusion is not claimed. Every provider job still owns its
bounded HTTP parameters; the wrapper cannot make an arbitrary adapter bounded.

The full regression identified exact historical source pins on the legacy CLI
and operations service. Proposed lock hooks into those frozen files were
removed, not whitelisted by weakening tests or rewriting historical artifacts.
Consequently, legacy CLI/scheduler entry points do **not** take this additive
lease. They must remain inactive during this worker's run. All-entry-point
coordination and broad recurring source composition remain incomplete; do not
claim an unattended production worker is ready from this entry-point proof.

The existing API is deliberately **read-only operations health**, with no job
dispatch. It reads the same durable receipts. Registering provider write jobs
in API startup would add unwanted behavior, not reconcile a defect. Existing
historical CLI jobs remain separate from current acquisition. NEWS retains its
existing job/ingestion boundary. No source scheduler has been enabled.

## Reference and consumer boundaries

On 22 September, official EOD source rows identify APOLLO (`INE713T01028`) and
MANORAMA (`INE00VM01036`) as EQ. The stored universe contains both symbol-only
legacy IDs and ISIN IDs for each. A source announcement without decisive ISIN
evidence therefore remains ambiguous; current EOD membership does not rewrite
the historical announcement's identity. There is no fuzzy resolution or new
security creation here.

Regime reuses `MarketRegimeEngine`: exact benchmark OHLC, its existing approved
strategy/rules, return lookback, trend and ATR inputs. No neutral fallback.
Sector logic reuses current-sector rotation: exact Nifty 500/sector identities,
20/60/120 aligned RS windows, current memberships and constituent 50/200-session
breadth (200 minimum, 320 preferred existing history coverage). Old ranking
timestamps are not current coverage. No new calibration or thresholds.

External discovery must use the existing verified package/intake schema,
deduplication, source provenance, PIT checks and quarantine. The disabled inbox
bridge is not re-enabled here. Its authenticated machine-ingestion route must
be reconciled with pilot Auth0 middleware before a bounded transport canary;
no bypass or service-to-human authority equivalence is permitted.
The current [pilot boundary](../../app/api/pilot_boundary.py) verifies managed
human identity and allowlists routes; the bridge's static intake Bearer is not
that human identity, and its POST is not an allowed pilot route. Enabling the
old timer would therefore not prove a working secure pilot transport.
The [Supabase API security guidance](https://supabase.com/docs/guides/api/securing-your-api)
was reviewed: service secrets stay server-side and do not substitute for HSI
resource authorization. No cloud grants, keys, RPCs or accounts were changed.

Broker-account holdings, funds and history remain a later closure gap. Dhan
profile/LTP and Upstox history canaries are not broker-account proof.

## Mandatory LIVE_SESSION_INTRADAY_CANARY

Before pilot intraday readiness, an operator must use the existing Dhan mapped
QUOTE/prospective runtime in an eligible canonical regular session:

1. Retain an exact source scope manifest for the existing five holdings, their
   canonical identity and Dhan security/segment mappings; never log credentials.
2. Record provider event timestamp and independent receive time. Missing event
   time, identity mismatch, future/out-of-order/conflicting packet or unverified
   session is rejected through the existing policy; receipt-only LTP is not proof.
3. Run a bounded 20-minute capture beginning before a full 15-minute partition,
   sufficient for one complete aligned window and explicit closure. The bound
   is operational, not a new strategy expiry or freshness rule. Stop early for
   provider halt, unsafe invariants or owner cancellation.
4. Use existing sealed one-minute aggregation and canonical 15-minute derivation.
   Every constituent minute, source mapping/session and provenance fingerprint
   must be retained as required by those contracts. A gap or no-trade partition
   stays explicitly incomplete; never synthesize bars to pass.
5. Verify disconnect/reconnect/resubscribe with the existing retry cap. Do not
   intentionally create connection-limit load. Disconnected windows cannot be
   called complete; clean Ctrl+C closes the sole socket and owned worker.
6. Replay exact retained receipts: no duplicate bars and no timestamp mutation.
   Verify DB integrity/FK/count deltas, zero P1 history, no per-tick SQLite
   accumulation, no order call and no portfolio mutation.

Acceptance is per instrument/window. Partial coverage remains partial. This
canary grants no V2/P1 activation and no authorization to trade. A 5/30-second
LTP/connection test cannot satisfy its sealed-window requirement.

## Validation and operational receipt

Unit tests cover current-session/holiday semantics, exact identity and coverage,
first-observation replay, verified readback, ledger required/optional/PIT states,
conflicting references, deterministic serialization, native-verifier requirement,
two-process exclusion, retry and durable operations replay. Existing identity,
P1, news, daily-temporal and sector tests remain regression boundaries.

Actual acquisition, backup/count deltas, exact test results and remaining gaps
are recorded in the local ignored operational report
`docs/reports/PILOT_SOURCE_OWNERSHIP_AND_ACQUISITION_2026-09-22.md`.
Do not interpret the presence of this specification or passing tests as closure.
The next task remains this same source slice until its non-live handoff and
consumer binding gaps are closed. No downstream closure begins automatically.

### Validated bounded checkpoint, 22 September 2026

- Current official EOD: 2,532 exact target bars accepted from a 2,553-target
  shared snapshot for the completed 22 September session. Replay: zero additions,
  2,532 duplicates, zero conflicts. There are 24 gap findings across 21 targets;
  three identity discontinuities overlap missing-target findings. This is
  partial RAW coverage, not complete technical-source readiness.
- Existing official index ingestion: Nifty 50 and Nifty 500, 248 observations
  each through 22 September; 259 newly accepted, 237 identical existing rows.
  Replay: zero additions, 496 duplicates, zero conflicts. These two benchmarks
  do not prove complete sector scope. A separate native reconciliation receipt
  retains that missing category and leaves INDEX_BARS health DEGRADED.
- Protected backup and completed post-ingestion audit: SQLite integrity `ok`,
  FK 0, schema unchanged, all prior canonical snapshots/fingerprints and bars
  unchanged. Exact additions: 2,532 historical bars and 320 native snapshots
  (including benchmark observations and operational evidence). Other table
  counts unchanged; P1 batch index and heads both zero. Backups/raw captures
  and the detailed operational report remain Git-excluded.
- New focused tests: **32 passed**. Relevant and frozen-source regression after
  removing the legacy hooks: **1,064 passed / 2 warnings**. Final full backend:
  **8,939 passed / 0 failed / 6 skipped / 2 warnings**. Skipped provider/Postgres
  integration tests are not live connectivity proof.
- The accepted package-discovery correction is retained in `pyproject.toml`.
  The isolated development install also declares `openpyxl` in its dev extra:
  existing BRSR tests need it for collection. `requests` was already declared;
  Dhan authentication and credential handling were not changed.
- **PARTIAL**: production owning-source readers for the complete P1 manifest,
  native technical/regime/sector bindings, coordinated recurring job composition
  and authenticated external transport remain unfinished. No timer, public
  deployment, P1 recording or Gate V2 activation is enabled by this checkpoint.
