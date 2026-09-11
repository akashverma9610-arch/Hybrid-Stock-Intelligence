# Canonical EBITDA / EBIT source audit and annual-history acquisition V1

Bounded financial-evidence slice from `e62a0224baa827c562c27e290dfe3e309c692238`.
No change to the canonical 61 rules, financial formulas, thresholds, timeframe
policy, company-type policy, internal Radar or execution authority.

## Source semantics and mapping decision

The retained official BSE corpus was scanned by qualified concept name, not by
financial-portal labels or a guessed EBITDA calculation. The opening corpus
contains 330 XML artifacts for the existing 31 financial-source companies.
The relative schema references actually present are:

| Schema reference | Opening artifacts | Namespace |
| --- | ---: | --- |
| `Ind-AS_entry_point_2020-03-31.xsd` | 20 | `http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin` |
| `in-capmkt-ent-2025-01-31.xsd` | 191 | `http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt` |
| `in-capmkt-ent-2026-01-31.xsd` | 119 | `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt` |

These are **observed schema references**, not a claim that their complete
official definition/label linkbases were independently retrieved. Exact-tag
official searches produced no indexed definition; attempts to open the
document-relative BSE schema and one source XML through web research failed.
The approved local BSE transport did retrieve the annual archive/XBRLs.
No third-party replacement taxonomy, blog, portal or inferred formula was used.

Representative official artifacts, also retained with hashes locally:

- [GENUSPOWER FY2022 official XBRL](https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/Main_Ind_As_530343_1252022165637.xml)
  uses the 2020 BSE taxonomy, consolidated, annual and quarter duration contexts.
- [GLAND FY2021 official XBRL](https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/Main_Ind_As_543245_175202119251.xml)
  is an older annual source listed by the official archive.
- [GENUSPOWER official archive](https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd=530343)
  supplies the exact period/scope/source URL and the original filing timestamp.

| Candidate | Classification | Decision |
| --- | --- | --- |
| Direct, company-level EBITDA | No observed qualified direct concept | `EXACT_DIRECT_EBITDA` not established; no mapping |
| Direct, company-level EBIT | No observed qualified direct concept | `EXACT_DIRECT_EBIT` not established; no mapping |
| `OperatingProfitBeforeProvisionAndContingencies` | `OPERATING_PROFIT_BUT_NOT_PROVEN_EBITDA` | Bank pre-provision line; not company EBITDA/EBIT; do not map to universal operating profit |
| `SegmentProfitLossBeforeTaxAndFinanceCosts` | `UNSUPPORTED` | Segment-scoped duration context; not a company-level EBIT observation; do not sum segments |
| `SegmentFinanceCosts` | `UNSUPPORTED` | Segment component, not company finance cost |
| `ProfitBeforeExceptionalItemsAndTax` | `COMPONENT_ONLY` | Before exceptional items/tax does not mean before interest or depreciation |
| `ExceptionalItems`, `ExceptionalItemsBeforeTax` | `COMPONENT_ONLY` | Neither a complete EBIT nor EBITDA line |
| `FinanceCosts`, `DepreciationDepletionAndAmortisationExpense`, `OtherIncome` | `COMPONENT_ONLY` | Existing direct mappings unchanged; no arithmetic combination |
| `AdjustmentsForFinanceCosts`, `AdjustmentsForDepreciationAndAmortisationExpense` | `COMPONENT_ONLY` | Cash-flow reconciliation adjustments are not automatically income-statement metrics |
| Unrecognized plausible label | `AMBIGUOUS` | Spelling alone cannot authorize an exact mapping |

The source audit records namespace, schema, document hash/path, company, scope,
period, context start/end/instant and unit reference. It deliberately excludes
the substring false positive `RegulatoryDeferralAccountDebitBalances...`:
"Debit" is not EBIT. No production `_CONCEPTS` entry or metric enum changed.
Consequently direct-mapping/synonym-extension tests are **not applicable to a
new mapping**; existing parser/importer regressions and explicit non-substitution
tests protect the unchanged path. No retained-XBRL metric replay was performed
to manufacture EBITDA/EBIT. Annual imports have separate replay evidence.

## Minimum annual source selection

[Selector](../../app/fundamentals/bse_annual_history.py),
[bounded operator](../../scripts/acquire_bse_missing_annual_history.py),
[read-only audit](../../scripts/audit_bse_annual_history.py) and
[focused regression](../../tests/unit/test_bse_annual_history.py).

- Scope is the existing 31 companies with canonical FinancialFacts, not a new
  NIFTY500 inventory or resumption of the halted broad acquisition plan.
- Read existing `BSE_OFFICIAL` provider mappings and exact instrument/ISIN/code.
  Conflicting identities do not choose a fuzzy match or a new legacy alias.
- Reuse canonical comparability and the accepted append-only period-identity
  correction projection. No stored original fact is rewritten.
- Rule 16's existing six annual endpoints define the bounded window. Five
  endpoints are insufficient for its five growth intervals. Select missing
  endpoints only; do not acquire a seventh year or retreat to an old window.
- The accepted BSE importer supports Apr--Mar annual contexts. Changed fiscal
  years/non-calendar contexts remain unavailable; quarterly/YTD values are not
  relabelled annual. A company with no annual anchor needs an explicit eligible
  official same-scope annual archive endpoint before a candidate window exists.
- Same-scope only: never fill consolidated gaps with standalone accounts.
  No prelisting accounts are fabricated and absent official years remain gaps.
- Original/revised archive metadata remains intact. Select the latest eligible
  representation for a missing endpoint; equal-time conflicting representations
  fail closed. Identical duplicate archive rows do not create extra work.
- The archive's existing `EXCHANGE_LOCAL_ASSUMPTION` marker and raw timestamp
  lineage remain explicit, not promoted to `DOCUMENTED`. Unknown timestamps
  remain excluded. Acquisition receipt time is never backdated to publication.
- Exact XBRL identity, scope and reporting period are rechecked by existing
  staging and the context-aware importer. Units, scales, original/derived status
  and revision/conflict behavior are unchanged. Only approved direct metrics
  are ingested. Bank-specific ratios are never substituted.
- One worker; atomic exclusive lock; at most 25 documents per invocation;
  0.5-second pacing; existing 5 MiB transport bound; no automatic document retry.
  Two source-unavailability failures save a halt that prevents automatic resume.
  Completed per-document receipts are immutable operational JSON artifacts.
- Existing local sources and this slice's hash-verified archive snapshots are
  reused. No duplicate source copies, discovery/mapping inventory rebuild or
  broad plan mutation is required. No new SQL schema or API/runtime wiring.
- Immediately replay each successful canonical import: require zero new facts
  and zero new conflicts. A replay invariant failure stops further work.

## Validation and measured results

Final measured tables and validation receipt are recorded below after bounded
acquisition and the final read-only audit. A source-history gain alone cannot
declare Rule 16, return ratios, leverage, EBITDA margins or EV/EBITDA ready.

## Final acquisition receipt

Final authoritative audit cutoff: `2026-09-11T18:12:39+00:00`.
Strict historical check: `2025-12-31T23:59:59+00:00`.
Local operational receipts: `reports/bse-annual-history-v1/acquisition/`;
authoritative audit: `reports/bse-annual-history-v1/final.json`.
These private/runtime artifacts are Git-excluded, not release source.

- 31 companies' official archives requested/cached: 4328 raw archive rows, including both scopes and Quarter/Year aliases.
- Acquisition window: missing eligible Apr--Mar endpoints within FY2021--FY2026 only.
- Completed document batches: 5, 25, 25, 25, 21 = **101 documents**. An initial archive-only pass selected zero documents while the new selector's timestamp handling was corrected; its raw snapshots were reused.
- **93 identity-valid XBRLs staged/parsed/imported; 8 identity rejections; 0 source-unavailable, size-limit, malformed-document or import-conflict outcomes.** No provider halt.
- 93 new filings, zero identical-first-import filings. Immediate second imports: **0 new facts, 2,051 identical facts, 0 conflicts**.
- Eight identity rejections: ACUTAAS FY2022/23/24; AFFLE FY2021; DEEPINDS FY2021/22/24/25. No automatic legacy-ISIN reconciliation. Rejection receipts retain the exact archive metadata/source identifier and failure; their rejected raw bodies were not retained by the existing staging rejection path. They are not counted as staged/imported.
- Completed rejected documents are not retried. Other missing years mean **no eligible same-scope annual row in the inspected archive**, not a universal assertion that no historical filing exists anywhere. Changed fiscal calendars and short listing histories are not filled synthetically.
- No old source had to be downloaded twice for import; the 93 successful document imports used 93 new source artifacts. Both scopes in original evidence and immutable archive rows remain retained. New requests targeted only the preferred diagnostic scope.

| Canonical row count | Before | After | Delta |
| --- | ---: | ---: | ---: |
| FinancialFacts | 4,067 | 6,118 | +2,051 |
| CorporateFilings (all types) | 362 | 455 | +93 |
| BSE financial-result filings | 332 | 425 | +93 |
| Financial-source companies | 31 | 31 | 0 |
| EBITDA | 0 | 0 | 0 |
| EBIT | 0 | 0 | 0 |
| ANNUAL / FULL_YEAR | 787 | 1,598 | +811 |
| QUARTERLY / QUARTER_ONLY | 2,214 | 2,861 | +647 |
| QUARTERLY / YEAR_TO_DATE | 586 | 586 | 0 |
| POINT_IN_TIME / UNKNOWN | 480 | 1,073 | +593 |

811 + 647 + 593 = 2,051. Annual source documents contain separately reported
same-end quarter-duration and instant contexts; the existing context-aware
importer retained them, without annual-to-quarter derivation or prior-year
comparative backfill. All new facts remain reported, not derived.

## All-31 company matrix

Scope **C = CONSOLIDATED** throughout; standalone source evidence is neither
deleted nor merged. Annual endpoints below are **source dates**, not certification
that all four Rule-16 metrics exist. Every company has **zero EBITDA years,
zero EBIT years and zero all-four comparable Rule-16 years**.
I = `INSUFFICIENT_DATA`; X = `EVIDENCE_CONFLICTED`.
Filings/revisions are BSE financial-result filings / explicit revision-parent
links (not an inferred revision from a changed number).

| Symbol | Canonical instrument | Scope | Facts before → after | Annual endpoints before → after | Available years | BSE filings / revisions | Rule 16 | Additional blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACC | `NSE:INE012A01025` | C | 136 → 160 | 2 → 3 | 2024, 2025, 2026 | 12 / 0 | I | No eligible older same-scope annual row |
| ACUTAAS | `NSE:INE00FF01025` | C | 136 → 136 | 2 → 2 | 2025, 2026 | 11 / 0 | I | Exact ISIN rejection; no alias |
| AFFLE | `NSE:INE00WC01027` | C | 136 → 208 | 2 → 5 | 2022, 2023, 2024, 2025, 2026 | 14 / 0 | I | Exact ISIN rejection; no alias |
| APARINDS | `NSE:INE372A01015` | C | 324 → 348 | 5 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 20 / 1 | I | Direct EBITDA/EBIT absent |
| APOLLOHOSP | `NSE:INE437A01024` | C | 7 → 151 | 0 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 7 / 0 | I | Direct EBITDA/EBIT absent |
| ASTRAL | `NSE:INE006I01046` | C | 136 → 232 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 15 / 0 | I | Direct EBITDA/EBIT absent |
| BIKAJI | `NSE:INE00E101023` | C | 136 → 184 | 2 → 4 | 2023, 2024, 2025, 2026 | 13 / 0 | I | No eligible older same-scope annual row |
| CRAFTSMAN | `NSE:INE00LO01017` | C | 143 → 263 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 0 | X | Existing vintage conflict |
| CRISIL | `NSE:INE007A01025` | C | 89 → 89 | 0 → 0 | none | 11 / 0 | I | Non-March annual basis unsupported |
| DABUR | `NSE:INE016A01026` | C | 136 → 230 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 15 / 0 | I | Direct EBITDA/EBIT absent |
| DALBHARAT | `NSE:INE00R701025` | C | 136 → 256 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 0 | I | Direct EBITDA/EBIT absent |
| DEEPINDS | `NSE:INE0FHS01024` | C | 198 → 198 | 2 → 2 | 2023, 2026 | 14 / 1 | I | Exact ISIN rejection; no alias |
| GENUSPOWER | `NSE:INE955D01029` | C | 300 → 324 | 5 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 19 / 0 | I | Direct EBITDA/EBIT absent |
| GESHIP | `NSE:INE017A01032` | C | 136 → 232 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 15 / 0 | I | Direct EBITDA/EBIT absent |
| GLAND | `NSE:INE068V01023` | C | 300 → 324 | 5 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 19 / 0 | I | Direct EBITDA/EBIT absent |
| ICICIBANK | `NSE:INE090A01021` | C | 23 → 43 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 0 | I | Bank metric/applicability gaps |
| IDBI | `NSE:INE008A01015` | C | 23 → 48 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 0 | I | Bank metric/applicability gaps |
| INFY | `NSE:INE009A01021` | C | 136 → 232 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 15 / 0 | I | Direct EBITDA/EBIT absent |
| LT | `NSE:INE018A01030` | C | 145 → 259 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 1 | I | PAT missing one annual endpoint |
| LTTS | `NSE:INE010V01017` | C | 113 → 233 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 14 / 0 | I | Direct EBITDA/EBIT absent |
| MGL | `NSE:INE002S01010` | C | 145 → 193 | 1 → 3 | 2024, 2025, 2026 | 13 / 2 | I | No eligible older same-scope annual row |
| ONESOURCE | `NSE:INE013P01021` | C | 150 → 174 | 1 → 2 | 2025, 2026 | 12 / 0 | X | No eligible older same-scope annual row |
| ORIENTTECH | `NSE:INE0PPK01015` | C | 7 → 31 | 0 → 1 | 2026 | 2 / 0 | I | No eligible older same-scope annual row |
| RELIANCE | `NSE:INE002A01018` | C | 88 → 208 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 13 / 0 | I | Direct EBITDA/EBIT absent |
| SAFARI | `NSE:INE429E01023` | C | 7 → 149 | 0 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 7 / 0 | I | Direct EBITDA/EBIT absent |
| SIEMENS | `NSE:INE003A01024` | C | 101 → 101 | 1 → 1 | 2026 | 11 / 0 | I | Fiscal-calendar / existing conflict |
| SJVN | `NSE:INE002L01015` | C | 136 → 256 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 1 | I | Direct EBITDA/EBIT absent |
| SWIGGY | `NSE:INE00H001014` | C | 136 → 136 | 2 → 2 | 2025, 2026 | 11 / 0 | I | No eligible older same-scope annual row |
| TEGA | `NSE:INE011K01018` | C | 136 → 232 | 1 → 5 | 2022, 2023, 2024, 2025, 2026 | 15 / 0 | X | No eligible older same-scope annual row |
| TEJASNET | `NSE:INE010J01012` | C | 136 → 232 | 2 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 15 / 0 | I | Direct EBITDA/EBIT absent |
| ZYDUSLIFE | `NSE:INE010B01027` | C | 136 → 256 | 1 → 6 | 2021, 2022, 2023, 2024, 2025, 2026 | 16 / 0 | I | Direct EBITDA/EBIT absent |

### Metric-level six-point qualification

| Annual metric | Companies with exactly six observations AND comparable-series state READY |
| --- | ---: |
| Revenue | 16 |
| EBITDA | 0 |
| PAT | 15 |
| EPS_BASIC | 16 |
| All four | **0** |

Nineteen companies have six raw annual endpoints, **not nineteen Rule-16-ready
companies**. The remaining twelve retain date/history gaps. CRAFTSMAN,
ONESOURCE and TEGA retain conflicted annual evidence. ICICIBANK and IDBI have
annual source dates but lack the required bank-specific canonical Revenue/PAT/EPS
observations. LT has six Revenue/EPS observations but only five PAT observations.
No industrial accounting interpretation is assigned to financial institutions.

Counts below are individually materialized annual observations, not a claim
that a conflicted series is usable. An asterisk marks a non-READY series with
nonzero observations. EBITDA/EBIT counts are explicitly zero in every row.

| Symbol | Revenue years | EBITDA years | EBIT years | PAT years | EPS years |
| --- | ---: | ---: | ---: | ---: | ---: |
| ACC | 3 | 0 | 0 | 3 | 3 |
| ACUTAAS | 2 | 0 | 0 | 2 | 2 |
| AFFLE | 5 | 0 | 0 | 5 | 5 |
| APARINDS | 6 | 0 | 0 | 6 | 6 |
| APOLLOHOSP | 6 | 0 | 0 | 6 | 6 |
| ASTRAL | 6 | 0 | 0 | 6 | 6 |
| BIKAJI | 4 | 0 | 0 | 4 | 4 |
| CRAFTSMAN | 5* | 0 | 0 | 5* | 5* |
| CRISIL | 0 | 0 | 0 | 0 | 0 |
| DABUR | 6 | 0 | 0 | 6 | 6 |
| DALBHARAT | 6 | 0 | 0 | 6 | 6 |
| DEEPINDS | 2* | 0 | 0 | 2* | 2* |
| GENUSPOWER | 6 | 0 | 0 | 6 | 6 |
| GESHIP | 6 | 0 | 0 | 6 | 6 |
| GLAND | 6 | 0 | 0 | 6 | 6 |
| ICICIBANK | 0 | 0 | 0 | 0 | 0 |
| IDBI | 0 | 0 | 0 | 0 | 0 |
| INFY | 6 | 0 | 0 | 6 | 6 |
| LT | 6 | 0 | 0 | 5* | 6 |
| LTTS | 6 | 0 | 0 | 6 | 6 |
| MGL | 3 | 0 | 0 | 3 | 3 |
| ONESOURCE | 1* | 0 | 0 | 1* | 1* |
| ORIENTTECH | 1 | 0 | 0 | 1 | 1 |
| RELIANCE | 6 | 0 | 0 | 6 | 6 |
| SAFARI | 6 | 0 | 0 | 6 | 6 |
| SIEMENS | 1 | 0 | 0 | 1 | 1 |
| SJVN | 6 | 0 | 0 | 6 | 6 |
| SWIGGY | 2 | 0 | 0 | 2 | 2 |
| TEGA | 4* | 0 | 0 | 4* | 4* |
| TEJASNET | 6 | 0 | 0 | 6 | 6 |
| ZYDUSLIFE | 6 | 0 | 0 | 6 | 6 |

Exact metric period-end lists, series states, reasons, source fingerprints and
rejected observations are retained in the authoritative machine audit.

## Complete qualified-concept inventory

B20 = BSE 2020 financial taxonomy; S25/S26 = SEBI capmkt 2025/2026;
B19 = BSE banking 2019. Final artifact counts: B20 89, S25 204, S26 122,
B19 8; total **423 files**. Concept document counts below deduplicate the raw
document hash, so they need not equal filesystem artifact counts.
Duration contexts remain distinct from instant contexts; cash-flow adjustments
are not reinterpreted as quarterly earnings. Opening and newly acquired
documents establish **no exact company-level EBITDA/EBIT mapping**.

| Qualified namespace family | Raw concept | Unique documents | Companies | Raw duration buckets | Scopes | Classification |
| --- | --- | ---: | ---: | --- | --- | --- |
| B19 | `AdjustmentsForDepreciationAndAmortisationExpense` | 8 | 2 | FY, Q | Consolidated | COMPONENT_ONLY |
| B19 | `AdjustmentsForFinanceCosts` | 8 | 2 | FY, Q | Consolidated | COMPONENT_ONLY |
| B19 | `ExceptionalItems` | 8 | 2 | FY, Q | Consolidated | COMPONENT_ONLY |
| B19 | `OperatingProfitBeforeProvisionAndContingencies` | 8 | 2 | FY, Q | Consolidated | OPERATING_PROFIT_BUT_NOT_PROVEN_EBITDA |
| B19 | `OtherIncome` | 8 | 2 | FY, Q | Consolidated | COMPONENT_ONLY |
| B19 | `SegmentFinanceCosts` | 7 | 2 | FY, Q | Consolidated | UNSUPPORTED |
| B19 | `SegmentProfitLossBeforeTaxAndFinanceCosts` | 8 | 2 | FY, Q | Consolidated | UNSUPPORTED |
| B20 | `AdjustmentsForDepreciationAndAmortisationExpense` | 87 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `AdjustmentsForFinanceCosts` | 87 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `DepreciationDepletionAndAmortisationExpense` | 89 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `ExceptionalItemsBeforeTax` | 89 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `FinanceCosts` | 89 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `OtherIncome` | 89 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `ProfitBeforeExceptionalItemsAndTax` | 89 | 23 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| B20 | `SegmentFinanceCosts` | 54 | 16 | FY, Q | Consolidated, Standalone | UNSUPPORTED |
| B20 | `SegmentProfitLossBeforeTaxAndFinanceCosts` | 57 | 16 | FY, Q | Consolidated, Standalone | UNSUPPORTED |
| S25 | `AdjustmentsForDepreciationAndAmortisationExpense` | 97 | 30 | FY, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `AdjustmentsForFinanceCosts` | 97 | 30 | FY, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `DepreciationAndAmortisationExpense` | 1 | 1 | FY, Q | Consolidated | COMPONENT_ONLY |
| S25 | `DepreciationDepletionAndAmortisationExpense` | 186 | 28 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `ExceptionalItems` | 17 | 3 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `ExceptionalItemsBeforeTax` | 186 | 28 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `FinanceCosts` | 187 | 28 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `OperatingProfitBeforeProvisionAndContingencies` | 16 | 2 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | OPERATING_PROFIT_BUT_NOT_PROVEN_EBITDA |
| S25 | `OtherIncome` | 203 | 30 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `ProfitBeforeExceptionalAndExtraordinaryItemsAndTax` | 1 | 1 | FY, Q | Consolidated | COMPONENT_ONLY |
| S25 | `ProfitBeforeExceptionalItemsAndTax` | 186 | 28 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S25 | `SegmentFinanceCosts` | 89 | 19 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | UNSUPPORTED |
| S25 | `SegmentProfitLossBeforeTaxAndFinanceCosts` | 95 | 19 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | UNSUPPORTED |
| S26 | `AdjustmentsForDepreciationAndAmortisationExpense` | 63 | 31 | FY, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `AdjustmentsForFinanceCosts` | 63 | 31 | FY, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `DepreciationDepletionAndAmortisationExpense` | 114 | 29 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `ExceptionalItems` | 8 | 2 | FY, Q | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `ExceptionalItemsBeforeTax` | 114 | 29 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `FinanceCosts` | 114 | 29 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `OperatingProfitBeforeProvisionAndContingencies` | 8 | 2 | FY, Q | Consolidated, Standalone | OPERATING_PROFIT_BUT_NOT_PROVEN_EBITDA |
| S26 | `OtherIncome` | 122 | 31 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `ProfitBeforeExceptionalItemsAndTax` | 114 | 29 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | COMPONENT_ONLY |
| S26 | `SegmentFinanceCosts` | 55 | 19 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | UNSUPPORTED |
| S26 | `SegmentProfitLossBeforeTaxAndFinanceCosts` | 59 | 19 | FY, Q, YTD/OTHER_DURATION | Consolidated, Standalone | UNSUPPORTED |

## Diagnostic input effects and exact remaining blockers

Raw duration buckets in the inventory are descriptive source-audit groupings,
not admission decisions: Q/FY denote quarter-length/year-length contexts;
YTD/OTHER_DURATION remains distinct. No plausible earnings concept was found
in an instant context. The unchanged importer/comparability boundary, not
these audit labels, decides exact calendar period eligibility.

These are read-only **input readiness** results, not new diagnostic materialization,
Brain refreshes, financial advice, signal generation or trade authorization.
Baseline comparisons include the accepted 150 period-identity corrections.

| Rule | Before | After | Remaining boundary |
| --- | --- | --- | --- |
| 16 | 28 insufficient / 3 conflicted | unchanged | Direct EBITDA unavailable for 31; 12 shallow histories; 3 conflicts; 1 ambiguous fiscal-period case |
| 17 | 28 policy-blocked / 3 conflicted | unchanged | EBIT 31, total debt 31, equity 24, cash 24, PAT 7 not READY; exact-as-of company-type/applicability intake absent |
| 19 | 28 policy-blocked / 3 conflicted | unchanged | Debt 31, EBIT 31, equity 24, cash 24, finance cost 6 not READY; applicability remains blocked |
| 25 | 22 partial / 5 insufficient / 4 conflicted | unchanged | EBITDA 31, Revenue 9, PAT 13, EPS 13 not READY in required latest-quarter windows; no interpolation |
| 26 | 27 policy-blocked / 4 conflicted | unchanged | EBITDA 31, gross margin 31, Revenue 9 not READY; no PBT/operating-profit substitution |
| 29 | 20 partial / 8 insufficient / 3 conflicted | 23 partial / 5 insufficient / 3 conflicted | Partial current PE input improves; EV/EBITDA, forward PE, PEG and P/B remain unavailable for all 31 |

Metric blocker counts overlap. Zero securities have ceased to be EBIT-blocked.
More raw balance observations do not establish correct ratio denominators,
company applicability or average-period coverage. Six annual points are
still required; five are never used for a five-interval CAGR.
The PE-only improvement is APOLLOHOSP/ORIENTTECH/SAFARI obtaining an annual
EPS observation, not an EBITDA/EV valuation improvement.

### Representative research names and PIT

- APARINDS, GENUSPOWER and GLAND: five → six annual Revenue/PAT/EPS observations;
  direct EBITDA/EBIT remain missing; Rule 16 insufficient; Rule 25 partial.
- DEEPINDS: annual FY2023/FY2026 only; four older official documents rejected for
  exact ISIN mismatch; no six-point claim; Rule 25 partial under accepted period corrections.
- RELIANCE: one → six annual endpoints; six Revenue/PAT/EPS, no EBITDA.
- ORIENTTECH: zero → one annual endpoint; no manufactured prelisting history.
- No EBITDA-direct-mapping or EBIT-direct-mapping success example exists.
- At the explicit 2025 historical cutoff, **0/31 companies have eligible
  canonical financial observations**. New FY2021--FY2026 accounts were acquired
  in 2026; neither their accounting year nor source publication date backdates
  HSI receipt/availability. Current descriptive input remains PARTIAL.

## Final readiness matrix

| ID | Area | State | Evidence |
| --- | --- | --- | --- |
| A | BSE_DIRECT_EBITDA_SOURCE_SEMANTICS | NOT_READY | No exact direct company-level concept in 423 retained files; definition proof unavailable |
| B | BSE_DIRECT_EBIT_SOURCE_SEMANTICS | NOT_READY | Segment profit is not company EBIT |
| C | EBITDA_CANONICAL_MAPPING | NOT_READY | No admitted mapping; facts 0 → 0 |
| D | EBIT_CANONICAL_MAPPING | NOT_READY | No admitted mapping; facts 0 → 0 |
| E | EXISTING_XBRL_REPLAY | NOT_APPLICABLE | No new metric mapping, so no legacy metric replay; 93 new annual imports each replayed successfully |
| F | ANNUAL_OFFICIAL_SOURCE_ACQUISITION | PARTIAL | 31 archives; 101 attempts; 93 accepted; 8 exact-identity rejections |
| G | ANNUAL_IDENTITY_INTEGRITY | READY | All 93 accepted are exact code/ISIN; all 8 mismatches excluded before financial persistence |
| H | ANNUAL_PERIOD_IDENTITY | READY | +811 actual ANNUAL/FULL_YEAR facts; current canonical correction projection retained |
| I | ANNUAL_SCOPE_COMPARABILITY | PARTIAL | No mixed scopes; existing conflicts/noncomparable fiscal histories remain |
| J | SIX_ANNUAL_PERIOD_COVERAGE | PARTIAL | 19 raw six-date histories; Revenue 16/PAT 15/EPS 16 READY six-point series; EBITDA 0 |
| K | RULE_16_FINANCIAL_TREND_INPUT | NOT_READY | 0 all-four complete; 28 insufficient / 3 conflicted |
| L | RULE_17_RETURN_RATIO_INPUT | NOT_READY | EBIT/debt/applicability plus denominator blockers |
| M | RULE_19_LEVERAGE_INPUT | NOT_READY | EBIT/debt/applicability plus cash/equity blockers |
| N | RULE_25_LATEST_QUARTER_INPUT | PARTIAL | 22 partial / 5 insufficient / 4 conflicted |
| O | RULE_26_MARGIN_TRAJECTORY_INPUT | NOT_READY | 27 policy-blocked / 4 conflicted |
| P | RULE_29_VALUATION_INPUT | PARTIAL | 23 partial PE inputs; no EV/EBITDA readiness |
| Q | CURRENT_DESCRIPTIVE_FINANCIAL_INPUT | PARTIAL | Canonical evidence increased without deriving missing metrics |
| R | STRICT_HISTORICAL_PIT_FINANCIAL_INPUT | NOT_READY | 0/31 at the historical cutoff |
| S | NEXT_DOMINANT_FUNDAMENTAL_BLOCKER | NOT_READY | Direct company-level EBITDA/EBIT source semantics absent for 31/31 |

`POLICY_OR_SOURCE_SEMANTICS_UNRESOLVED` applies to both proposed direct mappings,
not to the accepted annual source facts.

## Storage, replay and protected state

- DB file: 18,341,171,200 → 18,346,504,192 bytes (**+5,332,992**).
- Added raw XML: **6,879,698 bytes**; archive snapshots/sidecars: **867909 bytes**.
  No full production DB copy or backup was created.
- Hash comparison of the original 4,067 financial rows and 362 filing rows is
  exact: no original evidence was overwritten. Added rows are fully accounted
  for above. No accepted import/replay reported a conflict.
- Mapping entries 500, inventories 3, broad acquisition plan 1 remain
  fingerprint-identical. Portfolio snapshot 1, transactions 5, paper trades 0,
  trade plans 0, generic strategies/results 0, canonical definitions 1 and
  canonical diagnostic results 2,074 remain fingerprint-identical.
- No provider credential input, broker/order interface, portfolio mutation,
  per-tick writes, financial derivation, formula/threshold change or runtime
  activation was introduced.

## Defensive review and validation

The new audit initially used the correction class name rather than the existing
persisted record-type constant. Defensive review corrected this and added a
read-only store/PIT regression. Earlier local audit files are **superseded**;
`final.json` includes the accepted 150 corrections. The pre-fix partial test run
was stopped and is not cited as validation. The final completed regression is
recorded below. Production originals and the accepted correction store were
unchanged throughout.

Review also corrected the new selector's initial exclusion of the existing
labelled exchange-local timestamp convention, and made the outer acquisition
handler preserve an invariant halt and stop immediately. No real import hit that
invariant; tests inject it. Rejected incoming hashes are retained by the final
worker when bytes reach it; historical rejection receipts are never rewritten.

Focused: **28 passed**. Relevant BSE/import/comparability/period-repair:
**107 passed**.

Final completed backend suite: **3,362 passed / 0 failed / 6 skipped /
2 warnings**, 290.48 seconds. JUnit independently records 3,368 total cases,
0 failures, 0 errors, 6 skipped. Warnings are the existing Starlette/httpx and
AnyIO deprecations; opt-in external integrations remain skipped.

Read-only production checks: SQLite **integrity = ok**, **FK violations = 0**,
duplicate logical filings **0**; cash remains **UNKNOWN**. No broker/order
tables or calls were introduced. The original financial/filing row hashes and
all protected row hashes described above match. No production rollback or
destructive database operation was required.

Authoritative local audit SHA-256:
`e41a80e3346dc0aba6c1f8adf259b7b3ad4a5f5bcea93304f57bf630d1b9e9d6`.
Markdown local links: **240 checked / 0 broken**. Edited Markdown whitespace
and `git diff --check`: passed. Operational artifacts, raw XML, production DB,
test output and temporary databases remain Git-excluded.

## One next bounded continuation (not started)

`OFFICIAL_COMPANY_LEVEL_EBITDA_EBIT_SOURCE_FEASIBILITY_V1`

Research-only, first-party company-level reported EBITDA/EBIT disclosure and
taxonomy-definition feasibility for the same source population, with exact
scope/context/reconciliation boundaries. **No derivation-policy implementation,
legacy-ISIN repair or ingestion is authorized by this recommendation.**
The measured universal blocker is EBITDA/EBIT (31/31), not merely the twelve
remaining annual-date gaps. Balance-sheet, cash-conversion and valuation
denominator expansions would not remove that universal blocker. No jump to
Portfolio/Harvest/Sell/Rotation is justified.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
NO_INDICATOR_EXPANSION = TRUE
HSI_INTERNAL_RADAR = ACTIVE
RULE_HORIZON_TIMEFRAME_POLICY = FROZEN
AI_DECISION_AUTHORITY = FALSE
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```
