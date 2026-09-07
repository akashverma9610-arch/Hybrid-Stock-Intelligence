# NSE All-Listed Security Taxonomy Source Feasibility and Acquisition Policy V1

**Status:** `COMPLETE / FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL / CURRENT_DESCRIPTIVE_ONLY / ACQUISITION_NOT_ACTIVE`

## Purpose and boundary

This bounded slice determines whether a first-party source can safely extend
current-descriptive canonical taxonomy beyond the retained Nifty Total Market
universe. It does **not** bulk-acquire, persist, supersede, or promote any
taxonomy record. It does not change a rule, peer policy, technical input,
sector-index mapping, historical taxonomy, provider integration, portfolio, or
execution boundary.

The existing `NseIndicesTaxonomyImporter` and append-only
`InstrumentTaxonomyClassification` store remain the only promotion path. The
new pure contract at
`app/taxonomy/nse_all_listed_security_taxonomy_source.py` assesses injected
source findings and defines a future acquisition safety policy; it has no
network, filesystem, database, clock, or write dependency.

```text
CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY = ACTIVE_FOR_EXISTING_711_ONLY
NEW_ALL_LISTED_CURRENT_DESCRIPTIVE_PATH = NOT_ACTIVE
STRICT_HISTORICAL_PIT_TAXONOMY = NOT_READY
```

## First-party sources examined

| Candidate | Authority / shape | Exact identity capability | Classification capability | Universe semantics | Observed access / version semantics | Result |
| --- | --- | --- | --- | --- | --- | --- |
| [NSE equity quote page](https://www.nseindia.com/get-quote/equity/APARINDS/Apar-Industries-Limited) | `FIRST_PARTY_NSE` / per-security | Page presentation exposes symbol and ISIN; listing/trading state and series are also displayed for an active equity | Page presentation exposes **Basic Industry**. An exact Basic Industry could be resolved through the official four-level NSE Indices hierarchy. Macro sector, sector, and industry were not independently received in a retained API receipt. | one requested security; no all-listed proof | Direct public page/API probe from this host: `HTTP 403`; no response schema or source timestamp could be retained. No source-level version was found. | viable candidate, access/schema proof incomplete |
| [NSE all equities CSV](https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv) | `FIRST_PARTY_NSE` / bulk | Header is exactly `SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE` | none | broad current security inventory, not a taxonomy corpus | `HTTP 200` header probe; current file has no publication/version field in its header | identity/security-status support only |
| [NSE Indices Nifty Total Market constituent CSV](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market) and retained structure | `FIRST_PARTY_NSE_INDICES` / bulk | company, symbol, series, ISIN | retained constituent `Industry` column is proven sector-level only | bounded 752-row index universe | already retained and versioned by content SHA; current descriptive / first observed | existing 711 canonical records only |
| [NSE Indices industry classification](https://www.nseindia.com/static/products-services/industry-classification) | `FIRST_PARTY_NSE_INDICES` / structure page | none | 12 macro sectors, 22 sectors, 59 industries, 197 basic industries | vocabulary/definitions, not company assignments | page says classifications are reviewed annually; page was published with an update date, but no per-security assignment version is supplied | hierarchy only |

NSE states that its four-tier classification is based on company business and
that classifications are reviewed annually. It is authoritative hierarchy
evidence, but not an effective-dated historical security-assignment feed.

## Bounded quote-source probe

The representative probe used one session and stopped after a uniform host
access failure. No response body was interpreted as an absence of taxonomy.

| Canonical symbol | Canonical ISIN | Existing coverage role | Public quote probe | Taxonomy conclusion |
| --- | --- | --- | --- | --- |
| `APARINDS` | `INE372A01015` | existing 711 | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `GLAND` | `INE068V01023` | existing 711 | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `ICICIBANK` | `INE090A01021` | existing 711 | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `DEEPINDS` | `INE0FHS01024` | `SOURCE_UNIVERSE_LIMITATION` | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `GENUSPOWER` | `INE955D01029` | `SOURCE_UNIVERSE_LIMITATION` | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `TDPOWERSYS` | `INE419M01027` | retained-source ISIN conflict | `HTTP 403` | `SOURCE_ACCESS_BLOCKED`; no symbol repair |
| `INFY` | canonical sample across Information Technology | existing 711 representative | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |
| `HDFCBANK` | canonical sample across Financial Services | existing 711 representative | `HTTP 403` | `SOURCE_ACCESS_BLOCKED` |

The public quote-page presentation independently shows the following labels
for representative securities: `APARINDS` is `INE372A01015`, `Listed`,
`Active`, and Basic Industry `Other Electrical Equipment`; `GLAND` is
`INE068V01023`, `Listed`, `Active`, and Basic Industry `Pharmaceuticals`.
These are discovery observations only. They are not retained source receipts,
are not a verified JSON/API schema, and do not promote a classification.

### Exact response/schema result

No successful first-party quote response was received on this host. Therefore
the following are explicitly **unverified** for a future machine acquisition:

- quote API field names and nested object layout;
- response source timestamp or last-update field;
- source-level classification version/date;
- direct macro-sector, sector, industry, and basic-industry fields in the
  machine response;
- response reliability under a throttled serial client.

The only verified quote-page presentation fields are issuer display name,
symbol, ISIN, series, listing status, trading status, listing date, and Basic
Industry. `EQUITY_L.csv` verifies only its eight-header identity/security
schema above. A failed request remains `ACCESS_BLOCKED`, not
`SUCCESS_INCOMPLETE` and never “no taxonomy.”

## Identity and four-level rule

Any later promotion must require all of the following:

```text
source ISIN == canonical HSI ISIN
AND source symbol == canonical current NSE symbol
AND source Basic Industry exactly resolves in the retained official hierarchy
```

The source Basic Industry, if present and exactly unique, is the only label
that may yield macro sector, sector, industry, and basic industry through the
official hierarchy. It must not be replaced with a name match, a sector/index
proxy, an LLM inference, or an existing taxonomy value.

`TDPOWERSYS` remains blocked: retained source `INE419M01035` is not canonical
`INE419M01027`. A symbol match cannot repair that disagreement.

## Existing-711 reconciliation

No quote receipt was available, so none of the existing 711 records was
reconciled or changed in this slice. The bounded result for every direct probe
is `SOURCE_ACCESS_BLOCKED`, rather than `EXACT_SAME`, `RICHER_HIERARCHY`, or
`CONFLICT`. The previous exact regression result remains authoritative:
all 711 retained current records are `EXACT_SAME` against their selected NSE
Indices source rows.

## Future acquisition policy — not active

The pure contract fixes the safety requirements for a later separately
approved `NSE_PER_SECURITY_CURRENT_TAXONOMY_CANONICAL_BACKFILL_V1`:

| Control | Fixed requirement |
| --- | --- |
| Input scope | immutable eligible-universe snapshot, with its identity and fingerprint recorded before requests |
| Concurrency | exactly one active request |
| Pacing | at least two seconds between requests; no parallel workers |
| Receipt | retain byte-preserved first-party response and its SHA-256 before normalization |
| Cache / replay | cache successful exact responses; identical replay is idempotent; conflicting same-identity content is an immutable conflict |
| Checkpoint | one durable document receipt per attempted security before the next request |
| Success | exact current ISIN + compatible symbol + exact unique Basic Industry hierarchy resolution |
| Empty/incomplete | `SUCCESS_INCOMPLETE`; no absent taxonomy inference |
| Access / rate limit | `ACCESS_BLOCKED` or `RATE_LIMITED`; stop immediately and preserve the checkpoint |
| Identity / schema | `IDENTITY_MISMATCH` or `SCHEMA_DRIFT`; fail closed and do not promote |
| Time semantics | retain `observed_at`; use `CURRENT_SOURCE_VERSION_UNAVAILABLE` when no genuine source version/date exists |

This is current-descriptive only. It cannot provide historical taxonomy or
alter `STRICT_HISTORICAL_PIT_TAXONOMY = NOT_READY`.

## Result and next continuation

**Exact result:** `FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL`.

The official quote surface appears capable of supplying a per-security Basic
Industry and identity context, while `EQUITY_L.csv` provides a broader identity
inventory. However, no successful host-accessible quote receipt or stable
machine schema was proven, and no all-listed classification bulk artifact was
found. The sample proves neither per-security acquisition reliability nor
whole-universe coverage.

**One exact next slice:**
`NSE_FIRST_PARTY_QUOTE_TAXONOMY_ACCESS_AND_SCHEMA_PROOF_V1`.

It must perform a fresh low-rate, representative, first-party quote receipt
probe from an approved access context; retain byte-preserved receipts; prove
machine fields, exact identity, four-level hierarchy resolution, source time
semantics, and access behavior before authorising a backfill. It must not
reclassify a 403, missing field, stale ISIN, or ambiguous hierarchy label.

## Validation

`tests/unit/test_nse_all_listed_security_taxonomy_source.py` exercises exact
Basic Industry hierarchy resolution, all-listed bulk schema requirements,
access/rate/schema failure classification, exact-ISIN identity failure,
incomplete and unresolved labels, PIT exclusion, stable serialization,
tamper rejection, and the serial/checkpointed acquisition contract. It also
proves the policy module does not import network, persistence, API, broker,
portfolio, order, or signal dependencies.

No database write, schema change, or full-market request occurs in this slice.
