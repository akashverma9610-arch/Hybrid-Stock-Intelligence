# EBITDA / EBIT Diagnostic Policy Alternatives — Research V1

**Status:** `RESEARCH_COMPLETE / POLICY_NOT_APPROVED / NOT_ACTIVE`
**Research policy:** `ebitda-ebit-diagnostic-policy-alternative-research-v1`
**Scope:** primary-source accounting and regulated-entity research plus a
read-only, PIT-vintage feasibility audit. This document does not define a
metric, change a diagnostic, or activate a policy.

## Decision

The direct-source audit established that the current exact-identity corpus has
no qualified company-level reported `EBITDA` or `EBIT`. This is an HSI corpus
coverage finding, not a claim that no Indian issuer ever reports either term.

The current research finds that an industrial-company construct can be
*described* from reported components, but cannot yet be called EBIT or EBITDA
or used to relax Rules 16, 17, 19, 25, 26, or 29. Accounting presentation and
issuer-defined KPI evidence do not establish one cross-company operating
earnings definition. The measured component coverage is therefore not policy
approval.

**Exactly one proposed next slice:**
`FUNDAMENTAL_DIAGNOSTIC_POLICY_UNRESOLVED_V1`.

That slice is not started by this research receipt. It must first choose
whether a future non-financial derivation policy, financial-sector
applicability policy, or versioned diagnostic redesign is justified. The
current evidence does not safely choose among them.

## Primary-source receipt

| Authority | Source and claim supported | Research conclusion |
|---|---|---|
| MCA | [Schedule III notification](https://www.mca.gov.in/Ministry/pdf/NotificationScheduleIII_12102018.pdf) | Indian presentation prescribes profit-or-loss statement scaffolding, including revenue/other income, finance cost, depreciation/amortisation, tax and profit lines; it does not create one universal EBITDA or EBIT line. |
| ICAI | [Guidance Note on Division II — Ind AS Schedule III](https://kb.icai.org/pdfs/PDFFile5b27857548bee2.71295102.pdf) | Division II presentation supports standard accounting-line provenance, but does not turn a market KPI label into a universally defined measure. |
| SEBI | [Revised formats for Ind AS financial results](https://www.sebi.gov.in/legal/circulars/jul-2016/revised-formats-for-financial-results-and-implementation-of-ind-as-by-listed-entities_32788.html) and [LODR regulations](https://www.sebi.gov.in/web/?file=https%3A%2F%2Fwww.sebi.gov.in%2Fsebi_data%2Fattachdocs%2Fdec-2025%2F1766551151465.pdf) | Exchange-filed, regulated financial results are the appropriate primary route for reported accounting facts; regulated result presentation alone does not standardize EBITDA/EBIT. |
| SEBI issuer filing | [SEBI-hosted 2025 offer document](https://www.sebi.gov.in/sebi_data/attachdocs/apr-2025/1743751804884_762.pdf) | A reported KPI formula uses pre-exceptional PBT plus finance cost and D&A, less other income; another presentation also treats associate/JV profit separately. The filing itself notes that KPIs need not be Ind AS-defined or Ind AS-presented. This is direct formula-variation evidence, not a universal rule. |
| SEBI issuer filing | [SEBI-hosted InvIT document](https://www.sebi.gov.in/web/?file=/sebi_data/attachdocs/apr-2021/1619501607293.pdf) | A second official filing uses a materially different EBIT/EBITDA presentation involving comprehensive income, finance costs, tax, D&A/impairment and investment-income adjustments. It proves variation; it is not generalized to ordinary companies. |
| NSE | [XBRL information](https://www.nseindia.com/static/companies-listing/xbrl-information), [integrated financial filing](https://www.nseindia.com/companies-listing/corporate-integrated-filing?symbol=BSE&tabIndex=equity), and [2025 XBRL filing circular](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Circular_02042025_0.pdf) | NSE is a primary structured-filing route. Structured availability does not remove the need for exact instrument, period, scope, and semantic validation. |
| RBI | [Banks: financial-statement presentation and disclosures](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html) and [NBFC disclosure requirements](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12292) | Interest income and interest expense are central banking/NBFC economics and regulatory presentation has separate requirements. An industrial add-back formula cannot be applied by default. |
| IRDAI | [Insurance financial-statement preparation](https://irdai.gov.in/document-detail?documentId=374643) and [insurance financial-statement regulation detail](https://irdai.gov.in/hi/document-detail?documentId=366477) | Insurer reporting uses policyholder revenue accounts, shareholder profit/loss and insurance-specific statements. Industrial EBITDA/EBIT is not a default insurer metric. |

No source above approves an HSI formula. The source hierarchy remains MCA/ICAI,
SEBI/exchange filings, RBI/IRDAI, then secondary literature only for questions
that primary material cannot answer.

## Accounting-line baseline

For ordinary Ind AS non-financial company presentation, HSI can retain factual
reported facts for the following when exactly sourced, scoped, period-identified
and PIT-visible: revenue from operations, other income, finance cost,
depreciation/amortisation, profit before exceptional items where separately
reported, exceptional items, PBT, tax and PAT. A line’s availability is not a
license to classify it as operating, recurring, or comparable across issuers.

| Item | Factual presentation role | Can support a future deterministic parent set? | Prohibited shortcut |
|---|---|---|---|
| Revenue from operations | Reported top-line input | Yes, with existing scope/period/PIT controls | Treating all revenue economics as comparable across financial sectors |
| Other income | Separately reported presentation line | Yes, as a retained parent fact | Automatically subtracting it as non-operating |
| Finance cost | Reported presentation line | Yes, as a retained parent fact | Treating it as pure interest expense or as industrial financing for banks/NBFCs |
| D&A | Reported presentation line | Yes, as a retained parent fact | Assuming its add-back establishes EBITDA |
| Pre-exceptional profit / exceptional items | May be separately reported | Only where exact source semantics exist | Assuming PBT consistently excludes exceptional items |
| PBT, tax, PAT | Reported profit/tax outcomes | Yes, as accounting facts | Reclassifying PBT as operating earnings |
| EBITDA / EBIT | KPI or issuer-defined measure when disclosed | Optional reported enrichment only, after exact source validation | Calling it a universal Ind AS line or canonical cross-company fact |

### Formula-family evidence

The SEBI-hosted issuer examples show at least these non-equivalent families:

| Family | Example treatment | Consequence |
|---|---|---|
| Reported KPI formula | Pre-exceptional PBT, add finance cost and D&A, subtract other income | Issuer-defined; not equivalent to a universal EBITDA definition. |
| Reported KPI with equity-accounting treatment | Similar construction with associate/JV profit separated | Same label can have additional adjustments. |
| Infrastructure/InvIT-style formula | Comprehensive-income and investment-income/impairment adjustments | A reported EBIT/EBITDA-like term can have sector-specific economics. |
| Current HSI direct-source corpus | 0 qualified direct EBITDA; 0 qualified direct EBIT; no eligible source-declared formula | No direct cross-company input is presently available. |

## Candidate non-financial constructs — research only

These are symbolic candidates. The audit never calculates values, writes a
`FinancialFact`, or creates a derived metric.

| Candidate | Descriptive label only | Semantic result | Research conclusion |
|---|---|---|---|
| A: `PBT + FINANCE_COST` | `PRE_FINANCE_COST_PRE_TAX_PROFIT` | `NOT_EBIT` | PBT can contain other income, fair-value effects, associates/JVs, exceptional items and discontinuing-operation effects. Finance cost may not be pure interest. Not comparable enough to call EBIT. |
| B: `PBT + FINANCE_COST + DEPRECIATION` | `PRE_FINANCE_COST_PRE_DA_PRE_TAX_PROFIT` | `NOT_EBITDA` | Inherits Candidate A issues. Adding D&A does not remove them. |
| C: `B - OTHER_INCOME` | `PRE_FINANCE_COST_PRE_DA_PRE_TAX_PROFIT_MINUS_OTHER_INCOME` | `NOT_EBITDA_AND_OTHER_INCOME_SUBTRACTION_UNAPPROVED` | Other income can be recurring or operating-related; subtracting all of it creates an unjustified hidden adjustment. Fail closed. |
| D: issuer-reported EBITDA/EBIT | `REPORTED_EBITDA` / reported EBIT only | `OPTIONAL_ENRICHMENT_ONLY` | May be useful source-specific context after exact definition validation; not canonical cross-company comparison evidence. |

### Semantic comparability matrix

| Component or issue | A: PBT + FC | B: A + D&A | C: B − other income | Why automatic standardization fails |
|---|---|---|---|---|
| Exceptional items | Retained unless exact PBT basis proves otherwise | Same | Same | PBT presentation does not universally identify an adjustment basis. |
| Other income | Retained | Retained | Unconditionally removed | Neither retention nor removal proves operating/non-operating classification. |
| Finance income / finance cost | Cost added back; finance income remains in PBT | Same | Same | Financing income/cost labels and lease components are not a universal operating boundary. |
| Fair-value gains/losses | Can remain in PBT | Same | Same | Source-specific classification is required. |
| Associate/JV profit | Can remain in PBT | Same | Same | SEBI issuer KPI evidence demonstrates explicit variation. |
| Discontinued operations | May affect profit presentation | Same | Same | Requires exact source/period treatment. |
| Lease finance components | Can be included in finance cost | Same | Same | Cannot be silently normalized without a policy. |
| Cross-company use | Not approved | Not approved | Rejected at this stage | No discretionary issuer-specific adjustment is permitted in the current model. |

## Reported versus future derived metric

`REPORTED_EBITDA` and a possible future
`HSI_STANDARDIZED_DERIVED_OPERATING_EARNINGS` are different semantic
identities. A future derived measure must **not** reuse `FinancialMetric.EBITDA`
merely because it is EBITDA-like. A new canonical identity is required if, and
only if, a separately approved derivation policy establishes its meaning.

The existing `FinancialFact` contract has useful primitive support for a future
`DERIVED` fact: immutable parent IDs are required, and it retains instrument,
scope, period, currency/unit/scale, fact kind, publication/receipt times,
normalization and provenance. The existing generic `FinancialDerivedMetric` is
not sufficient policy on its own. A future implementation would also require a
new formula identifier/version, approved exact parent semantic key, frozen
vintage selector, PIT visibility, deterministic replay, no representation
conversion, no hidden adjustments, and a derivation-specific integrity
contract. None is created here.

## Entity-type applicability

The existing PIT company-type classifier supplies only exact evidence-backed
`NON_FINANCIAL`, `BANK`, `NBFC`, and `INSURER` classifications. All missing,
conflicted, unsupported, or non-comparable results remain
`UNKNOWN_NON_COMPARABLE`; they are not a permission to use the non-financial
branch.

| Rule | NON_FINANCIAL | BANK | NBFC | INSURER | UNKNOWN / NON-COMPARABLE |
|---|---|---|---|---|---|
| 16 — Five-Year Financial Trend | `POLICY_REDESIGN_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `POLICY_UNRESOLVED` |
| 17 — Return Ratios | `POLICY_REDESIGN_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `POLICY_UNRESOLVED` |
| 19 — Balance Sheet Leverage | `STANDARDIZED_DERIVED_METRIC_CANDIDATE` only as research; no activation | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `POLICY_UNRESOLVED` |
| 25 — Latest Quarterly Results | `USE_EXISTING_CANONICAL_ACCOUNTING_METRIC` for revenue/PAT/EPS; EBITDA component is `OPTIONAL_ENRICHMENT_ONLY` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `POLICY_UNRESOLVED` |
| 26 — Operating/Gross Margin Trajectory | `POLICY_REDESIGN_REQUIRED` | `NOT_APPLICABLE` to industrial margin semantics; branch required before any substitute | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `NOT_APPLICABLE` to industrial margin semantics; branch required before any substitute | `POLICY_UNRESOLVED` |
| 29 — Valuation Multiples | P/E remains existing canonical input; EV/EBITDA is `OPTIONAL_ENRICHMENT_ONLY` / policy-blocked | `ENTITY_SPECIFIC_BRANCH_REQUIRED` for valuation conventions | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `ENTITY_SPECIFIC_BRANCH_REQUIRED` | `POLICY_UNRESOLVED` |

`NOT_APPLICABLE` is confined to an industrial-company component where the
entity’s economics make that component invalid. It is never used for missing
data. Entity-specific applicability is not missing-data forgiveness.

Banks require a future exact-policy review of official measures such as net
interest income, officially defined operating/pre-provision profit, PAT, ROA,
capital adequacy and asset quality. NBFCs require a separate review; finance
cost is not automatically industrial financing. Insurers require policyholder
and shareholder-account semantics. No such inputs, diagnostic branches, or
new diagnostics are added here.

## Affected-rule research recommendation

| Rule | Current required metric / blocker | Non-financial proposal | Financial-sector proposal | Canonical impact | Registry change? | Data readiness / primary basis |
|---|---|---|---|---|---|---|
| 16 | Revenue, EBITDA, PAT, EPS CAGR; direct EBITDA absent | Do not replace EBITDA silently. Candidate B requires a new derivation policy and a semantic rule redesign. | Separate branches required. | Material name/input change if EBITDA no longer literal. | Yes, if changed. | Parent lines have coverage; semantic comparability unresolved. MCA/ICAI/SEBI. |
| 17 | ROCE requires EBIT; ROE uses PAT | ROE can retain existing PAT/equity facts; ROCE numerator and denominator remain policy redesign. `PBT + FC` is not EBIT. | Separate branches required. | No substitute approved. | Yes, if ROCE changes. | Balance-sheet denominator and entity treatment remain unresolved. MCA/ICAI/RBI/IRDAI. |
| 19 | Interest coverage uses EBIT / finance cost | A governed pre-finance construct is only a future candidate; `FINANCE_COST` is not assured interest expense. | Separate branches required. | No replacement now. | Yes, if numerator changes. | Parent-line coverage does not prove coverage semantics. MCA/ICAI/RBI. |
| 25 | Quarterly acceleration includes EBITDA | Retain revenue, PAT and EPS factual inputs. Do not manufacture an EBITDA component. | Separate branches required. | Existing rule can remain partial only under its current semantics. | Yes, if component set is changed. | Quarterly parent coordinates are available, but no operating-earnings policy exists. SEBI/NSE. |
| 26 | Operating and gross margin trajectory includes EBITDA | Do not call PBT margin operating margin. Gross-margin parent semantics require separate cost-of-sales evidence. | Industrial margin semantics invalid or branch-specific. | Redesign required. | Yes. | No approved standardized numerator or gross-margin denominator policy. MCA/ICAI/IRDAI. |
| 29 | P/E, forward P/E, PEG, EV/EBITDA, P/B; current code already policy-blocks non-P/E multiples | Retain existing P/E behavior; EV/EBITDA remains optional/policy-blocked. | Entity-specific valuation logic required. | No scoring renormalization. | No, unless a future valuation policy activates more multiples. | Existing rule’s P/E path remains independent of EV/EBITDA. |

### Rule-specific conclusions

- **Rule 16:** Policy 16-A fails current direct coverage. 16-B is not yet
  approved. 16-C would materially change information content. 16-D is a
  possible architecture, but has no approved bank/NBFC/insurer policy.
- **Rule 17:** ROE can remain factual, but neither a new ROCE numerator nor a
  capital-employed denominator is selected. Alternatives such as
  equity+debt−cash, net worth+debt, or assets−current liabilities have distinct
  accounting meanings and cannot be chosen by popularity.
- **Rule 19:** No coverage numerator is approved. `FINANCE_COST` cannot be
  silently renamed interest expense.
- **Rule 25:** Existing direct quarterly revenue/PAT/EPS retain their factual
  value. Replacing only the missing EBITDA component needs registry governance,
  not a coverage-driven shortcut.
- **Rule 26:** There is no approved standardized operating margin. PBT margin
  is explicitly not one.
- **Rule 29:** EV/EBITDA is correctly partial/policy-blocked today. Its absence
  must not block the existing P/E path or silently change score weights.

## Read-only current-data feasibility receipt

The script `scripts/audit_ebitda_ebit_diagnostic_alternatives.py` read the
production SQLite database in `mode=ro` with `PRAGMA query_only=ON`, at the
explicit cutoff `2026-09-12T00:00:00+00:00`. It selected reported factual
vintages only through the frozen
`financial-fact-vintage-selection-policy / v1-approved` selector. It stored
no value, made no financial calculation, and wrote only an ignored research
report file.

Population: 31 instruments with official BSE financial facts. Exact
PIT company-type receipts at the cutoff classified 10 `NON_FINANCIAL`, 2
`BANK`, and left 19 `UNKNOWN_NON_COMPARABLE`; no target received an NBFC or
insurer classification. Candidate coverage below is raw parent-coordinate
readiness for all 31 targets, **not** entity-policy eligibility.

| Candidate | Annual ≥1 | Annual ≥2 | Annual ≥5 | Annual ≥6 | Quarterly depth ≥5 | Compatible parent coordinates | Unit/scope mismatch | Period-identity mismatch | Parent-vintage conflicted/invalid | Missing component distribution |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A: `PBT + FC` | 28 | 25 | 18 | 16 | 26 | 614 | 0 | 0 | 32 | PBT 2; finance cost 2 |
| B: `PBT + FC + D&A` | 28 | 25 | 18 | 16 | 26 | 614 | 0 | 0 | 48 | PBT 2; finance cost 2; D&A 2 |
| C: `B − other income` | 28 | 25 | 18 | 16 | 26 | 614 | 0 | 0 | 64 | PBT 2; finance cost 2; D&A 2; other income 0 |

The candidate-coverage test requires exact agreement on instrument, reported
fact kind, statement scope, period type/basis/start/end/fiscal identity,
currency, unit, scale, normalization version, and PIT-selected fact lineage.
It does not compare numbers, calculate candidate values, test correlation with
PBT/PAT, tune a threshold, or claim predictive value. Parent-vintage conflict
counts remain excluded rather than repaired. Replaying the report with the same
immutable facts and cutoff yields report ID
`ebitda-ebit-alternatives:cf3ad51e591c24d5f8f9e3a2ffbed86b`; the recorded
report fingerprint is
`sha256:68e47095d7b954da91adec636a4e97abdbba073b0fd5f8c934062cadc96cd817`.

Strict historical PIT can only reduce this availability: facts received after a
historical cutoff are excluded, even where their accounting period predates the
cutoff. Current coverage is not authorization to backfill historical knowledge.

## Architectural answers

1. **Continue waiting for direct reported EBITDA/EBIT?** Do not make it a hard
   universal requirement; current safe direct coverage is too sparse. Preserve
   it as optional issuer-reported enrichment only.
2. **Can HSI now define standardized derived operating earnings?** Not safely.
   The factual parent set is feasible for research, but accounting semantics,
   financial-sector branches and a transparent adjustment policy are unresolved.
3. **What future name avoids false representation?** If approved later, use a
   new term such as `HSI_STANDARDIZED_DERIVED_OPERATING_EARNINGS`, never
   `REPORTED_EBITDA` or `EBITDA` by implication. This is a naming constraint,
   not authorization to create it.
4. **Can candidates satisfy current rule semantics without a registry version?**
   No. Substituting any candidate would change Rule 16/17/19/25/26 semantics;
   governance/versioning is required first.
5. **Which rules require entity-specific branches?** Rules 16, 17, 19, 25, 26
   and financial-sector valuation within 29.
6. **Which measures remain optional enrichment?** Exact issuer-reported
   EBITDA/EBIT and EV/EBITDA until a separately approved valuation policy.
7. **Is Rule 29 EV/EBITDA overly strict?** No. The present implementation
   already treats it as policy-blocked while retaining P/E; no score change is
   justified.

## Frozen safeguards

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
NO_SILENT_REGISTRY_REWRITE = TRUE
NO_SYNTHETIC_REPORTED_FACTS = TRUE
AI_DECISION_AUTHORITY = FALSE
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```

- Issuer EBITDA ≠ standardized EBITDA.
- Derived metric ≠ reported metric.
- PBT + finance cost ≠ automatically EBIT.
- PBT + finance cost + D&A ≠ automatically EBITDA.
- Other income ≠ automatically non-operating.
- Finance cost ≠ always pure interest expense.
- Bank/NBFC interest economics ≠ industrial-company financing economics.
- Insurer economics ≠ industrial EBITDA economics.
- Missing evidence ≠ `NOT_APPLICABLE`.
- Entity-specific applicability ≠ missing-data forgiveness.
- Rule semantic change requires governance/versioning.
- More coverage is not a reason to weaken financial meaning.

## Sources

- [MCA Schedule III notification](https://www.mca.gov.in/Ministry/pdf/NotificationScheduleIII_12102018.pdf)
- [ICAI Guidance Note on Division II — Ind AS Schedule III](https://kb.icai.org/pdfs/PDFFile5b27857548bee2.71295102.pdf)
- [SEBI revised formats for Ind AS financial results](https://www.sebi.gov.in/legal/circulars/jul-2016/revised-formats-for-financial-results-and-implementation-of-ind-as-by-listed-entities_32788.html)
- [SEBI-hosted issuer formula-variation example](https://www.sebi.gov.in/sebi_data/attachdocs/apr-2025/1743751804884_762.pdf)
- [NSE XBRL information](https://www.nseindia.com/static/companies-listing/xbrl-information)
- [RBI financial-statement presentation and disclosures](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html)
- [IRDAI financial-statement preparation](https://irdai.gov.in/document-detail?documentId=374643)
