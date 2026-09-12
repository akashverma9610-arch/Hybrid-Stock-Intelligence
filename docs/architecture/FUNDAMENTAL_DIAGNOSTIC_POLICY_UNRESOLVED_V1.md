# Fundamental Diagnostic Policy Resolution — Research V1

**Status:** `RESEARCH_COMPLETE / FUNDAMENTAL_REGISTRY_V2_REQUIRED / NOT_ACTIVE`
**Research policy:** `fundamental-diagnostic-policy-unresolved-research-v1`

## Decision outcome

**Outcome: C — `FUNDAMENTAL_REGISTRY_V2_REQUIRED`.**

The evidence resolves the principal ambiguity: HSI must not repair absent
EBITDA/EBIT coverage by relabelling PBT, PBT plus finance cost, DSCR, or another
issuer-specific ratio. Rules 16 and 26 have material canonical-name/input
mismatches; changing either requires a governed registry version. Rule 19 would
also require V2 if it moves from jointly required leverage/coverage inputs to
component-level outcomes.

**Exactly one next continuation:** `FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSAL`.
It is a policy/governance proposal that can use current evidence. It is not
started here and does not trigger data acquisition. If a later V2 decision
requires material acquisition of ratios, balance-sheet inputs, entity evidence,
or longer history, `DATA_BUILD_VS_BUY_AUDIT_V1` is mandatory first.

## Primary-source receipt

| Source | Claim used | Bounded conclusion |
|---|---|---|
| MCA, [Schedule III Amendment notification, 24 March 2021](https://www.mca.gov.in/Ministry/pdf/ScheduleIIIAmendmentNotification_24032021.pdf) | The applicable Schedule III ratio disclosure includes debt-equity, DSCR, ROE, ROCE and return on investment, and requires the company to explain numerator and denominator items. | Ratio labels alone do not establish one universal formula. |
| ICAI, [Guidance Note on Division II — Ind AS Schedule III](https://kb.icai.org/pdfs/PDFFile5b27857548bee2.71295102.pdf) | Schedule III/Ind AS presentation governs financial-statement presentation and disclosure context. | It supports source lineage, scope and period checks; it does not license formula inference. |
| SEBI, [official issuer filing example](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2024/1727675578109.pdf) | An issuer describes DSCR as PBT + finance cost + depreciation over debt service and ROCE as PBT + finance cost − other income over a company-selected capital measure. | Reported DSCR/ROCE definitions can differ from HSI’s current semantics. |
| NSE, [annual report ratio example](https://nsearchives.nseindia.com/corporate/NAGREEKEXP_29082025173738_Annual_Report_Final.pdf) and [integrated filing example](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152826_24042026225714_iXBRL_WEB.html) | Official issuer filings expose numerator/denominator details, while ratios can be reproduced in notes because they have no designated XBRL rows. | Future ratio ingestion must retain the source filing and formula definition; it cannot assume a universal taxonomy field. |
| RBI, [Financial Statements — Presentation and Disclosures Directions](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html) and [bank statement-format evidence](https://systemhealth.rbi.org.in/Scripts/bs_viewcontent.aspx_Id%3D3093.html) | Bank presentation separately identifies net interest income, fees/commissions, trading income, impairments and other income. | Interest economics are core banking activity; industrial EBITDA/interest-coverage logic is not portable. |
| RBI, [NBFC disclosure requirements](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12292) | NBFC financial reporting follows a distinct prudential and disclosure context. | NBFC finance cost is not automatically industrial financing. |
| IRDAI, [financial-statement preparation](https://irdai.gov.in/document-detail?documentId=374643) and [insurance reporting regulation detail](https://irdai.gov.in/hi/document-detail?documentId=366477) | Insurers use policyholder revenue accounts, shareholder profit/loss, separate receipts/payments and solvency-related reporting. | Industrial EBITDA/EV-EBITDA and margin semantics must not be forced onto insurers. |

The source receipt demonstrates disclosure availability and issuer formula
variation; it does not approve a new accounting formula, metric, threshold, or
diagnostic outcome.

## Schedule III ratio finding

Schedule III makes disclosure of named ratios and numerator/denominator
explanations valuable primary evidence **where the disclosure is applicable**.
It does not prescribe a single numerator and denominator for every named ratio.
The official SEBI/NSE examples confirm material variations in debt definitions,
capital-employed definitions, debt-service denominators, treatment of other
income, and use of PBT/finance-cost/D&A components.

Accordingly, a formula fingerprint can establish that two reported ratios have
the same disclosed formula payload; it cannot establish cross-company
comparability when either formula, scope, entity type, period basis, adjustment
or source definition is missing or differs.

## Candidate non-active issuer-ratio evidence contract

`ISSUER_REPORTED_FINANCIAL_RATIO` is a future **reported-evidence** contract,
not a derived `FinancialFact` and not a substitute for an HSI calculation.

| Candidate field | Required policy condition |
|---|---|
| `ratio_type`, `value`, `period_end`, `statement_scope` | Exact issuer label/value, period and scope; no label normalization by guesswork. |
| `source_filing_id`, `source_authority`, `published_at`, `received_at` | Immutable official filing identity and PIT visibility. |
| `pit_visibility` | Explicit publication/receipt selection state for the ratio revision at the requested as-of; period end alone is never PIT visibility. |
| `numerator_definition`, `denominator_definition`, `formula_fingerprint` | Source-declared definitions must be complete, normalized only as text/structure, and fingerprinted. Missing definition is not comparable. |
| `revision_lineage` | Revisions remain immutable and PIT-selected. |
| `comparability_status` | At minimum `FORMULA_MATCHED`, `FORMULA_UNAVAILABLE`, `FORMULA_CONFLICTED`, `ENTITY_BRANCH_REQUIRED`, or `PIT_UNAVAILABLE`; no silent promotion. |

**Architecture conclusion:** a distinct future canonical ratio contract is
required. `FinancialFact` is an accounting-fact contract; its existing
`DERIVED` state requires HSI parent facts and must not be used to disguise an
issuer-reported ratio as HSI-derived. Existing generic research evidence is
also insufficient because it lacks the explicit ratio, formula, revision and
comparability identity above. No contract is implemented here.

## Entity applicability

| Entity type | Rules 16 / 25 | Rules 17 / 19 | Rule 26 | Rule 29 |
|---|---|---|---|---|
| `NON_FINANCIAL` | Revenue/PAT/EPS are factual candidates; EBITDA remains optional enrichment. | Existing ROE/D/E parent paths may remain factual only where exact inputs exist. ROCE/interest-coverage remain blocked without their own approved semantics. | `POLICY_REDESIGN_REQUIRED`; no PBT/PAT relabel. | P/E remains independent; EV/EBITDA optional/policy-blocked. |
| `BANK` | Raw results may be observed but need a bank branch before diagnostic interpretation. | NIM, ROA/ROE, asset quality, capital adequacy and officially defined operating measures require a separate policy. | Industrial operating/gross margin is not applicable. | Sector-specific valuation branch required. |
| `NBFC` | Raw results may be observed but need an NBFC branch. | Finance cost cannot be treated as ordinary industrial financing. | Industrial margin requires a branch. | Sector-specific valuation branch required. |
| `INSURER` | Policyholder/shareholder reporting requires an insurer branch. | Solvency and insurance-specific measures require a branch. | Industrial margin is not applicable. | Industrial EV/EBITDA is not applicable; insurer valuation branch required. |
| `UNKNOWN_NON_COMPARABLE` | `POLICY_UNRESOLVED` | `POLICY_UNRESOLVED` | `POLICY_UNRESOLVED` | `POLICY_UNRESOLVED` |

The minimum future identity evidence for an unknown entity is an exact,
PIT-visible issuer/security bridge plus an official exchange classification,
applicable Schedule III division, or exact RBI/IRDAI registration/linkage.
Company name, business description, or regulator absence are insufficient.

## Rule policy resolution

### Rule 16 alternatives assessed

| Family | Accounting meaning and comparability | Evidence/stability assessment | Capital-structure, non-operating and adjustment sensitivity | Name / registry consequence | Decision |
|---|---|---|---|---|---|
| `16-A KEEP_EXISTING_HARD_REQUIREMENT` | The existing name accurately says EBITDA, but only if direct, standardized EBITDA is available. | Direct reported EBITDA is zero in the current corpus, so the six-year four-metric requirement is not currently testable. | No new risk, but total unavailability is not a semantic repair. | No change if retained exactly. | Not selected as a universal operational policy. |
| `16-B REPLACE_WITH_PBT` | PBT includes finance and non-operating effects and is not operating earnings. It is not comparable to EBITDA. | PBT coverage does not cure the semantic mismatch. | High capital-structure and other-income sensitivity; issuer adjustments can also differ. | Materially false under the current name; would require V2 even if renamed. | Rejected. |
| `16-C HSI_DERIVED_OPERATING_EARNINGS` | Could be comparable only after an approved numerator, excluded items, entity branches, restatement treatment and parent-fact contract. | Current corpus cannot support a standardized, longitudinal measure. | The exact sensitivity depends on the unapproved formula; no candidate may be named EBITDA or EBIT. | New named metric and V2 would be required. | Deferred; no formula is approved. |
| `16-D ENTITY_SPECIFIC_BRANCHES` | Necessary for financial-sector accounting, but each branch needs its own purpose and evidence contract. | Non-financial, bank, NBFC and insurer inputs are not interchangeable; 19 entity types are presently unknown. | Prevents the error of treating finance cost or policyholder accounts as industrial operating items. | V2 for a revised rule; separate policy for every branch. | Required future design constraint, not a current evaluator. |
| `16-E FEWER_MANDATORY_DIMENSIONS_PLUS_OPTIONAL_EBITDA` | Revenue, PAT and EPS remain distinct reported trends; EBITDA becomes explicitly optional enrichment rather than a substitute. | The current receipt finds at least six annual Revenue/PAT/EPS coordinates for 8 of 10 `NON_FINANCIAL` and 7 of 19 `UNKNOWN_NON_COMPARABLE` instruments; it does not itself prove fiscal-continuity eligibility. | Does not eliminate PAT/EPS comparability or entity-branch issues; it only avoids false operating-earnings labelling. | A truthfully renamed core trend policy requires V2. | Selected recommendation for a future V2 proposal, subject to entity branches. |

The ranking is accounting correctness first, then source authority, comparability,
PIT safety, availability, simplicity and testability. It is not a coverage-led
selection and does not authorize a changed Rule 16 today.

| Rule | Current semantic / blocker | Final policy recommendation | Reported-ratio eligibility | Derived-metric eligibility | Registry requirement |
|---|---|---|---|---|---|
| 16 | Five-Year Revenue, EBITDA, PAT, EPS CAGR; direct EBITDA is absent. | Do not keep a universal direct-EBITDA hard requirement. Do not substitute PBT. V2 should propose a precisely renamed core-accounting trend policy with Revenue/PAT/EPS and optional reported operating-earnings enrichment, plus entity branches. | None. | Future named operating-earnings measure remains unapproved. | `CANONICAL_DIAGNOSTIC_REGISTRY_V2_REQUIRED` |
| 17 | ROCE + ROE; direct EBIT absent. | Retain existing ROE parent-fact meaning only where current non-financial evidence qualifies. Do not consume issuer ROE/ROCE as current rule inputs; they are formula-matched enrichment candidates only. Do not define an HSI ROCE now. | Optional future enrichment only, after exact formula match. | No standardized ROCE selected. | `NO_REGISTRY_CHANGE` while semantics remain unchanged; V2 if either formula/input changes. |
| 19 | Debt/equity, net debt, interest coverage; total debt/EBIT absent. | Keep debt-equity, net debt and interest coverage semantically independent. Do not replace interest coverage with DSCR. A future move to component-level partial outcomes requires V2. | Future formula-matched debt/equity can corroborate, not replace current parent-fact semantics. DSCR is separate evidence only. | Net debt only after an approved exact debt/cash balance policy; no derivation now. | `NO_REGISTRY_CHANGE` if unchanged; `CANONICAL_DIAGNOSTIC_REGISTRY_V2_REQUIRED` for partial-component semantics. |
| 25 | Latest quarterly Revenue, EBITDA, PAT, EPS; current evaluator permits metric-level partiality. | EBITDA absence must `REDUCE_COMPONENT_COVERAGE`, not block the whole rule and not become a synthetic value. Revenue/PAT/EPS remain current factual components; entity interpretation stays branch-gated. | None. | No operating-earnings derivation. | `POLICY_ONLY_VERSION_CHANGE` to document component policy; V2 only if mandatory-core semantics change. |
| 26 | Operating Margin & Gross Margin Trajectory; legacy path effectively uses EBITDA margin and has no gross-margin calculation. | Do not call PBT or PAT margin operating margin. No standardized operating/gross margin is presently available. Keep fail-closed until V2 proposes a truthful name and exact metric contracts. | Issuer margin is enrichment only with exact definition. | No approved numerator. | `CANONICAL_DIAGNOSTIC_REGISTRY_V2_REQUIRED` |
| 29 | P/E, forward P/E, PEG, EV/EBITDA, P/B; P/E currently drives classification while other components are policy-blocked. | Treat components independently. Absence of EV/EBITDA blocks only that component, not P/E. Do not invent forecasts, shares, or EBITDA. Financial-sector valuation requires branches. | Reported ratio evidence may enrich, never silently renormalize scoring. | EV/EBITDA remains unavailable. | `NO_REGISTRY_CHANGE` |

## Final six-rule policy matrix

The matrix is a research-policy resolution, not a registry mutation, evaluator
specification, formula approval or score change. “Potential coverage” means
only exact, PIT-selected parent-fact presence under the read-only receipt.

| Rule | Current semantic / blocker | Non-financial proposed semantic | Bank / NBFC / insurer applicability | Unknown behavior | Mandatory vs optional inputs | Reported-ratio / derived-metric eligibility | Registry change | Current feasibility | Remaining gap | Policy confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 16 | Revenue, EBITDA, PAT, EPS CAGR; no direct EBITDA. | Future renamed Revenue/PAT/EPS core trend with optional reported operating-earnings enrichment. | Separate branches; none is authorized. | `POLICY_UNRESOLVED`. | Future core: Revenue, PAT, EPS; optional: formula-matched reported operating earnings. | Reported operating measures: enrichment only; derived measure: unapproved. | `CANONICAL_DIAGNOSTIC_REGISTRY_V2_REQUIRED`. | 8/10 non-financial and 7/19 unknown have six annual Revenue/PAT/EPS parent coverage; strict EBITDA 0. | Entity type, revised name/policy, operating-earnings contract. | High for prohibition; medium for future core. |
| 17 | ROCE + ROE; direct EBIT absent. | Preserve current ROE parent path only where existing facts already meet it; no new ROCE. | Separate policies required. | `POLICY_UNRESOLVED`. | Existing ROE parents remain exact PAT/equity facts; ROCE is not newly defined. | Reported ROE/ROCE: formula-matched enrichment only; new derived ROCE: unapproved. | `NO_REGISTRY_CHANGE` if untouched; V2 for any changed formula/input. | ROE parent alignment: 10/10 non-financial, 12/19 unknown; ROCE alignment 0. | Formula consistency, entity applicability and required historical averaging semantics. | High for preservation; low for extension. |
| 19 | Debt/equity, net debt, interest coverage; total debt and EBIT absent. | Keep three independent meanings; no DSCR substitution. | Separate capital/liquidity policies required. | `POLICY_UNRESOLVED`. | Existing rule stays joint as currently governed; any partial-component rule is future policy. | Formula-matched reported D/E may corroborate; DSCR separate evidence; net debt derivation unapproved. | `NO_REGISTRY_CHANGE` if untouched; V2 for partial components. | D/E 0, net debt 0, interest coverage 0 in every bucket. | Exact debt/cash contracts, EBIT, finance-cost/interest scope, sector branches. | High for separation; low for coverage. |
| 25 | Quarterly Revenue, EBITDA, PAT, EPS; metric-level partiality already exists. | Preserve factual Revenue/PAT/EPS components; EBITDA absence reduces component coverage. | Branch-gated interpretation required. | `POLICY_UNRESOLVED`. | Current components: Revenue, PAT, EPS where PIT-visible; optional enrichment: EBITDA/approved operating earnings. | No reported ratio; no derivation. | `POLICY_ONLY_VERSION_CHANGE` for explicit component wording; V2 only if core requirements change. | Revenue/PAT/EPS components: 10/10 non-financial, 16/19 unknown; EBITDA 0. | Entity branches and any revised mandatory-core rule. | High. |
| 26 | Named operating and gross-margin trajectory; legacy route relies on EBITDA margin, gross margin absent. | Do not interpret until V2 supplies a truthful named numerator/denominator contract. | Industrial margin not applicable; each financial branch requires own policy. | `POLICY_UNRESOLVED`. | No current mandatory/optional metric is approved for the named rule. | Formula-matched issuer margin only future enrichment; no derivation. | `CANONICAL_DIAGNOSTIC_REGISTRY_V2_REQUIRED`. | EBITDA-margin parents 0; gross-margin parents 0. | Exact operating/gross-margin semantics, costs, entity branches. | High for fail-closed conclusion. |
| 29 | P/E, FPE, PEG, EV/EBITDA, P/B; only P/E has an existing financial input path. | Component-level applicability; retain P/E independently, do not fabricate other components. | Financial-sector valuation branches required for P/B and other components. | `POLICY_UNRESOLVED`. | P/E requires its already-governed PIT price/EPS inputs; each other component has its own inputs. | Issuer ratios may enrich only; EV/EBITDA derivation unapproved. | `NO_REGISTRY_CHANGE`. | Annual EPS financial input: 10/10 non-financial, 18/19 unknown; no proof of P/E readiness; FPE/PEG/EV-EBITDA/PB 0. | PIT price, forecasts, shares/equity/value definitions, sector policies. | High for component separation. |

### Required answers

1. **Rule 16 EBITDA requirement:** no; not universal. It cannot be replaced by
   PBT without V2 semantic governance.
2. **Rule 16 replacement/context:** V2 should decide a truthfully renamed
   Revenue/PAT/EPS core plus optional reported operating-earnings enrichment;
   future standardized derivation remains separate.
3. **Issuer ROCE/ROE:** not current canonical rule input. Formula-complete,
   formula-matched ratios can be future issuer-reported enrichment.
4. **HSI standardized ROCE:** no; numerator/denominator/entity policy remains
   unapproved.
5. **Reported debt-equity:** future formula-matched corroborating evidence only;
   not a replacement for the current canonical parent-fact path.
6. **DSCR:** separate from interest coverage, because its denominator includes
   debt service/principal and issuer numerator definitions vary.
7. **Rule 25 EBITDA:** optional enrichment; its absence reduces component
   coverage rather than blocking the current metric-level-partial rule.
8. **Rule 26 meaning:** unresolved under the current name; no metric may be
   relabelled to preserve coverage. V2 redesign is required.
9. **Rule 29 EV/EBITDA:** optional/component-level only; its absence must not
   block P/E.
10. **Financial-sector branches:** all six rule areas need explicit branches
    before bank/NBFC/insurer interpretation.
11. **Registry V2:** required for Rules 16 and 26, and for Rule 19 only if
    component-level partial semantics are adopted.
12. **Future Build-vs-Buy audit fields:** official filing/issuer identity,
    filed ratio type/value/period/scope, numerator/denominator text and formula
    fingerprint, revision/PIT timestamps, Schedule III division, exact
    regulator classification, annual/quarterly history, balance-sheet parent
    facts, units/scales/currency and data licence/commercial terms.

## Current-data feasibility receipt

The new read-only audit ran at `2026-09-12T00:00:00+00:00` against the current
31-instrument official-BSE population using the frozen factual-vintage selector.
It uses SQLite `mode=ro` and `PRAGMA query_only=ON`; it calculates neither
ratios nor derived earnings values. Counts are potential exact-parent readiness,
not diagnostic results or policy eligibility.

| Entity bucket | Denominator | Rule 16 Revenue/PAT/EPS six-year core | Rule 17 ROE parent alignment | Rule 19 D/E, net-debt, interest-coverage parents | Rule 25 Revenue/PAT/EPS quarterly components | Rule 25 EBITDA | Rule 26 EBITDA/gross parents | Rule 29 annual EPS financial input |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `NON_FINANCIAL` | 10 | 8 | 10 | 0 / 0 / 0 | 10 / 10 / 10 | 0 | 0 / 0 | 10 |
| `BANK` | 2 | 0 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 | 0 |
| `NBFC` | 0 | 0 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 | 0 |
| `INSURER` | 0 | 0 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 | 0 |
| `UNKNOWN_NON_COMPARABLE` | 19 | 7 | 12 | 0 / 0 / 0 | 16 / 16 / 16 | 0 | 0 / 0 | 18 |

There are zero stored issuer-reported-ratio rows because no such canonical
contract exists. There are zero direct EBIT/EBITDA facts, zero total-debt
facts, and no approved reported-ratio or forward-estimate source in this
audit. A financial-only annual EPS count is not proof of P/E readiness because
the required PIT-aligned price input is outside this accounting-only receipt.

Report ID: `fundamental-diagnostic-policy:80380f5c54fd8a63eac243e3d48d9833`
Fingerprint: `sha256:3f3312a61476b25444712c571c272498285686e7ea07397b2cf7d04cc05add48`

Strict historical PIT can only reduce these results. A fact whose period ended
before a cutoff is excluded if it was published or received later.

## Policy-minimality ranking

1. Preserve current factual accounting facts and component-level Rule 29
   behavior; this has the strongest authority and lowest semantic risk.
2. Keep reported ratios as future formula-fingerprinted enrichment, not as
   interchangeable canonical calculations.
3. Propose Registry V2 for the two material name/input mismatches: Rules 16
   and 26; consider Rule 19 only if its component structure changes.
4. Defer any non-financial operating-earnings derivation and all financial
   sector branches until separately governed.

This order values accounting correctness, source authority, comparability and
PIT safety before data coverage. It makes no threshold, score, backtest or
performance decision.

## Build-vs-Buy gate

`HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1` remains frozen:
**rent commodity data where reliable and commercially usable; own
decision-critical truth and intelligence.** No material raw financial-data
acquisition is authorized by this receipt. The required provider/data decision
must occur through `DATA_BUILD_VS_BUY_AUDIT_V1` before any such expansion.

## Frozen safeguards

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
NO_SILENT_REGISTRY_REWRITE = TRUE
NO_SYNTHETIC_REPORTED_FACTS = TRUE
AI_DECISION_AUTHORITY = FALSE
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 = FROZEN
DATA_BUILD_VS_BUY_AUDIT_V1 = MANDATORY_BEFORE_MATERIAL_FINANCIAL_ACQUISITION
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```

- Reported ratio ≠ derived metric.
- Issuer-defined non-GAAP metric ≠ standardized accounting fact.
- PBT margin ≠ operating margin; PAT margin ≠ operating margin.
- DSCR ≠ interest coverage.
- Missing evidence ≠ `NOT_APPLICABLE`.
- Entity-specific applicability ≠ missing-data forgiveness.
- Rule semantic change requires governance/versioning.
- More coverage is not a reason to weaken financial meaning.

## Sources

1. Ministry of Corporate Affairs. [Schedule III Amendment notification, 24 March 2021](https://www.mca.gov.in/Ministry/pdf/ScheduleIIIAmendmentNotification_24032021.pdf).
2. Institute of Chartered Accountants of India. [Guidance Note on Division II — Ind AS Schedule III](https://kb.icai.org/pdfs/PDFFile5b27857548bee2.71295102.pdf).
3. Securities and Exchange Board of India. [Official issuer ratio-definition example](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2024/1727675578109.pdf).
4. National Stock Exchange of India. [Official annual-report ratio disclosure example](https://nsearchives.nseindia.com/corporate/NAGREEKEXP_29082025173738_Annual_Report_Final.pdf).
5. Reserve Bank of India. [Financial Statements — Presentation and Disclosures Directions](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html).
6. Insurance Regulatory and Development Authority of India. [Financial-statement preparation detail](https://irdai.gov.in/document-detail?documentId=374643).
