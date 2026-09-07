# NSE Quote Taxonomy Published Machine Contract Proof V1

**Status:** `COMPLETE / NON_INTRUSIVE / NO_PUBLISHED_NORMAL_ACCESS_MACHINE_CONTRACT`
**Primary result:** `D: NO_PUBLISHED_NORMAL_ACCESS_MACHINE_TAXONOMY_CONTRACT_FOUND`
**Scope:** bounded final archaeology-only proof of a normally accessible per-security taxonomy machine contract.

## Decision

After the bounded official-documentation-only follow-up, there is no published,
normal-access machine contract or downloadable artifact from NSE/NSE Indices that
provides a per-security assignment record containing **ISIN** (or exact identity
equivalent) plus at least **Basic Industry** for materially broader than the
currently retained Nifty Total Market coverage.

The authoritative result for this final slice is:

`D. NO_PUBLISHED_NORMAL_ACCESS_MACHINE_TAXONOMY_CONTRACT_FOUND`

No undocumented endpoint probing, proxy bypass, anti-bot workaround, or private API
reverse-engineering was used.

## Exact accepted result and state transition

| Result | Consequence |
| --- | --- |
| `D: NO_PUBLISHED_NORMAL_ACCESS_MACHINE_TAXONOMY_CONTRACT_FOUND` | `NSE_TAXONOMY_SOURCE_ARCHAEOLOGY = CLOSED` |

Taxonomy remains:

- `STRICT_HISTORICAL_PIT_TAXONOMY = NOT_READY`
- `CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY = PARTIAL`
- `RULE-2/3` sector inputs unchanged (`207` ready each)

The scope and state are unchanged from the previously accepted partial baseline
except that additional evidence confirms no normal-access machine contract exists
for this step.

## Official documentation/materials inspected

The following first-party, official sources were inspected using official links only
and used only for schema/access proof.

| Source family | Exact URL | Access / evidence | Result against this slice |
| --- | --- | --- | --- |
| NSE industry hierarchy portal | `https://www.nseindia.com/static/products-services/industry-classification` | page-level access; official hierarchy publication | proves 4-level vocabulary only |
| NSE industry hierarchy PDF | `https://nsearchives.nseindia.com/content/equities/nse-indices_industry-classification-structure-2023-07.pdf` | downloadable static structure file | proves code/label hierarchy (12/22/59/197), no per-security assignments |
| Nsearchives equities master export | `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | public static CSV | proves identity/security columns only (symbol, ISIN, status, lot, etc.), no industry fields |
| NSE Indices broad market constituent page and retained artifacts | `https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market` and retained CSV captures | retained current constituent sources | proves sector-level assignments for retained universe, no full all-listed security assignment |
| NSE market data documentation pages | `https://www.nseindia.com/market-data/about-our-market-data` and related index/reports catalog pages | vendor/docs-only access | proves report-product semantics; no documented per-security taxonomy assignment feed |
| NSE master/data access guide | `https://www.nseindia.com/resources/exchange_documents/pdf/NSE-Masters_Data-v1.6.pdf` | official format documentation | confirms master metadata schema; no per-security Basic Industry/taxonomy assignment field |

No official downloadable CSV/XML/JSON/ZIP/UDiFF/security-master extension was found in this bounded search that carries the required tuple of exact per-security **identity + Basic Industry** (or higher tiers) for materially broader all-listed coverage.

## Machine contract and bulk artifact result

### Public quote machine contract

Previously confirmed request behavior from this host remains part of the frozen
baseline:

- rendered symbol page path: `200 text/html`
- quote-resource API-like path `https://www.nseindia.com/api/quote-equity?symbol=...` → `403 text/html`

A rendered page confirms visible fields for selected samples only and is **not** a
documented machine contract for taxonomy ingestion. No stable API field map,
source version/date, or schema semantics were established for taxonomy parsing.

### Bulk assignment artifact search result

No official machine-readable bulk per-security taxonomy assignment artifact (CSV/XML/JSON/ZIP/etc.) mapping identity to Basic Industry and the preferred higher tiers was discovered through official first-party catalogues in this bounded search.

## Licensed-first-party source classification

No authoritative normal-access feed was found to satisfy this per-security
assignment requirement. This slice does **not** identify a required licensed
product path from the documents inspected, and does **not** purchase or integrate
any license here.

If a licensed equivalent appears in future through separate approved procurement,
it should be classified as:

`LICENSED_FIRST_PARTY_TAXONOMY_SOURCE`

## Hierarchy preservation (unchanged)

The already-proven hierarchy evidence remains:

- 12 Macro-Economic Sectors
- 22 Sectors
- 59 Industries
- 197 Basic Industries

No additional hierarchy inference or hierarchy expansion was performed in this
slice.

## Continuation rule applied

Since this final proof reached **Result D**, taxonomy source archaeology is
frozen and no further taxonomy-source discovery slice is started.

## Next continuation

`CANONICAL_PRI_SECTOR_INDEX_OHLC_LINEAGE_CLOSURE_V1`

Preferred next measured blocker:

- 601 mapped securities currently have governed sector-index mappings
- 207 of those have canonical index-history readiness
- approximately 394 remain blocked by canonical PRI OHLC lineage.

## Formal final status

| Field | Status |
| --- | --- |
| Machine quote contract with ISIN + hierarchy | `NOT_FOUND` |
| Bulk per-security assignment artifact | `NOT_FOUND` |
| Licensed normal-access mapping path | `NOT_FOUND` (this slice) |
| `NSE_TAXONOMY_SOURCE_ARCHAEOLOGY` | `CLOSED` |
| Taxonomy coverage (eligible universe) | unchanged (`711 / 2,553`) |
| `CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY` | `PARTIAL` |
| `STRICT_HISTORICAL_PIT_TAXONOMY` | `NOT_READY` |

No source-control bypass, no provider merge, no company-description inference, no
symbol-only override, and no PIT timestamp fabrication were introduced.
