# NSE UDiFF series-aware observation storage repair V1

Scope: `NSE_UDIFF_SERIES_AWARE_OBSERVATION_STORAGE_REPAIR_V1`.

This is source-evidence preservation, not technical-series selection or
historical-security continuity approval. The
[complete preceding collision audit](NSE_UDIFF_CONFLICT_SEMANTICS_AND_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_V1.md)
remains immutable historical evidence. Its storage blocker is resolved only
when the production validation receipt described below passes.

## Proven defect chain

For example, an archived BL row and an EQ row share ISIN, symbol, trade date
and F1 session but differ in `FinInstrmId` and `SctySrs`:

1. The UDiFF parser retained all source columns and generated different bar IDs.
2. `CanonicalOHLCVBar` retained token in provider provenance and source series,
   session, business date and artifact in warnings. Its instrument symbol was
   accepted only by exact source-symbol matching, not historical alias inference.
3. The old SQLite/PostgreSQL key was `(instrument_id, timeframe, start_time,
   end_time, provider_identity)`. It rejected the second source observation.
4. Ingestion also grouped incoming bars by canonical interval, ignoring source
   identity. The UDiFF importer had a separate incomplete duplicate key.
5. Generic historical grouping then selected one provider observation per
   canonical interval. Source priority alone could not distinguish series.
6. The price-bar snapshot bridge discarded the source-series distinction;
   technical snapshot readers had no UDiFF series-selection guard.

Thus SQL uniqueness alone was insufficient. The repair covers ingestion,
storage, raw reads, canonical grouping, readiness counts and snapshot boundaries.

## Source identity and duplicate semantics

The exact audit identity is reused without changing its hash:

`nse-udiff-source-row:<sha256>` over deterministic canonical JSON containing
contract `nse-udiff-conflict-semantics-v1`, source family
`NSE_CM_UDIFF_FINAL_BHAVCOPY`, source version `nse-udiff-final-bhavcopy-v1`, and
the ordered fields `TradDt`, `BizDt`, `FinInstrmId`, `ISIN`, `TckrSymb`,
`SctySrs`, `SsnId`. Symbol means the symbol recorded in the source row, never
a current-master lookup. NSE/CM/STK, RAW basis, exact business/trade date and
the 2024-07-08 era boundary are validated before admission.

Canonical security linkage is separate. EQ, BE, BL and T0 may coexist for the
same canonical interval. Different tokens or series are not duplicates.
Neither BL nor T0 is interchangeable with EQ.

An equivalent duplicate has the same material source identity, normalized
values, normalization/source semantics and descriptive warnings. Archive
receipt/row ordinal differences do not create a value amendment. Exact raw
archives retain their own immutable lineage. A changed value for the same
source identity is rejected as a conflict; the old observation is not updated.
There is no amendment precedence or silent replacement.

## Explicit versioned persistence repair

The new shared table key appends `source_observation_identity` to the old key.
The field is a UDiFF-specific source-security component, not a new parallel
observation database. Non-UDiFF providers use the empty component and retain
their existing identity/content semantics and raw values.

- Fresh SQLite stores use the new schema. Existing provider-versioned stores
  refuse UDiFF writes until the explicit v1 migration is run; startup does not
  migrate production history.
- The explicit SQLite migration requires a verified backup and verifies every
  stored UDiFF observation against its exact retained archive row. It copies
  all original columns verbatim, proves equality and commits the table switch
  transactionally. Original IDs, prices, volume, provenance and timestamps stay
  unchanged. `historical_bars_pre_udiff_series_v1` retains the original table
  behind write-rejection triggers. Foreign-key/view dependencies stop migration
  rather than being silently retargeted. Injected faults roll back the switch.
- PostgreSQL Alembic `20260906_10` appends the same identity dimension, validates
  archived UDiFF rows, retains the pre-migration table and changes the PK in its
  transaction. A destructive downgrade is prohibited; later rollback requires
  an evidence-preserving forward migration. PostgreSQL live validation must be
  reported separately from SQLite results.
- Reads verify the persisted identity against recorded source provenance.

No original conflict payload is rewritten. Separate immutable local repair
receipts link both recovered observations to each historical conflict ID.
New genuine UDiFF value-conflict artifacts include the source-observation
identity in their lineage/fingerprint. The optional field is absent when
decoding old artifacts, preserving their exact legacy hashes; non-UDiFF
conflict serialization is unchanged.
`HISTORICAL_CONFLICT_ARTIFACT` is not equivalent to
`CURRENT_UNRESOLVED_SOURCE_CONFLICT`.

## Read and snapshot boundaries

`raw_range` returns all source observations; every bar exposes its computed
source identity. It does not merge provider lineages or choose a series.

`range`, `latest`, canonical count and readiness do not admit a UDiFF interval
without a governed technical-series policy. Presence of UDiFF blocks implicit
fallback to another provider for that interval. Reconciliation explicitly
reports `SOURCE_SERIES_SELECTION_REQUIRED`. In-memory source storage allows
distinct source identities; it does not make them technical candles.

The snapshot bridge refuses UDiFF with
`NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE`. The technical snapshot reader
also fails closed if a UDiFF observation was supplied through another path.
No insertion-order, latest-series, EQ-first, BL-first or T0-first winner exists.
Upstox-only observations retain their prior behavior and UNKNOWN basis.

The earlier explicit UDiFF source selector also returns
`SERIES_SELECTION_NOT_ACTIVE` once coverage/identity prechecks pass: those
prechecks alone never approved a series. Legacy `SELECTED_UDIFF` receipts remain
deserializable historical evidence; no stored receipt is rewritten.

## Controlled retained replay and audit

The explicit offline operation is
`python -m scripts.repair_nse_udiff_series_storage`, requiring database, backup,
output and accepted audit paths. It has no credential or network configuration.
Its provider stub rejects any fetch. It reuses the existing UDiFF parser,
current exact target resolution, quality validator and historical store.

All 532 retained sessions are replayed twice. Original acquisition receipts and
manifests are unchanged; separate per-session repair receipts record inserts,
duplicates, invalid/excluded identities and conflicts. Unexpected conflicts or
second-pass inserts halt the operation. Missing historical identity rows remain
excluded, and invalid OHLC is not repaired or admitted.

The final audit verifies both archived sides of every one of the 784 structural
cases, all 354 affected instruments, source counts by series, the five holdings,
all pre-migration bar values, every unrelated table's count/content digest,
SQLite integrity and foreign keys. Reports and the backup are local-only and
must never be committed. Completed measurements are recorded below, not assumed
from the expected 784 insertions.

## Preserved governance

- `NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY`
- `NSE_UDIFF_CANONICAL_DAILY_HISTORY_BACKFILL = READY`
- `UDIFF_SESSION_COVERAGE = READY`
- `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`
- `EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`
- `NO_INDICATOR_EXPANSION = TRUE`
- `EFFECTIVE_DATED_HISTORICAL_IDENTITY_PROMOTION = NOT_ACTIVE`
- Canonical UDiFF technical-series selection, horizon policies and MTF remain
  `NOT_ACTIVE`. No Weekly/Monthly bars, indicators, strategy, portfolio or
  execution authority is added.

FACT → DATA → INTERPRETATION → INFERENCE remains unchanged. Source preservation
precedes technical selection. Storage repair does not establish historical
security continuity.

## Next bounded continuation

Only after a clean repair checkpoint:
`NSE_UDIFF_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_PROMOTION_V1`, followed by
`NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1`.
Neither is executed in this slice. Weekly derivation remains downstream of a
separately READY Daily technical eligibility gate.

## Completed local production validation — 2026-09-06

Local SQLite storage/read repair: **READY**. Source-series technical selection
and effective-dated identity promotion remain **NOT_ACTIVE**.

| UDiFF series | Before | After | Recovered |
|---|---:|---:|---:|
| EQ | 975,747 | 976,447 | 700 |
| BE | 109,904 | 109,905 | 1 |
| BL | 701 | 766 | 65 |
| T0 | 0 | 18 | 18 |
| Other: BZ / SM / ST | 16,801 | 16,801 | 0 |
| Total | 1,103,153 | 1,103,937 | 784 |

Active historical rows: **2,648,292 → 2,649,076**. Non-UDiFF counts and all
original 18-column observation values/IDs remain unchanged. All 784 recovered
rows match the previously rejected distinct-source population; no unexplained
inserts or new conflicts occurred. **354/354** affected instruments repaired,
**0** unresolved structural cases. All **784** original UDiFF conflict artifacts
(**795** across providers) remain unchanged and verify under the legacy reader.
All **1,568** accepted archived-side source identities reproduce exactly.

| Replay | Sessions | Inserted | Equivalent/already present | New conflicts |
|---|---:|---:|---:|---:|
| First | 532 | 784 | 1,103,153 | 0 |
| Second | 532 | 0 | 1,103,937 | 0 |

Each replay inspected **1,659,029** source rows, excluded the same **194** invalid
OHLC rows and **14,723** historical-symbol rows, and performed no network fetch.
All **532** raw artifacts, **590** acquisition receipts, **8** acquisition
manifests, **532** valid sessions and **29** confirmed non-trading days remain
unchanged; source gaps remain zero. Historical identity promotion remains zero.

| Holding | Before → after retained source observations |
|---|---|
| APARINDS | EQ 532 → 532 |
| DEEPINDS | EQ 532 → 532 |
| GENUSPOWER | EQ 520 → 522; BE 10 → 10; BL 2 → 2 |
| GLAND | EQ 532 → 532 |
| ICICIBANK | EQ 524 → 532; BL 8 → 8 |

These are source facts, not investment conclusions or technical eligibility.

Final SQLite integrity: **ok**; FK violations: **0**. Exact before/after content
digests and counts match for every unrelated table. Core snapshots **195,922**,
FinancialFacts **4,067**, filings **362**, portfolio snapshots **1**, canonical
diagnostic definitions **1**, generic strategies/results **0/0**, paper trades
and trade plans **0/0** remain unchanged. Cash remains **UNKNOWN**. No provider, portfolio or execution
operation occurred.

The first migration attempt rolled back on an internal SQLite read/write-lock
conflict: archive verification used a second live-DB connection. The correction
reads the verified backup. The rollback retained the original 18-column table,
2,648,292 bars and all conflict artifacts; a separate second backup was used for
the successful attempt. Neither backup was deleted or overwritten.

Database size **5,140,566,016 → 10,118,086,656 bytes** includes retention of the
entire original table, the expanded replacement and indexes; it is not per-tick
accumulation. Both backups, per-session receipts and audit reports remain
Git-excluded. The final local receipt is
`reports/udiff-series-storage-repair-v1/final.json`, SHA-256
`37e513851dd1cd19953c1c0104eb09227b6cfe0a580bb189414084007d21fe2e`.

Validation: **71 focused passed**; **265 relevant passed / 2 warnings**;
**2,941 full backend passed / 0 failed / 6 skipped / 2 warnings**.
The 6 skips are existing opt-in live-provider/PostgreSQL tests. PostgreSQL row
round-trips, repository query semantics and migration structure are tested, but
no live PostgreSQL server or Alembic runtime was available: its migration is
prepared, not claimed production-executed. Local Markdown links and whitespace
checks passed. No indicator, API, UI, policy activation or credential changes.

| Readiness boundary | State | Evidence / reason |
|---|---|---|
| A. UDiFF source identity | READY | Exact audited identity reproduced; raw provenance verified |
| B. Series-aware persistence | READY | Local SQLite migrated PK; PostgreSQL migration prepared, live proof pending |
| C. Series-aware read grouping | READY | Distinct source rows retained and exposed |
| D. Duplicate semantics | READY | Same-source equivalent replay is a no-op |
| E. True source-conflict containment | READY | Amendments rejected; series-bound new conflict lineage tested |
| F. Historical conflict preservation | READY | 784/784 UDiFF artifacts unchanged |
| G. Distinct-series recovery | READY | 784 rows, 354/354 instruments |
| H. Replay idempotency | READY | Second replay: zero inserts/conflicts |
| I. Generic Daily read ambiguity protection | READY | Explicit fail-closed guards; no series winner/fallback |
| J. Effective-dated identity promotion | NOT_READY | NOT_ACTIVE in this slice; continuity not yet approved |
| K. Canonical Daily technical source selection | NOT_READY | NOT_ACTIVE; series/continuity certification required |
| L. Current descriptive Daily technical data | NOT_READY | No technical promotion from this storage repair |
| M. Weekly derivation gate | NOT_READY | Daily eligibility gate remains unfulfilled |
