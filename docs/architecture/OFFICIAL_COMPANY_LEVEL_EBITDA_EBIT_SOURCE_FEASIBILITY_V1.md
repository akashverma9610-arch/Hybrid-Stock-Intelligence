# Official company-level EBITDA / EBIT source feasibility V1

**Status:** `COMPLETED_RESEARCH_ONLY / NOT_ACTIVE / NO_CANONICAL_MAPPING_APPROVED`

This bounded audit evaluates whether the current canonical 31-company financial
population has an official, company-level, directly disclosed EBITDA or EBIT
source that could be considered in a future governed policy. It does not add a
metric mapping, derive a value, alter Rules 16, 17, 19, 25, or 26, write a
`FinancialFact`, or change diagnostic outcomes.

It follows the earlier [canonical EBITDA / EBIT source audit and annual-history
acquisition](CANONICAL_EBITDA_EBIT_AND_ANNUAL_HISTORY_ACQUISITION_V1.md). The
earlier result of zero canonical EBITDA and EBIT facts remains unchanged.

## Governance boundary

The authoritative research receipt is local-only and ignored by Git:

`reports/official-company-level-ebitda-ebit-source-feasibility-v1/final.json`

Receipt SHA-256:

`330f799ae6f835d6e41b0b0bf7984edf4a4384e9b692dc9fdcccb858068fd766`

The receipt is semantic metadata only: classifications, source family,
publication semantics, machine-readability, and formula-treatment fingerprints.
It intentionally contains no disclosed financial values. Research was received
at `2026-09-11T18:52:40.658877+00:00`; a source publication date never
backdates HSI receipt or makes the research usable at an earlier historical
as-of time.

No source document was persisted as canonical evidence. The production database
therefore remains at 6,118 `FinancialFacts` and 455 `CorporateFilings` for this
audit; its content was queried read-only.

## Method and authority classification

The audit admitted only HTTPS sources whose provenance could be stated exactly.
NSE documents used the published [XBRL information surface](https://www.nseindia.com/static/companies-listing/xbrl-information),
the [Integrated Filing—Financials surface](https://www.nseindia.com/companies-listing/corporate-integrated-filing?symbol=BSE&tabIndex=equity),
and documented exchange archive links. [NSE's 2025 circular](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Circular_02042025_0.pdf)
requires an Integrated Filing—Financial in XBRL on the financial-results date;
that supports the source route, not a universal EBITDA/EBIT definition.

| Source family | Authority classification | Bounded treatment | Result |
| --- | --- | --- | --- |
| Retained BSE financial-result XBRL | `PRIMARY_EXCHANGE` | Full retained corpus, exact ISIN required | 423 XML documents; available for all 31 targets |
| NSE Integrated Filing—Financial XBRL | `PRIMARY_EXCHANGE` | Latest relevant filing, latest annual filing, and one older useful filing where available; exact ISIN required | Available for all 31 targets |
| NSE annual-report XBRL | `PRIMARY_EXCHANGE` | Latest annual plus one historical annual where available; exact ISIN required | Available for 27 targets; unavailable for 4 |
| NSE annual-report PDF metadata | `PRIMARY_EXCHANGE` | Metadata/link availability only | Available for all 31; PDF contents were not parsed and no OCR was used |
| Issuer annual report linked through an exchange | `PRIMARY_ISSUER` when exact linkage is proven | Not established by this bounded source route | `SOURCE_UNAVAILABLE` for all 31 in this audit |
| Exchange-hosted company investor presentation | `PRIMARY_COMPANY_FILED_WITH_EXCHANGE` when exact linkage is proven | Not established by this bounded source route | `SOURCE_UNAVAILABLE` for all 31 in this audit |

`SECONDARY` and `UNSUPPORTED` sources were not admitted. In particular, there
was no financial portal, broker, news snippet, web-search snippet, inferred
formula, issuer-site crawl, OCR, or AI extraction call. Source authority is
about provenance; it is not a statement that every source has a comparable
company-level metric.

## Qualification rules applied

A candidate observation had to be exact-ISIN matched, company-level, and
directly disclosed under the requested classification. Segment observations
were retained as `SEGMENT_LEVEL_ONLY` / `SEGMENT_EBIT_ONLY` and were never
summed or promoted. `OperatingProfitBeforeProvisionAndContingencies` remained
`OPERATING_PROFIT_ONLY`; it was not renamed EBITDA or EBIT. Profit-before-tax
and profit-before-exceptional-items-and-tax lines remained
`PBT_LIKE_NOT_EBIT`.

The audit records a formula fingerprint only when the document itself declares
the treatment. It never computes EBITDA/EBIT from components. Formula stability
is `STABLE_DEFINITION` only for repeat source-declared treatment fingerprints,
`CHANGED_DEFINITION` only for conflicting declared fingerprints, `UNDEFINED`
when no eligible formula is declared, and `INSUFFICIENT_HISTORY` where an
eligible declared formula has only one qualified period.

Machine-readability labels are restricted to `STRUCTURED_NUMERIC_FIELD`,
`STRUCTURED_TEXT_BLOCK`, `HTML_TABLE`, `PDF_TEXT`, `PDF_TABLE`, and `OTHER`.
Only the first two occurred in this receipt. A structured field can still be an
ineligible metric: structured formatting does not establish economic semantics.

## Measured result

The probe examined 552 exact-identity-admitted documents across the 31 targets.
It rejected 41 candidate documents on missing, mismatched, or ambiguous ISIN
identity and retained eight bounded `NSE_SOURCE_RESPONSE_TOO_LARGE` failures.
Those documents are not silently treated as `NOT_DISCLOSED`; they are a reason
that this is a source-feasibility result rather than comprehensive certification.

| Measure | Result |
| --- | ---: |
| Targets | 31 |
| Retained BSE XBRL documents scanned | 423 |
| Exact-identity-admitted documents examined | 552 |
| Candidate documents rejected for identity | 41 |
| Bounded source-response-too-large failures | 8 |
| `COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_WITH_FORMULA` EBITDA | 0 |
| `COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA` EBITDA | 0 |
| `COMPANY_LEVEL_DISCLOSED_FORMULA_ONLY` EBITDA | 0 |
| `COMPANY_LEVEL_DIRECT_EBIT_VALUE` | 0 |
| `COMPANY_LEVEL_EBIT_FORMULA` | 0 |
| Eligible source-declared formula fingerprints | 0 |
| Stable or changed eligible definition histories | 0 |

The source classifications were 29 `NOT_DISCLOSED` and two
`OPERATING_PROFIT_ONLY` for EBITDA; all 31 EBIT results were
`PBT_LIKE_NOT_EBIT`. There are no definition fingerprints to compare, so both
metric definition-stability outputs are `UNDEFINED` for every target. The two
operating-profit cases are IDBI and ICICI Bank; neither is evidence for a
universal financial-company EBITDA/EBIT substitute.

### Per-company evidence matrix

`Docs` counts exact-identity-admitted documents. `I` is excluded candidate
document identity failures; `L` is a bounded source-response-too-large failure.
All rows preserve the same source timestamp semantic:
`SOURCE_PUBLICATION_TIMESTAMP_PRESERVED_WHEN_EXCHANGE_METADATA_PROVIDES_IT`.

| Symbol | Canonical instrument | Docs | EBITDA classification | EBIT classification | EBITDA machine field | EBIT machine field | I | Source limit |
| --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| ACC | `NSE:INE012A01025` | 17 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| ACUTAAS | `NSE:INE00FF01025` | 14 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| AFFLE | `NSE:INE00WC01027` | 19 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| APARINDS | `NSE:INE372A01015` | 25 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| APOLLOHOSP | `NSE:INE437A01024` | 12 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| ASTRAL | `NSE:INE006I01046` | 20 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| BIKAJI | `NSE:INE00E101023` | 18 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| CRAFTSMAN | `NSE:INE00LO01017` | 19 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| CRISIL | `NSE:INE007A01025` | 16 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| DABUR | `NSE:INE016A01026` | 20 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| DALBHARAT | `NSE:INE00R701025` | 21 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| DEEPINDS | `NSE:INE0FHS01024` | 17 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| GENUSPOWER | `NSE:INE955D01029` | 23 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 1 | — |
| GESHIP | `NSE:INE017A01032` | 18 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| GLAND | `NSE:INE068V01023` | 22 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| ICICIBANK | `NSE:INE090A01021` | 19 | `OPERATING_PROFIT_ONLY` | `PBT_LIKE_NOT_EBIT` | `STRUCTURED_NUMERIC_FIELD` | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| IDBI | `NSE:INE008A01015` | 19 | `OPERATING_PROFIT_ONLY` | `PBT_LIKE_NOT_EBIT` | `STRUCTURED_NUMERIC_FIELD` | `STRUCTURED_NUMERIC_FIELD` | 0 | — |
| INFY | `NSE:INE009A01021` | 19 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| LT | `NSE:INE018A01030` | 20 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| LTTS | `NSE:INE010V01017` | 21 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| MGL | `NSE:INE002S01010` | 16 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| ONESOURCE | `NSE:INE013P01021` | 16 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| ORIENTTECH | `NSE:INE0PPK01015` | 6 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 1 | — |
| RELIANCE | `NSE:INE002A01018` | 18 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD`, `STRUCTURED_TEXT_BLOCK` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| SAFARI | `NSE:INE429E01023` | 12 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| SIEMENS | `NSE:INE003A01024` | 14 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| SJVN | `NSE:INE002L01015` | 21 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 1 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| SWIGGY | `NSE:INE00H001014` | 14 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | — |
| TEGA | `NSE:INE011K01018` | 19 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |
| TEJASNET | `NSE:INE010J01012` | 18 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 2 | — |
| ZYDUSLIFE | `NSE:INE010B01027` | 19 | `NOT_DISCLOSED` | `PBT_LIKE_NOT_EBIT` | — | `STRUCTURED_NUMERIC_FIELD` | 0 | `NSE_SOURCE_RESPONSE_TOO_LARGE` |

## Feasibility decision

**Final result: C — `DIRECT_SOURCE_COVERAGE_TOO_SPARSE`.**

The qualified, currently available primary structured sources do not establish
a direct company-level EBITDA or EBIT value or a source-declared company-level
formula for any of the 31 companies. The non-qualified `OPERATING_PROFIT_ONLY`
and `PBT_LIKE_NOT_EBIT` observations cannot be repaired through arithmetic or
renaming. The identity exclusions and eight response-size limits additionally
mean the result is not a claim that an issuer never discloses the measure in
another document; it is a fail-closed statement about this bounded, verified
source route.

| Policy option | Assessment | Decision |
| --- | --- | --- |
| A — standardize direct EBITDA/EBIT from a common disclosed source | No eligible direct values or source-declared common formulas were found | Not activated |
| B — preserve company-defined disclosure without canonical comparability | No qualified company-defined direct value/formula is available in this receipt | Not activated |
| C — retain existing evidence and research an alternative diagnostic policy | The only justified path after the measured coverage result | Selected; no policy is activated by this audit |

No Rule 16, 17, 19, 25, or 26 input becomes newly ready. In particular, zero
qualified EBITDA observations leave Rule 16 and Rules 25/26 unchanged; zero
qualified EBIT observations leave Rules 17/19 unchanged. This audit does not
alter formulae, thresholds, applicability, or existing insufficient/conflicted
outcomes.

## AI and extraction implication

This result does **not** make an AI extraction provider active or authorized.
The primary structured route was machine-readable enough to determine that no
qualified direct observation was present; an AI system may not infer a metric
from components, a segment, a ratio, or ambiguous prose. The unparsed PDF and
unlinked issuer/presentation routes are not a license for OCR or AI-based
canonical extraction. Any future use would require a separately approved
source-identity, extraction, review, formula, comparability, and PIT policy.

## Next bounded slice

The sole next slice selected by result C is:

`EBITDA_EBIT_DIAGNOSTIC_POLICY_ALTERNATIVE_RESEARCH_V1`

It must research only fail-closed diagnostic-policy alternatives. It must not
create a metric, map an operating-profit/PBT surrogate, modify diagnostic
formulae or thresholds, backdate evidence, or write production facts without a
later explicit approval.

## Explicit non-changes

- `FinancialFact` enum, mappings, ingestion, and persistence: unchanged.
- Rule 16/17/19/25/26 policies, thresholds, and diagnostics: unchanged.
- Canonical 61 registry and Shared Brain: unchanged.
- No provider credential, AI provider call, extraction job, API, UI, broker,
  order, portfolio, or database mutation occurred.
- No third-party financial data, snippets, OCR, derived values, or synthetic
  comparability was used.
