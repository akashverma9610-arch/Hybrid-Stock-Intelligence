# Long-Term Quality at Fair Value — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

## Scope

This policy is an isolated research-shadow classifier for
`LONG_TERM_QUALITY_FAIR_VALUE`. It consumes the existing immutable Long-Term
Thesis Review and Research Shadow readiness receipts; canonical financial
observations/trajectories; reliability/governance evidence; and, only if a
future contract supplies it, valuation-comparability evidence. It creates no
second dossier, score, forecast, intrinsic value, price target, recommendation,
portfolio result, API, persistence, broker or order surface.

Results are limited to `SHADOW_CANDIDATE`, `SHADOW_NOT_QUALIFIED`,
`DATA_INSUFFICIENT`, `EVIDENCE_CONFLICTED`, `POLICY_PARAMETER_UNAVAILABLE`,
and `NOT_APPLICABLE`, with fixed `WATCH_ONLY / NON_EXECUTABLE /
RESEARCH_SHADOW_V1` boundaries. A research result has no capital or execution
meaning.

## Methodological and regulatory lineage

The economic motivation is methodological, not a copied screen or a claim of
Indian-market performance. Novy-Marx’s original work measures gross
profitability as gross profits divided by assets; it supports investigating
profitability alongside valuation, not any HSI cutoff or forecast.
[Novy-Marx (NBER working paper 15940)](https://www.nber.org/papers/w15940)
and [published-paper record](https://www.nber.org/papers/w15940.pdf) are the
source lineage. [Piotroski (2000)](https://www.jstor.org/stable/2672906) uses
historical financial-statement information in a value context, and
[Fama–French](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=570343)
relates profitability, investment, and book-to-market in its empirical setting.
None establishes a universal threshold, a fair value, or an Indian-market
production rule.

[Ind AS 7](https://www.icai.org/post/10450) describes cash-flow presentation;
it does not define HSI cash conversion. The [Companies Act, 2013](https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf)
provides financial-statement context. Banks require their own capital,
asset-quality, and liquidity disclosure context under the
[RBI financial-statement direction](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html),
and insurers have separate solvency contexts in the
[IRDAI regulations inventory](https://irdai.gov.in/consolidated-gazette-notified-regulations).
Those sources prohibit treating an industrial debt/EBITDA or CFO/PAT heuristic
as universal.

## Applicability branches

| Branch | Research Shadow V1 treatment | Required future policy work |
| --- | --- | --- |
| Non-financial corporate | May be evaluated only if all required PIT evidence and a governed valuation-comparison record are supplied. | Metric formulae, sector-specific calibration, cyclicality adjustment and shadow outcome. |
| Bank | `NOT_APPLICABLE`. | Separate bank capital, asset-quality, liquidity and profitability policy. |
| NBFC | `NOT_APPLICABLE`. | Separate NBFC capital, asset-quality, liquidity and provisioning policy. |
| Insurer | `NOT_APPLICABLE`. | Separate solvency, underwriting/business-quality and reserve policy. |
| Structurally non-comparable/unknown | `NOT_APPLICABLE`. | Exact classification and applicable policy branch. |

## Canonical input map and PIT rule

| Candidate input | Canonical source | Exact current treatment |
| --- | --- | --- |
| Instrument, as-of, dossier identity/fingerprint, diagnostics/evidence lineage | `LongTermThesisReview` over the existing `BrainOutputProjection` | Required; verify exact identity and no later dossier/lineage. |
| Financial scope, period, revision and fact availability | `FinancialResearchObservationBundle`, `FinancialMetricTrajectory`, frozen fact-vintage selection | Required where a metric is used; same instrument, scope, basis, currency/unit/scale, fiscal alignment and PIT visibility. No restated-history repair. |
| Governance/reliability | Existing dossier/research-shadow coverage lineage | Required; conflicted/unavailable evidence fails closed. No new severity score. |
| Profitability/capital efficiency | Canonical metric observations if a future policy chooses them | `POLICY_PARAMETER_UNAVAILABLE`: no approved normalized ROCE/ROE/gross-profitability materialization or threshold. |
| Balance-sheet safety | Canonical debt/cash/finance-cost facts if comparable | `POLICY_PARAMETER_UNAVAILABLE`: no approved debt/coverage formula, and no financial-company substitution. |
| Cash conversion/earnings quality | Canonical CFO/PAT facts only if selected and comparable | `POLICY_PARAMETER_UNAVAILABLE`: no approved formula, minimum history, or cash-flow normalization coverage. |
| Valuation/historical-peer comparison/margin of safety | Brain comparability policy | `POLICY_PARAMETER_UNAVAILABLE`: valuation is currently `UNSUPPORTED`; no price basis, denominator, peer universe, multiple, DCF or fair-value method is allowed. |
| Cyclicality, horizon, review, invalidation, shadow outcome | No approved canonical policy artifact | `POLICY_PARAMETER_UNAVAILABLE`; no synthetic dates, forecast, outcome or lifecycle. |

For every input, `available_at > thesis_as_of`, missing lineage, fingerprint
mismatch, incompatible statement scope/basis, revision conflict, or conflicting
evidence fails closed.  Current/runtime time never participates.

## Versioned parameter register

| Parameter | Status | Candidate values/grid | Rationale and limitation |
| --- | --- | --- | --- |
| Gross profitability | `PARAMETER_RESEARCH_REQUIRED` | Formula candidate: `gross_profit / average_or_period_assets`; no value threshold | Novy-Marx uses gross profits/assets in a US empirical setting. HSI lacks a governed gross-profit and asset-period materialization/calibration. |
| Cash conversion | `PARAMETER_RESEARCH_REQUIRED` | Formula candidate: `CFO / PAT`; no threshold | Ind AS 7 supports cash-flow presentation only. CFO/PAT is invalid for financial institutions and needs scope, sign, period and revision rules. |
| Leverage/coverage | `PARAMETER_RESEARCH_REQUIRED` | Possible non-financial formulas `net_debt / EBITDA`, `EBIT / finance_cost`; no threshold | Existing evidence lacks an approved derived-metric and financial-company branch. |
| Relative valuation | `PARAMETER_RESEARCH_REQUIRED` | Historical/peer multiple or book-to-market candidates; no method/threshold | Canonical valuation comparison is explicitly unsupported. |
| Minimum history, cyclicality, review cadence, invalidation and evaluation horizon | `PARAMETER_RESEARCH_REQUIRED` | None | Must be predeclared and calibrated chronologically before outcome inspection. |

No number is promoted by this document. Any later numeric value is at most
`RESEARCH_SHADOW_V1_CANDIDATE`, must retain its full grid and sensitivity
cases, and requires prospective/walk-forward evidence before any promotion.

## Exact result semantics

1. A source-review integrity/PIT failure returns `DATA_INSUFFICIENT` or
   `EVIDENCE_CONFLICTED` according to the verified upstream receipt.
2. A non-financial classification that is absent, conflicted, or unsupported,
or any financial-sector branch, returns `NOT_APPLICABLE`.
3. Missing valuation comparability, quality parameter approval, cash/return
metric materialization, lifecycle or calibration returns
`POLICY_PARAMETER_UNAVAILABLE` with every missing requirement retained.
4. `SHADOW_CANDIDATE` is reserved for a later version that has every required
policy parameter and canonical domain. Version 1 deliberately cannot emit it.
5. `SHADOW_NOT_QUALIFIED` is likewise reserved until a governed parameter set
exists; it never means weak, unattractive, or a portfolio instruction.

## Implementation and rollback

The initial pure evaluator is limited to identity/PIT verification, explicit
sector applicability, and deterministic unavailable/conflict propagation. It
does not calculate a quality metric or valuation. It is independent of storage,
providers, portfolio, API/UI, broker/order, runtime clock, and `app.signals`.
Deleting the isolated module and tests is a complete rollback.
