# Long-Term Fundamental Compounder — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

## Boundary

`LONG_TERM_FUNDAMENTAL_COMPOUNDER` is a read-only, deterministic research
classifier over the existing Long-Term Thesis Review and Research Shadow
readiness receipt. It may propagate applicability, PIT/integrity, conflict,
data insufficiency, and policy-parameter unavailability. It creates neither a
new dossier nor a score, forecast, expected return, recommendation, portfolio
state, persistence, API, provider, broker, or order behavior.

The only permitted outputs are `SHADOW_CANDIDATE`, `SHADOW_NOT_QUALIFIED`,
`DATA_INSUFFICIENT`, `EVIDENCE_CONFLICTED`,
`POLICY_PARAMETER_UNAVAILABLE`, and `NOT_APPLICABLE`; all have fixed
`WATCH_ONLY / NON_EXECUTABLE / RESEARCH_SHADOW_V1` status. Version 1 reserves
both candidate labels until every listed parameter is separately governed.

## Research and regulatory lineage

[Fama and French](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=570343)
relate profitability, investment, and book-to-market in their studied setting.
[Chan et al.](https://www.nber.org/papers/w8308) distinguish accrual and cash
components of earnings; [Wu, Zhang and Zhang](https://www.nber.org/papers/w13525)
also document an investment-based interpretation. These sources motivate
testing growth persistence, cash quality, and investment intensity. They do
not define Indian-company thresholds, prove a company will compound, or choose
HSI parameters.

Ind AS 7 and the Companies Act provide statement context, not a cash-conversion
rule. RBI’s [NBFC disclosure direction](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12292)
requires institution-specific capital, asset-quality and liquidity context.
Banks, NBFCs and insurers therefore cannot receive industrial-company
revenue/PAT, debt/EBITDA, working-capital, or CFO/PAT interpretation.

## Exact canonical map

| Domain | Existing PIT-safe source | V1 treatment |
| --- | --- | --- |
| Instrument/as-of/dossier/diagnostic/evidence lineage | `LongTermThesisReview` and `LongTermThesisResearchShadow` | Required and verified exactly. |
| Revenue/PAT/finance-cost facts | Fact-vintage selection, `FinancialResearchObservationBundle`, factual trajectories | Required when a later metric uses them; same instrument, scope, basis, currency, unit, scale, fiscal alignment, revision and visibility. |
| Margin/operating leverage | Financial observations where retained | `POLICY_PARAMETER_UNAVAILABLE`: no approved operating-profit/EBITDA derivation and minimum history. |
| Cash conversion, working capital, debt trajectory | Financial observation domains | `POLICY_PARAMETER_UNAVAILABLE`: no complete materialization/formula/history or specialist branch. |
| Governance/reliability | Existing dossier/readiness lineage | Required; conflicting or unavailable evidence fails closed. |
| Dilution, review cadence, deterioration/invalidation and shadow outcome | No approved compatible artifact | `POLICY_PARAMETER_UNAVAILABLE`. |

`available_at > as_of`, a mismatched or tampered fingerprint, non-comparable
scope/basis, revision conflict, or missing lineage must fail closed. Runtime
time, later restatements and arbitrary latest-value selection are excluded.

## Sector applicability

| Business branch | V1 behavior |
| --- | --- |
| Non-financial corporate | May receive only deterministic unavailable/conflict/data state propagation. |
| Bank, NBFC, insurer | `NOT_APPLICABLE` until separate capital, asset-quality, liquidity, provisioning/solvency and profitability branches are approved. |
| Unknown/structurally non-comparable | `NOT_APPLICABLE`. |

## Parameter register

| Parameter | Status | Exact candidate/grid | Why unavailable |
| --- | --- | --- | --- |
| Revenue/PAT growth consistency | `RESEARCH_SHADOW_V1_CANDIDATE` | `{3/3, 4/5, 5/5}` positive comparable annual observations | Existing policy research records the grid, but no selected value, period selector, zero/negative-base treatment or Indian calibration. |
| Margin/operating leverage | `PARAMETER_RESEARCH_REQUIRED` | No threshold | Metric materialization and sector basis are unapproved. |
| Cash conversion, working capital, debt trajectory, dilution | `PARAMETER_RESEARCH_REQUIRED` | No threshold | Formula, scope, history, financial-company treatment and source coverage are missing. |
| Review cadence, deterioration, invalidation, outcome horizon | `PARAMETER_RESEARCH_REQUIRED` | None | Requires predeclared chronological calibration and prospective shadow evidence. |

Candidate grids are retained without optimization; they must be evaluated by
chronological validation and holdout before any later promotion. They are not
performance claims.

## Deterministic V1 semantics

- Unsupported/unknown or financial-sector branch: `NOT_APPLICABLE`.
- Upstream conflict: `EVIDENCE_CONFLICTED`.
- Upstream PIT/integrity/missing/stale/non-comparable state:
  `DATA_INSUFFICIENT`.
- A valid non-financial source receipt: `POLICY_PARAMETER_UNAVAILABLE` with
  growth, margin, cash, working-capital/debt, lifecycle and calibration gaps.
- No current input set can return `SHADOW_CANDIDATE` or
  `SHADOW_NOT_QUALIFIED`.

The implementation is a pure module with no store, provider, portfolio,
API/UI, broker/order, `app.signals`, runtime clock, or action vocabulary.
