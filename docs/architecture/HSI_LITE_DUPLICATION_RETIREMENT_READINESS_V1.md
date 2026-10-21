# HSI Lite duplication and retirement readiness — V1

Status: `AUDIT_ONLY / NO_RETIREMENT_AUTHORITY / NOT_ACTIVE`.

This is a byte-overlap and consumer-boundary audit, not an approval to activate
Lite policies, replace Core V1 diagnostics, or delete either repository.

## Inspected baselines and exact overlap

- Canonical review branch: `5eb6721a47e437697901a35c9e915396a35172a8`.
- HSI Lite: `fcf288918591b0b6383dbc66bac70d7e9a4010fc`.
- All 1,715 tracked files in the canonical review checkout were compared by
  SHA-256 content with all 227 tracked Lite files. Exactly **36** Lite files
  matched byte-for-byte: the 35 `hsi_knowledge/strategies/taxonomy/*.json`
  records and `hsi_knowledge/strategies/STRATEGY_DEPENDENCY_MATRIX.json` match
  [the imported draft catalog](../../app/lens_knowledge/README.md). They remain
  proposed and inactive. The other **191** Lite files had no byte-identical
  counterpart in this tracked canonical checkout. A non-match does not prove
  unique semantics, and a match does not confer policy authority.

| Remaining Lite group | Tracked files | Disposition |
| --- | ---: | --- |
| Diagnostic knowledge | 65 | Review against the canonical 61-rule owner and historical receipts; do not import as a second registry. |
| Discovery knowledge | 15 | Compare with live read-only funnel and candidate-union consumers. |
| Gate knowledge | 10 | Retain V1 active and V2 not active; no policy promotion. |
| Governance knowledge | 10 | Reconcile provenance and status, not override approved contracts. |
| Portfolio knowledge | 11 | Preserve private ownership and no automated action. |
| Schemas | 8 | Check contract equivalence before replacing any schema. |
| Scoring knowledge | 2 | Do not change Decision Score weights or authority. |
| Other strategy knowledge | 13 | Keep proposed taxonomies distinct from approved policies. |
| Docs | 37 | Retain provenance; review for unique design/history. |
| Tests | 12 | Check what behavior they cover before retirement. |
| Root files | 8 | Review repository metadata, packaging and manifest separately. |

## Calculation and consumer boundaries

The Lite repository's `docs/LEGACY_HSI_DUPLICATION_AUDIT.md` at its frozen
source commit identifies **22 candidate** repeated-computation paths:
`D03, D05, D07, D09, D13, D14, D25, D38, D40, D41, D42, D43, D44, D46,
D50, D51, D52, D53, D54, D55, D56, D58`. Its source file
`docs/LEGACY_HSI_DUPLICATION_AUDIT.md` has SHA-256
`55db6d597f0ebdad86add23eab9b7bc5e02d6d999346ffb1399238232c41339a`.
These are static call-graph candidates, not 22 proven same-input duplicates.
The same audit separately flags `D35` as conflicting source authority and
`D57` as needing canonical event/source extraction. Neither can be fixed by
memoization or relabelling unavailable evidence as ready.

The [canonical draft binding](../../app/lens_knowledge/canonical_binding.py)
now reuses one validated native technical projection per selected stock per
page; 35 draft lenses consume one canonical diagnostic result set. This is a
proven local reuse, not a cache across source vintages or cutoffs.

Do **not** delete the multi-funnel implementation: the current
[`hsi_scan_market` API](../../app/api/agent_tools.py) calls
[`SharedMarketScanService`](../../app/intelligence/shared_market_scan.py),
which composes the existing
[whole-market funnel orchestrator](../../app/intelligence/multi_funnel_orchestration.py)
and preserves candidate origin and coverage. The draft lens coverage layer
does not replace these semantics. Historical audits that found no caller were
valid for their own baselines, not evidence of current dead code.

Core V1 helper files including `app/analysis/liquidity.py` are source-pinned
in historical governance/test receipts. Preserve those receipts. A proposed
internal compute-once refactor must first prove exact canonical identity,
as-of, timeframe, source vintage, parameters, output/lineage parity and
call-count reduction; it must not silently rewrite old source fingerprints.

## Diagnostic-knowledge disposition and external provenance

The 65 unmatched diagnostic-knowledge files comprise 61 catalog records plus
`CALCULATION_OWNER_MAP.json`, `EVIDENCE_DEPENDENCY_CATALOG.json`, `index.json`
and `README.md`. All 61 catalog records declare
`deterministic_computation=false`, have no effective date and have no assigned
calculation owner. **59** are `REVIEW_REQUIRED`; `D35` and `D57` are
`QUARANTINED`. The two maps are conceptual source/dependency inventories, not
a Lite runtime. Disposition: retain these 65 in historical provenance; do not
copy them into the canonical runtime as another 61-rule registry. Their
content remains available for a separately reviewed semantic crosswalk.

Six imported taxonomy records contain a literal reference to the Lite
`hsi_knowledge/strategies/registry.json#Task007` source. The draft catalog
does not load that file as strategy authority, but its historical reference
must remain recoverable. Removing the Lite remote without a durable, verified
archive or an approved provenance-location mapping would break that audit
trail. The referenced Lite registry's SHA-256 is
`9801a85b4567075144fb3f56eafe2b661a838b312424bc69b1fa13be987feca1`.
No reference was silently rewritten in the byte-identical taxonomy.

A complete local Git bundle was created at the Git-ignored
`D:/nse-stock-manager/.tmp/hsi-lite-fcf288918591b0b6383dbc66bac70d7e9a4010fc-full.bundle`.
`git bundle verify` confirmed complete history and the main/origin refs at
the Lite SHA. Its SHA-256 is
`183979349f1b501b361d16efb977c0cbbb0371203ee902909278d7df7d618ecd`.
This is one **local** recoverable copy, not an off-machine backup and not
sufficient alone to authorize deleting the GitHub repository.

## Retirement gate

No Lite repository or funnel deletion is approved by this audit. Before Lite
retirement, classify the remaining 126 non-identical files as superseded,
uniquely retained, or intentionally archived; preserve a recoverable full Git
history in a durable location and verify no live consumer depends on it.
The 65 diagnostic-knowledge files above are designated historical-only, not
approved runtime replacements. Before removing a funnel
path, replace its currently consumed candidate identity, origin, coverage,
PIT and failure semantics and prove parity with focused and full regression.
Only then should the exact deletion targets be reviewed. No data, credentials,
portfolio state, broker/order interface or deployment setting was changed.
