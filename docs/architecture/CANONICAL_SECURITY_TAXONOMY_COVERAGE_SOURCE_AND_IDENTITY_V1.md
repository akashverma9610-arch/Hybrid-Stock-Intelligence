# Canonical Security Taxonomy Coverage, Source, and Identity V1

**Status:** `COMPLETE / CURRENT_DESCRIPTIVE / STRICT_HISTORICAL_PIT_NOT_READY / SOURCE_UNIVERSE_LIMITED`

## Scope and fixed boundaries

This is the completed source-and-identity audit for the canonical route:

```text
official NSE Indices constituent row + official hierarchy
    -> exact canonical ISIN and symbol identity
    -> InstrumentTaxonomyClassification
    -> existing sector-index mapping coverage policy
```

It does not create another taxonomy, infer classification from names or
descriptions, use index membership as taxonomy, fetch providers, create a peer
cohort, alter any technical rule, or create any portfolio, broker, order,
signal, API, or UI behavior.

`app/taxonomy/security_taxonomy_coverage.py` is a pure injected-data audit.
It cannot fetch, write, or promote a classification. The append-only
`InstrumentTaxonomyClassification` store and `NseIndicesTaxonomyImporter`
remain the sole canonical promotion/persistence path.

```text
CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY = ACTIVE_FOR_CURRENT_READS
STRICT_HISTORICAL_PIT_TAXONOMY = NOT_READY
```

## Existing 711-source lineage

The production read found **711** selected current classifications. Every one
is `OFFICIAL` `NSE_INDICES_OFFICIAL`, version `nse-indices-taxonomy-v1`, with
`FIRST_OBSERVED_OFFICIAL_SNAPSHOT` semantics, selected from the retained Nifty
Total Market constituent artifact.

| Retained provenance | Exact value |
| --- | --- |
| Local source set | `data/official_sources/nse_indices/2026-08-27/` |
| Nifty 500 SHA-256 | `637b99dc20a36a994b8dd43ae8449781258a9c94fab20ca3b87741fb39bd67db` |
| Nifty Total Market SHA-256 | `69ee01618f0a6a9ca57f63522329d03f4c179cf8cf0da29b5b80804f008dc1ac` |
| Classification-page SHA-256 | `06db6aeeeb7443f682616110caafe587508e39606838db35b5edbac01a583470` |
| Classification-structure SHA-256 | `8ae58cbd10d7dd5184d76cfec6486f91c019026c8de329432b69c54ff7235f8b` |
| Assigned per-security fields | macro-economic sector and sector |
| Unassigned per-security fields | industry and basic industry |
| Identity | exact ISIN and exact NSE symbol |
| Source reference | source name, SHA-256, line, `EXACT_ISIN_AND_SYMBOL` |

The importer proved that the constituent CSV `Industry` column is a
**sector-level** label by exact comparison against the official hierarchy. It
therefore does not manufacture industry or basic-industry fields. The assigned
current hierarchy is 711 macro sectors, 711 sectors, 0 industries, and 0 basic
industries; those are assignment counts, not global taxonomy-node counts.

## First-party source assessment

NSE describes a four-tier taxonomy of 12 macro-economic sectors, 22 sectors,
59 industries, and 197 basic industries, and says listed-company
classifications are reviewed annually. Its methodology/structure is not a
per-security all-listed assignment download. [NSE Industry Classification](https://www.nseindia.com/static/products-services/industry-classification)

| Candidate | Identity fields | Assignment fields | Scope/result | Applicability |
| --- | --- | --- | --- | --- |
| Retained Nifty Total Market CSV | company, symbol, series, ISIN | one sector-level label | 752 current constituent rows; authoritative but bounded | current descriptive |
| Retained Nifty 500 CSV | company, symbol, series, ISIN | one sector-level label | 500 rows; all reconcile to Total Market | current descriptive |
| Retained NSE Indices page/structure | version and hierarchy | four global levels | vocabulary, not per-security assignments | current structure |
| NSE security/all-report surfaces | identifiers where supplied | none | identity/report source, not taxonomy assignment | not promotable |

The Nifty Total Market page describes a broad-market index—not an all-listed
security master—so its membership is not proof of all-market coverage.
[Nifty Total Market](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market)

No verified, retained first-party assignment corpus was found with an exact
ISIN plus Macro Sector, Sector, Industry, and Basic Industry for the whole NSE
eligible universe. This is `SOURCE_UNIVERSE_LIMITATION`, not evidence that an
unclassified security has no real-world sector.

## Exact source reconciliation

The frozen artifacts have 500 Nifty 500 rows and 752 Nifty Total Market rows.
All 500 shared rows reconcile with the same ISIN and sector label (`MATCH`);
the Total Market file contributes 252 additional rows. The selected source is
752 unique `(ISIN, symbol)` rows.

| Reconciliation result | Count | Fail-closed handling |
| --- | ---: | --- |
| Exact canonical ISIN + symbol | 749 | eligible only for exact hierarchy resolution |
| Exact hierarchy resolution | 711 | existing classifications retained |
| Exact identity but hierarchy label absent from retained structure | 38 | `OTHER_EXACT_REASON / NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED` |
| Source rows without exact canonical match | 3 | excluded; never symbol-repaired |
| Duplicate official identity | 0 | would be `IDENTITY_AMBIGUOUS` |
| Equivalent-source taxonomy conflict | 0 | would be `TAXONOMY_EVIDENCE_CONFLICTED` |

The three unmatched source records are `DUMMYINXGN` (`DUM510W01014`),
`DUMMYTRVN` (`DUM256C01024`), and `TDPOWERSYS` (`INE419M01035`). The first two
have no canonical-security identity. Canonical `TDPOWERSYS` is
`INE419M01027`; its source symbol cannot override the contradictory ISIN. It
is therefore `IDENTITY_UNRESOLVED / ISIN_SYMBOL_CONFLICT`.

| Exact source label missing from retained hierarchy | Count |
| --- | ---: |
| `Media Entertainment & Publication` | 8 |
| `Oil Gas & Consumable Fuels` | 17 |
| `Telecommunication` | 13 |

No whitespace repair, nearest-name comparison, description inference, or
index-to-sector inference is permitted. A newer retained first-party structure
and exact per-security assignment evidence are prerequisites to promotion.

## One whole-universe audit

The final read-only 2,553-security audit uses the frozen current universe and
the retained artifacts. Its deterministic fingerprint is
`sha256:d85ec6802f14b5c808699e5b3e437b35376003e82242592a7766d39482cc86a6`.

| State | Eligible | Technical scope |
| --- | ---: | ---: |
| `TAXONOMY_READY` | 711 | 711 |
| `SOURCE_UNIVERSE_LIMITATION` | 1,803 | 1,788 |
| `IDENTITY_UNRESOLVED / ISIN_SYMBOL_CONFLICT` | 1 | 1 |
| `OTHER_EXACT_REASON / NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED` | 38 | 38 |
| identity ambiguity, unsupported series, source conflict | 0 | 0 |
| **Total** | **2,553** | **2,538** |

The 15 eligible but technically out-of-scope securities are all
`SOURCE_UNIVERSE_LIMITATION`. Every formerly missing sector now has an exact
post-audit state: 1,803 source-universe limited, 1 identity-unresolved, and
38 hierarchy-label unresolved. The 1,827 technical-scope cases divide into
1,788, 1, and 38 respectively; there is no unexplained residual.

| Canonical assignment field | Before | After | Defensible promotion |
| --- | ---: | ---: | ---: |
| Macro sector | 711 / 2,553 | 711 / 2,553 | 0 |
| Sector | 711 / 2,553 | 711 / 2,553 | 0 |
| Industry | 0 / 2,553 | 0 / 2,553 | 0 |
| Basic industry | 0 / 2,553 | 0 / 2,553 | 0 |

No additional taxonomy record was safely promotable. This is a successful
fail-closed coverage result, not a reason to classify by proxy.

## Regression, storage, and sector-index reuse

All **711** existing classifications are `EXACT_SAME`: macro-sector, sector,
source family, source SHA-256, source reference, version, and exact resolution
status all match their selected official source rows. There are zero
supersessions, conflicts, missing-new-source cases, or identity changes.

No production taxonomy was persisted or changed; SQLite growth is **0 bytes**.
The repeated pure audit has the same injected-data result/fingerprint. The
existing `CANONICAL_SECURITY_TO_SECTOR_INDEX_MAPPING_COVERAGE_GOVERNANCE_V1`
was reused without a new mapping/index/OHLC record.

| Input/readiness | Before | After |
| --- | ---: | ---: |
| Technical scope | 2,538 | 2,538 |
| Exact governed sector-index mappings | 601 | 601 |
| Canonical sector-index OHLC ready | 207 | 207 |
| Rule 2 sector-health input ready | 207 | 207 |
| Rule 3 sector-rotation input ready | 207 | 207 |
| Rule 6 sector component ready | 207 | 207 |
| Rule 6 full readiness | `NOT_READY` | `NOT_READY` |

Current technical blockers remain 1,827 taxonomy source/identity cases, 394
mapped securities without canonical index OHLC lineage, 84 with no governed
official sector index, and 26 mapping-policy-not-governed cases. Rule 6 full
readiness remains blocked by peer cohort policy (`NOT_APPLICABLE`).

## Five-holding audit

| Symbol | Source/identity | Macro / sector | Industry / basic | Mapping | Index history / Rules 2–3 / Rule 6 sector |
| --- | --- | --- | --- | --- | --- |
| APARINDS | Total Market / exact ISIN + symbol | Industrials / Capital Goods | unavailable / unavailable | exact / Nifty Capital Goods | absent / not ready / not ready |
| DEEPINDS | source record not found | unavailable / unavailable | unavailable / unavailable | taxonomy missing | not applicable / not ready / not ready |
| GENUSPOWER | source record not found | unavailable / unavailable | unavailable / unavailable | taxonomy missing | not applicable / not ready / not ready |
| GLAND | Total Market / exact ISIN + symbol | Health / Healthcare | unavailable / unavailable | exact / Nifty Healthcare Index | absent / not ready / not ready |
| ICICIBANK | Total Market / exact ISIN + symbol | Financial Services / Financial Services | unavailable / unavailable | exact / Nifty Financial Services | 247 sessions / ready / ready; full Rule 6 separate |

This is source/readiness evidence only; it has no investment interpretation.

## Final readiness matrix

| Item | State | Exact reason |
| --- | --- | --- |
| A. Canonical taxonomy source authority | `READY` | retained first-party NSE Indices lineage for 711 |
| B. Taxonomy source-universe completeness | `PARTIAL` | 752 constituent rows; no verified all-listed assignment corpus |
| C. Canonical security taxonomy identity | `PARTIAL` | 749 exact rows; one stale-ISIN contradiction; three unmatched source rows |
| D. Macro-sector coverage | `PARTIAL` | 711 / 2,553 |
| E. Sector coverage | `PARTIAL` | 711 / 2,553 |
| F. Industry coverage | `NOT_READY` | 0 / 2,553 per-security assignments |
| G. Basic-industry coverage | `NOT_READY` | 0 / 2,553 per-security assignments |
| H. Current-descriptive taxonomy | `READY` | 711 first-observed exact assignments |
| I. Strict historical PIT taxonomy | `NOT_READY` | no effective-dated historical assignment source |
| J. Existing-711 regression | `READY` | 711 `EXACT_SAME`, zero regression |
| K. Security-to-sector-index reuse | `READY` | existing exact-only policy; no new mapping |
| L. Rule 2 sector-health input | `PARTIAL` | 207 ready / 2,331 blocked |
| M. Rule 3 sector-rotation input | `PARTIAL` | 207 ready / 2,331 blocked |
| N. Rule 6 sector component | `PARTIAL` | 207 ready; no peer-policy implication |
| O. Rule 6 full readiness | `NOT_READY` | peer cohort `NOT_APPLICABLE` |
| P. Next dominant technical blocker | `PARTIAL` | 1,827 taxonomy source/identity cases, then 394 missing index OHLC lineage |

The frozen boundaries remain unchanged: `CANONICAL_DAILY_TECHNICAL_INPUT =
READY`, `CANONICAL_WEEKLY_TECHNICAL_INPUT = READY`,
`STRICT_HISTORICAL_PIT = NOT_READY`,
`ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`,
`SEPARATE_TECHNICAL_BRAIN = FALSE`, `NO_INDICATOR_EXPANSION = TRUE`,
`PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`,
`EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`,
`HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`,
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`, and
`HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE`.

The next measured continuation requires a retained, first-party,
all-listed-security current assignment artifact with exact ISIN and versioned
per-security hierarchy fields. Historical taxonomy remains a separate
evidence-acquisition problem.
