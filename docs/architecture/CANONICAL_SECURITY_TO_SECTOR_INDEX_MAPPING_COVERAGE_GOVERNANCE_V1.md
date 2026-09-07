# Canonical Security-to-Sector-Index Mapping Coverage Governance V1

**Status:** `COMPLETE / CURRENT_DESCRIPTIVE / STRICT_HISTORICAL_PIT_NOT_READY`

## Scope and non-goals

This slice audits the existing canonical route:

```text
NSE eligible security → InstrumentTaxonomyClassification → NseSectorIndexMapping → canonical PRI index OHLC
```

It does not create a sector, industry, theme, index, benchmark, technical
Brain, score, peer-cohort policy, indicator, provider fallback, or synthetic
index. It does not change a Rule 2, Rule 3, or Rule 6 definition; it reports
only their source-input coverage. It has no portfolio, strategy, broker,
order, API, or UI behavior.

The mapping is not a historical taxonomy reconstruction. Every result is
explicitly `CURRENT_DESCRIPTIVE`; `STRICT_HISTORICAL_PIT` remains
`NOT_READY`.

## Reused canonical contracts

| Concern | Canonical contract retained | This slice's role |
| --- | --- | --- |
| Security identity and eligible universe | `NseEquityInstrument` and `UniverseSnapshot` | supplies security, symbol, ISIN, and the declared technical scope only |
| Taxonomy | `InstrumentTaxonomyClassification` | supplies only the already-resolved macro sector, sector, industry, and basic industry fields |
| Sector-index identity | immutable `NseSectorIndexMapping` | remains the one mapping receipt; this slice neither substitutes nor overwrites it |
| PRI technical index observations | `CANONICAL_INDEX_OHLC_OBSERVATION` | supplies only supplied per-index session counts; a positive count is not a Rule result |
| Rule assembly | `CanonicalBenchmarkSectorTechnicalInput` | unchanged and intentionally not imported by the coverage contract |
| Existing current-sector/RS work | `CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY` and current sector ranking | remains the existing descriptive ranking definition; it is not a competing mapping or readiness definition |

`app/taxonomy/security_sector_index_mapping_coverage.py` is a pure,
injected-data audit contract. Its compact fixed policy is
`canonical-sector-index-mapping-policy / v1`; it requires
`PRICE_RETURN_INDEX`, exact `EXACT_OFFICIAL` mappings, current-descriptive
applicability, and `STRICT_HISTORICAL_PIT = NOT_READY`. Broad proxies, fuzzy
matching, and synthetic indexes are all fixed `False`.

The per-security outputs are transient audit rows, not mapping receipts. The
one immutable mapping receipt is still `NseSectorIndexMapping`, keyed by the
canonical sector relationship. The audit has no repository, SQLite, HTTP,
clock, persistence, or diagnostic dependency.

## Current-descriptive taxonomy audit

The authoritative universe snapshot contains **2,553** eligible NSE
securities. The mapped technical population used by the preceding Daily/Weekly
technical readiness receipt is **2,538**; the other **15** are reported as
`TECHNICAL_INPUT_OUT_OF_SCOPE` and are deliberately not folded into the
historical **1,973** mapping blocker.

| Taxonomy field | Classified | Missing |
| --- | ---: | ---: |
| macro sector (`super_sector`) | 711 | 1,842 |
| sector | 711 | 1,842 |
| industry | 0 | 2,553 |
| basic industry | 0 | 2,553 |

The classifications are first-observed official snapshots, not effective-dated
historical membership proof. A missing or stale taxonomy identity therefore
blocks the security; this slice never changes a security's taxonomy to make an
index mapping fit.

## Exact 1,973 blocker reconstruction

Before this slice, the 2,538-security technical scope contained 565 existing
exact governed mappings and 1,973 unmapped securities. The final audit
enumerates every security with its canonical ID, symbol, ISIN (or unavailable
ISIN), technical-scope flag, four taxonomy levels, selected mapping identity
and status, canonical index identity, canonical OHLC session count, and one
stable reason code. Its deterministic audit fingerprint is:

`sha256:4e26715b14f01829dc7082ed0cc7ec75eae17f4c2e084a76042fc557eb81e025`

The existing historic blocker separates exactly as follows:

| Previous blocker class | Securities | Exact interpretation |
| --- | ---: | --- |
| `SECURITY_SECTOR_CLASSIFICATION_MISSING` | 1,827 | no current canonical sector classification exists in the technical scope |
| `OFFICIAL_SECTOR_INDEX_UNAVAILABLE` | 120 | no exact governed appropriate index relation exists under the stored mapping policy; this is not permission to use a similarly named product |
| `MAPPING_POLICY_NOT_GOVERNED` | 26 | taxonomy sector exists, but the stored mapping is deliberately unresolved |
| **Total** | **1,973** | no residual or guessed category |

The 15 technically out-of-scope securities are separate from this population.

## Official NSE/NSE Indices catalogue and mapping standard

Only first-party NSE Indices evidence was considered: the archived 2026-08-27
sectoral catalogue and dedicated pages, plus a read-only current catalogue
check. The relevant catalogue is [NSE Indices sectoral indices](https://www.niftyindices.com/indices/equity/sectoral-indices).
`PRICE_RETURN_INDEX` remains the only return family eligible for the technical
path; total-return variants are not interchangeable.

A relation is `EXACT_GOVERNED_MAPPING` only when the existing taxonomy sector
and retained official description establish sufficiently equivalent sector
semantics. A name-looking-similar product is never enough. Industry and basic
industry are not bridged to an index. `GOVERNED_BROAD_PROXY` is not permitted
by this policy.

| Canonical taxonomy sector / candidate | First-party catalogue observation | Governance result |
| --- | --- | --- |
| Information Technology / `Nifty IT` | The dedicated [Nifty IT page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-it) identifies it as the benchmark for the Indian IT segment. | `EXACT_GOVERNED_MAPPING`; newly added immutable mapping receipt. |
| Automobile and Auto Components / `Nifty Auto` | The [Nifty Auto page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-auto) describes the Indian automobiles sector. | Not mapped: retained evidence does not establish that its taxonomy relation includes the whole canonical auto-components scope. |
| Construction Materials / `Nifty Cement` | `Nifty Cement` is a narrower materials product. | `SEMANTICALLY_INCOMPATIBLE`; cement is not an approved bridge for all construction materials. |
| Oil, Gas & Consumable Fuels / `Nifty Oil & Gas` | The [Nifty Oil & Gas page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-oil-and-gas-index) names Oil, Gas and Petroleum. | `SEMANTICALLY_INCOMPATIBLE`; it does not prove equivalence to the broader consumable-fuels taxonomy sector. |
| Services / `Nifty Commercial & Transport Services` | Catalogue product is narrower than canonical `Services`. | `NOT_GOVERNED`; existing unresolved receipt retained. |
| `Telecommunic ation` / `Nifty Telecommunications` | The [Nifty Telecommunications page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-telecommunications) uses a different canonical label. | `TAXONOMY_IDENTITY_INCOMPLETE`; no whitespace/name repair or inferred match is allowed. |
| Diversified, Forest Materials, Textiles, Utilities | No exact equivalent is evidenced by the retained sectoral-index mapping inventory. | `NO_OFFICIAL_INDEX` under the exact-only policy. |

This table distinguishes a catalogued candidate from an approved mapping. It
does not reinterpret an existing `NO_OFFICIAL_SECTOR_INDEX` record as proof
that no related NSE product exists anywhere in the catalogue; it means no
**appropriate exact governed** relation exists.

## Current sector/index inventory and coverage

The importer replayed only the already archived first-party source set. It
added exactly one mapping snapshot:

`Information Technology → Nifty IT` (`mapping_id=1d4075049014bcb8e48acc1b`).

All other existing receipts are unchanged. The following table is the one
whole-universe current-descriptive audit; security counts are within the
2,538-security technical scope.

| Canonical sector | Technical-scope securities | Stored mapping state / official target | Canonical PRI OHLC sessions | Coverage result |
| --- | ---: | --- | ---: | --- |
| Automobile and Auto Components | 48 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |
| Capital Goods | 112 | `EXACT_OFFICIAL` / Nifty Capital Goods | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Chemicals | 45 | `EXACT_OFFICIAL` / Nifty Chemicals | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Construction | 23 | `EXACT_OFFICIAL` / Nifty Construction | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Construction Materials | 16 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |
| Consumer Durables | 41 | `EXACT_OFFICIAL` / Nifty Consumer Durables Index | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Consumer Services | 46 | `EXACT_OFFICIAL` / Nifty Consumer Services | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Diversified | 3 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |
| Fast Moving Consumer Goods | 45 | `EXACT_OFFICIAL` / Nifty FMCG | 247 | mapped with canonical index history |
| Financial Services | 121 | `EXACT_OFFICIAL` / Nifty Financial Services | 247 | mapped with canonical index history |
| Forest Materials | 1 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |
| Healthcare | 70 | `EXACT_OFFICIAL` / Nifty Healthcare Index | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Information Technology | 36 | `EXACT_OFFICIAL` / Nifty IT | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Media, Entertainment & Publication | 0 | `EXACT_OFFICIAL` / Nifty Media | 247 | no currently classified technical-scope security |
| Metals & Mining | 24 | `EXACT_OFFICIAL` / Nifty Metal | 247 | mapped with canonical index history |
| Oil, Gas & Consumable Fuels | 0 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no currently classified technical-scope security |
| Power | 21 | `EXACT_OFFICIAL` / Nifty Power | 0 | `CANONICAL_INDEX_OHLC_LINEAGE_ABSENT` |
| Realty | 17 | `EXACT_OFFICIAL` / Nifty Realty | 247 | mapped with canonical index history |
| Services | 26 | `UNRESOLVED` / — | 0 | `MAPPING_POLICY_NOT_GOVERNED` |
| Telecommunic ation | 0 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no currently classified technical-scope security |
| Textiles | 12 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |
| Utilities | 4 | `NO_OFFICIAL_SECTOR_INDEX` / — | 0 | no exact governed relation |

There are 13 exact official sector relationships in the immutable current
mapping inventory, 19 represented current taxonomy sectors, and 601 mapped
technical-scope securities. The security inherits a relation from its exact
canonical sector; no per-stock mapping policy was created.

## Consumer Durables and Healthcare

The source-name reconciliation remains unchanged:

| Sector | Working official report parameter | Canonical identity / close-lineage state | Mapping effect |
| --- | --- | --- | --- |
| Consumer Durables | `Nifty Consumer Durables` | `IDENTITY_AMBIGUOUS`; `CANONICAL_CLOSE_LINEAGE_ABSENT` | no activation; 41 remain index-history blocked |
| Healthcare | `Nifty Healthcare` | `IDENTITY_AMBIGUOUS`; `CANONICAL_CLOSE_LINEAGE_ABSENT` | no activation; 70 remain index-history blocked |

The successful retrieval of a first-party report does not create canonical
close lineage, and the report's PRI semantics do not allow TRI substitution.

## Coverage and diagnostic-input impact

| Measure | Before | After | Activated effect |
| --- | ---: | ---: | --- |
| exact governed sector mappings in technical scope | 565 | 601 | +36 Information Technology securities |
| technically scoped securities still without exact mapping | 1,973 | 1,937 | −36, no fuzzy expansion |
| mapped securities with canonical sector-index OHLC | 207 | 207 | unchanged |
| mapped securities with absent canonical sector-index OHLC | 358 | 394 | +36 visible as an exact history blocker |
| Rule 2 sector-health input ready | 207 | 207 | unchanged; mapping alone is insufficient |
| Rule 3 sector-rotation input ready | 207 | 207 | unchanged; mapping alone is insufficient |
| Rule 6 sector component ready | 207 | 207 | unchanged |
| Rule 6 full readiness | `NOT_READY` | `NOT_READY` | peer-cohort policy remains `NOT_APPLICABLE`; no claim is made from sector mapping alone |

`ACTUAL_READY_GAIN = 0`. The Nifty IT mapping has no canonical OHLC lineage,
so it produces no hypothetical or activated Rule 2/3 gain. The dominant
remaining blockers are 1,827 current technical-scope securities without a
canonical sector classification, followed by 394 mapped securities without
canonical sector-index OHLC lineage.

## Five-holding audit

| Symbol | Canonical sector | Mapping state / official index | Index-history state | Rule 2 / Rule 3 input | Rule 6 sector component |
| --- | --- | --- | --- | --- | --- |
| APARINDS | Capital Goods | exact / Nifty Capital Goods | absent | not ready | not ready |
| DEEPINDS | — | taxonomy missing | not applicable | not ready | not ready |
| GENUSPOWER | — | taxonomy missing | not applicable | not ready | not ready |
| GLAND | Healthcare | exact / Nifty Healthcare Index | absent | not ready | not ready |
| ICICIBANK | Financial Services | exact / Nifty Financial Services | ready (247) | sector input ready | sector component ready; full Rule 6 remains separate |

This is a data-coverage audit only; it carries no investment conclusion.

## Idempotency, storage, and validation boundary

The first importer application created one new immutable mapping snapshot.
The second replay left the mapping-snapshot count at **23**, the Nifty IT
mapping count at **1**, and the database byte size unchanged at
**18,294,304,768**. No OHLC observation, source artifact, bar, readiness
record, diagnostic result, portfolio object, broker record, or order was
created.

## Final readiness matrix

| Item | State | Exact reason |
| --- | --- | --- |
| A. Canonical security-sector classification | `PARTIAL` | 711/2,553 have macro-sector and sector; industry/basic-industry are absent for all 2,553 |
| B. Canonical sector-index mapping policy | `READY` | one immutable mapping source plus exact-only current-descriptive coverage policy |
| C. Official sector-index catalogue | `PARTIAL` | first-party catalogue audited; only 13 relationships satisfy exact policy |
| D. Consumer Durables index identity | `NOT_READY` | `IDENTITY_AMBIGUOUS`; no canonical close lineage |
| E. Healthcare index identity | `NOT_READY` | `IDENTITY_AMBIGUOUS`; no canonical close lineage |
| F. Canonical index close/OHLC lineage | `PARTIAL` | 207 mapped securities have canonical PRI OHLC; 394 do not |
| G. Security-to-sector-index coverage | `PARTIAL` | 601 mapped / 1,937 still unmapped in the 2,538 technical scope |
| H. Unmapped-security root-cause classification | `READY` | all prior 1,973 classified; no residual unknown bucket |
| I. Rule 2 sector-health input | `PARTIAL` | 207 ready; 2,331 blocked |
| J. Rule 3 sector-rotation input | `PARTIAL` | 207 ready; 2,331 blocked |
| K. Rule 6 sector component | `PARTIAL` | 207 exact sector contexts ready |
| L. Rule 6 full readiness | `NOT_READY` | peer cohort remains ungoverned/not applicable |
| M. Strict historical PIT sector mapping | `NOT_READY` | current mapping/taxonomy are not historical known-at evidence |
| N. Next dominant technical blocker | `PARTIAL` | sector-classification coverage (1,827) dominates; index OHLC lineage (394) is next |

The following frozen boundaries remain unchanged:

- `CANONICAL_DAILY_TECHNICAL_INPUT = READY`
- `CANONICAL_WEEKLY_TECHNICAL_INPUT = READY`
- `STRICT_HISTORICAL_PIT = NOT_READY`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `NO_INDICATOR_EXPANSION = TRUE`
- `PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR`
- `EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY`
- `HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`
- `MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
- `HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE`
