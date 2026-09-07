# NSE First-Party Quote Taxonomy Access and Schema Proof V1

**Status:** `COMPLETE / CURRENT_DESCRIPTIVE_ONLY / NO_BACKFILL_AUTHORIZED`
**Primary result:** `QUOTE_TAXONOMY_SOURCE_PARTIAL`
**Scope:** bounded source-access, schema, identity, and hierarchy proof only.

## Decision

The official NSE equity quote surface visibly renders current security identity,
series, listing/trading status, and **Basic Industry** for a small public-page
sample. It is therefore useful first-party *descriptive evidence*. It is not a
canonical HSI taxonomy acquisition source: the normal static page is a
client-rendered shell, and the normal public quote-data resource returned
`HTTP 403`. No access control was bypassed, and no DOM selector, OCR, visual
scrape, reverse-engineered endpoint, proxy, or header-evasion method is used.

The source remains **partial** rather than missing or unsuitable: `403` is
recorded as `SOURCE_ACCESS_BLOCKED`, never as a missing taxonomy field. This
result authorises no full-market request, parser, taxonomy write, or historical
backfill.

## Bounded normal-access receipt

At the audit boundary, the ordinary public page request for APARINDS succeeded:

| Item | Result |
| --- | --- |
| Quote page | `https://www.nseindia.com/get-quote/equity/APARINDS/Apar-Industries-Limited` |
| Normal static response | `200 text/html`, 146,357 bytes |
| Retained ignored receipt | `data/official_sources/nse_quote_taxonomy/2026-09-07/APARINDS-INE372A01015-c1587f291187.html` |
| Receipt content fingerprint | `sha256:c1587f291187f64f8df944c732ee9a59840ae00788fddab6f97b21618e28700d` |
| Static content result | client-rendered shell; it contains neither the exact ISIN nor `Basic Industry` |
| Public quote-data resource | `https://www.nseindia.com/api/quote-equity?symbol=APARINDS` |
| Normal resource result | `403 text/html`; no programmatic retry or alternate-resource fallback was attempted |

The static body is byte-retained with a provenance manifest, but is not a
taxonomy receipt because it has no exact identity/taxonomy fields. A normal
interactive public page rendered the fields below. Those observations are
source-proof evidence only; they are not byte-retained machine receipts and are
explicitly not promotable classifications.

## Quote-page field proof

The public page rendered the heading `<legal name>(<ISIN>)`, `EQ` (and for
some securities `T0`) series, `Status Listed`, `Trading Status Active`, and
`Basic Industry`. It did not render a Basic Industry code, classification
review/effective date, or a four-tier security assignment. The taxonomy version
state is `SOURCE_CLASSIFICATION_VERSION_UNAVAILABLE`; HSI retains only an
observation time when an acquisition is later authorised.

| Requested symbol | Quote ISIN | Series observed | Status | Basic Industry | Identity result | Sample state |
| --- | --- | --- | --- | --- | --- | --- |
| APARINDS | `INE372A01015` | `EQ` | Listed / Active | Other Electrical Equipment | exact | rendered evidence only |
| DEEPINDS | `INE0FHS01024` | `EQ` | Listed / Active | Oil Equipment & Services | exact | rendered evidence only |
| GENUSPOWER | `INE955D01029` | `EQ`, `T0` | Listed / Active | Other Electrical Equipment | exact | rendered evidence only |
| GLAND | `INE068V01023` | `EQ` | Listed / Active | Pharmaceuticals | exact | rendered evidence only |
| ICICIBANK | `INE090A01021` | `EQ`, `T0` | Listed / Active | Private Sector Bank | exact | rendered evidence only |
| TDPOWERSYS | `INE419M01035` | `EQ` | Listed / Active | Heavy Electrical Equipment | **mismatch** with HSI `INE419M01027` | `IDENTITY_MISMATCH` |
| INFY | `INE009A01021` | `EQ`, `T0` | Listed / Active | Computers - Software & Consulting | exact | rendered evidence only |
| HDFCBANK | `INE040A01034` | `EQ`, `T0` | Listed / Active | Private Sector Bank | exact | rendered evidence only |

DEEPINDS and GENUSPOWER show that the UI currently displays exact Basic
Industry outside the retained 711-security source universe. They are **not**
`SAMPLE_TAXONOMY_PROVEN`: a stable byte-retained parser or normally accessible
machine payload is still required before their fields can become canonical
evidence. TDPOWERSYS is fail-closed; its symbol does not repair its ISIN
conflict.

## Machine-schema decision

`SOURCE_MACHINE_SCHEMA_NOT_READY` is intentional. The UI label proves only
what a user can see. There is no normally accessible machine response from
which this slice can truthfully record field names, nesting, null semantics,
timestamp/update semantics, a Basic Industry code, or source classification
version. No brittle rendered-page parser was created.

If a separately approved normal-access payload becomes available, its minimum
receipt is: requested symbol; canonical and source ISIN; source symbol; all
series; listing/trading state; Basic Industry and code if supplied; explicitly
supplied parent tiers; source URL; observed-at; payload fingerprint; and
missing/null semantics. A source ISIN equal to canonical ISIN plus compatible
symbol remains mandatory.

## Official hierarchy audit

The retained official NSE Industry Classification structure contains:

| Level | Count |
| --- | ---: |
| Macro-Economic Sector | 12 |
| Sector | 22 |
| Industry | 59 |
| Basic Industry | 197 |
| Unique Basic Industry labels | 197 |
| Duplicate / ambiguous Basic Industry labels | 0 / 0 |
| Unique Basic Industry codes | 197 |
| Missing Basic Industry codes | 0 |

The authoritative hierarchy is `Basic Industry → Industry → Sector →
Macro-Economic Sector`. The code is preferred when a future quote receipt
actually supplies it. Without it, HSI permits only exact whitespace-normalized,
case-normalized label matching when the label is globally unique in the
retained official hierarchy. No alias, partial string, nearest string,
company-description, business-model, or LLM classification is allowed.

## Existing-current-taxonomy reconciliation

For the existing `nse-indices-taxonomy-v1` 711-security coverage, a future
byte-retained quote receipt may be compared without overwrite. Matching retained
macro/sector plus an exact quote-derived Industry/Basic Industry is
`RICHER_HIERARCHY_COMPATIBLE`; a matching four-tier record is
`EXACT_COMPATIBLE`; a parent-tier mismatch is `CONFLICTED`; and an ISIN mismatch
is `IDENTITY_MISMATCH`. Rendered-only observations are descriptive
cross-checks, not a replacement or merge path. No 711 record changed here.

| Existing 711 sample | Retained macro / sector | Quote-derived Basic Industry | Reconciliation |
| --- | --- | --- | --- |
| APARINDS | Industrials / Capital Goods | Other Electrical Equipment | `RICHER_HIERARCHY_COMPATIBLE` |
| GLAND | Healthcare / Healthcare | Pharmaceuticals | `RICHER_HIERARCHY_COMPATIBLE` |
| ICICIBANK | Financial Services / Financial Services | Private Sector Bank | `RICHER_HIERARCHY_COMPATIBLE` |
| INFY | Information Technology / Information Technology | Computers - Software & Consulting | `RICHER_HIERARCHY_COMPATIBLE` |
| HDFCBANK | Financial Services / Financial Services | Private Sector Bank | `RICHER_HIERARCHY_COMPATIBLE` |

The sample count is seven exact rendered identities, one identity mismatch
(TDPOWERSYS), zero promotable `SAMPLE_TAXONOMY_PROVEN` receipts, and one
machine-resource access block. It says nothing about the remaining 1,803
source-universe-limited securities.

## Temporal and acquisition boundary

Any quote taxonomy is only `CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY`.
`STRICT_HISTORICAL_PIT_TAXONOMY = NOT_READY` remains unchanged: no observed
quote field carries an effective date or historical revision history.

The approved prospective safety contract remains unchanged: one serial worker,
at least two seconds between requests, byte-retain/cache successful first-party
responses, checkpoint every attempt, stop on access/rate limit, and preserve
schema drift, identity mismatch, incomplete response, and replay/idempotency
outcomes. It was not executed at market scale.

## Exact next continuation

Because the result is `QUOTE_TAXONOMY_SOURCE_PARTIAL`, the bounded follow-up was
`NSE_QUOTE_TAXONOMY_PUBLISHED_MACHINE_CONTRACT_PROOF_V1`.

That proof completed with authoritative Result `D:
NO_PUBLISHED_NORMAL_ACCESS_MACHINE_TAXONOMY_CONTRACT_FOUND`; taxonomy archaeology is now
`CLOSED` and the existing coverage limitation remains authoritative.

No full backfill, persistence, provider merge, sector-index repair, rule
changes, or any portfolio/policy/strategy action is part of this result.

No full backfill, persistence, provider merge, technical-rule change, sector
index repair, portfolio action, signal, UI, or execution capability is part of
this result.
