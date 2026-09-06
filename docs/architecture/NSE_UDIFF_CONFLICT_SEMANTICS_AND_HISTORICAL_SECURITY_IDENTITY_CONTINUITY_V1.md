# NSE UDiFF Conflict Semantics and Historical Security Identity Continuity V1

Status: `AUDIT_IMPLEMENTED / SYSTEMIC_PERSISTENCE_KEY_REPAIR_REQUIRED / NOT_ACTIVE`.

This is the explicit repair-stop checkpoint from the authorized slice, **not**
identity/technical continuity closure. Baseline: `83584db251a3cd199eb250ef90ae5530179ab999`.
No historical observations, conflict artifacts, identity receipts, portfolio
state, provider configuration, or production schema were changed.

## Exhaustive evidence and the stop condition

The read-only audit revalidated all 532 retained ZIP artifacts, scanned all
1,659,029 rows, and joined **both sides of every one of the 784 conflicts** to
one exact source row using artifact URL/date, canonical ISIN, NSE token and
all seven OHLC/volume/value/trade-count values. Missing or ambiguous joins
abort rather than disappear from the denominator. Legacy conflict fingerprints
and source artifact fingerprints are verified before use.

| Stored series | Rejected incoming series | Conflicts |
| --- | --- | ---: |
| BL | EQ | 700 |
| EQ | BL | 56 |
| BE | BL | 9 |
| BL | BE | 1 |
| EQ | T0 | 18 |
| Total | | 784 |

All 784 differ in **FinInstrmId and SctySrs**. Trade/business dates, segment,
exchange, financial-instrument type, ISIN, symbol and F1 session agree.
Primary class: `DISTINCT_SERIES` (784); underlying defect: `HSI_KEY_TOO_COARSE`.
Affected canonical instruments: 354. Exact duplicate-equivalent pairs: 0;
same-exact-source-identity value conflicts: 0; unclassified joins: 0 **within
these 784 artifacts only**. These are not claims about every possible source
revision or a permission to remove conflict blockers.

The persisted conflict ledger still contains all 784. Zero are erased, zero
arbitrary winners are chosen, and zero new production resolution receipts are
created. Semantic explanation is complete; storage separation is not.

The 1,103,153 stored UDiFF observations include 975,747 EQ, 109,904 BE, 11,336 BZ,
4,187 SM, 1,278 ST and **701 BL** rows. Thus this is not merely a missing rejected
row problem: 701 coarse keys currently hold the BL observation. Replaying the
existing importer skips already-completed session receipts and cannot fix it.

## First-party series and final-file semantics

- [NSE block-deal documentation](https://www.nseindia.com/static/products-services/equity-market-inter-institutional-block-deals)
  identifies BL as the block-deal series. It must not be substituted for the
  corresponding regular-market observation.
- [NSE T+0 FAQ](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Download%20FAQs%20on%20T%2B0%20Security.pdf),
  questions 4, 6, 22 and 24, distinguishes T0 settlement while retaining the
  corresponding ISIN/symbol and including T0 in the existing Bhavcopy.
  Identical ISIN/symbol therefore does not prove interchangeable market series.
- [NSE UDiFF formats](https://www.nseindia.com/static/resources/forms-formats-members)
  and the retained files identify the final artifact with `F_0000`; the row
  session is `F1`. These are different dimensions, neither erases series.

All audited pairs occur inside the **same exact final artifact**, not competing
revisions. Retained acquisition evidence has one artifact per audited date.
No authoritative precedence for conflicting later versions has been established
here. Final filenames, acquisition time and filesystem modification time are
not revision authority. Incompatible values under one exact identity remain
`TRUE_SOURCE_VALUE_CONFLICT`; the classifier never picks latest/first/average.

## Implemented source-row contract (audit only)

[`nse_udiff_conflict_semantics.py`](../../app/market_data/nse_udiff_conflict_semantics.py)
provides immutable source-row evidence and a pure symmetric classifier. It does
not import a current universe to manufacture historical names.

`source_row_id` hashes canonical sorted JSON containing contract version,
source family/version, and exactly:

```text
TradDt, BizDt, FinInstrmId, ISIN, TckrSymb, SctySrs, SsnId
```

CM/NSE/STK are enforced scope constants. Business date must equal trade date
for this bounded final Daily contract. Series and token are proven distinct
dimensions in production; ISIN/symbol prevent accidental identity drift from
being treated as the same source row. This is a conservative source identity,
not a claim that NSE tokens are permanent across dates or lifecycle events.
No smaller token-only key is approved. Row ordinal, values, current HSI symbol,
local time and artifact arrival order do not participate in the logical ID.

A separate content fingerprint covers all 34 exact source fields, row ordinal,
artifact ID/fingerprint, ZIP content hash, official URL and UTC-normalized
local observation time. Same logical row with changed values has the same ID
but different content fingerprint. The factory revalidates archived bytes;
construction validates the seal and rejects malformed identity/lineage. Hashes
are integrity checks, not proof of authenticity independent of the archive.

Classification precedence: differing date -> `UNRESOLVED`; changed ISIN/symbol
-> `HISTORICAL_IDENTITY_DISCONTINUITY` (no continuity conclusion); differing
series -> `DISTINCT_SERIES`; session -> `DISTINCT_SESSION`; token ->
`DISTINCT_SOURCE_SECURITY_IDENTITY`; identical complete row ->
`DUPLICATE_EQUIVALENT`; incompatible finite normalized values ->
`TRUE_SOURCE_VALUE_CONFLICT`; otherwise `UNRESOLVED`. Exact duplicates may be
deduplicable conceptually but no persisted evidence is removed. The assessment
retains every differing identity dimension, not only its primary class.

## Existing storage defect and why migration is not performed here

[`historical.py`](../../app/market_data/historical.py) currently uses:

```text
PRIMARY KEY (instrument_id, timeframe, start_time, end_time, provider_identity)
```

`_same_bar_content` compares only OHLC, volume, turnover, trades and basis.
`_bar_key`, `canonicalize_market_bars`, canonical `range`, and reconciliation
also group without series/session/source security. A SQLite key-only alteration
would leave downstream selection capable of collapsing distinct series again.
Equal-valued distinct series could also be silently labelled identical by the
existing content comparison (a structural risk, not an observed extra count).

The importer attaches current target instrument metadata, while exact source
series survives in warnings and archived rows. A provenance-preserving repair
therefore needs an observation-identity migration, archive-to-old-row mapping,
recovery of rejected source rows, duplicate semantics, and read grouping changes.
It cannot safely be reduced to clearing the 784 artifacts or changing provider
priority. The user's systemic-key/large-repair stop condition applies.

## Historical identity findings; no fabricated interval

Reuse [`HistoricalSecurityIdentity`](../../app/historical/security_master.py),
its existing store, [`PIT selector`](../../app/historical/security_identity_selector.py),
the MII snapshot/row contracts and existing lifecycle/action evidence. No parallel
identity registry has been created.

All 14,723 excluded rows are exact current-universe ISIN matches with a different
source symbol. All 63 pairings also have a same-token/same-series current-symbol
source observation. Descriptive class for each is
`SAME_ISIN_DIFFERENT_SOURCE_SYMBOL`. This is useful first-party transition
evidence, **not** proof that every interval between observations is continuous.
No current symbol is written backwards. The report retains every date, token,
series, artifact and ordinal, plus matching current-symbol source points.

| Current symbol | Historical source symbol | Excluded rows |
| --- | --- | ---: |
| ABREL | CENTURYTEX | 65 |
| ACUTAAS | AMIORG | 26 |
| ADOR | ADORWELD | 189 |
| AEROENTER | SATINDLTD | 239 |
| AERONEU | SAH | 280 |
| AEROPLANE | AMIRCHAND | 72 |
| AFSL | AHL | 182 |
| ALIVUS | GLS | 134 |
| ALLDIGI | ALLSEC | 57 |
| ANTELOPUS | SELAN | 300 |
| ARIS | ARISINFRA | 155 |
| ASHIKAG | ASHIKA | 67 |
| AURUS | LYPSAGEMS | 497 |
| BILVYAPAR | BINANIIND | 252 |
| BIRLANU | HIL | 188 |
| BOSCH-HCIL | JCHAC | 364 |
| CCAVENUE | INFIBEAM | 391 |
| CEMPRO | ITDCEM | 297 |
| CNL | CREATIVE | 354 |
| COHANCE | SUVENPHAR | 212 |
| CPCAP | CAREERP | 175 |
| DHARAN | KBCGLOBAL | 240 |
| ETERNAL | ZOMATO | 191 |
| GANESHHOU | GANESHHOUC | 296 |
| GMRAIRPORT | GMRINFRA | 107 |
| GUJENERGY | GUJGASLTD | 488 |
| GVPIL | GEPIL | 283 |
| GVT&D | GET&D | 83 |
| HALEOSLABS | SMSLIFE | 344 |
| HBLENGINE | HBLPOWER | 115 |
| HEALTHX | SASTASUNDR | 449 |
| HGM | HOVS | 287 |
| IBULLSLTD | YAARI | 291 |
| IIFLCAPS | IIFLSEC | 101 |
| JSWDULUX | AKZOINDIA | 437 |
| KAVDEFENCE | KAVVERITEL | 237 |
| LANDSMILL | EXCEL | 429 |
| LMW | LAXMIMACH | 65 |
| LTM | LTIM | 409 |
| ONIDA | MIRCELECTR | 481 |
| ORTINGLOBE | ORTINLAB | 39 |
| RVTH | REVATHIEQU | 51 |
| SAMMAANCAP | IBULHSGFIN | 13 |
| SETL | SGLTL | 251 |
| SIGMAADV | MEGASOFT | 394 |
| SMLMAH | SMLISUZU | 332 |
| SUDARCOLOR | HEUBACHIND | 381 |
| SUNDROP | ATFL | 182 |
| SWANCORP | SWANENERGY | 289 |
| TARIL | TRIL | 33 |
| TEAMGTY | TIMESGTY | 274 |
| TICL | TCLCONS | 148 |
| TIPSMUSIC | TIPSINDLTD | 58 |
| TMPV | TATAMOTORS | 325 |
| TRANSWORLD | SHREYAS | 74 |
| TSFINV | SUNDARMHLD | 317 |
| UFBL | BARBEQUE | 314 |
| UMIYA-MRO | MRO-TEK | 190 |
| URAVIDEF | URAVI | 129 |
| VEEDOL | TIDEWATER | 64 |
| VISACHROME | VISASTEEL | 339 |
| VIYASH | SEQUENT | 384 |
| WORTHPERI | WORTH | 313 |

For example ZOMATO/ETERNAL is a source-backed same-ISIN symbol observation pair;
GENUSPOWER has EQ/BE/BL tokens, which must not become interchangeable series;
TATAMOTORS/TMPV observations do not by themselves resolve economic consequences
of a demerger. No changed-ISIN example is claimed from a population selected by
**equal ISIN**. ISIN-change and contrary-lifecycle adjudication remain unperformed
at this stop, rather than being fabricated from the 63 pairs.

Effective-dated production identity receipts remain **0 -> 0** because promotion
is stopped on the proven storage/read-key defect, not because UDiFF lacks source
identity. Exact dated facts can support non-zero receipts after that repair.
The existing PIT selector uses one timestamp for both known and effective state;
a retrospective Daily identity consumer must keep `effective_at` and
`knowledge_as_of` separate. Acquisition in 2026 must not imply HSI knew a 2024
fact in 2024. A source-day receipt must not become an open-ended listing or
tradability interval. Lifecycle review is still required before joining days.

## MII source feasibility and acquisition boundary

[NSE MSD60315](https://nsearchives.nseindia.com/content/circulars/MSD60315.pdf)
documents daily website dissemination from 2024-02-05, before the UDiFF era.
The existing [MII acquisition](NSE_HISTORICAL_MII_SECURITY_MASTER_SNAPSHOT_ACQUISITION_V1.md)
uses `NSE_CM_security_DDMMYYYY.csv.gz` and preserves date-labelled identity
without inventing publication instants.

The directly queried `HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT` family contains
61,850 records on two report dates: 24,694 records for 2024-02-05 and 37,156 for
2026-08-31 (records include headers and rows, not that many files). This is not a
full inventory of separately nested BRSR anchor evidence. No MII download or
continuity activation was attempted after the repair stop. Historical archive
availability for all 532 dates is **not proven** by the dissemination circular.
The next identity stage should first reuse retained exact-date evidence, then
probe only unresolved transition anchors; no blanket 532-file download.

## Five-holding source audit

Each has 532 stored Daily observations. These counts describe stored facts,
not repaired source selection or continuity certification.

| Symbol / canonical suffix (all `NSE:`) | Source tokens by series | Conflicts | Class | Action intersections from retained prior audit |
| --- | --- | ---: | --- | --- |
| APARINDS / INE372A01015 | EQ:11491 | 0 | none recorded | 2 dividends |
| DEEPINDS / INE0FHS01024 | EQ:3292 | 0 | none recorded | 0 known |
| GENUSPOWER / INE955D01029 | EQ:11905; BE:11908; BL:12383 | 2 | BL/EQ distinct series | 1 demerger |
| GLAND / INE068V01023 | EQ:1186 | 0 | none recorded | 3 dividends |
| ICICIBANK / INE090A01021 | EQ:4963; BL:12458 | 8 | BL/EQ distinct series | 0 known |

All five retain exact same-ISIN/symbol source observations; no observed symbol
change in this retained set. Effective interval certification and canonical
Daily source-addressability promotion are deferred for all five. An absence of
recorded actions is not a complete action-free-window certificate.

## Independent readiness matrix at repair stop

| Gate | State | Evidence / remaining boundary |
| --- | --- | --- |
| A. UDIFF_SOURCE_ROW_IDENTITY | READY | Deterministic audit contract; 1,568 sealed sides for all 784 collisions. Not a production store key. |
| B. INGESTION_KEY_SEMANTICS | NOT_READY | Five-column key and read grouping conflate material series identities. |
| C. SAME_PROVIDER_CONFLICT_CLASSIFICATION | READY | 784/784 exact joins, all DISTINCT_SERIES. |
| D. SAME_PROVIDER_CONFLICT_RESOLUTION | PARTIAL | Semantics explained; all 784 immutable artifacts retained and repair pending. |
| E. MII_HISTORICAL_IDENTITY_SOURCE | PARTIAL | Existing source contract and retained dates; full era archive availability unproven, 0 new downloads. |
| F. EFFECTIVE_DATED_SECURITY_IDENTITY | NOT_READY | 0 receipts; production promotion stopped on structural repair. |
| G. SYMBOL_CHANGE_CONTINUITY | PARTIAL | 63 source-backed same-ISIN pairs, 14,723 rows; no certified intervals. |
| H. ISIN_CHANGE_CONTINUITY | NOT_READY | Not demonstrated by equal-ISIN pairings; lifecycle proof required. |
| I. SERIES_CHANGE_SEMANTICS | PARTIAL | EQ/BL/T0 distinctness proven; BE/BZ and other transitions not globally certified. |
| J. CURRENT_TO_HISTORICAL_SECURITY_LINK | PARTIAL | Exact same-ISIN source observations; no heuristic or changed-ISIN bridges. |
| K. DAILY_SOURCE_ADDRESSABILITY | PARTIAL | 2,553 securities have raw observations; 1,568 audited row IDs; 0 newly certified canonical bars/securities. |
| L. CANONICAL_DAILY_SOURCE_SELECTION | NOT_READY | Existing pure selector unmodified; series-aware reads need repair first. |
| M. PRICE_CONTINUITY | NOT_READY | Identity is not adjustment/action-window certification. |
| N. VOLUME_CONTINUITY | NOT_READY | No share-count continuity certificate. |
| O. CURRENT_DESCRIPTIVE_DAILY_TECHNICAL_DATA | PARTIAL | Raw source facts accessible; no technical certification promoted. |
| P. WEEKLY_DERIVATION_GATE | NOT_READY | No derivation or indicator activation. |

Population: 2,553; recorded-conflict-free: 2,199; affected: 354. Production
certified identity chains READY: 0, PARTIAL: 0, NOT_READY: 2,553. These are
certificate counts, not evidence-availability counts. True source-value
conflicts in the audited 784: 0; semantically unexplained: 0; pending
storage/read separation: 784. No subset is promoted by merely deleting a blocker.

## Reproduction, integrity and validation

From the authoritative root, using its approved Python environment:

```powershell
python -m scripts.audit_nse_udiff_identity_boundary --database D:/nse-stock-manager/data/nse_stock_manager.db --output D:/nse-stock-manager/reports/udiff-identity-boundary
```

The tool uses SQLite URI `mode=ro`, `query_only=ON` and one read transaction.
It cannot create a missing database. Output is immutable, content-addressed
local JSON, never a canonical receipt. The complete report has every conflict's
exact raw fields, persistence key, both sealed lineages, per-date/per-instrument
detail, all 63 pairings and the schema witness. Raw reports remain Git-excluded.

Report SHA-256: `49e31c20dbc4471e5b47e778ecc731c4fbe8d3fad83a70372bc3199c6d85b02f`.
SQLite integrity: `ok`; FK violations: `0`. Bars: 2,648,292; UDiFF: 1,103,153;
canonical actions: 3,886; historical effective identities: 0. No production
write methods are used, and no schema migration runs.

Final validation: focused 30 passed; relevant source/storage/identity/MII/
lifecycle/action/session tests 174 passed; complete backend 2,915 passed,
0 failed, 6 skipped, 2 dependency-deprecation warnings (200.34 seconds).
The full audit was executed twice with the identical report hash above and
no additional report/production receipt. Edited Markdown local-file links:
209 checked, zero missing; whitespace and `git diff --check` passed.
Production portfolio snapshots remain 1, cash UNKNOWN, paper trades/trade
plans/generic strategy versions/generic diagnostic results all 0. Existing
portfolio transactions remain 5; none were created by this read-only task.

## One exact bounded repair continuation

`NSE_UDIFF_SERIES_AWARE_OBSERVATION_STORAGE_REPAIR_V1`

Before any identity/technical promotion:

1. Inventory each existing UDiFF row against its exact archived row; include
   equal-valued cross-series deduplication cases, not only the 784 ledger entries.
2. Extend the **existing** observation identity boundary with a source-scoped
   key. Keep non-UDiFF keys unchanged. Preserve all old values/provenance and
   immutable conflict artifacts through a deterministic migration receipt.
3. Map every migrated key to the archived source identity; recover rejected
   rows from the validated artifacts idempotently. Do not relabel BL as EQ,
   overwrite values or use fake provider names to separate series.
4. Make both duplicate detection and raw/canonical read grouping source-aware.
   No implicit winner across EQ/BE/BZ/BL/T0/SM/ST. Ordinary Daily selection
   requires an explicit governed series contract; ambiguous reads fail closed.
5. Prove migration/reopen/replay, exact row deltas, old-evidence preservation,
   unaffected other providers, and full regression/integrity. Only then resume
   effective-dated identity receipts with separate historical/known-time axes.

This checkpoint does not authorize a generalized cross-provider rewrite. It
does not proceed to Daily continuity certification or Weekly derivation.

```text
NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY
NSE_UDIFF_CANONICAL_DAILY_HISTORY_BACKFILL = READY
UDIFF_SESSION_COVERAGE = READY
UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
```

The inherited source/backfill READY states mean retained raw acquisition, not
corrected series selection. FACT -> DATA -> INTERPRETATION -> INFERENCE;
identity continuity != price continuity != volume continuity. No provider
mixing/fallback, price/volume adjustment, indicators, Weekly/Monthly bars,
portfolio authority, alerts, scores, technical Brain or execution authority.
