# NSE UDiFF historical security identity continuity promotion V1

Scope: `NSE_UDIFF_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_PROMOTION_V1`.

This is an identity-only, source-date promotion. It makes an exact retained
UDiFF source observation addressable to a current canonical NSE security when
the governed evidence below supports that relationship. It does not certify
price continuity, volume continuity, corporate-action adjustment, technical
series equivalence, a Daily canonical source, weekly bars, indicators or any
portfolio/execution outcome.

## Reused boundary and immutable records

The operation reuses the existing `HistoricalSecurityIdentity` master as the
sole effective-dated security receipt. Two additive Core snapshot families
retain the narrower source evidence and decision provenance:

- `NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL` contains an observed interval of
  exact `ISIN + FinInstrmId + TckrSymb + SctySrs` facts, its exact
  source-observation identities, raw artifact IDs, session coverage
  fingerprints, source date span, retrieval known-at and content fingerprint.
- `NSE_UDIFF_HISTORICAL_IDENTITY_PROMOTION_RECEIPT` accounts for one
  current-symbol/source-symbol pairing, its interval and historical-security
  IDs, current-symbol chronology evidence, exact lifecycle blockers and a
  deterministic continuity decision.

Neither is a second security registry. The first is retained exchange source
evidence; the second is a versioned decision explaining a link made through
the existing security master. All writes are insert-only. Replaying an equal
plan is a no-op; stronger future evidence must create a new receipt rather
than replace a prior one.

`known_at` is the retained artifact retrieval time. It is explicitly not an
assertion that HSI knew the fact on the historical trading date;
`historical_known_at` remains unavailable. The observed dates are labelled
exchange trade-date facts, not claimed market-close timestamps.

## Evidence standard and continuity decisions

For a current eligible target, an old source symbol can be promoted only when
all of the following hold:

1. Its retained source ISIN exactly equals the current canonical ISIN and the
   current canonical ID is exactly `NSE:<ISIN>`.
2. Retained UDiFF chronology has a current-symbol source fact with the same
   ISIN, source token and source series after the old-symbol span.
3. There is no retained exact-ISIN lifecycle evidence of delisting,
   merger/cessation or compulsory delisting inside that observed span.

The source chronology is sufficient first-party evidence in this bounded
case; a duplicate symbol-change document is preferred if already retained but
not required. Company names are never used. A changed ISIN is not linked by
this operation: it receives no current canonical target, produces no receipt
and remains unavailable pending explicit first-party lifecycle, corporate
action or security-master evidence.

When the above conditions are satisfied, a single-series/token alias is
`SAME_SECURITY_SYMBOL_CHANGE_PROVEN`. Multiple historical source series are
`SAME_ISIN_SERIES_VARIANT`; multiple tokens within one series are
`TOKEN_CHANGE_SAME_SECURITY_PROVEN`. A series variant retains the same
underlying-security link but also records
`SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY`.

`LIFECYCLE_BREAK`, `CURRENT_CANONICAL_MAPPING_DEFECT` and
`HISTORICAL_IDENTITY_UNRESOLVED` are fail-closed. They have no historical
security receipt and are never replayed into raw observations.

## Source intervals and raw replay

Intervals follow the reconciled valid-session sequence, not calendar-day
adjacency. Friday to Monday and known holiday spans are compatible when no
valid UDiFF session has been omitted. An interval begins at its first observed
source date and ends at its last observed source date; no earlier identity is
invented.

The local replay reads every retained artifact one ZIP at a time. It maps a
source row only through a promoted interval and calls the existing UDiFF row
parser, quality validator and provider-versioned historical-bar writer. The
bar preserves its historical `TckrSymb` as `instrument.symbol` and
`trading_symbol`; it is never rewritten to the current symbol. The current
canonical instrument ID remains the exact ISIN-backed ID. Invalid OHLC rows
remain invalid, and same-provider conflicts remain immutable conflict
artifacts.

The existing series-aware source-observation key remains authoritative. EQ,
BE, BL, T0 and every other exchange source series remain distinct raw facts.
BL remains BL and T0 remains T0. This identity decision cannot make either an
EQ technical candle or activate an ordinary `range`, `latest`, readiness,
snapshot-bridge or indicator read.

## Explicit non-goals

- no generic or canonical UDiFF technical read activation;
- no action-free/price/volume continuity certificate;
- no corporate-action adjustment or price rewrite;
- no weekly/monthly derivation, indicators, patterns or horizon policy;
- no new external acquisition, MII bulk download or provider fallback;
- no API, UI, portfolio, order, broker or execution behavior.

FACT → DATA → INTERPRETATION → INFERENCE remains unchanged. A source-date
identity fact is not a current symbol, a technical series or an investment
conclusion.

## Local operation

Run from the repository root:

```powershell
& 'C:\Users\Acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m scripts.promote_nse_udiff_historical_security_identity
```

The command uses only the existing local SQLite database and retained UDiFF
artifacts. Its JSON receipt reports intervals, classifications, source rows
addressable, raw-bar outcomes and confirms `technical_selection=NOT_ACTIVE`.
It does not fetch a network source.

## Preserved governance

- `NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY`
- `NSE_UDIFF_CANONICAL_DAILY_HISTORY_BACKFILL = READY`
- `UDIFF_SESSION_COVERAGE = READY`
- `UDIFF_SERIES_AWARE_STORAGE = READY`
- `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`
- `EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`
- `NO_INDICATOR_EXPANSION = TRUE`

The only subsequent bounded technical task, after the production receipt is
validated, is
`NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1`.
It must independently combine source authority, session completeness,
series policy, effective-dated identity, corporate actions, price continuity
and volume continuity. This identity promotion does none of those things.

## Completed local production receipt — 2026-09-06

The retained local archive was replayed twice without any network request.
The first pass inserted **201** source intervals, **201** historical-security
identity receipts and **63** pairing receipts. It made all **14,723** audited
historical-symbol rows source-addressable and admitted all **14,723** as
distinct raw UDiFF observations. It found **0** invalid source rows, **0**
same-provider conflicts and **0** replay errors. The second pass inserted
**0** intervals, identities, receipts or bars, and found **14,723** equivalent
observations already present.

All 63 pairings are accounted for:

| Continuity state | Pairings | Source rows |
|---|---:|---:|
| `SAME_SECURITY_SYMBOL_CHANGE_PROVEN` | 32 | 5,827 |
| `SAME_ISIN_SERIES_VARIANT` | 31 | 8,896 |
| Fail-closed lifecycle/current-mapping/unresolved | 0 | 0 |

The 201 interval records retain **88 EQ**, **98 BE** and **15 BL** exact source
series facts. No T0 historical-symbol alias occurred in the 63-pair cohort;
T0 remains independently protected by the series-aware source boundary.
There was no standalone same-series token-change pairing. Where tokens differ
inside this cohort they are associated with distinct source-series facts, not
treated as an underlying-security break or as technical-series equivalence.

Representative exact source cases are `SAMMAANCAP ← IBULHSGFIN`
(`INE148I01020`, 13 source rows, one interval) for a proven symbol change and
`RVTH ← REVATHIEQU` (`INE0DAB01012`, 51 source rows, three intervals) for a
same-ISIN series variant. No retained exact lifecycle record contradicted the
63 links; no MII or new symbol-change source was fetched.

The five governed holdings have no historical-symbol alias in this cohort, so
their promotion-interval count is zero. Their retained current-symbol UDiFF
source facts remain unchanged:

| Holding | Canonical ID | Raw UDiFF source facts | Series | Tokens | Existing corporate-action facts |
|---|---|---:|---|---|---:|
| APARINDS | `NSE:INE372A01015` | 532 | EQ 532 | 11491 | 2 |
| DEEPINDS | `NSE:INE0FHS01024` | 532 | EQ 532 | 3292 | 0 |
| GENUSPOWER | `NSE:INE955D01029` | 534 | EQ 522; BE 10; BL 2 | 11905, 11908, 12383 | 1 |
| GLAND | `NSE:INE068V01023` | 532 | EQ 532 | 1186 | 3 |
| ICICIBANK | `NSE:INE090A01021` | 540 | EQ 532; BL 8 | 12458, 4963 | 0 |

The listed corporate-action counts are lineage only; this operation neither
interpreted an action nor certified adjusted prices.

SQLite integrity is `ok` and foreign-key violations are `0`. Historical bars
changed only by the accounted UDiFF raw additions: **2,649,076 → 2,663,799**;
UDiFF observations **1,103,937 → 1,118,660**. No portfolio, order, broker,
generic strategy/result or canonical diagnostic record was changed.

| Readiness boundary | State | Exact reason |
|---|---|---|
| A. UDiFF source-date identity | READY | Exact source fields retained for every promoted row |
| B. Effective-dated identity intervals | READY | 201 immutable observed-session intervals |
| C. Effective-dated identity receipts | READY | 201 historical-security receipts; replay-safe |
| D. Symbol-change continuity | READY | 32 exact same-ISIN chronology links |
| E. Token-change continuity | NOT_APPLICABLE | No standalone same-series token-change case in this cohort |
| F. ISIN-change continuity | NOT_READY | No automatic changed-ISIN bridge is authorized |
| G. Series-variant identity | READY | 31 links; 98 BE and 15 BL interval facts remain distinct |
| H. Current-to-historical security link | READY | 63 exact current ISIN-backed canonical links |
| I. 63-pairing classification | READY | 63/63, with no generic residual state |
| J. 14,723-row reconciliation | READY | 14,723/14,723 source-addressable and replayed |
| K. Daily source addressability | READY | Identity linkage only; 14,723 raw facts added |
| L. Canonical Daily technical selection | NOT_READY | Series-selection policy is still not active |
| M. Price continuity | NOT_READY | No action/basis continuity certification |
| N. Volume continuity | NOT_READY | No volume continuity certification |
| O. Current descriptive Daily technical data | NOT_READY | Identity promotion is not technical eligibility |
| P. Weekly derivation gate | NOT_READY | Requires the separately governed Daily eligibility result |
