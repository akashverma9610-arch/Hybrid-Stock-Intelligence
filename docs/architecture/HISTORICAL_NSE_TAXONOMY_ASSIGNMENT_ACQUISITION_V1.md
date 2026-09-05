# Historical NSE Taxonomy Assignment Acquisition V1

**Status:** `COMPLETE / COVERAGE_UNAVAILABLE / DISCOVERY_ONLY / NOT_ACTIVE / NON_EXECUTABLE`

## Decision

The bounded official-source audit did not recover an NSE or NSE Indices artifact that proves a historical company/security-to-taxonomy assignment. Therefore:

```text
HISTORICAL_TAXONOMY_ASSIGNMENT_COVERAGE = UNAVAILABLE
```

No historical taxonomy assignment, taxonomy-category receipt, code-map result, or company type was created. The current 2026 classification corpus remains separate and has not been projected backward.

This is a source-discovery result, not a claim that such an artifact can never exist. It records that no qualifying artifact was recovered from the bounded official surfaces below.

## Admissibility rule

For a historical cutoff `T`, an accepted artifact must prove all of the following:

```text
official NSE/NSE Indices artifact
-> explicit historical publication, observation, or effective date
-> exact security or issuer identity
-> assigned taxonomy codes (at every level the artifact supplies)
-> explicit taxonomy structure/version
-> immutable source and receipt fingerprints
```

Historical structure documents satisfy only the structure part of that chain. They describe codes, hierarchy, definitions, and the four classification levels; they do not pair a security/ISIN with an assigned code. Structure is not a company-assignment artifact.

## Bounded first-party discovery

| Artifact family | Official source inspected | What it proves | Why it is not a historical company assignment |
| --- | --- | --- | --- |
| Current classification resource | [NSE Indices Industry Classification](https://www.niftyindices.com/resources/industry-classification) | NSE Indices maintains a four-level company-classification structure. | It exposes current structure resources, not a dated historical security-assignment dataset. |
| Current NIFTY 500 / Total Market exports | Retained `nifty500.csv` and `nifty_total_market.csv` source artifacts | Exact current `ISIN`/symbol and a constituent `Industry` label. | Both were first observed locally at `2026-08-27T15:33:21.747410+00:00`; neither has a historical snapshot date. |
| Historical reports | [NSE Indices Historical Data Reports](https://niftyindices.com/reports) | Index OHLC, P/E, P/B, dividend-yield, and total-return report formats. | Published schemas are index-level series, not company/security taxonomy assignments. |
| Historical structures | [March 2022 structure](https://www.niftyindices.com/docs/default-source/default-document-library/nse-indices_industry-classification-structure-2022-03.pdf?sfvrsn=a97a9534_2) and [November 2022 structure](https://www.niftyindices.com/docs/default-source/default-document-library/nse-indices_industry-classification-structure-2022-11.pdf?sfvrsn=6df89434_2) | Historical code hierarchy, categories, and definitions. | Neither supplies an exact company/security identifier or a company-to-code assignment. |
| Current index pages/downloads | Official NSE Indices constituent-download surfaces | Current constituent and sector-distribution views. | “Data as on” is a current-page observation, not an archived dated assignment file. |

The discovery was deliberately limited to these first-party NSE/NSE Indices families. It did not crawl arbitrary URLs, use cached search copies, subscribe to a data vendor, or use a third-party dataset.

## Existing HSI taxonomy provenance

[`app/taxonomy/nse_indices.py`](../../app/taxonomy/nse_indices.py) is a local-file-only importer. It preserves source artifacts in `NSE_INDICES_TAXONOMY_SOURCE` and creates append-only `TAXONOMY_CLASSIFICATION` snapshots. Its retained corpus is current-only:

| Source artifact | SHA-256 | Local observation semantics |
| --- | --- | --- |
| `NIFTY_500_CONSTITUENTS` | `637b99dc20a36a994b8dd43ae8449781258a9c94fab20ca3b87741fb39bd67db` | `FIRST_OBSERVED_OFFICIAL_SNAPSHOT` at `2026-08-27T15:33:21.747410+00:00` |
| `NIFTY_TOTAL_MARKET_CONSTITUENTS` | `69ee01618f0a6a9ca57f63522329d03f4c179cf8cf0da29b5b80804f008dc1ac` | `FIRST_OBSERVED_OFFICIAL_SNAPSHOT` at `2026-08-27T15:33:21.747410+00:00` |
| `NSE_INDICES_CLASSIFICATION_PAGE` | `06db6aeeeb7443f682616110caafe587508e39606838db35b5edbac01a583470` | Current page capture at the same observation time |
| `NSE_INDICES_CLASSIFICATION_STRUCTURE` | `8ae58cbd10d7dd5184d76cfec6486f91c019026c8de329432b69c54ff7235f8b` | Current retained July-2023 structure at the same observation time |

The constituent schema is `Company Name, Industry, Symbol, Series, ISIN Code`. In the retained corpus, `Industry` was proven only as an exact **sector-level** hierarchy label. The importer retains macro-economic sector and sector codes only where exact resolution is possible, marks each classification `CURRENT_TAXONOMY_ONLY`, and does not invent lower levels.

There are 711 current official classifications under `nse-indices-taxonomy-v1`; no historical-assignment source family or historic company-classification artifact exists in the repository.

## Five-target audit

Each target has a date-labelled exact NSE MII/session identity row on 2024-02-05. That proves security identity only; it has no NSE Indices taxonomy field and cannot fill one.

| Symbol | Exact 2024-02-05 NSE identity | Official historical taxonomy assignment artifact | PIT assignment at `2024-02-05T23:59:59Z` | Result |
| --- | --- | --- | --- | --- |
| APARINDS | `NSE:INE372A01015` / `APARINDS` | Not recovered | 0 | `HISTORICAL_COMPANY_ASSIGNMENT_UNAVAILABLE` |
| DEEPINDS | `NSE:INE0FHS01024` / `DEEPINDS` | Not recovered | 0 | `HISTORICAL_COMPANY_ASSIGNMENT_UNAVAILABLE` |
| GENUSPOWER | `NSE:INE955D01029` / `GENUSPOWER` | Not recovered | 0 | `HISTORICAL_COMPANY_ASSIGNMENT_UNAVAILABLE` |
| GLAND | `NSE:INE068V01023` / `GLAND` | Not recovered | 0 | `HISTORICAL_COMPANY_ASSIGNMENT_UNAVAILABLE` |
| ICICIBANK | `NSE:INE090A01021` / `ICICIBANK` | Not recovered | 0 | `HISTORICAL_COMPANY_ASSIGNMENT_UNAVAILABLE` |

No target's 2026 category is used. This audit emits no `NON_FINANCIAL`, `BANK`, `NBFC`, or `INSURER` result.

## Coverage receipt

| Measure | Result |
| --- | ---: |
| Historical official source families inspected | 5 |
| Historical structure artifacts discovered/referenced | 2 |
| Historical company-assignment artifacts discovered | 0 |
| Historical artifacts / assignment rows ingested | 0 / 0 |
| Distinct historically classified securities | 0 |
| Exact historical assignment identities | 0 |
| Earliest/latest proved historical assignment date | — / — |
| PIT-valid assignments at `2024-02-05T23:59:59Z` | 0 |
| Historical taxonomy-category receipts | 0 |
| Conflicts / unresolved assignment identities | 0 / 0 |

`0` unresolved assignment identities means that no candidate company-assignment row was admitted for reconciliation. It does not mean historical coverage is complete.

## Version compatibility and code stability

March and November 2022 structure versions establish that historical hierarchy must be versioned separately. They do not establish which version was assigned to any company on 2024-02-05. This audit therefore makes no code-stability or semantic-compatibility claim against the active `nse-indices-taxonomy-v1` 19-pair map:

```text
HISTORICAL_TAXONOMY_MAP_VERSION_COMPATIBILITY_REQUIRED
```

There are zero known compatible historical assignments, zero known incompatible assignments, and zero assignments eligible for automatic compatibility. A future exact historical assignment must retain its source structure version. If exact compatibility is not independently proven, `HISTORICAL_NSE_TAXONOMY_CODE_COMPATIBILITY_POLICY_PROPOSAL_V1` is required.

## Safeguards and stop condition

- `current taxonomy -> historical assignment` is prohibited.
- `historical structure + financials -> official company assignment` is prohibited.
- Fuzzy identity, company-name inference, cached search copies, third-party classifications, and fund-portfolio classifications are inadmissible.
- Existing current classifications and taxonomy-category evidence remain untouched.
- No company-type activation, Compounder qualification/backtest, portfolio operation, broker/order access, API/UI change, or execution operation occurred.

This preserves `FACT -> DATA -> INTERPRETATION -> INFERENCE`: a future official assignment would be a fact/data input; neither a structure document nor a current snapshot is that fact for an earlier date.

The slice stops here. The next dependency is an actual first-party historical company-assignment artifact with exact identity, taxonomy assignment, and eligible source-date semantics. Only after that artifact is recovered may historic-map compatibility be considered. Until then, Compounder work needing taxonomy/company type must use a later genuine-PIT start date or remain unavailable; `PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1` and `COMPOUNDER_BACKTEST_PANEL_READINESS_V2` are not authorized by this result.
