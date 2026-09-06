# HSI storage footprint and repository-size audit V1

Status: `READ_ONLY_AUDIT / NO_CLEANUP_AUTHORIZED / NO_DATA_MUTATION`.

Scope: `HSI_STORAGE_FOOTPRINT_AND_REPOSITORY_SIZE_AUDIT_V1`, measured from
`ef1d406fc0ba75f6f41ccd210f80f07d4124d603` on 2026-09-06. This document is a
logical-byte audit of `D:\nse-stock-manager`; it is not a cleanup plan or a
deletion authorization. No project file, database, Git object, cache, report,
or backup was changed while collecting these facts.

## Executive result

The repository is **data- and runtime-heavy, not Git-heavy**. The measured
logical footprint is **50,938,202,378 bytes** (50,938.20 MB / 50.94 GB decimal;
47.44 GiB), materially above the previously reported approximate 20 GB.

`MULTIPLE_MATERIAL_CAUSES` is the appropriate classification:

1. `.tmp` contains 29,583,149,916 bytes (29.58 GB) of ignored retained test
   databases, staging XML, and test output.
2. `data` contains 20,937,118,982 bytes (20.94 GB), chiefly the production DB
   and three immutable migration/repair backups.
3. `.git` is only 5,248,063 bytes (5.25 MB): Git history is healthy and is not
   the growth source.

This audit establishes no safe deletion. It does establish that further
substantial data accumulation should be preceded by a separately approved
data/runtime separation and retention decision.

## Exact footprint and working-tree status

| Measure | Bytes | MB | GB | Classification |
|---|---:|---:|---:|---|
| Entire project root | 50,938,202,378 | 50,938.20 | 50.94 | `MULTIPLE_MATERIAL_CAUSES` |
| Git metadata/history | 5,248,063 | 5.25 | 0.005 | `KEEP_IN_GIT` |
| Working tree | 50,932,954,315 | 50,932.95 | 50.93 | local data/runtime dominates |
| Current tracked working files | 11,015,647 | 11.02 | 0.011 | `KEEP_IN_GIT` |
| Ignored working files | 50,921,938,668 | 50,921.94 | 50.92 | local data/runtime |
| Untracked working files | 0 | 0 | 0 | none |

The working tree was clean before and after this audit. All large current files
are ignored rather than accidentally staged or tracked.

### Direct top-level children, descending

| Child | Bytes | GB | Notes |
|---|---:|---:|---|
| `.tmp` | 29,583,149,916 | 29.58 | ignored pytest/runtime retention |
| `data` | 20,937,118,982 | 20.94 | canonical DB, backups, official sources |
| `reports` | 194,690,516 | 0.195 | ignored generated operational/test outputs |
| `frontend` | 183,133,010 | 0.183 | mostly ignored `node_modules` |
| `tests` | 16,930,817 | 0.017 | tracked tests/fixtures |
| `app` | 14,310,760 | 0.014 | tracked application source |
| `docs` | 1,644,648 | 0.002 | tracked documentation |
| `automation` | 665,990 | 0.001 | automation assets and ignored fixture exports |
| `.git` | 5,248,063 | 0.005 | Git metadata/history |
| `.pytest_cache` | 391,653 | <0.001 | ignored cache |
| all remaining top-level files/tools/migrations | 476,023 | <0.001 | source/config/test receipts |

No root `venv`, `.venv`, `tmp`, `cache`, `build`, `dist`, `database`, `db`, or
`logs` directory was present. `frontend/node_modules` is present inside
`frontend`.

## Git footprint and history audit

| Git area | Bytes |
|---|---:|
| `.git` total | 5,248,063 |
| objects | 5,026,907 |
| pack files | 3,740,426 |
| loose objects | 1,279,221 |
| logs | 51,956 |
| index | 141,025 |
| refs | 164 |
| LFS object directory | 0 |

`git count-objects -v` reports two packs, 3,051 packed objects, 263 loose
objects, zero garbage, and zero prune-packable objects. The Git classification
is `HEALTHY`; no `git gc`, repack, prune, or history rewrite is indicated by
this evidence.

The bounded all-history blob audit found no historical data/blob bloat. The
largest reachable historical blob is 180,044 bytes
(`app/storage/sqlite_governance_repository.py`); the next largest are ordinary
source/UI files and `frontend/package-lock.json` at 148,523 bytes. There are no
historical SQLite DBs, archives, backups, raw-market payloads, or generated
reports among the 50 largest reachable Git blobs. No currently tracked file is
over 10 MB.

Git LFS has no repository usage: no `.git/lfs` directory, no LFS objects, no
`filter=lfs` entry in `.gitattributes`, and `git lfs ls-files --all` is empty.
The configured `filter.lfs.*` values are machine-level capability settings, not
evidence of repository LFS content.

## Database and backup footprint

| Path | Bytes | Modified (UTC) | Role/status |
|---|---:|---|---|
| `data/nse_stock_manager.db` | 10,159,243,264 | 2026-09-06 08:00:59 | ignored production canonical SQLite DB; `KEEP_LOCAL_DATA`, `SECURITY_SENSITIVE` |
| `data/backups/nse_stock_manager.pre-udiff-series-v1-attempt2.db` | 5,140,566,016 | 2026-09-06 07:01:15 | ignored series-storage migration backup; `FUTURE_MOVE_OUT_OF_REPO`, `ARCHIVE_CANDIDATE`, `SECURITY_SENSITIVE` |
| `data/backups/nse_stock_manager.pre-udiff-series-v1.db` | 5,140,566,016 | 2026-09-06 06:55:25 | ignored series-storage migration backup; `FUTURE_MOVE_OUT_OF_REPO`, `ARCHIVE_CANDIDATE`, `SECURITY_SENSITIVE` |
| `data/backups/nse_stock_manager.pre_u06r.20260827T191037Z.db` | 411,881,472 | 2026-08-27 19:10:38 | ignored repair/migration backup; `FUTURE_MOVE_OUT_OF_REPO`, `ARCHIVE_CANDIDATE`, `SECURITY_SENSITIVE` |

There are 61,959 database-named files in total, but 61,633 are ignored
`.tmp` SQLite/test databases or sidecars. The 389 filename-based backup
candidates total 10,697,909,253 bytes; the three `data/backups` files account
for 10,693,013,504 bytes of that total. No `-wal` or `-journal` file is
material; one SQLite sidecar totals 16,928 bytes.

The two 5,140,566,016-byte series backups are an **equal-size duplication
candidate only**. They were not content-hashed: hashing would read more than
10 GB and equality of size/name does not prove they are safely interchangeable.
They remain preserved and unmodified.

### Why the production DB is 10.16 GB

`PRAGMA page_size=4096`, `page_count=2,480,284`, and `freelist_count=0` show
that the DB space is allocated rather than a large freelist. Read-only
`dbstat` reports the dominant structures below.

| Structure | Bytes | Interpretation |
|---|---:|---|
| `historical_bars` | 4,412,039,168 | active provider-versioned historical bars |
| `historical_bars_pre_udiff_series_v1` | 3,625,095,168 | retained pre-series-aware historical-bar table from the governed migration |
| active historical-bar primary/index structures | 838,295,552 | active lookup and provider/time indexes |
| retained pre-series primary index | 270,225,408 | retained migration-era table index |
| `core_api_snapshots` | 907,513,856 | immutable source/evidence/receipt payloads |
| remaining tables/indexes | about 106 MB | diagnostics, facts, filings, setups, conflicts, and governance |

The DB is therefore broadly plausible for 2,663,799 active historical bars,
1,118,660 UDiFF observations, immutable source/provenance records, and
preserved migration lineage. It also contains a material retained historical
bar table; whether that structure may ever be retired or externalized is a
separate migration-retention decision, not an audit conclusion.

## Raw source artifacts, reports, and runtime data

Physical raw market-data files are small relative to the DB. The 532 retained
UDiFF source artifacts are serialized inside immutable `core_api_snapshots`:
their payload JSON totals 126,600,796 bytes (largest 276,111 bytes), rather
than occupying a multi-GB archive tree.

| Family | Count | Bytes | Notes |
|---|---:|---:|---|
| UDiFF/bhavcopy physical files | 1,663 | 2,184,016 | delivery CSVs and small test artifacts; not the immutable snapshot payloads |
| NSE corporate-action physical artifacts | 224 | 956,591 | retained local source files |
| Other market-data physical artifacts | 578 | 133,929 | small index/provider/test files |
| UDiFF snapshot artifacts | 532 | 126,600,796 | payload JSON retained in the production DB |
| `reports` total | 1,568 files | 194,690,516 | generated reports; `FUTURE_MOVE_OUT_OF_REPO` |
| `reports/task035_pytest_tmp` | 351 files | 172,896,070 | mostly temporary pytest material under reports |

`.tmp` contains 77,863 ignored files:

| `.tmp` class | Files | Bytes |
|---|---:|---:|
| SQLite/test databases and sidecars | 61,633 | 28,790,161,952 |
| XML staging/test artifacts | 4,653 | 762,310,388 |
| other temporary files | 1,422 | 23,713,158 |
| test/report output | 5,384 | 6,185,763 |
| raw/data test artifacts | 4,771 | 778,655 |

The largest `.tmp` subtrees are repeated full-suite basetemps, each about
470–474 MB (for example `pytest-full-udiff-identity` is 474,280,686 bytes).
This is accumulated ignored test/runtime state, not canonical production data.
It is a `TEMPORARY_CANDIDATE` for a future separately approved retention
operation; no removal is authorized here.

`frontend/node_modules` is 183,133,010 bytes and is ignored. It is a normal
local dependency tree, not HSI canonical evidence; classify it
`FUTURE_MOVE_OUT_OF_REPO`/runtime dependency. No root Python virtual environment
exists.

## Top 50 largest files

All top-50 entries are ignored or Git metadata; none is tracked. Bytes are
logical file sizes. The repeated 5,244,320-byte XML files are test staging
copies; matching size/path patterns are not a deletion conclusion.

| # | Bytes | Category | Exact path |
|---:|---:|---|---|
| 1 | 10,159,243,264 | SQLite DB | `data/nse_stock_manager.db` |
| 2 | 5,140,566,016 | migration backup | `data/backups/nse_stock_manager.pre-udiff-series-v1-attempt2.db` |
| 3 | 5,140,566,016 | migration backup | `data/backups/nse_stock_manager.pre-udiff-series-v1.db` |
| 4 | 411,881,472 | repair backup | `data/backups/nse_stock_manager.pre_u06r.20260827T191037Z.db` |
| 5 | 13,814,958 | temporary regulator source | `.tmp/regulator-historical/irdai_annual_2020_21.pdf` |
| 6 | 11,694,592 | dependency | `frontend/node_modules/tsx/node_modules/@esbuild/win32-x64/esbuild.exe` |
| 7 | 10,617,344 | dependency | `frontend/node_modules/@esbuild/win32-x64/esbuild.exe` |
| 8 | 9,497,600 | dependency | `frontend/node_modules/lightningcss-win32-x64-msvc/lightningcss.win32-x64-msvc.node` |
| 9 | 9,066,411 | dependency | `frontend/node_modules/typescript/lib/typescript.js` |
| 10 | 6,589,364 | report | `reports/udiff-identity-boundary/audit-49e31c20dbc4471e5b47e778ecc731c4fbe8d3fad83a70372bc3199c6d85b02f.json` |
| 11 | 6,233,112 | official BSE XML | `data/official_sources/bse_financial_results/collector/bse-532174-INE090A01021-2025-03-31-standalone-7a3ab81f01b435ddb88a.xml` |
| 12 | 6,172,356 | dependency | `frontend/node_modules/typescript/lib/_tsc.js` |
| 13 | 5,851,246 | official BSE XML | `data/official_sources/bse_financial_results/collector/bse-532174-INE090A01021-2025-09-30-standalone-4b071c2e0a16d8bf3b25.xml` |
| 14 | 5,812,227 | report | `reports/udiff-identity-boundary/raw-audit.json` |
| 15 | 5,568,459 | official BSE XML | `data/official_sources/bse_financial_results/collector/bse-532174-INE090A01021-2026-03-31-standalone-b2d074daad9d907a8c93.xml` |
| 16 | 5,405,192 | dependency | `frontend/node_modules/lucide-react/dist/umd/lucide-react.js.map` |
| 17 | 5,306,418 | dependency | `frontend/node_modules/lucide-react/dist/cjs/lucide-react.js.map` |
| 18 | 5,244,320 | temporary XML | `.tmp/annual-backfill-focused-final/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 19 | 5,244,320 | temporary XML | `.tmp/annual-backfill-focused-final/test_only_official_staged_inge0/validated-bse.xml` |
| 20 | 5,244,320 | temporary XML | `.tmp/annual-backfill-focused/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 21 | 5,244,320 | temporary XML | `.tmp/annual-backfill-focused/test_only_official_staged_inge0/validated-bse.xml` |
| 22 | 5,244,320 | temporary XML | `.tmp/annual-backfill-full-rerun/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 23 | 5,244,320 | temporary XML | `.tmp/annual-backfill-full-rerun/test_only_official_staged_inge0/validated-bse.xml` |
| 24 | 5,244,320 | temporary XML | `.tmp/annual-backfill-full/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 25 | 5,244,320 | temporary XML | `.tmp/annual-backfill-full/test_only_official_staged_inge0/validated-bse.xml` |
| 26 | 5,244,320 | temporary XML | `.tmp/annual-backfill-regression/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 27 | 5,244,320 | temporary XML | `.tmp/annual-backfill-regression/test_only_official_staged_inge0/validated-bse.xml` |
| 28 | 5,244,320 | temporary XML | `.tmp/annual-backfill-relevant/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 29 | 5,244,320 | temporary XML | `.tmp/annual-backfill-relevant/test_only_official_staged_inge0/validated-bse.xml` |
| 30 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full-final/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 31 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full-final/test_only_official_staged_inge0/validated-bse.xml` |
| 32 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full-recovery/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 33 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full-recovery/test_only_official_staged_inge0/validated-bse.xml` |
| 34 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 35 | 5,244,320 | temporary XML | `.tmp/batch1-readiness-full/test_only_official_staged_inge0/validated-bse.xml` |
| 36 | 5,244,320 | temporary XML | `.tmp/compounder-annual-full-final/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 37 | 5,244,320 | temporary XML | `.tmp/compounder-annual-full-final/test_only_official_staged_inge0/validated-bse.xml` |
| 38 | 5,244,320 | temporary XML | `.tmp/compounder-annual-full/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 39 | 5,244,320 | temporary XML | `.tmp/compounder-annual-full/test_only_official_staged_inge0/validated-bse.xml` |
| 40 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 41 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused/test_only_official_staged_inge0/validated-bse.xml` |
| 42 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused2/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 43 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused2/test_only_official_staged_inge0/validated-bse.xml` |
| 44 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused3/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 45 | 5,244,320 | temporary XML | `.tmp/historical-bse-focused3/test_only_official_staged_inge0/validated-bse.xml` |
| 46 | 5,244,320 | temporary XML | `.tmp/nse-udiff-integrity-pytest-basetemp-20260906/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 47 | 5,244,320 | temporary XML | `.tmp/nse-udiff-integrity-pytest-basetemp-20260906/test_only_official_staged_inge0/validated-bse.xml` |
| 48 | 5,244,320 | temporary XML | `.tmp/nse-udiff-integrity-pytest-basetemp-rerun-20260906/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |
| 49 | 5,244,320 | temporary XML | `.tmp/nse-udiff-integrity-pytest-basetemp-rerun-20260906/test_only_official_staged_inge0/validated-bse.xml` |
| 50 | 5,244,320 | temporary XML | `.tmp/p1c-full-retry/test_bse_streaming_quarantines0/staging/bse-532259-INE372A01015-2026-06-30-standalone-40ad531116c0b4ca4b91.xml` |

## Ignore policy and future layout

The current `.gitignore` already protects databases, SQLite sidecars,
`.env`/`.env.*`, node modules, logs, `.tmp`, reports, `data`, selected staging
directories, test results, and common tool caches. This is why all material
files are ignored and the worktree is clean.

Report-only gaps for a future policy decision:

- a generic root `tmp/`, `cache/`, and `logs/` directory is not explicitly
  ignored (although the currently present `.tmp`, file-extension logs, and
  named tool caches are protected);
- generic backup extensions such as `.bak`/`.backup` are not independently
  covered outside already ignored `data/`/`.tmp` paths;
- generated operational state has accumulated under both `.tmp` and
  `reports`, so future retention should name an external runtime location.

Nothing was changed in `.gitignore` during this audit.

The future target separation, not implemented here, is:

| Current material | Future ownership |
|---|---|
| tracked source, tests, docs, migrations, `.git` | `repo/` |
| canonical DB and official/source artifacts | `data/` on a protected local/server data volume |
| migration/repair backups | `backups/` with explicit retention and restore governance |
| `.tmp`, test basetemps, logs, dependency cache | `runtime/` outside the source repository |
| generated reports/audit exports | `exports/` with named retention/audit policy |

For local Windows Master development, the present layout is operational but
not storage-scalable: it co-locates source, canonical data, backups, and
accumulated test runtime. A SenseEdge/server deployment should separate code,
database, raw source artifacts, backups, and logs onto independently protected
locations; this audit does not deploy that layout.

## Backup and security implications

A nominal 64 GB USB device has approximately 59.60 GiB of decimal capacity.
The current 47.44 GiB logical project would fit only if the device is otherwise
empty, leaving about 12.16 GiB of theoretical headroom before filesystem
overhead and growth. It is not a durable near-term plan for repeated full
copies or further material data growth. Future backup design should create a
small Git/source artifact separately from governed data/backup artifacts;
this is a recommendation only, not a backup operation.

The production DB, backups, user portfolio state, raw uploads, audit reports,
runtime logs, secrets, and proprietary HSI configuration require future
access-control and backup protection review. No permission, encryption, or
credential behavior changed here.

## Preserved technical continuation

This audit does not alter HSI market/technical governance:

- `NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY`
- `NSE_UDIFF_CANONICAL_DAILY_HISTORY_BACKFILL = READY`
- `UDIFF_SESSION_COVERAGE = READY`
- `UDIFF_SERIES_AWARE_STORAGE = READY`
- `EFFECTIVE_DATED_HISTORICAL_IDENTITY = OPERATIONAL`
- `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`
- `EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`
- `NO_INDICATOR_EXPANSION = TRUE`

No cleanup, deletion, movement, compression, Git garbage collection, history
rewrite, database vacuum, data mutation, or feature expansion occurred. The
exact next HSI Brain-development slice remains
`NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1`.
