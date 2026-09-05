# NSE Taxonomy Company-Type Code-Map Proposal V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## Decision boundary

This document defines the smallest deterministic proposal for using existing
canonical NSE Indices business-classification evidence as a **candidate**
input to a later issuer company-type policy. It does not select a company type,
write a receipt, change the active regulator or issuer-continuity policies, or
make any Compounder/backtest, portfolio, Discovery, API, UI, broker, order, or
execution decision.

In particular, this proposal does **not** mean:

```text
not found in RBI / IRDAI
    -> NON_FINANCIAL
```

The only proposed positive path is:

```text
official NSE Indices classification
    -> exact canonical taxonomy identity
    -> this still-unapproved code map
    -> NON_FINANCIAL_CANDIDATE research evidence
```

`NON_FINANCIAL_CANDIDATE` is not the authoritative `NON_FINANCIAL` company
type. Regulator evidence establishes regulated legal status; NSE taxonomy
describes revenue-business classification. They are separate facts with no
unstated precedence rule.

The executable-but-non-active representation is
[`app/intelligence/nse_taxonomy_company_type_map_proposal.py`](../../app/intelligence/nse_taxonomy_company_type_map_proposal.py).
It has the fixed status tuple above, produces only taxonomy-audit observations,
and is intentionally not imported by the existing
[`pit_company_type_classification.py`](../../app/intelligence/pit_company_type_classification.py)
contract or any runtime path.

## Existing canonical taxonomy contract

The current source is the official NSE Indices industry-classification
hierarchy and constituent exports, ingested through the existing local-only
[`NseIndicesTaxonomyImporter`](../../app/taxonomy/nse_indices.py). Each
`InstrumentTaxonomyClassification` retains exact canonical instrument ID,
macro/sector/industry/basic-industry codes where the source supplied them,
source hash, observation time, classification version, and effective/PIT
semantics. The current local source artifacts are:

| Field | Exact current value |
| --- | --- |
| Authority | `NSE_INDICES_OFFICIAL` / `www.niftyindices.com` |
| Classification page | `https://www.niftyindices.com/resources/industry-classification` |
| Import version | `nse-indices-taxonomy-v1` |
| Observation semantics | `FIRST_OBSERVED_OFFICIAL_SNAPSHOT` |
| First observed / effective / as-of | `2026-08-27T15:33:21.747410+00:00` |
| Total current records | 711 |
| NIFTY 500 constituent SHA-256 | `637b99dc20a36a994b8dd43ae8449781258a9c94fab20ca3b87741fb39bd67db` |
| NIFTY Total Market constituent SHA-256 | `69ee01618f0a6a9ca57f63522329d03f4c179cf8cf0da29b5b80804f008dc1ac` |
| Classification page SHA-256 | `06db6aeeeb7443f682616110caafe587508e39606838db35b5edbac01a583470` |
| Classification structure SHA-256 | `8ae58cbd10d7dd5184d76cfec6486f91c019026c8de329432b69c54ff7235f8b` |

The present constituent `Industry` column was proven by exact hierarchy
comparison to be a **sector-level** label. Accordingly, all 711 current
records contain exact macro-economic-sector and sector codes; none contains an
industry or basic-industry code. The map must therefore operate on the exact
pair `(macro_economic_sector_code, sector_code)`. Names are retained only as
source display metadata and never participate in matching.

If a later official snapshot supplies a reliable industry or basic-industry
code, this sector-only proposal returns
`LOWEST_RELIABLE_LEVEL_MAP_REQUIRED`, rather than falling back to a broader
sector map. A later, explicitly approved most-specific code map would then be
required.

## Proposed immutable map artifact

Policy identity: `nse-taxonomy-company-type-code-map-proposal / v1`.
Contract identity: `nse-taxonomy-company-type-code-map-proposal-contract / v1`.
The current deterministic proposal fingerprint is:

```text
sha256:2d2e0745d310fb52ae9de4e853e30083d8da81f201a8d91e35457892ee364e16
```

Every entry contains the exact source/version, `SECTOR` taxonomy level, exact
macro/sector code pair, candidate category, rationale, deterministic entry ID,
and deterministic fingerprint. It is immutable and deterministically ordered
by `(macro_code, sector_code, entry_id)`. It is neither a persistence artifact
nor an active map selection.

| Macro code | Sector code | Exact official hierarchy display | Proposed research category | Rationale |
| --- | --- | --- | --- | --- |
| `IN01` | `IN0101` | Commodities / Chemicals | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN01` | `IN0102` | Commodities / Construction Materials | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN01` | `IN0103` | Commodities / Metals & Mining | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN01` | `IN0104` | Commodities / Forest Materials | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN02` | `IN0201` | Consumer Discretionary / Automobile and Auto Components | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN02` | `IN0202` | Consumer Discretionary / Consumer Durables | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN02` | `IN0203` | Consumer Discretionary / Textiles | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN02` | `IN0205` | Consumer Discretionary / Realty | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN02` | `IN0206` | Consumer Discretionary / Consumer Services | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN04` | `IN0401` | Fast Moving Consumer Goods / Fast Moving Consumer Goods | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN05` | `IN0501` | Financial Services / Financial Services | `UNSUPPORTED_FINANCIAL` | Present level cannot distinguish banks, NBFCs, insurers, brokers, exchanges, depositories, asset/wealth managers, financial holding/investment companies, rating agencies, or other intermediaries. |
| `IN06` | `IN0601` | Healthcare / Healthcare | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN07` | `IN0701` | Industrials / Construction | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN07` | `IN0702` | Industrials / Capital Goods | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN08` | `IN0801` | Information Technology / Information Technology | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN09` | `IN0901` | Services / Services | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN11` | `IN1101` | Utilities / Power | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN11` | `IN1102` | Utilities / Utilities | `NON_FINANCIAL_CANDIDATE` | Exact official sector identity. |
| `IN12` | `IN1201` | Diversified / Diversified | `UNKNOWN_NON_COMPARABLE` | Current sector-level evidence is not sufficiently specific. |

There are no current `REGULATED_FINANCIAL_CANDIDATE` entries: the source's
only financial-sector identity is the broad `IN05 / IN0501` pair. It is not a
bank/NBFC/insurer discriminator and must not be treated as one. The category
exists only for a future separately approved, exact, more-specific official
taxonomy identity.

Runtime matching is equality-only on the two exact codes after verifying:

1. exact canonical `NSE:<ISIN>` instrument identity;
2. `OFFICIAL` source type, `NSE_INDICES_OFFICIAL` source and
   `nse-indices-taxonomy-v1` version;
3. `EXACT_UNIQUE` official hierarchy resolution;
4. `FIRST_OBSERVED_OFFICIAL_SNAPSHOT` semantics;
5. non-empty 64-hex official source SHA-256;
6. PIT eligibility at the supplied `as_of`; and
7. absence of a more specific industry/basic-industry code.

It uses no taxonomy display-name matching, `contains`, prefix, regular-
expression, or negative-regulator heuristic. Unknown pairs and unsupported
source/version states return a descriptive `UNMAPPED` research result. A
malformed canonical identity or source hash is rejected rather than repaired.

## Proposed positive non-financial rule — not active

A later policy may consider a positive `NON_FINANCIAL` research receipt only
when all of the following independently hold:

1. exact issuer/security identity is known;
2. exact PIT-valid canonical NSE taxonomy assignment is available;
3. that assignment has an exact map entry whose category is
   `NON_FINANCIAL_CANDIDATE`;
4. an approved map has replaced this proposal; and
5. the future final classifier has retained and fail-closed any conflicting
   exact regulator/company-type evidence.

This proposal satisfies none of the activation conditions by itself. The
absence of exact RBI/IRDAI linkage is neither a conflict clearance nor
evidence of non-financial status. Conversely, taxonomy evidence does not make
bank-like business evidence an authoritative `BANK` result without the
separately required exact RBI/legal-entity path.

## 2026-08-31 read-only mapping audit

The audit used only the existing 2026-08-31 PIT-eligible current taxonomy and
active exact ISIN issuer observations. It emitted no company type, no receipt,
and no database write.

| Measure | Count / result |
| --- | ---: |
| Active issuer observations | 335 (334 unique ISINs) |
| Active issuer observations with exact taxonomy | 202 (201 unique taxonomy records) |
| Active issuer observations with no exact taxonomy | 133 |
| Current canonical taxonomy records | 711 |
| Exact taxonomy identities encountered | 19 |
| Exact identities represented in proposal | 19 |
| All-taxonomy `NON_FINANCIAL_CANDIDATE` records | 587 |
| All-taxonomy `UNSUPPORTED_FINANCIAL` records | 121 |
| All-taxonomy `UNKNOWN_NON_COMPARABLE` records | 3 |
| All-taxonomy unmapped records | 0 |
| Linked-observation `NON_FINANCIAL_CANDIDATE` | 168 observations / 167 distinct taxonomy records |
| Linked-observation `UNSUPPORTED_FINANCIAL` | 33 |
| Linked-observation `UNKNOWN_NON_COMPARABLE` | 1 |
| Linked-observation unmapped | 0 |
| Proven regulator/taxonomy conflicts | 0 — no exact PIT-valid regulator-to-issuer link exists to compare |

`0` proven conflicts is not a clean regulatory result. It records lack of an
admissible exact regulator/issuer bridge, so a final classifier remains
unavailable.

### Five-target audit — descriptive only

| Symbol | Active exact issuer bridge | PIT taxonomy at 2026-08-31 | Exact hierarchy | Proposed taxonomy-map result | Exact regulator evidence status | Can a future non-financial path be supported? |
| --- | --- | --- | --- | --- | --- | --- |
| APARINDS | Present | Present | `IN07 / IN0702` — Industrials / Capital Goods | `NON_FINANCIAL_CANDIDATE` | No exact RBI/IRDAI issuer link | Candidate taxonomy evidence only after map approval; no final company type. |
| DEEPINDS | Present | Absent | — | `TAXONOMY_LINKAGE_UNAVAILABLE` | No exact RBI/IRDAI issuer link | No; exact taxonomy assignment is missing. |
| GENUSPOWER | Present | Absent | — | `TAXONOMY_LINKAGE_UNAVAILABLE` | No exact RBI/IRDAI issuer link | No; exact taxonomy assignment is missing. |
| GLAND | Present | Present | `IN06 / IN0601` — Healthcare / Healthcare | `NON_FINANCIAL_CANDIDATE` | No exact RBI/IRDAI issuer link | Candidate taxonomy evidence only after map approval; no final company type. |
| ICICIBANK | Present | Present | `IN05 / IN0501` — Financial Services / Financial Services | `UNSUPPORTED_FINANCIAL` | RBI legal-name correspondence has no exact CIN link | No. The generic exact code map is deliberately non-financial-safe and does not hardcode a bank result. |

The target rows are reached through generic ISIN-to-canonical-instrument and
exact-code logic; no symbol is present in the implementation map.

## PIT and historical taxonomy gap

At `2024-02-05T23:59:59Z`, the existing taxonomy record count eligible at the
cutoff is **0**, so proposed mapped records are **0**. The 2026 source is never
used backward.

The repository contains only the first-observed 2026 official source artifacts
listed above. Test fixtures and the 2023-07 hierarchy PDF are not historical
constituent-assignment snapshots and cannot establish a historical security
classification. The importer is local-file-only; it cannot retrieve older
classifications itself. Therefore a historical Compounder backtest would need
a separate, source-bounded:

```text
HISTORICAL_NSE_TAXONOMY_ASSIGNMENT_ACQUISITION_V1
```

The exact blocker is the absence of a retained date-labelled official
constituent/classification assignment snapshot whose known/available time is
eligible at the historical evaluation cutoff. No broad acquisition is started
by this proposal.

## Safety and approval boundary

- Financial-services taxonomy evidence never becomes `NON_FINANCIAL` merely
  because regulator evidence is unavailable.
- Regulated categories and taxonomy categories are not assumed mutually
  exclusive; the future final classifier must consume all exact evidence and
  retain conflicts.
- No authoritative `BANK`, `NBFC`, `INSURER`, or `NON_FINANCIAL` output, map
  selection, company-type receipt, or policy activation exists.
- No Compounder candidate grid, metric grid, rank, backtest, portfolio action,
  Discovery action, broker/order call, or execution authority is introduced.
- The existing RAW_EXACT regulator linkage, historical regulator acquisition,
  and ISIN issuer-continuity policies are not modified.

Focused tests prove exact code matching, fixed proposed status and fingerprint,
positive non-financial candidate handling, broad-financial fail-closed
handling, unknown/unmapped handling, most-specific-level protection,
PIT exclusion, source/version and malformed-identity handling, stable
serialization, and absence of issuer/company-type/execution dependencies.

**`HUMAN_APPROVAL_REQUIRED`**

Only after explicit approval of this exact code map may the next bounded slice
be considered:

```text
NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_ACTIVATION_V1
```

Before any final company-type activation, the separate final classifier must
still verify exact issuer identity, exact regulator evidence where relevant,
exact taxonomy evidence, approved map lineage, PIT validity, and fail-closed
conflict handling.
