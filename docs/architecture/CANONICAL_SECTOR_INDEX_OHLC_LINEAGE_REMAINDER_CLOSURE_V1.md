# Canonical Sector-Index OHLC Lineage Remainder Closure V1

**Status:** `COMPLETE / CURRENT_DESCRIPTIVE_TECHNICAL / STRICT_HISTORICAL_PIT_NOT_READY`

## Scope and retained boundaries

This receipt accounts for the remaining `283` current-technical-scope
securities with an existing `EXACT_OFFICIAL` sector-index mapping but no
canonical price-return Daily OHLC lineage after the two-alias closure. The
unit of work is the selected canonical sector-index identity, never an
individual security.

It does not reopen the externally blocked all-listed NSE taxonomy source,
quote-page acquisition, Basic Industry research, peer-cohort policy, horizon
policy, or the existing mappings. It does not construct a synthetic index,
promote close-only data to OHLC, query a provider/broker, add a fallback,
alter a Rule, write a diagnostic, or access portfolio or order state.

`INDEX != EQUITY_SECURITY` and `PRICE_RETURN_INDEX != TOTAL_RETURN_INDEX`
remain mandatory. The results are current-descriptive only: neither the
retrieval timestamp nor current evidence is treated as historical PIT proof.

## A. Remaining unique sector-index inventory

The one authoritative mapped-population audit at
`2026-09-08T16:33:47.603340+00:00` used the current `2,553`-security technical
scope, unchanged current taxonomy selections, the existing `601` exact
mappings, and canonical index-OHLC snapshot counts. Before this closure,
the six rows below account for every one of the `283` blockers with no
residual.

| Canonical HSI index | Canonical display / exact query | Mapped securities | Earlier query evidence | Current probe result | Canonical Daily OHLC after closure | Current lineage state | Alias state | PRI / official sectoral page / historical selector |
| --- | --- | ---: | --- | --- | ---: | --- | --- | --- |
| `NSE_SECTOR_INDEX:CAPITAL_GOODS` | `Nifty Capital Goods` | 112 | exact query was close-only through 2026-09-04 | 249 Date/Close rows; `OFFICIAL_CLOSE_ONLY` | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` | direct exact name; no alias considered | PRI / available / exact query returned |
| `NSE_SECTOR_INDEX:CONSUMER_SERVICES` | `Nifty Consumer Services` | 46 | exact query was close-only through 2026-09-04 | 249 Date/Close rows; `OFFICIAL_CLOSE_ONLY` | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` | direct exact name; no alias considered | PRI / available / exact query returned |
| `NSE_SECTOR_INDEX:CHEMICALS` | `Nifty Chemicals` | 45 | exact query had incomplete OHLC through 2026-09-04 | 249 rows; O/H/L/C columns present but one or more values unavailable; `OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND` | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` | direct exact name; no alias considered | PRI / available / exact query returned |
| `NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY` | `Nifty IT` | 36 | no prior retained full-OHLC probe | 249 valid exact-identity OHLC rows; `OFFICIAL_OHLC_VERIFIED` | 249 | `READY` | direct exact name; no alias required | PRI / available / exact query returned |
| `NSE_SECTOR_INDEX:CONSTRUCTION` | `Nifty Construction` | 23 | exact query was close-only through 2026-09-04 | 249 Date/Close rows; `OFFICIAL_CLOSE_ONLY` | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` | direct exact name; no alias considered | PRI / available / exact query returned |
| `NSE_SECTOR_INDEX:POWER` | `Nifty Power` | 21 | exact query was close-only through 2026-09-04 | 249 Date/Close rows; `OFFICIAL_CLOSE_ONLY` | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` | direct exact name; no alias considered | PRI / available / exact query returned |

The canonical mapping pages and descriptions were retained in the existing
mapping evidence. The primary source is the [NSE Indices sectoral catalogue](https://www.niftyindices.com/indices/equity/sectoral-indices),
the applicable dedicated sector-index page, and the [NSE Indices historical-data report](https://www.niftyindices.com/reports/historical-data).
The report probes were bounded to 2025-09-08 through 2026-09-08, paced one
request apart, used the stored exact names, retained no probe payload, and
did not retry an unavailable source name.

## B. Official historical-query coverage and identity decision

All six first-party, exact-name probes returned one price-return series with
no duplicate sessions, no conflicting duplicate values, and no missing stored
`NIFTY_50` reference sessions. Their immutable response hashes were:

| Canonical HSI index | Query | Availability / reason | Probe response SHA-256 |
| --- | --- | --- | --- |
| `NSE_SECTOR_INDEX:CAPITAL_GOODS` | `Nifty Capital Goods` | `OFFICIAL_CLOSE_ONLY` / `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | `65579ee7987870f08979e3c74c28e3f193874c2744e597f21e5ebbd559e09eec` |
| `NSE_SECTOR_INDEX:CHEMICALS` | `Nifty Chemicals` | `OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND` / `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | `d02e879cfbeaa922c19ce4364a6b014a0286c086feb08dd264c0192c8817f2d4` |
| `NSE_SECTOR_INDEX:CONSTRUCTION` | `Nifty Construction` | `OFFICIAL_CLOSE_ONLY` / `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | `e35073aa69955dfcbffeeadb27510b415666388cf9fc785bca81a2376f7f36b1` |
| `NSE_SECTOR_INDEX:CONSUMER_SERVICES` | `Nifty Consumer Services` | `OFFICIAL_CLOSE_ONLY` / `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | `c69799c78e503a5868737c7cb5dea62b1c88b613e465f806c0e5c44f06791789` |
| `NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY` | `Nifty IT` | `OFFICIAL_OHLC_VERIFIED` / `NSE_INDICES_HISTORICAL_FULL_OHLC_VERIFIED` | `f9a65894619045d905a14bc58a282466478cb0b3265ab4baecafdbdf3e40b38f` |
| `NSE_SECTOR_INDEX:POWER` | `Nifty Power` | `OFFICIAL_CLOSE_ONLY` / `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | `ae9f9a67095c9f7d6859690bee967acafb90ca7ed33f7cd2640f8b9afc9b0b20` |

No name rewrite, suffix removal, token similarity, thematic substitute, or
alternate product was used. `Nifty IT` is an exact current mapping name and
exact historical-report identity; it is not an alias. No additional alias was
added or rejected in this closure. The previously proven Consumer Durables and
Healthcare aliases are unchanged and remain the only non-direct query
resolutions.

## C. Governed `Nifty IT` canonical ingestion and replay

The new bounded command is:

```text
python -m app.runtime ingest-official-nse-sector-index-remainder-ohlc
```

It resolves exactly one persisted mapping:
`Information Technology → Nifty IT → NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY`.
It rejects an absent, duplicate, non-exact, renamed, or non-direct source
mapping before the existing official first-party OHLC writer is constructed.
The generic broad refresh is not invoked.

| Run | Sessions before → after | Inserted | Identical | Canonical conflicts | Session range | Retained raw SHA-256 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| first | 0 → 249 | 249 | 0 | 0 | 2025-09-08T10:00:00Z–2026-09-08T10:00:00Z | `379229ec7c375a56ade0c08b7d4d9e69757aad8ddd03d16be6a054353c94f433` |
| second | 249 → 249 | 0 | 249 | 0 | 2025-09-08T10:00:00Z–2026-09-08T10:00:00Z | `85eb363fed2b7534a5c34fc84bbadc9b8381982856bb4dfbb65bab5be4d17d74` |

Both raw artifacts are retained independently. The second raw document had a
different content hash but its every canonical session level was identical;
the append-only canonical store therefore created no duplicate observation and
no conflict. Each observation retains the direct official historical-data
source reference, its raw-artifact SHA-256, exact canonical index ID, `Date`,
`Open`, `High`, `Low`, `Close`, PRI identity, and current retrieval timestamp.
No volume, VWAP, breadth, TRI, missing session, or synthetic field exists.

## D. Ready-index controls

Two already-ready paths were traced through the same lineage boundary:

| Canonical index | Official query → canonical display | Retained raw artifacts | Canonical OHLC sessions | Current mapped Rule 2/3/6 sector input |
| --- | --- | --- | ---: | ---: |
| `NSE_SECTOR_INDEX:FAST_MOVING_CONSUMER_GOODS` | direct `Nifty FMCG` → `Nifty FMCG` | `44490fbb814fcb132a35efc97dd2ebb85d54cca805e9fb9cb2ff3d38150c1d11`; `eccdbc6b131c60f33af499d37a8020b86d60ff45ff735b7ee8cc0d310b331bda` | 247 | 45 |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | proven alias `Nifty Consumer Durables` → `Nifty Consumer Durables Index` | `4f0f3f4e1690597d5943a756026aea0dcd59e12d2a653f05d0e09d1c6307a344`; `7aa2f601cd24098257bb454860c9dfc1d77fd0de13d09e2ba1073da0d0f4c037` | 249 | 41 |

The first uses no alias. The second retains its immutable alias-resolution
fingerprint in every canonical observation source reference. Both become
current sector input only through the pre-existing exact security mapping and
canonical OHLC readiness audit; this closure changed neither Rule 2, Rule 3,
nor Rule 6 evaluator logic.

## E. Final mapped-population readiness and boundaries

| Measure | Before | After |
| --- | ---: | ---: |
| exact governed mappings | 601 | 601 |
| mapped securities with canonical sector-index OHLC | 318 | 354 |
| mapped securities with absent canonical sector-index OHLC | 283 | 247 |
| Rule 2 sector-health source coverage | 318 | 354 |
| Rule 3 sector-rotation source coverage | 318 | 354 |
| Rule 6 sector-context coverage | 318 | 354 |

The remaining mapped blocker distribution is exact: Capital Goods `112`,
Consumer Services `46`, Chemicals `45`, Construction `23`, and Power `21`.
Each lacks usable first-party Daily OHLC at its exact verified identity; no
query alias or substitute was inferred. Rule 6 full readiness remains separate
because it additionally requires aligned benchmark and certified equity
sessions and has no peer-cohort policy in this scope.

The frozen classification state remains
`CURRENT_NSE_SECURITY_CLASSIFICATION_COVERAGE = PARTIAL / EXTERNALLY_BLOCKED`
with `1,827` missing all-listed source classifications. That external block is
not a license to invent a mapping or history.

## Final readiness matrix

| Domain | State | Exact current result / reason |
| --- | --- | --- |
| A. Remaining unique sector-index inventory | `READY` | 6/6 identities accounted for; all 283 baseline records attributed |
| B. Official historical-query coverage | `PARTIAL` | 6/6 exact first-party queries probed; 1 full OHLC, 5 unavailable |
| C. Exact alias governance | `READY` | no new aliases; Consumer Durables/Healthcare aliases preserved; `Nifty IT` direct |
| D. PRI identity | `READY` | all six probe targets are price-return index identities; no TRI accepted |
| E. Canonical sector-index Daily OHLC | `PARTIAL` | 354 mapped ready; 247 exact mapped source-data blockers |
| F. Mapped-283 lineage coverage | `PARTIAL` | 36 resolved by Nifty IT; 247 remain exactly attributed |
| G. Security-to-sector-index mapping | `READY` | 601 existing exact mappings unchanged |
| H. Rule 2 sector-health input | `PARTIAL` | 318 → 354 source-ready mappings |
| I. Rule 3 sector-rotation input | `PARTIAL` | 318 → 354 source-ready mappings |
| J. Rule 6 sector-context input | `PARTIAL` | 318 → 354 source-ready mappings |
| K. Rule 6 full readiness | `PARTIAL` | Rule 6 is applicable. `354` securities retain valid sector context, but authoritative business-peer membership and the full peer comparison policy were not assembled; benchmark/equity alignment remains separate. |
| L. Current NSE security classification coverage | `PARTIAL` | externally blocked; 1,827 all-listed classifications remain missing |
| M. Next dominant solvable internal blocker | `NOT_READY` | `TECHNICAL_PEER_COHORT_POLICY_V1`; remaining sector-OHLC gaps are first-party source limitations |

## Verification

- The focused official-OHLC, feasibility, reconciliation, and exact remainder
  command tests cover exact identity, PRI-only parsing, unavailable fields,
  per-index blockers, bounded pacing, replay, direct-command selection, and
  no broad-refresh fall-through.
- The affected Rule 2/3/6 mapping-input tests are run without changing their
  policies or thresholds.
- Focused source-contract tests: `32 passed`; affected mapping/technical-input
  tests: `65 passed`; full backend regression: `3141 passed / 0 failed / 6
  skipped / 2 warnings`.
- Production evidence remains append-only. The refreshed series has no
  canonical conflict and no fallback source.
- Production SQLite `quick_check` and `integrity_check` both reported `ok`;
  `foreign_key_check` reported `0` violations. The final snapshot totals are
  `2,229` canonical index-OHLC observations and `24` official OHLC artifacts.
- `STRICT_HISTORICAL_PIT = NOT_READY`; only current-descriptive technical
  assemblies may use this source after session close and retrieval.

This completes the bounded remainder identity/OHLC closure. It does not close
the five first-party source-data gaps, establish peer cohorts, activate horizon
semantics, widen classification coverage, or authorize a portfolio action.

## Subsequent reporting-semantics correction

The five unavailable exact-index probes returned a first-party source response.
`SOURCE_RESPONSE_AVAILABLE` is therefore distinct from
`FULL_OHLC_CONTRACT_NOT_SATISFIED`: the former records a received, exact
official response; the latter records that its fields cannot satisfy the
existing canonical Daily OHLC contract. Neither state means that the source or
index identity is absent.

Likewise, the adapter-local `PeerCohortState.NOT_APPLICABLE` records that the
current Rule 6 evaluator does not yet consume a peer series; it is not a
global applicability verdict for canonical Rule 6. The policy/readiness
interpretation is recorded in
[Technical Peer Cohort Policy V1](TECHNICAL_PEER_COHORT_POLICY_V1.md), where
full Rule 6 readiness is `PARTIAL` rather than `NOT_APPLICABLE` while its
business-peer leg remains unassembled.
