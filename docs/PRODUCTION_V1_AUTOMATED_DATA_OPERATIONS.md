# Production-v1 Automated Data Operations

U17 adds one operational control plane around existing canonical evidence
stores. It does not create a replacement market-data, filing, delivery, or
research store.

## Scope and safety

The pipeline is append-only at the evidence boundary:

`refresh job -> existing canonical importer/store -> immutable operations receipt`

An `EvidenceRefreshRun`, historical `EvidenceRefreshWatermark`, and typed
reconciliation findings are operations metadata held separately from evidence.
They cannot overwrite an OHLCV bar, delivery observation, financial fact,
filing, corporate action, or membership interval. Identical source evidence is
idempotent. Changed same-source evidence is returned by the underlying store's
existing conflict/revision path; it is never silently replaced.

## Supported families and cadence

The cadence registry is configuration in `app.data_operations.service`, not a
set of hidden per-feature timers.

| Family | Default cadence | Intended source behavior |
| --- | --- | --- |
| OHLCV / index bars | daily, two-session reconciliation overlap | provider-versioned historical bars |
| NSE delivery | daily | official locally staged `sec_bhavdata_full` file |
| index membership | weekly | effective-dated membership importer |
| corporate actions / financial results | daily | official filing/import path, append/revision only |
| shareholding | weekly | period snapshot history |
| taxonomy/reference | 30 days | effective-dated official reference data |
| macro | daily | only an already registered approved source |
| news | hourly | only an already registered approved source |

The worker dispatches only registered source adapters. A family without a
configured approved adapter is shown as `NEVER_RUN`/`SOURCE_NOT_CONFIGURED` on
manual invocation; it never falls back to an unofficial provider.

## Backfill, incremental, and reconciliation

Jobs receive an explicit mode:

- `BACKFILL` fills missing required coverage in resumable chunks.
- `INCREMENTAL` starts from a store-verified prior watermark plus the governed
  overlap, rather than redownloading full history.
- `RECONCILIATION` reports gaps, conflicts, malformed evidence, and source
  unavailability as typed findings.

### OHLCV finding-count semantics

`gaps` in a U17 OHLCV receipt is an aggregate of typed operational findings,
not a count of presumed missing market sessions. In the current local
reconciliation, `gaps=2555` means 2,554 instruments without an exact Upstox
mapping plus one mapped source-unavailable instrument (`IDEA`); it includes zero
historical session-gap findings. This wording must not be interpreted as 2,555
missing trading sessions.

For a deliberately bounded replay of the latest recorded OHLCV conflict
subjects only, an interactive operator may run:

```powershell
python -m app.runtime reconcile-upstox-historical-conflicts
```

The command reuses the existing two-session reconciliation overlap and only the
immutable `CONFLICT_FOUND` subjects from the latest OHLCV receipt. It does not
backfill the universe, overwrite a bar, or select a correction. Detailed
stored-versus-incoming evidence is then available through
`historical-bar-conflicts`.

Watermarks are immutable observations with a run identity. They are not a
substitute for inspecting canonical store coverage. A job may advance a
watermark only after it declares store verification.

## Delivery staging workflow

The current official delivery adapter watches project-owned paths:

```text
data/incoming/delivery/
data/archive/delivery/
data/quarantine/delivery/
```

An external downloader (including a Google AI Studio workflow) may only place a
file in `incoming`. It has no canonical write authority. HSI validates the
official filename/date and CSV schema through the existing NSE delivery
importer, preserves its source artifact/fingerprint, then moves a valid file to
`archive`. Invalid files move to `quarantine` with a typed run finding. Neither
file mtime nor downloader output is treated as trading-date evidence.

## Scheduling and manual recovery

Scheduling is opt-in and clock-injected. FastAPI never starts an operations
worker. Operators may use:

```powershell
python -m app.runtime data-operations-status
python -m app.runtime data-operations-run --family delivery --mode incremental
python -m app.runtime data-operations-schedule-once
$env:DATA_OPERATIONS_ENABLED='true'; python -m app.runtime data-operations-worker
```

`DATA_OPERATIONS_POLL_SECONDS` controls worker polling (default `300`). A
per-family in-process lock rejects overlapping runs. Retry is bounded and only
for explicitly transient source failures; validation, conflict, and credential
errors are not hammered.

The read-only status endpoint is:

`GET /api/v1/data-operations/health`

It reports factual operational health, latest receipt counts, safe reasons and
next cadence time. It does not run jobs.

## Freshness, last-known-good, and Shared Brain

U17 does not introduce a second freshness or reliability interpretation. The
existing evidence/provenance/freshness layers remain authoritative. On source
outage, old canonical last-known-good evidence remains historical evidence; it
is never relabelled as fresh. Since U16/U15 build directly from canonical
stores and do not cache a second Brain state, the next read-only Shared Brain
request sees newly accepted evidence. An earlier `as_of` remains bounded by
the original evidence availability timestamps.

## Current source limitations

- The local automatic source adapter presently wires official NSE delivery
  staging only when the existing bounded delivery composition is available.
- OHLCV, index, membership, corporate-action, financial, shareholding,
  taxonomy, macro, and news adapters remain source-registration work: their
  existing canonical importers/stores are retained, but U17 never invents an
  unauthorised live source or credentials.
- Therefore broad unattended production operation requires approved source
  adapters/configuration for each needed family before use.

## Explicit non-goals

No U17 job computes investment semantics or emits recommendations, alerts,
BUY/SELL actions, paper orders, execution orders, or new directionality or
materiality rules.
