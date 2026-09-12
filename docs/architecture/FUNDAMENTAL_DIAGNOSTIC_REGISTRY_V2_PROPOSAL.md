# Fundamental Diagnostic Registry V2 Proposal

Status: `PROPOSED / DOCUMENTATION_AND_MACHINE_PROPOSAL_ONLY / NOT_ACTIVE`.

Parent: `diagnostic-registry-v1`, accepted commit
`f19f8072792d6cbf54310e359e4306153dc7a6a3`.
Candidate: `diagnostic-registry-v2-proposed`.
Component policy candidate: `fundamental-component-policy-v2-proposed`.

This is a successor proposal for the same 61 canonical IDs. It has no execution,
persistence, data-acquisition or activation authority. Exactly IDs
**16, 17, 19, 25, 26 and 29** have proposed semantic changes. The other **55**
inherit their exact parent definitions. The
[machine proposal](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSED.json)
is normative for the explicit field values; this document explains the
decisions and contains the matching human diff. Neither is loaded by runtime.

## Accepted sources and current evidence

The proposal reuses the accepted
[policy-resolution receipt](FUNDAMENTAL_DIAGNOSTIC_POLICY_UNRESOLVED_V1.md),
[EBITDA/EBIT alternatives](EBITDA_EBIT_DIAGNOSTIC_POLICY_ALTERNATIVE_RESEARCH_V1.md)
and [V1 comparability contract](CANONICAL_FINANCIAL_DIAGNOSTIC_INPUT_COMPARABILITY_CLOSURE_V1.md).
Source authority establishes accounting/disclosure meaning, not HSI thresholds,
score weights or performance.

- [MCA Schedule III amendment](https://www.mca.gov.in/Ministry/pdf/ScheduleIIIAmendmentNotification_24032021.pdf)
  requires applicable ratio disclosures and numerator/denominator explanations.
  The same ratio label does not establish identical formulas.
- [MCA Ind AS 1](https://www.mca.gov.in/Ministry/pdf/Ind_AS1.pdf) supplies financial-statement
  presentation context. Revenue and after-tax profit do not become EBITDA.
  The proposed net-profit-margin scope below is an HSI governance proposal,
  not a formula prescribed by MCA.
- [ICAI Division II guidance](https://kb.icai.org/pdfs/PDFFile5b27857548bee2.71295102.pdf)
  and [SEBI issuer ratio definitions](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2024/1727675578109.pdf)
  provide presentation and source-specific formula context from the accepted research.
- [RBI bank reporting](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html),
  [RBI NBFC disclosure context](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12292)
  and [IRDAI reporting](https://irdai.gov.in/document-detail?documentId=374643)
  justify separate applicability. Bank interest income/expense, NBFC funding
  and insurer policyholder/shareholder accounts cannot inherit industrial formulas.
- [Official NSE filing structure](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152826_24042026225714_iXBRL_WEB.html)
  and the existing [BSE official parser](../../app/fundamentals/bse_official.py)
  preserve source lineage. No new provider/parser is introduced.

The accepted 31-company receipt found 10 non-financial, 2 banks and 19 unknown.
It found no direct EBIT/EBITDA, total-debt facts or canonical issuer-ratio
contract. Annual Revenue/PAT/EPS coordinate coverage was 8/10 non-financial
and 7/19 unknown; those counts do not certify contiguous six-year eligibility.
This slice does not recalculate production readiness or classify the unknowns.

## Version authority and lifecycle

`DIAGNOSTIC_REGISTRY_V1` remains immutable authority for V1 executions.
`DIAGNOSTIC_REGISTRY_V2_PROPOSED` is an inactive successor definition of the
same set, never a financial sub-registry or a second active Brain.

Proposed state progression:
`PROPOSED -> RESEARCH_VALIDATED -> GOVERNANCE_APPROVED -> SHADOW -> ACTIVE -> RETIRED`.
Each transition requires its own immutable evidence/approval receipt.
Passing the proposal's tests does **not** advance its state. This slice creates
only `PROPOSED`. Rejected/revised proposals retain their old fingerprint;
a replacement proposal receives a new fingerprint and review.

Every future execution must bind exact `registry_version`, `strategy_version`,
`policy_version` and caller-supplied `as_of`, together with their semantic
fingerprints and effective approval lineage. Missing, conflicting, future or
ambiguous bindings fail closed. “Current registry” is not an execution identity.
Only one registry version is active for one execution. Explicit parallel
research comparisons are separate, labelled runs, not two votes in a score.

The current runner authorizes only `canonical-universe-analysis / v1`,
fingerprint
`sha256:3144ec1e9452f24a1e9f3776c77e33cbd59f31459c3e2f7d734c4924bb2b9ee3`.
This proposal creates no V2 strategy record. That strategy fingerprint differs
from the registry-definition fingerprint and proposal fingerprint.

V1 has declared `UNVERSIONED_DEPENDENCY` limitations, including runner/evaluator
dependencies. Reproducibility therefore also requires preserving the exact V1
source/dependency artifacts; a constant alone is not sufficient. The proposal
pins the relevant baseline Git blobs and full 61-definition semantic fingerprint.
Future implementation must retain a V1 execution path, not edit its formulas
in place.

## Exact 61-ID inheritance

The machine artifact lists every integer 1 through 61 once, in order. Its 55
`INHERIT_EXACT_PARENT` rows contain the exact parent reference and fingerprint
over the entire `DiagnosticRuleDefinition`, including its original calculation
version. They are not newly authored rule definitions. IDs 1–15, 18, 20–24,
27–28 and 30–61 keep their names, purpose, evidence permissions, dependencies,
statuses, confidence/missing-data policy and calculation semantics.

A future V2 envelope identifies the selected registry while an inherited rule's
calculation lineage remains V1. Dependency version binding is explicit per run:
for example Rule 33 may consume changed inputs 16/17/19 in a labelled V2 replay,
but its unchanged definition is not silently rewritten by this proposal.

## Shared evidence and comparison contract

This proposed contract applies only to the six affected rules. It creates no
new input requirement on the 55 inherited rules.

- Use the existing canonical instrument identity, selected statement scope,
  FinancialFact vintage selection, metric observations and comparability path.
- Require exact fiscal periods, representation, units/scale/currency and
  normalization/accounting basis within each metric series; cross-metric
  monetary operands must also match. EPS retains its distinct per-share unit.
  Never alternate consolidated and standalone periods for coverage.
- Evidence and source filings must be published and received by the explicit
  UTC-normalized as-of; period end alone never establishes knowability.
- No YTD-to-quarter, TTM, adjusted-EPS, FX, calendar approximation or backfill
  to an older complete window is authorized.
- Keep source PAT/equity attribution and continuing/discontinued-operation
  basis explicit. The current PAT tags alone do not prove a shareholder-
  attributable ROE or fully comparable net-profit-margin numerator.
- Keep contradictory evidence as `EVIDENCE_CONFLICTED`; reject duplicate or
  conflicting lineage identities and invalid fingerprints.
- Source freshness policy is reused with explicit dates. No new expiry,
  wall-clock dependency or unapproved numerical cutoff is introduced.

All measurement expressions below are **proposed**, not approved formulas.
No values are calculated here. Numeric-domain rules are mathematical validity
conditions, not investment thresholds. Existing V1 growth, margin, leverage and
valuation classification thresholds are not imported into changed V2 aggregates.

## Exact six-rule V1 to V2 diff

### Rule 16: Five-Year Financial Trend — Revenue, PAT and EPS CAGR

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR | Five-Year Financial Trend — Revenue, PAT and EPS CAGR |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR. | Describe five-year changes in revenue, after-tax accounting profit and per-share earnings; operating earnings are separately labelled enrichment. |
| Actual V1 behavior | Six annual rows; all four Revenue/EBITDA/PAT/EPS components required. The canonical input bridge certifies fiscal continuity and positive endpoints. V1 classification aggregates four growth rates. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | Remove EBITDA from mandatory core; retain Revenue, PAT and EPS, each with six comparable consecutive full-year observations spanning five fiscal intervals. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | Source-qualified reported EBITDA and separately governed operating earnings become optional enrichment. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | Require exact NON_FINANCIAL classification for standard branch; bank/NBFC/insurer branch policy and unknown classification block interpretation. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | One result exposes three core CAGR components, completeness and optional coverage; no four-to-three score conversion or automatic ACCELERATING/HEALTHY carry-forward. |
| Reason/source basis | MCA_SCHEDULE_III, MCA_IND_AS_1, SEBI_RATIO_EXAMPLE, ACCEPTED_RESEARCH | EBITDA is not a universal standardized reported line; exact wording is narrower than ambiguous Revenue, Profitability and EPS Trend. |
| Migration risk | Preserve source-defined V1 behavior. | Three rates cannot inherit V1 four-component aggregates or calibrated state cutoffs; PAT/EPS attribution and restatements must remain comparable. |

Aggregation: `ALL_MANDATORY_CORE`. Preserve five-year CAGR mathematics. Retain available signed raw series when CAGR is undefined; label INSUFFICIENT_DATA with CAGR_DOMAIN_INVALID, not NOT_APPLICABLE. Missing a latest period never permits fallback to an older window.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| REVENUE_CAGR | MANDATORY_CORE | REVENUE six annual observations | (value_at_t / value_at_t_minus_5) ** (1/5) - 1; positive endpoints only. No calculation in this proposal. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Six consecutive fiscal years, exactly five fiscal intervals. | PROPOSED_ONLY |
| PAT_CAGR | MANDATORY_CORE | PAT six annual observations | (value_at_t / value_at_t_minus_5) ** (1/5) - 1; positive endpoints only. No calculation in this proposal. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Six consecutive fiscal years, exactly five fiscal intervals. | PROPOSED_ONLY |
| EPS_BASIC_CAGR | MANDATORY_CORE | EPS_BASIC six annual observations | (value_at_t / value_at_t_minus_5) ** (1/5) - 1; positive endpoints only. No calculation in this proposal. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Six consecutive fiscal years, exactly five fiscal intervals. | PROPOSED_ONLY |
| ISSUER_REPORTED_EBITDA | OPTIONAL_COMPONENT | direct official EBITDA; issuer definition; revision and PIT lineage | Issuer-defined value only; never a canonical standardized EBIT/EBITDA. | Exact same period/scope; formula stable across comparisons. | FUTURE_CONTRACT_REQUIRED |
| HSI_STANDARDIZED_OPERATING_EARNINGS | OPTIONAL_COMPONENT | approved distinct metric contract; immutable compatible parent facts | No approved formula: POLICY_BLOCKED | Same compared fiscal periods. | POLICY_BLOCKED |

| Wording alternative | Decision |
|---|---|
| CURRENT_FOUR_COMPONENT_NAME | Reject universal hard EBITDA dependency. |
| Revenue, Profitability and EPS Trend | Reject vague profitability basis and loss of explicit CAGR scope. |
| Revenue, PAT and EPS CAGR | Selected precise three-component name; operating-earnings coverage is explicitly not claimed. |

### Rule 17: Entity-Aware Return Efficiency — ROE and Qualified ROCE

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Return Ratios — ROCE and ROE | Entity-Aware Return Efficiency — ROE and Qualified ROCE |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Return Ratios — ROCE and ROE. | Describe return efficiency using a standard non-financial ROE core and separately qualified ROCE; require native financial-sector contracts. |
| Actual V1 behavior | Joint PAT/EBIT/equity/debt/cash intake; latest PAT divided by mean beginning/end equity; EBIT divided by capital employed. Legacy ending-only denominator fallback is explicitly labelled. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | ROE is the proposed non-financial core. Require exact beginning/end total equity matched to annual PAT; V2 removes ending-only fallback for average-equity ROE. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | Qualified ROCE and formula-matched official ROE/ROCE corroboration; absence does not erase ROE evidence. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | BANK native ROE/ROA may be future branch candidates; NBFC/INSURER remain policy blocked. Industrial ROCE is not the bank/insurer return concept. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | READY_STANDARD_BRANCH only for complete standard core; READY_ENTITY_SPECIFIC_BRANCH only after separate native branch approval; PARTIAL, POLICY_BLOCKED, INSUFFICIENT_DATA and conflict states remain explicit. |
| Reason/source basis | MCA_SCHEDULE_III, SEBI_RATIO_EXAMPLE, RBI_BANK, RBI_NBFC, IRDAI, ACCEPTED_RESEARCH | ROE and ROCE definitions, equity attribution and capital-employed denominators are not automatically uniform. |
| Migration risk | Preserve source-defined V1 behavior. | Removing joint requirements and ending fallback changes eligibility; source PAT/equity scope must agree. No V1 joint healthy classification may be reused. |

Aggregation: `ALL_MANDATORY_CORE`. This proposal does not approve a new ROCE numerator or capital-employed formula. Negative PAT is descriptive if denominator valid; no universal healthy threshold.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| ROE | MANDATORY_CORE | annual PAT; beginning total equity; ending total equity; consistent profit/equity attribution | Annual PAT / ((beginning total equity + ending total equity) / 2); exact matching basis, positive mean equity, no parent-only/group-total mix. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Two consecutive annual equity boundaries; latest annual PAT. | PROPOSED_ONLY |
| ROCE | OPTIONAL_COMPONENT | approved EBIT or separately named numerator contract; approved average capital-employed definition | No approved formula: POLICY_BLOCKED | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Two aligned balance boundaries; no ending fallback. | POLICY_BLOCKED |
| ISSUER_REPORTED_ROE_ROCE | OPTIONAL_COMPONENT | ISSUER_REPORTED_FINANCIAL_RATIO; exact formula match | Corroboration only; cannot satisfy ROE/ROCE parent requirements. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. | FUTURE_CONTRACT_REQUIRED |

### Rule 19: Entity-Aware Leverage — Debt/Equity, Net Debt and Qualified Interest Coverage

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage | Entity-Aware Leverage — Debt/Equity, Net Debt and Qualified Interest Coverage |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage. | Expose leverage, net-debt position and independently qualified coverage without concealing missing coverage or creating a healthy verdict. |
| Actual V1 behavior | All debt/equity/cash/EBIT/interest inputs required jointly; any absent input blocks the entire leverage evaluation; coverage drives STRESSED before D/E drives ELEVATED. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | Debt/equity is the proposed ordinary non-financial core; absence prevents full core readiness but does not delete other ready component evidence. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | Net debt and qualified interest coverage are OPTIONAL_COMPONENT; observed adverse coverage is retained prominently, with risk escalation dependent on separate approved policy. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | Banks, NBFCs and insurers require native capital, leverage/solvency contracts; unknown classification remains policy blocked. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | Core completeness and full component coverage are distinct. Optional absence cannot become HEALTHY; no new BLOCKING_COMPONENT threshold is introduced. |
| Reason/source basis | MCA_SCHEDULE_III, SEBI_RATIO_EXAMPLE, RBI_BANK, RBI_NBFC, IRDAI, ACCEPTED_RESEARCH | Debt/equity, net debt and interest coverage answer independent questions; DSCR includes debt service and cannot replace interest coverage. |
| Migration risk | Preserve source-defined V1 behavior. | Partial leverage evidence must not suppress red flags or be interpreted as V1 healthy; financial debt semantics differ. |

Aggregation: `ALL_MANDATORY_CORE`. No component is designated BLOCKING_COMPONENT without an approved adverse-condition policy. That role would block semantic evaluation even when evidence is present, not merely mean absent optional input. DSCR is separate evidence outside these three component calculations.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| DEBT_EQUITY | MANDATORY_CORE | exact total debt definition; same-end total equity | Total debt / total equity; positive equity, explicit debt definition and treatment of leases/restricted instruments. | Same fiscal-end POINT_IN_TIME balances and representation. | PROPOSED_ONLY |
| NET_DEBT | OPTIONAL_COMPONENT | same-end total debt; eligible cash and equivalents; approved debt/cash boundary | Total debt - cash and equivalents, only under an approved exact debt/cash contract; negative net debt is retained as a measurement. | Same fiscal-end POINT_IN_TIME balances and representation. | POLICY_BLOCKED |
| INTEREST_COVERAGE | OPTIONAL_COMPONENT | approved earnings numerator; explicit interest-only denominator or approved finance-cost bridge | No approved formula: POLICY_BLOCKED | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. | POLICY_BLOCKED |
| ISSUER_REPORTED_DEBT_EQUITY | OPTIONAL_COMPONENT | ISSUER_REPORTED_FINANCIAL_RATIO; exact formula match | Corroboration only, never a replacement for mandatory parents. | Exact matched fiscal end. | FUTURE_CONTRACT_REQUIRED |

### Rule 25: Latest Quarterly Results — Revenue, PAT and EPS YoY & QoQ

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Latest Quarterly Results — YoY & QoQ | Latest Quarterly Results — Revenue, PAT and EPS YoY & QoQ |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Latest Quarterly Results — YoY & QoQ. | Describe current quarterly revenue, after-tax profit and per-share earnings comparisons with complete-core and optional-earnings coverage separated. |
| Actual V1 behavior | Five quarterly rows; positive latest, previous and year-ago triples independently produce each Revenue/EBITDA/PAT/EPS growth pair; even one metric can be wrapper-eligible. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | Revenue/PAT/EPS become CORE_REQUIRED (alias of MANDATORY_CORE) for full readiness; one surviving component remains partial. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | EBITDA and approved distinct operating earnings optional; absence cannot invalidate complete core. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | Standard branch requires NON_FINANCIAL; financial entities require their reporting-basis contracts. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | READY core only when all three YoY and QoQ pairs satisfy comparison-domain checks; missing components preserve PARTIAL evidence without full semantic eligibility. |
| Reason/source basis | MCA_IND_AS_1, NSE_FILING, ACCEPTED_RESEARCH | Quarterly reporting purpose is retained without universal EBITDA requirement or one-component completeness claims. |
| Migration risk | Preserve source-defined V1 behavior. | Stricter full-core readiness differs from V1 wrapper eligibility; reported growth is not organic acceleration. |

Aggregation: `ALL_MANDATORY_CORE`. No new negative-base percentage convention, nearest-quarter substitution or implied earnings-acceleration verdict.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| REVENUE_YOY_QOQ | MANDATORY_CORE | REVENUE quarter-only observations | YoY = q / q_minus_4 - 1; QoQ = q / q_minus_1 - 1, retaining current positive triple domain. Signed raw values retained if growth domain invalid. | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | PROPOSED_ONLY |
| PAT_YOY_QOQ | MANDATORY_CORE | PAT quarter-only observations | YoY = q / q_minus_4 - 1; QoQ = q / q_minus_1 - 1, retaining current positive triple domain. Signed raw values retained if growth domain invalid. | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | PROPOSED_ONLY |
| EPS_BASIC_YOY_QOQ | MANDATORY_CORE | EPS_BASIC quarter-only observations | YoY = q / q_minus_4 - 1; QoQ = q / q_minus_1 - 1, retaining current positive triple domain. Signed raw values retained if growth domain invalid. | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | PROPOSED_ONLY |
| ISSUER_REPORTED_EBITDA | OPTIONAL_COMPONENT | direct official EBITDA; issuer definition; revision and PIT lineage | Issuer-defined value only; never a canonical standardized EBIT/EBITDA. | Exact same period/scope; formula stable across comparisons. | FUTURE_CONTRACT_REQUIRED |
| HSI_STANDARDIZED_OPERATING_EARNINGS | OPTIONAL_COMPONENT | approved distinct metric contract; immutable compatible parent facts | No approved formula: POLICY_BLOCKED | Same compared fiscal periods. | POLICY_BLOCKED |

### Rule 26: Profitability Margin Trajectory — Net Profit Core, Qualified Margin Context

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Operating Margin & Gross Margin Trajectory | Profitability Margin Trajectory — Net Profit Core, Qualified Margin Context |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Operating Margin & Gross Margin Trajectory. | Describe explicitly named after-tax profitability margins while separating operating, gross and issuer-defined EBITDA contexts. |
| Actual V1 behavior | Name promises operating and gross margins; actual evaluator measures latest quarterly EBITDA/revenue and YoY change with five-quarter intake. No canonical gross-margin numerator. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | Propose NET_PROFIT_MARGIN as named non-financial core from exact reported PAT and revenue; this is a new proposed scope requiring human governance, not an already approved formula. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | PBT, direct operating, gross and issuer EBITDA margins are distinctly named optional components with independent contracts. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | No industrial PAT/revenue, operating or gross-margin mechanics for BANK/NBFC/INSURER without native policy; unknown remains blocked. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | Descriptive net margin levels and YoY percentage-point change; no V1 EXPANDING/CONTRACTING threshold transfer or inference about gross/operating margins. |
| Reason/source basis | MCA_IND_AS_1, MCA_SCHEDULE_III, SEBI_RATIO_EXAMPLE, ACCEPTED_RESEARCH | Profitability is broader than operating/gross profitability. The explicit net-profit core makes the semantic loss visible rather than relabelling a substitute. |
| Migration risk | Preserve source-defined V1 behavior. | Net profit includes finance, tax and non-operating effects; cannot establish operational efficiency. Thresholds and source PAT attribution need governance/calibration before activation. |

Aggregation: `ALL_MANDATORY_CORE`. PAT is not gross profit; PBT is not operating profit; issuer EBITDA is not standardized operating profit. HSI_STANDARDIZED_OPERATING_EARNINGS remains a formula-null placeholder, not a parent for the core.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| NET_PROFIT_MARGIN | MANDATORY_CORE | exact reported PAT; same-period revenue; consistent PAT attribution and revenue basis | PAT / revenue; revenue > 0, finite signed PAT; levels are dimensionless fractions and YoY percentage-point change = 100 * (margin_q - margin_q_minus_4). | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | PROPOSED_ONLY |
| PBT_MARGIN | OPTIONAL_COMPONENT | reported PBT; same-period revenue | PBT / revenue, revenue > 0; explicitly before tax and after financing. Not operating margin. | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | PROPOSED_ONLY |
| OPERATING_MARGIN | OPTIONAL_COMPONENT | direct operating-profit numerator; exact excluded-item definition; same-period revenue | No approved formula: POLICY_BLOCKED | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | POLICY_BLOCKED |
| GROSS_MARGIN | OPTIONAL_COMPONENT | direct gross-profit or governed COGS contract; matching revenue/cost scope | No approved formula: POLICY_BLOCKED | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | POLICY_BLOCKED |
| ISSUER_EBITDA_MARGIN | OPTIONAL_COMPONENT | direct issuer EBITDA; disclosed definition; matching revenue | Issuer EBITDA / revenue only after a source-qualified ratio contract; not standardized operating margin. | Five consecutive QUARTER_ONLY fiscal observations q-4..q; exact YoY q/q-4 and QoQ q/q-1; no YTD substitution. | FUTURE_CONTRACT_REQUIRED |

| Wording alternative | Decision |
|---|---|
| Profitability Margin Trajectory | Selected with explicit Net Profit Core, Qualified Margin Context suffix to disclose the changed purpose. |
| Operating Profitability Trajectory | Rejected: unavailable standardized operating-profit contract would make wording misleading. |
| Margin Structure & Profitability Trend | Rejected: implies full cost/margin decomposition that current evidence cannot establish. |

### Rule 29: Entity-Aware Valuation Multiples — Independently Qualified Components

| Diff field | Frozen V1 | Proposed V2 |
|---|---|---|
| Canonical name | Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B | Entity-Aware Valuation Multiples — Independently Qualified Components |
| Registry purpose (verbatim) | Canonical diagnostic checkpoint for Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B. | Preserve independently comparable valuation evidence with explicit component applicability and no automatic cross-component scoring. |
| Actual V1 behavior | P/E drives classification; forward P/E, PEG, EV/EBITDA and P/B are optional calculations in the legacy evaluator. Canonical bridge blocks unsupported forward/share inputs and prevents legacy EV missing-debt/cash zero defaults. | See proposed components and aggregation below. |
| Mandatory input change | V1 source intake and behavior above. | No universal mandatory multiple; AT_LEAST_ONE_READY_APPLICABLE_COMPONENT establishes descriptive availability, not a full valuation verdict. |
| Optional input change | Generic registry corroboration; actual evaluator behavior above. | P/E, P/B, EV/EBITDA, forward P/E and PEG are independently optional; omitted inputs never default to zero. |
| Entity applicability | V1 financial adapter branch gates differ by rule; no universal financial-sector policy. | Financial-sector P/E/P/B require native basis/comparison policy; industrial EV/EBITDA marked not applicable only by an approved classified entity exclusion. |
| Output semantics | V1 result/eligibility and source defaults remain untouched. | Each component uses READY/PARTIAL/NOT_READY/NOT_APPLICABLE/POLICY_BLOCKED presentation aliases; exact underlying insufficiency/conflict remains retained. |
| Reason/source basis | MCA_IND_AS_1, RBI_BANK, RBI_NBFC, IRDAI, ACCEPTED_RESEARCH | Absent EV/EBITDA must not erase valid P/E/PB evidence; fair-value and score conclusions require separate versioned interpretation. |
| Migration risk | Preserve source-defined V1 behavior. | An available multiple is not ATTRACTIVE. No score weighting, forecast or missing-debt/cash fill is authorized. |

Aggregation: `AT_LEAST_ONE_READY_APPLICABLE_COMPONENT`. NOT_READY is a presentation alias for INSUFFICIENT_DATA or EVIDENCE_CONFLICTED with the underlying state/reasons retained; do not collapse conflict. Zero ready components cannot produce a ready rule.

| Component | Proposed role | Exact evidence | Measurement definition (proposal only) | Period contract | Policy availability |
|---|---|---|---|---|---|
| PE | OPTIONAL_COMPONENT | PIT price; positive annual EPS_BASIC; same currency/per-share unit and adjustment basis | PIT price / annual EPS; preserve annual horizon, no implicit forward or TTM conversion. | FULL_YEAR, exact fiscal identity, same statement scope and accounting basis; no TTM substitution. Price cutoff equals execution as_of; actual price session retained. | PROPOSED_ONLY |
| PB | OPTIONAL_COMPONENT | PIT price; exact outstanding shares; positive attributable book equity; share/equity alignment policy | No approved formula: POLICY_BLOCKED | Exact priced capital and balance-date bridge required. | POLICY_BLOCKED |
| EV_EBITDA | OPTIONAL_COMPONENT | approved EV debt/cash/share bridge; direct source-qualified positive EBITDA; formula comparability | No approved formula: POLICY_BLOCKED | Explicit EV cutoff and earnings period. | POLICY_BLOCKED |
| FORWARD_PE | OPTIONAL_COMPONENT | PIT forecast EPS; forecast horizon; revision/source contract; PIT price | No approved formula: POLICY_BLOCKED | Exact forecast availability and horizon. | POLICY_BLOCKED |
| PEG | OPTIONAL_COMPONENT | qualified PE; positive approved growth measure; growth method and unit policy | No approved formula: POLICY_BLOCKED | Growth lookback or forecast horizon must be explicit. | POLICY_BLOCKED |

## Entity applicability matrix

| Rule | NON_FINANCIAL | BANK | NBFC | INSURER | UNKNOWN_NON_COMPARABLE |
|---|---|---|---|---|---|
| 16 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 17 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 19 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 25 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 26 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 29 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |

`STANDARD_BRANCH` means the proposed standard definition exists, conditional
on approval and data. It does not mean ready or active. Financial entities need
`ENTITY_SPECIFIC_BRANCH`; the policies are absent, so their current proposal
cells are `POLICY_BLOCKED`, not fictitious ready branches.
`OPTIONAL_COMPONENT_ONLY` and `NOT_APPLICABLE` are permitted vocabulary,
but no whole-rule cell is given either merely because evidence is missing.

A future exact bank branch may emphasize ROE/ROA and use NIM, asset-quality and
capital-adequacy context. No formulas or diagnostics for those are added.
NBFC and insurer branches remain blocked. Industrial ROCE/EV-EBITDA or gross
margin may be explicitly excluded at **component** level under approved
entity-specific policy; that exclusion does not make all return/valuation
intelligence inapplicable.

Classification requires an exact canonical instrument-to-issuer bridge and
PIT-visible authoritative evidence: regulator status first where applicable,
then statutory reporting framework, official exchange/issuer classification
and authoritative taxonomy. Contradictory effective records are conflicted;
a missing branch is policy-blocked. Names, descriptions, guessed sectors and
absence from a regulator list cannot prove non-financial status. The current
19 unknown entities remain unchanged.

## Proposed component readiness contract

`DiagnosticComponentState` remains a JSON-described proposal, not a new
runtime model. It feeds one canonical diagnostic result.

| State | Meaning |
|---|---|
| READY | Exact approved applicable component policy and all required verified PIT evidence exist; measurement domain is valid. |
| PARTIAL | Some valid submeasurements exist; this cannot satisfy mandatory core completeness. |
| INSUFFICIENT_DATA | Applicable approved definition exists but required evidence or mathematical domain is unavailable. |
| POLICY_BLOCKED | Required formula, entity classification/branch or interpretation policy is absent or unapproved. |
| NOT_APPLICABLE | A verified entity and approved policy explicitly exclude the concept; never missing-data forgiveness. |
| EVIDENCE_CONFLICTED | Unresolved contradictory required evidence, identity, definition or vintage; values are not selected arbitrarily. |

Required fields: `component_id`, `role`, `state`, evidence IDs/fingerprints,
reason codes, confidence with confidence lineage, policy ID/version/fingerprint,
as-of, entity branch, value/unit, measurement period and formula reference.
Unavailable numeric fields remain null. Confidence is null with
`CONFIDENCE_CALCULATION_NOT_APPROVED` unless a verified canonical source carries
a policy-defined confidence value. There is no new numeric confidence calculation.

`MANDATORY_CORE` is required for core completeness. `OPTIONAL_COMPONENT`
never automatically invalidates a complete core by being absent.
`BLOCKING_COMPONENT` is reserved for separately approved categorical blocking
conditions; none is designated here. Rule 19 does not invent a critical-risk
threshold through this role. Verified adverse evidence must remain visible and
may be consumed by an independently approved risk policy.

Aggregation preserves:

1. `core_completeness`: all mandatory components READY; an excluded mandatory
   component needs an explicitly approved alternative branch core, not silent removal.
2. `optional_enrichment_coverage`: ready/applicable counts plus unavailable and
   excluded counts. This is coverage metadata, never a score fraction.
3. `confidence`: source-carried or unavailable; no fabricated average.
4. `blockers`: every missing, conflicted, policy or comparability reason remains
   attached to its component and the diagnostic receipt.
5. Core-ready optional conflict retains valid core measurements and conflict
   disclosure, but cannot claim full component coverage or whole-rule health.
6. Zero usable components cannot produce vacuous readiness. Rule 29 explicitly
   requires at least one READY applicable component for descriptive availability.

Rule 17's `READY_STANDARD_BRANCH` / `READY_ENTITY_SPECIFIC_BRANCH` are
diagnostic presentation aliases for a complete approved branch core.
Rule 25's `CORE_REQUIRED` means `MANDATORY_CORE`; `UNAVAILABLE` is a
presentation state, not a role.
Rule 29's `NOT_READY` alias retains whether the underlying state is
`INSUFFICIENT_DATA` or `EVIDENCE_CONFLICTED`, including the reasons.

Readiness, descriptive measurement and economic classification are separate.
No readiness text maps to `PASS`, `HEALTHY`, `ATTRACTIVE`, a score or capital
authority. Changed V2 semantic verdict adapters remain unapproved. In particular,
an absent optional component neither invalidates the core nor grants a
favourable interpretation. Core-ready values can be useful research evidence
while the score remains unavailable.

## Downstream impact inventory

| Consumer | Actual dependency | Future impact | Required boundary |
|---|---|---|---|
| financial_intake_and_evaluators | Direct; affected IDs 16, 17, 19, 25, 26, 29 | IMPLEMENTATION_UPDATE_REQUIRED | Future explicit V2 dispatch; preserve V1 code path and thresholds. No change now. |
| canonical_execution_and_rehydration | Direct version binding; affected IDs 16, 17, 19, 25, 26, 29 | IMPLEMENTATION_UPDATE_REQUIRED | Current runner authorizes exact canonical-universe-analysis/v1; rehydration stamps current constant. Future version lookup must be exact, never relabel V1 records. |
| decision_score | Direct plus Rule31 indirect; affected IDs 16, 25, 26, 29 | SEMANTIC_REVIEW_REQUIRED; IMPLEMENTATION_UPDATE_REQUIRED; CALIBRATION_REQUIRED | 16/25/26 are optional inputs to 15% earnings component; 29 mandatory in 10% valuation/RR. Unknown state defaults to 5, PARTIAL scores 5; V2 readiness must never enter this mapping. Optional evidence changes component averages even with fixed top-level weights. |
| higher_order_thesis | 16/17/19 -> Rule33; 19/29 -> Rule31; Rule31/32/33 -> Rule34; affected IDs 16, 17, 19, 29 | SEMANTIC_REVIEW_REQUIRED; IMPLEMENTATION_UPDATE_REQUIRED; CALIBRATION_REQUIRED | Presence/non-weak checks can treat new readiness labels as supportive. Keep Rules31-34 definitions unchanged; future adapter must gate V2 semantic eligibility. |
| shared_brain_portfolio | Via canonical diagnostics and synthesized thesis; affected IDs 16, 17, 19, 25, 26, 29 | SEMANTIC_REVIEW_REQUIRED; IMPLEMENTATION_UPDATE_REQUIRED | Preserve exact as_of, strategy/registry version and blockers; no automatic portfolio action or thesis promotion. |
| six_gates | Indirect through scorecard and higher-order evidence; affected IDs 16, 17, 19, 25, 26, 29 | SEMANTIC_REVIEW_REQUIRED; CALIBRATION_REQUIRED | No new direct rule thresholds or gate changes. Require version-compatible complete score/evidence; never treat partial fundamental readiness as capital authority. |
| long_term_shadows | Indirect dossier and financial evidence lineage; no direct six-ID formula mapping; affected IDs 16, 17, 19, 25, 26, 29 | SEMANTIC_REVIEW_REQUIRED | Reuse same dossier; V2 coverage cannot satisfy missing family parameters. Existing financial-sector N/A vocabulary needs compatibility review; never copy it into V2 missing-policy semantics. |
| raw_evidence_stores | No formula/consumer change in proposal; affected IDs 16, 17, 19, 25, 26, 29 | NO_IMPACT | Facts, filings, provider integrations and storage are untouched; future acquisition separate. |

The exact paths and searched source symbols are part of the machine inventory.
The most material findings are:

- [Score engine](../../app/scoring/engine.py): 16/25/26 feed the 15% earnings
  component as optional rules; 29 is mandatory with 45 in the 10% valuation/RR
  component. 17/19 are not direct members of that component configuration,
  though 19/29 affect risk Rule 31. The evaluator's descriptive contribution
  map is not the actual score aggregation configuration.
- Current score behavior maps unknown text to 5 and `PARTIAL` to 5, and
  averages available rule values inside a component. Adding newly usable
  evidence can therefore change score behavior without changing top-level
  weights. Future V2 readiness must be kept out of this mapping until a
  versioned interpretation adapter and shadow calibration are approved.
- [Synthesis](../../app/diagnostics/synthesis.py): Rule 33 requires
  16/17/18/19/23 and treats only specific strings as weak. New readiness text
  must not become supportive by omission. Rule 31 reads 19/29; Rule 34 uses
  31/32/33. Rule 32's direct structure inputs are unaffected, while its
  evidence/lineage remains bound to one execution.
- [Six Gates](../../app/portfolio/canonical_six_gates_activation.py) receives
  the exact scorecard and registry lineage. No direct six-rule formula is
  introduced. Future V2 score compatibility and calibration require review;
  gate thresholds and evidence-only authority remain frozen.
- Long-term shadows preserve the existing dossier and family parameters.
  Some existing sector branches label missing family policies N/A. This is a
  compatibility issue to review before V2 integration; it is not copied into
  the new component contract and no shadow source is changed here.

Classification is future impact; all consumers are unchanged in this slice.
There is no second scoring engine, rule vote, or portfolio operation.

## Horizon impact

The frozen
[Rule × Horizon × Timeframe candidate](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1.md)
currently has machine status `CANDIDATE_NOT_ACTIVE`; it must not be described
as an active policy. Its fingerprint remains
`sha256:bc1f7548b372738d69b72c2e54afdc34c9f10929aee9a10d834ce99cb8d43d8a`.

| Rule | SHORT_TERM | POSITIONAL | LONG_TERM | Technical profile |
|---|---|---|---|---|
| 16 | CONTEXT | APPLICABLE | APPLICABLE | None |
| 17 | CONTEXT | APPLICABLE | APPLICABLE | None |
| 19 | APPLICABLE | APPLICABLE | APPLICABLE | None |
| 25 | CONTEXT | APPLICABLE | APPLICABLE | None |
| 26 | CONTEXT | APPLICABLE | APPLICABLE | None |
| 29 | CONTEXT | APPLICABLE | APPLICABLE | VALUATION_PRICE_CONTEXT |

No applicability or timeframe change is proposed. The changed rule names,
parent references and entity-branch gating need an explicitly versioned
successor policy before future V2 consumption. Rule 29's valuation price
context never means intraday earnings. No new horizons are created.

## Future evidence contracts

`ISSUER_REPORTED_FINANCIAL_RATIO` remains unimplemented. For Rules 17, 19 and
26 it may initially enter only as exact formula-matched corroboration or
optional context. It cannot satisfy a mandatory parent-fact requirement.
Future canonical use requires separately approved ratio and rule policies.
Retain ratio type/value, period/scope, source filing/authority, publication,
receipt/PIT visibility, numerator/denominator definitions, formula fingerprint,
comparability state and immutable revision lineage. A text fingerprint alone
does not prove economic equivalence. DSCR remains distinct from interest coverage.

`HSI_STANDARDIZED_OPERATING_EARNINGS` is a generic placeholder with
`formula = null`. Future approval requires immutable parent fact IDs, formula
version, scope, period identity, compatible units/scale/currency, vintage, PIT
eligibility, deterministic replay and conflict handling. It can never be stored
or displayed as issuer-reported EBITDA/EBIT. No derivation or ratio ingestion
occurs here.

## Migration, replay and approval boundary

V1 outputs, scorecards, gates, paper trades, decisions and outcomes retain their
original registry/strategy/policy identity. V2 activation may not recompute or
overwrite them. An explicit requested V2 research replay creates distinct
version-labelled results and comparisons, retaining V1. Retired versions remain
retrievable for replay.

The current rehydration path stamps `DIAGNOSTIC_REGISTRY_VERSION`; simply
changing that constant later would mislabel old results. Future implementation
must resolve the stored immutable execution/strategy version. The current
runner's exact V1 authorization must also remain intact.

Governance must explicitly decide the three-component Rule 16 core; Rule 17's
independent ROE and removal of the ending-equity fallback; Rule 19's D/E core
and optional coverage; Rule 25's complete three-component core; Rule 26's new
net-profit scope and proposed measurement; and Rule 29's independent availability.
The proposal does not approve these decisions.

Before future ACTIVE: approve exact fingerprint, bind strategy/policy versions,
implement explicit adapters, test V1 replay and V2 behavior, run full regression
and shadow evaluation, then create a time-bounded activation receipt. Numerical
classification thresholds and calibration for changed semantics remain deferred;
that is a disclosed activation gate, not an ambiguity in this proposal's scope.

Future data needs include entity classifications, six-year annual and five-quarter
histories, exact balance/attribution definitions, formula-qualified issuer
ratios, share/price/book alignment and licensed estimates if separately approved.
`DATA_BUILD_VS_BUY_AUDIT_V1` is mandatory before material acquisition. This
proposal requires no acquisition.

**Exactly one next continuation:**
`FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL`.
It is not started here.

## Validation and fingerprint protocol

The dedicated
[proposal tests](../../tests/unit/test_fundamental_diagnostic_registry_v2_proposal.py)
verify exact IDs, parent blobs/semantics, unchanged 55 definitions, six-rule
schema, entity matrix, component roles/states/examples, source/downstream
inventory, deterministic replay and tamper detection. The proposal fingerprint
is SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators,
ASCII escapes, no NaN), excluding only `proposal_fingerprint`. Array ordering
is normative. Parent-rule fingerprints cover the full dataclass metadata.
No system time, locale, environment or database is part of fingerprint input.

Full backend regression is unnecessary because no production runtime code is
changed. Local Markdown links and whitespace are checked. Any active-runtime
change would be scope drift and must block this proposal commit.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
NO_SILENT_REGISTRY_REWRITE = TRUE
NO_SYNTHETIC_REPORTED_FACTS = TRUE
AI_DECISION_AUTHORITY = FALSE
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 = FROZEN
DATA_BUILD_VS_BUY_AUDIT_V1 = MANDATORY_BEFORE_MATERIAL_FINANCIAL_ACQUISITION
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```
