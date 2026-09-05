# NSE Canonical Corporate-Action Coverage Backfill V1

**Status:** `IMPLEMENTED / INSERT_ONLY / CONTINUITY_EVIDENCE_ONLY / NOT_A_PRICE_BASIS_DECISION`

## Purpose and bounded historical window

This component acquires first-party NSE corporate-action evidence required to
audit technical price/volume continuity. It extends the existing immutable
`HistoricalCorporateAction` store; it does not create a second corporate-action
database or modify retained OHLCV.

The requested window is derived from the retained daily OHLCV population:

| Boundary | Date |
| --- | --- |
| Earliest retained bar | `2023-08-21` |
| Latest retained bar | `2026-08-31` |
| Requested official action window | `2023-08-21` through `2026-08-31`, inclusive |

The acquisition partitions that exact range into non-overlapping calendar-month
queries. It does not silently truncate history or issue per-symbol polling.

## First-party NSE source and immutable provenance

The source is the official NSE [Corporate Filings / Corporate
Actions](https://www.nseindia.com/companies-listing/corporate-filings-actions)
surface. Its bounded exchange-wide query identity is:

```text
GET /api/corporates-corporateActions
    ?index=equities
    &from_date=DD-MM-YYYY
    &to_date=DD-MM-YYYY
```

One request is made per monthly window with ordinary page-session bootstrap and
conservative pacing. The source is recorded as:

- family: `NSE_OFFICIAL_CORPORATE_ACTION_API`
- version: `nse-corporate-action-coverage-v1`
- mode: `EXCHANGE_WIDE_DATE_RANGE`

For every query HSI immutably retains a source artifact when NSE supplied a
response, a typed query receipt, and (for returned records) a raw observation.
The artifact includes the verbatim UTF-8 response, content SHA-256, date-window
identity, record count, acquisition observation time, and deterministic
fingerprint. Raw `subject`/purpose text is never replaced by a normalized
label.

An acquisition manifest is immutable and fingerprints its acquisition ID,
frozen eligible-universe snapshot, exact requested instrument IDs and date
range, source family/version/mode, source artifacts, query receipts, and the
separate counts for success, successful-empty, failed, blocked, and invalid
queries. Reusing an acquisition ID with any different universe or range fails
closed; exact replay returns the original manifest without re-fetching or
inserting equivalent records.

`SUCCESS_EMPTY` means NSE successfully returned zero records. It is never
equivalent to `SOURCE_FAILED`, `SOURCE_BLOCKED`, `INVALID_RESPONSE`, or
`NOT_QUERIED`.

## Identity, normalization, and date discipline

An observation maps to a canonical security only when its NSE ISIN maps to one
unique frozen-universe instrument **and** its NSE symbol agrees. If an ISIN is
absent, a unique exact `EQ` symbol match may be used. Company names, fuzzy
matching, and issuer CIN are never identity inputs. Unresolved or conflicting
records remain immutable source observations with `IDENTITY_UNRESOLVED` or
`IDENTITY_CONFLICT`; they are not promoted to canonical actions.

The raw purpose is retained along with a deterministic family classification:
`SPLIT`, `BONUS`, `RIGHTS`, `DIVIDEND`, `SPECIAL_DIVIDEND`,
`AGM_DIVIDEND_MIXED`, `BUYBACK`, `MERGER`, `DEMERGER`,
`CAPITAL_REDUCTION`, `FACE_VALUE_CHANGE`, `SYMBOL_CHANGE`, `RELISTING`,
`INTEREST_REDEMPTION`, `OTHER`, or `UNKNOWN`.

Only unambiguous, currently supported action families become an existing
`HistoricalCorporateAction` receipt. `RIGHTS` retains any exact parsed ratio
and its raw purpose (including a source-stated premium), but activates no
rights adjustment. Dividends are retained as continuity evidence only; HSI does
not turn price data into a total-return series. Complex/lifecycle events remain
descriptive evidence and never receive a synthetic multiplicative transform.

Ex-date, record date, book-closure start/end, and source observation time are
distinct fields. Record date is never treated as ex-date. Split/bonus ratios are
parsed only from explicit source wording; otherwise the receipt is preserved
with `ADJUSTMENT_INPUT_INCOMPLETE`.

NSE historical results do not provide an original dissemination timestamp.
Every imported observation therefore carries
`HISTORICAL_SOURCE_KNOWN_AT_UNAVAILABLE`: its `observed_at` proves when HSI
obtained the evidence, not when it could have known it in the past.

## Coverage and continuity boundary

The per-security assessment is scoped to the frozen eligible universe and uses
the following states:

- `QUERY_SUCCESS_WITH_ACTIONS`
- `QUERY_SUCCESS_NO_ACTIONS`
- `PARTIAL_DATE_RANGE`
- `QUERY_FAILED`
- `SOURCE_BLOCKED`
- `IDENTITY_UNRESOLVED`
- `NOT_QUERIED`

Every result also retains
`LIFECYCLE_SOURCE_REQUIRED`. Corporate-actions evidence alone cannot certify
an action-free technical lookback: suspension, delisting, relisting, symbol and
security continuity must remain separately composed from canonical lifecycle
evidence. Consequently this backfill produces **zero standalone
action-free-window certifications**. “No receipt” never means “no action.”

The existing technical price-adjustment formula and source-acceptance contract
are unchanged. This backfill neither relabels bars nor treats a current import
as historical PIT availability.

## Persisted families and safety

The existing core snapshot store gains additive immutable families only:

- `NSE_CORPORATE_ACTION_SOURCE_ARTIFACT`
- `NSE_CORPORATE_ACTION_QUERY_RECEIPT`
- `NSE_CORPORATE_ACTION_OBSERVATION`
- `NSE_CORPORATE_ACTION_COVERAGE_ASSESSMENT`
- `NSE_CORPORATE_ACTION_ACQUISITION_MANIFEST`

Existing `HISTORICAL_CORPORATE_ACTION` receipts are reconciled by exact
semantic action identity and are never overwritten. Equivalent existing
evidence is reported as duplicate provenance; conflicting immutable IDs fail
closed.

This component has no indicator calculation, weekly/monthly derivation,
technical voting, separate Brain, portfolio access, API/UI route, broker/order
interface, or execution authority. It preserves:

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
```

## State after acquisition

The production receipt must report query outcomes by year/window, exact
identity coverage, raw and canonical action-family counts, existing/new action
reconciliation, and the five prescribed holdings. It must separately preserve:

```text
UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
HISTORICAL_TECHNICAL_CONTINUITY = NOT_READY unless a separate governed basis decision changes
```

Corporate-action coverage cannot establish whether Upstox historical candles
are raw or adjusted. If that provider-basis ambiguity remains after this
coverage work, the next bounded architecture decision is prospective,
HSI-observed canonical bar capture rather than reconstructed historical
technical continuity.
