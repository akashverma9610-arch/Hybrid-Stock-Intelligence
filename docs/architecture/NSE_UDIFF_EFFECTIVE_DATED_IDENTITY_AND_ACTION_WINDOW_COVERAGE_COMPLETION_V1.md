# NSE UDiFF Effective-Dated Identity and Action-Window Coverage Completion V1

Status: `IMPLEMENTED_METADATA_BOUNDARY / NOT_TECHNICAL_ANALYSIS / NOT_ACTIVE`

## Purpose

This additive boundary composes retained first-party NSE UDiFF and corporate-action evidence so the existing Daily eligibility certifier can answer, for one requested window, whether selected source observations are addressable and whether the action-query source covered that window. It does not calculate an indicator, select a setup, alter an OHLCV row, adjust prices, derive Weekly bars, activate a generic technical read, or create trading authority.

`FACT → DATA → INTERPRETATION → INFERENCE` remains the governing order.

## Compact exact identity coverage

The retained source-row identity is `ISIN + FinInstrmId + TckrSymb + SctySrs + TradDt + SsnId`.

For a current eligible canonical security, an exact current canonical ISIN is the only new anchor. Current symbol equality, company name, a heuristic predecessor, and a changed ISIN are never an anchor. Source symbols remain as published. A changed ISIN or contrary lifecycle row without exact proof is unresolved.

The builder creates maximal adjacent runs only where the exact source identity tuple is unchanged across reconciled UDiFF session order. An interval retains start/end sessions, first/last source-row references, source-row count, an ordered source-lineage digest, source-artifact digest, current-universe anchor snapshot, and deterministic fingerprint. It does **not** retain an ID list or receipt per bar. The 201 existing historical-symbol intervals remain immutable and are excluded from new compact-run construction.

`NseUdiffEffectiveIdentityCoverageIndex` resolves an exact source observation through a keyed interval lookup. The Daily certifier constructs that index once and does not scan all identity receipts for every bar.

Identity coverage is addressability only. EQ, BE/BZ, BL, and T0 may be addressable with the same underlying ISIN but remain separate source-series facts. The accepted Daily policy continues to exclude BL and T0 and to fail closed on EQ↔BE/BZ transitions.

## Action and lifecycle window composition

`NseUdiffActionWindowCoverage` is a deterministic composable receipt, not a global “lifecycle complete forever” flag. It can be `READY` only when:

1. exact effective identity intervals cover every supplied required selected session in the requested security/window;
2. successful official exchange-wide corporate-action query receipts cover the entire date window with no query gap; and
3. the complete-source result was known by the caller's explicit evaluation as-of time.

Successful empty query windows are meaningful: when source query coverage is complete and no applicable exact canonical action exists, the receipt states `no_action_found_with_complete_query_coverage=true`. That is intentionally different from missing or failed query evidence. Known action identities are carried compactly; their payload is not copied into each coverage receipt.

This action coverage feeds the existing `CorporateActionCoverageAssertion` contract. It does not make price or volume continuous. The existing certifier retains its separate outcomes: split/bonus adjustment required, rights/complex action non-comparable, and dividend policy unavailable. A source/session gap is an identity/lifecycle-window failure; it is never filled as a holiday.

Exact action-observation mapping is restricted to exact source ISIN, source symbol, source series, effective source date, and one unambiguous effective UDiFF interval. There is no name or current-symbol fallback and no rewrite of legacy corporate-action receipts.

The initial retained observation audit considered 586 previously
identity-unresolved action observations. None supplied the complete unique
exact UDiFF identity needed for a new mapping, so all 586 remain explicitly
`IDENTITY_UNRESOLVED`; no old receipt was changed and no action was inferred.

## Persistence and replay

Only two new append-only Core snapshot families are used:

- `NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL`
- `NSE_UDIFF_EFFECTIVE_IDENTITY_RECEIPT`

They hold compact immutable metadata. Replaying unchanged retained archives must insert zero equivalent intervals and no second equivalent receipt. The local composition function reads stored UDiFF archives one at a time, makes no network call, and writes nothing until its explicit `complete()` operation. No OHLCV migration, raw-source copy, database backup, or action-receipt overwrite is part of this slice.

## Initial retained-source completion receipt

The initial local replay covered 1,118,854 retained current-universe source
observations: 14,723 remain represented by the immutable historical-symbol
intervals and 1,104,131 are represented by 7,956 compact exact-ISIN intervals;
zero source observations were unresolved by the anchor rule. One compact
coverage receipt was added. Local SQLite growth was approximately 35.8 MB,
metadata only.

The existing 37 successful monthly exchange-wide corporate-action queries and
3,886 immutable canonical action receipts were composed read-only. For the
latest source-date 4/5/6-session audit, raw-complete / ordinary-series-ready /
identity-ready / action-window-ready / final eligible counts were respectively
2,552 / 2,534 / 2,552 / 2,552 / 2,500; 2,551 / 2,527 / 2,551 / 2,551 / 2,483;
and 2,551 / 2,523 / 2,551 / 2,551 / 2,472. Remaining price/volume blocks were
the existing dividend, rights, and series-transition policies, not an inferred
absence of evidence. This is a certification result only: generic Daily
technical reads remain unactivated.

## Boundaries retained

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
- `LOCAL_STORAGE_HYGIENE_DEBT = OPEN`

No provider merge, Upstox fallback, indicators, technical strategy, Weekly or Monthly bar derivation, portfolio access, order/broker call, or execution authority is introduced.
