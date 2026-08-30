# Research Semantic Materiality Policy Proposal

U14D-7B established that directionality is a narrow metric-local orientation.
Materiality is the next semantic prerequisite, but it is not a synonym for a
non-zero delta, a percentage change, a sign crossing, or an absolute rupee
movement.

## Repository audit

The repository has no prior approved financial-trajectory materiality
calibration. Existing thresholds are isolated to their own domains: Pre-Breakout
technical and delivery rules, market-data freshness, governance drift, scoring,
diagnostic risk severity, and catalyst/news evidence. None is a transferable
financial materiality threshold. In particular, catalyst order-value/revenue
observation is event evidence, not a financial-trajectory materiality rule.

## Proposed v1 posture

`research-semantic-materiality-policy / v1-proposed` is calibration-gated.
The fourteen directionally eligible pairs may later be assessed only when a
separately governed calibration exists. Until then, every eligible pair is
`CALIBRATION_REQUIRED`, conceptually yielding `UNDETERMINED`; all other
directionality orientations are `NOT_APPLICABLE` for directional materiality.

The future input boundary is exact and bound:

`FinancialMetricTrajectory + bound ResearchMetricDirectionalityInterpretation + exact materiality policy`.

The directionality source trajectory fingerprint must equal the trajectory
fingerprint. Trajectory-policy and directionality-policy lineage must match
exact frozen v1 fingerprints. This proposal neither implements nor authorizes
an interpreter.

## Method audit

| Candidate method | v1 decision | Reason |
| --- | --- | --- |
| Relative delta | No safe current method | Missing for zero/negative bases and unstable at tiny bases. |
| Absolute delta | No safe current method | Company, metric, unit, and scale context are absent. |
| Sign transition | No safe current method | Crossing zero is not scale-aware. |
| Company normalization | Future research | No governed denominator/pairing method. |
| Historical distribution | Future research | No governed lookback, population, outlier, revision, or PIT contract. |
| Cross-sectional distribution | Future research | No governed peers, scale normalization, or PIT taxonomy contract. |

Future calibration must provide exact metric/basis, PIT-valid observation
population, sample period and distribution statistics, outlier/revision policy,
company-scale treatment, false-positive/negative tradeoff, methodology
fingerprint, and human approval. Thresholds, if later approved, belong only to
a versioned materiality policy/calibration artifact—not interpreter constants.

## Proposed eligible matrix

| Metric | Basis | Directionality | Method | v1 disposition |
| --- | --- | --- | --- | --- |
| REVENUE | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| REVENUE | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EBITDA | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EBITDA | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| OPERATING_PROFIT | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| OPERATING_PROFIT | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EBIT | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EBIT | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| PAT | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| PAT | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EPS_BASIC | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EPS_BASIC | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EPS_DILUTED | quarterly YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |
| EPS_DILUTED | annual YoY | potentially favorable/unfavorable | no safe current method | CALIBRATION_REQUIRED |

Context-dependent, non-directional, no-directional-change, and not-applicable
directionality cannot be promoted into directional materiality. Materiality is
also not persistence, acceleration, quality, attribution, thesis, opportunity,
score, alert, recommendation, or execution.
