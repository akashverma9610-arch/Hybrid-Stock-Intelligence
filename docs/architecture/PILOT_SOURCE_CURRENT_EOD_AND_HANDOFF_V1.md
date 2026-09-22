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

### Non-live binding audit follow-up

Baseline: `df563ad4fc7f76ad2564ad523d760cfdf64cfa28`. This follow-up is
**PARTIAL / SOURCE_CLOSURE_NOT_ACCEPTED**, not P1 activation. Concrete retained
source gaps prevent the requested final non-live closure. Nothing below
silently promotes source acceptance, a test fixture, or a historical artifact
to current readiness.

[NativeDailyTechnicalBinding](../../app/data_operations/native_technical_binding.py)
reads existing snapshot families and the historical bar store at an explicit
UTC cutoff. It reuses the native historical session-manifest reader inside
retained windows, forward calendar outside them, effective-identity index,
corporate-action query coverage composer, same-provider conflict audit and
Daily technical certifier. Only a READY certificate enters the existing
technical-input assembler. Shared source families are cached per instance and
cutoff; no per-user source job or indicator calculation is introduced.

This is a current-descriptive binding. Strict historical PIT remains unavailable.
It cannot extend frozen identity/action windows, fill a missing session from
another provider, infer an adjustment, invent weekly bars or change a native
bar's timestamp. Snapshot/native cutoff checks and explicit bar receipt/end
checks exclude future evidence. Duplicate bars remain visible to the native
ambiguity check; they are not silently discarded. Complete source-window
certification does not override each technical consumer's existing minimum
daily/weekly observation count.

The read-only production probes used `2026-09-22T18:00:00Z`, `mode=ro` and
`PRAGMA query_only=ON`, with zero connection changes:

| Surface | Actual evidence and result |
| --- | --- |
| Current master | 2,553 requested targets: 2,532 exact, 20 unresolved, 1 ambiguous, 0 governed exclusions within requested scope. Three identity-discontinuity findings overlap target gaps; no fuzzy correction. |
| Historical technical binding | `NSE:INE372A01015`, 3-31 August: 21 native bars, READY current-descriptive technical input. `NSE:INE727B01026`: NOT_READY, native `RIGHTS_ADJUSTMENT_NOT_READY`. Neither result is current September readiness. |
| Current technical binding | Both representative equities have 533 retained UDiFF bars but only one source row in the 11 required 7-22 September sessions. Effective-identity and corporate-action query coverage end 31 August. September certification remains NOT_READY. Whole-universe technical readiness was not measured. |
| Timestamp limitation | The 22 September RAW bar labels end at 18:30Z, later than this probe cutoff; the native store excludes it even though the exchange session has closed. The binding preserves that conservative owner rule, not a fabricated close or advanced cutoff. Empty series may yield native `SOURCE_ROW_INVALID`; that is not proof the retained current row is corrupt. |
| Nifty 50 / regime | 248 official observations through the 22 September 10:00Z close enter the existing benchmark context and the authorized existing rule-1 evaluation. Native result `neutral`, with 248 input references; not a neutral fallback. This was an in-memory read-only evaluation, not durable materialization or registration of a new regime publisher. |
| Sector | 23 mappings: 13 EXACT_OFFICIAL, 9 NO_OFFICIAL_SECTOR_INDEX, 1 UNRESOLVED. All 263 retained membership records lack source-as-of dates and effective-until semantics; latest capture 27 August. Latest ranking 1 September. Zero sectors proven current-ready: 13 mapping-eligible sectors remain blocked by current-membership validity; 10 lack an eligible official mapping. No current ranking was written. |
| P1 | 729 retained native setup assessments exist in their owning table. Inspected assessment contracts retain derived inputs and policy fingerprints, but do not expose a complete raw-observation dependency closure or separate known-at/ingestion-time fields. Evaluation-as-of is not substituted for them. Production P1 owning-source reader plumbing remains incomplete. |

The exact source archive fingerprint is
`sha256:06c13b683a7c52f37dbdf60f650f864256f325bb59398047de99ef6d4a20597b`.
The successful benchmark context fingerprint is
`sha256:8958d96ceee3d7c2f24f7cea8fcf2a48d64ca27cc8c314140bfdcae71da60208`.
The regime probe reused `canonical-universe-analysis/v1`, semantic fingerprint
`sha256:3144ec1e9452f24a1e9f3776c77e33cbd59f31459c3e2f7d734c4924bb2b9ee3`.
Its evaluation identity was
`diagnostic-1-canonical-universe-analysis-v1-2026-09-22T18:00:00+00:00`.
This does not claim a persisted diagnostic, a second regime engine or a
completed source-manifest publication path. Durable governed materialization
and its complete source receipt remain unfinished.

#### Exact remaining non-live work

1. Retain the missing eligible September sessions and corresponding exact
   identity/action-query evidence through existing acquisition owners. Do not
   extend an August certificate or backdate receipt times. Preserve genuine
   rights/action adjustment blockers.
2. Capture complete native assessment input references and independent time
   facts at their owning producer, without recalculating metrics or rewriting
   existing assessments. Bind that verified closure to the existing source
   ledger/P1 reader. Legacy derived values cannot reconstruct missing lineage.
3. Prove current membership validity, aligned official sector windows and
   constituent windows before publishing a current sector artifact. The
   existing 20/60/120-session RS and 50/200-session breadth requirements remain.
4. Finish canonical manifest/publication binding for the proven regime input
   and narrowly reconcile source-job dispatch. The additive current-EOD worker
   is conditionally schedulable on one exclusive host; universal legacy-worker
   exclusion is not implemented. Broad unattended acquisition is not closed.

These are source-slice blockers, not an excuse to transfer missing plumbing to
P1 activation. The existing seven-state source ledger vocabulary is unchanged;
an interface alone is not a production owning-source reader. No unavailable-only
replacement for a native producer or synthetic readiness adapter was added.

#### Machine-ingestion trust contract (design only, transport disabled)

Use a dedicated confidential machine client with the managed identity provider's
[client-credentials flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow),
not an invented human OWNER. Actual issuer, audience and client identifiers must
come from approved deployment configuration, never be guessed. The later
AI-agent ingestion slice must implement all of the following before transport:

- Separate machine audience, explicit machine-client allowlist and only the
  narrow evidence-ingestion permission. Human tokens cannot impersonate the
  machine, and machine tokens cannot access human/private-resource routes.
- Server-side signature/JWKS, issuer, audience, algorithm, expiry/not-before,
  authorized-client and permission validation; access-token lifetime at most
  600 seconds. Client secrets remain server-side. No global middleware bypass,
  owner role, user-ID injection or reuse of the disabled bridge's static token.
- Exact route/method authorization to the existing validated intake only;
  canonical schema, identity, provenance, PIT, deduplication and quarantine
  remain authoritative. The machine supplies evidence, never score/gate/trade
  authority. No portfolio, broker or order capability.
- Prove negative tests for wrong audience/client/scope, expired credentials,
  human/machine substitution, duplicate packages and private-route access,
  then a bounded authenticated ingestion canary before any timer is enabled.

This is not a deployed authentication implementation. No identity grants,
credentials, routes or middleware were changed. Read-only Windows task audit
confirmed `HSI External Intelligence Bridge = Disabled` and
`HSI Local Backend = Ready`; no new acquisition timer was enabled.

The separately frozen `LIVE_SESSION_INTRADAY_CANARY`, broker-account ingestion
closure and `HSI_DIAGNOSTIC_AUTHORITY_AND_DUPLICATION_AUDIT` remain later work.
They do not absorb the source blockers above. The next exact slice remains
**PILOT_SOURCE_OWNERSHIP_AND_ACQUISITION**. No later slice is started here.

Follow-up validation: 18 focused tests passed; 317 relevant source/P1/Auth0/
sector tests passed (2 warnings); completed full backend regression **8,957
passed / 0 failed / 6 skipped / 2 warnings**, 514.13 seconds. An earlier
incomplete run was stopped for the new adapter's historical-session correction
and is not counted as validation. Markdown links and whitespace checks passed.
Optional provider/PostgreSQL skips are not connectivity proof. No production
DB writes occurred; fresh FK check was zero and monitored table counts match
the accepted baseline. Prior full integrity `ok` was not relabelled as a new
scan. Tests do not resolve the operational source blockers above.
