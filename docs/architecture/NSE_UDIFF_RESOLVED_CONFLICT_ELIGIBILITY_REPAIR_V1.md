# NSE UDiFF resolved-conflict eligibility repair V1

Scope: `NSE_UDIFF_RESOLVED_CONFLICT_ELIGIBILITY_REPAIR_V1`.

The [series-aware storage repair](NSE_UDIFF_SERIES_AWARE_OBSERVATION_STORAGE_REPAIR_V1.md)
and [source-row classifier](NSE_UDIFF_CONFLICT_SEMANTICS_AND_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_V1.md)
remain authoritative. This correction connects their exact source/storage
evidence to the existing [Daily certifier](NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1.md)
and [current-descriptive reader](NSE_UDIFF_DAILY_TECHNICAL_READ_ACTIVATION_V1.md).
It creates no second conflict ledger and changes no stored artifact.

## Proven regression

At checkpoint `43d9ed3`, `audit_udiff_same_provider_conflicts()` mapped every
retained UDiFF `HistoricalBarConflictArtifact` to an assessment with
`CONFLICT_UNRESOLVED`. The assessment constructor permitted no other state.
The certifier filtered these assessments by canonical instrument and requested
NSE session, then emitted `SAME_PROVIDER_CONFLICT`. It did not consume the
structural repair evidence. The reader faithfully propagated that blocked
certificate; its EQ/BL source selection was not the defect.

GENUSPOWER has **two historical** BL/EQ artifacts, of which **one** falls in
the requested six-session window (2026-08-24/25/26/27/28/31):

| Artifact ID (immutable conflict fingerprint) | Source session | Window membership | Current source/storage classification |
| --- | --- | --- | --- |
| `27a8fc2b76f2b5f10c6e31b3fad1a5eb6b24d4b6b94688dfd4d02396d67d8274` | 2026-06-30 | Outside | DISTINCT_SERIES / resolved structural collision |
| `f4b5c66ac4adb61d7e08f6ebf01cc41301f2992f666f76ae22d3f2246879af47` | 2026-08-28 | Inside | DISTINCT_SERIES / resolved structural collision |

The earlier Daily-reader note incorrectly described both artifacts as inside
the exact window. That reporting error is corrected here and cross-referenced
from that note. Both artifacts retain their original payloads and timestamps.

The 28 August archive contains separate observations:

- EQ: token `11905`, source observation
  `nse-udiff-source-row:dbe6fdaf6fa4da5bfd309da4bd9240d7c4b31946848e84354745937bf2399219`,
  bar `nse-udiff:e1e1ccb813dd5fa2bbfe4b1892415430`, archive row 1104.
- BL: token `12383`, source observation
  `nse-udiff-source-row:acc4dc5717807202ece11aedc42e21ad2a89952154d3dedec2bdef2eba45060d`,
  bar `nse-udiff:1fe39e194d5c99d4c51815892b1c9705`, archive row 1103.

Both are exact `GENUSPOWER / INE955D01029 / F1` observations with distinct
source identities and distinct values. The six-session raw bundle contains
six EQ observations and this one BL observation; no BE or T0 observation
occurs in that window. BL remains retained and excluded from returned bars.

## Semantic boundary

`nse-udiff-conflict-resolution-v1` is an immutable, deterministic evidence
reconciliation, separate from the historical artifact it references:

| Object / state | Meaning | Technical-window behavior |
| --- | --- | --- |
| HistoricalBarConflictArtifact | Immutable evidence that ingestion once rejected a second observation | Artifact presence alone gives no proof of repair |
| `RESOLVED_STRUCTURAL_CONFLICT` | Existing classifier proves DISTINCT_SERIES within one exact archive; both exact source values are currently retained | May clear this collision blocker after window-local revalidation |
| `CURRENT_TRUE_SOURCE_CONFLICT` | Same exact source identity has incompatible values | Block; no amendment precedence or winner |
| `CURRENT_UNRESOLVED_CONFLICT` | Source binding/storage proof absent, incomplete, or not a supported structural resolution | Block |

The source-row contract, exact identity, archive parser, normalized historical
values and quality validator are reused. Reconciliation binds the original
conflict fingerprint, two sealed source rows, source family/version, dates,
ISIN, source symbol, token, series, session, values, retained bar IDs and exact
archived-row references. Its fingerprint includes all resolution inputs.
Tampering, duplicate evidence and orphan/misbound resolutions are rejected.

Only `DISTINCT_SERIES` within the same exact retained archive is eligible for
this structural resolution. Classification without both stored observations
is insufficient. Other classes retain their existing fail-closed meaning.
The read-only audit also verifies the archived bytes and compares both
observations with the existing `structural-resolutions.json` repair receipt.
The receipt's status string is never sufficient by itself.

The existing assessment gains optional reconciliation lineage. Without it,
its old payload and fingerprint remain unchanged and unresolved. With it,
`CONFLICT_RESOLVED_BY_SOURCE_SEMANTICS` is permitted only when the proof
verifies. The certifier retains every relevant assessment fingerprint,
including resolved ones, in its receipt. Before suppressing a blocker it
rechecks both observations against this request's actual raw bar bundle and
requires their current-descriptive evidence times at or before evaluation
as-of. The reader still obtains its entire decision from this certifier.

## Independent policies preserved

- EQ with BL/T0 storage coexistence is not an EQ↔BE/BZ technical transition.
  Competing ordinary series remain ambiguous; mixed-date ordinary transitions
  retain their existing independent blocker. No arbitrary winner is selected.
- BL and T0 cannot appear in an ordinary technical result.
- Dividend, rights, split, bonus, demerger and other action continuity rules
  are unchanged. Resolution is not price/volume adjustment approval.
- Strict historical PIT remains `NOT_READY` with
  `STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE`. Current archive
  receipt timestamps do not establish original historical availability.
- No Upstox fallback, provider merging, Weekly/Monthly derivation, indicator,
  strategy, signal, alert, portfolio or execution capability is added.

## Reproducible production audit

`python -m scripts.audit_nse_udiff_resolved_conflict_eligibility` takes explicit
`--database`, `--accepted-audit`, `--repair-receipt`, and `--output` paths.
It opens SQLite with `mode=ro`, `query_only=ON`, and a consistent transaction.
Only a content-addressed, exclusively created Git-excluded audit report is
written. The accepted collision audit and repair receipts are never changed.

It revalidates every accepted collision pair, audits all 354 affected
instruments, and performs actual before/after reader and certifier calls for
every canonical ISIN in the frozen 2,553-security universe. Evaluation time
comes only from retained canonical observations/query receipts. Both source
values must still exist; original artifacts remain sealed. Any unexplained
eligibility increase or reader/certifier mismatch aborts the audit.

## Completed audit

The frozen universe is
`nse-universe:fundamental-probe:2d5692582f3f43fda4eb73aa3caf2d34`.
Evaluation as-of remains `2026-09-05T21:05:05.485765+00:00`, derived from
retained source/action evidence. The latest six sessions are those listed
above; 4/5-session windows use the corresponding exact suffix.

**784/784** artifacts are `DISTINCT_SERIES / RESOLVED_STRUCTURAL_CONFLICT`.
All **354/354** affected instruments were re-audited. Both original source
sides (1,568 references, with no inferred replacement) reproduce from the
retained archive and current storage. True source-value conflicts: **0**;
unresolved structural cases: **0**. Neither zero is inferred merely from the
old repair status string. Every source row and stored value was rechecked.

| Sessions | Reader success before → after | Blocked before → after | False historical-conflict blocks removed | True-conflict blocks after | Reader/certifier mismatch |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 2,462 → 2,475 | 91 → 78 | 13 | 0 | 0 |
| 5 | 2,443 → 2,456 | 110 → 97 | 13 | 0 | 0 |
| 6 | 2,430 → 2,444 | 123 → 109 | 14 | 0 | 0 |

All increases correspond exactly to an existing false artifact-presence block
cleared by verified structural proof. No previously READY instrument regressed.
The per-instrument report retains both reason lists and selected source series.

| Affected population only (354 instruments) | 4 sessions | 5 sessions | 6 sessions |
| --- | ---: | ---: | ---: |
| Eligible before | 337 | 335 | 334 |
| Eligible after | 350 | 348 | 348 |
| Still blocked by independent policies | 4 | 6 | 6 |

Current selected series within this affected population are EQ and BE;
coexisting BL/T0 observations are not selected. Individual historical
classifications and both retained source identities remain in the local
report, including artifacts outside these latest windows.

The unchanged 4/5/6-session independent reason counts are: action/identity
coverage or missing security session 26/29/30; dividend policy 33/40/47;
rights 1/4/4; EQ↔BE/BZ transitions 18/24/28; invalid source rows 2/2/1.
Reason categories can overlap and must not be summed as distinct instruments.

| Holding | Before → after six-session read | Returned observations | Price / volume |
| --- | --- | --- | --- |
| APARINDS | READY → READY | 6 EQ | READY / READY |
| DEEPINDS | READY → READY | 6 EQ | READY / READY |
| GENUSPOWER | NOT_READY → READY | 6 EQ; retained BL excluded | READY / READY |
| GLAND | READY → READY | 6 EQ | READY / READY |
| ICICIBANK | READY → READY | 6 EQ | READY / READY |

GENUSPOWER's returned source observation hashes (all prefixed
`nse-udiff-source-row:`) are:

| Session | Exact selected EQ observation hash |
| --- | --- |
| 2026-08-24 | `7712c29641b7e1db558e0abfd7407c37a0078ee9c1cc14c1a63bd2454d273257` |
| 2026-08-25 | `fbd1e1566f46e92b322baa21350594fd34ab3b1cedd5bae76e6ab4da13cf3085` |
| 2026-08-26 | `bb7d9a56053c2a2e9cf40475115d619faf56802b924ab0a0d54f48f8535b7aff` |
| 2026-08-27 | `8ede845c29da2b94d4a1a9a13b70fb312aa943d187eda90e017a377e774c5b33` |
| 2026-08-28 | `dbe6fdaf6fa4da5bfd309da4bd9240d7c4b31946848e84354745937bf2399219` |
| 2026-08-31 | `107c7a18175a0e0c83b7a182807331a044e1c48a927a0e42f008dd8b1c0b470f` |

## Readiness matrix

| Boundary | State | Evidence / limits |
| --- | --- | --- |
| A. HISTORICAL_CONFLICT_ARTIFACT_SEMANTICS | READY | Artifact and current conflict are distinct; all 784 artifacts preserved |
| B. RESOLVED_STRUCTURAL_CONFLICT_STATE | READY | 784 exact archived/storage pairs reconciled |
| C. CURRENT_TRUE_SOURCE_CONFLICT_STATE | READY | Explicit blocking state; 0 observed, incompatible same-source fixture tested |
| D. GENUSPOWER_BLOCK_ROOT_CAUSE | READY | One in-window BL/EQ artifact incorrectly propagated as unresolved |
| E. 354_INSTRUMENT_RECONCILIATION | READY | 354/354 audited at all three window lengths |
| F. CERTIFIER_CONFLICT_HANDLING | READY | Proof validated against the actual window; absent/invalid proof fails closed |
| G. READER_CONFLICT_HANDLING | READY | Existing reader consumes the corrected certificate; no alternative selector |
| H. READER_CERTIFIER_PARITY | READY | 0 mismatches across all before/after universe reads |
| I. NSE_UDIFF_DAILY_TECHNICAL_READ | READY | ACTIVE_FOR_CURRENT_DESCRIPTIVE_READS, per-window fail-closed |
| J. CURRENT_DESCRIPTIVE_DAILY_TECHNICAL_DATA | PARTIAL | 2,475/2,456/2,444 eligible; independent blockers remain |
| K. STRICT_HISTORICAL_PIT | NOT_READY | Original historical source availability remains unproved |
| L. WEEKLY_DERIVATION_GATE | READY | Corrected certified Daily source boundary; future Weekly must retain every per-window check |

## Validation and preservation

Focused reconciliation: **27 passed**. Relevant conflict/series storage,
identity, Daily certifier/reader, continuity/action and strict-PIT regressions:
**191 passed**. Complete backend: **3,038 passed / 0 failed / 6 skipped /
2 warnings**. The warnings are the existing Starlette/httpx and AnyIO
deprecations; skips remain opt-in live-provider/PostgreSQL checks.

The read-only audit's before/after counts are identical: historical bars
**2,663,799**, conflict artifacts **795** across providers (**784 UDiFF**),
core snapshots **204,344**, portfolio snapshots **1**, generic strategy/result
rows **0/0**. Exact historical conflict payload equality is verified; their
before/after aggregate digest is
`1214d96be06b53dd33cff1b8542fd0c43771fb73dba73aa81c6df6399b2e3406`.
No production DB backup, update, deletion, acquisition or replay ingestion
was necessary.

The final stricter provenance replay reproduces identical reconciliation
fingerprints, selected observations, holding results and universe coverage.
Resolved-artifact, true-conflict and unresolved-conflict blockers after repair
are each **0** for these latest windows. The final immutable local report is
`reports/udiff-resolved-conflict-eligibility-v1/audit-2548821e1bcb7b0c8b74aa3f86e2792f013b2860825775b70be96019552d3571.json`.
The earlier audit report is preserved beside it. No report or production data
is included in Git.

Final full SQLite integrity: **ok**; foreign-key violations: **0**. A separate
read-only connection confirms the same production row counts after the audit.
Changed-document Markdown validation: **216 local links / 0 broken**, with
no trailing whitespace. `git diff --check` passes. The final defensive review
confirms no source mutation, provider request, adjustment-policy change,
indicator activation, portfolio mutation, or execution authority.

## Preserved platform boundaries

- `NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY`
- `NSE_UDIFF_DAILY_TECHNICAL_READ = ACTIVE_FOR_CURRENT_DESCRIPTIVE_READS`
- `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`
- `EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`
- `NO_INDICATOR_EXPANSION = TRUE`

After this repair is validated, the next bounded continuation is
`CANONICAL_WEEKLY_TECHNICAL_BAR_DERIVATION_V1`. Weekly bars are not derived here.
