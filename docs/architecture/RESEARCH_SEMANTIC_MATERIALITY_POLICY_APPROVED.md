# Research Semantic Materiality Policy v1 Approved

## Identity

- Policy: `research-semantic-materiality-policy / v1-approved`
- Fingerprint: `7eceb06f9c99e496953188e6e0fce71987663600ffa5ab371978333f2fb9921a`
- Lineage: `v1-proposed → v1-approved`
- Approval: `human:Akash-Verma`
- Selected: `false`
- Active: `false`

## Frozen v1 contract

This is an immutable, passive, code-only governance artifact. It binds exactly
the frozen financial trajectory policy and the frozen metric directionality
policy. A future materiality input must bind one trajectory to its exact
directionality interpretation by matching the trajectory fingerprint and all
three policy lineages.

The policy contains exactly fourteen eligible pairs: Revenue, EBITDA, Operating
Profit, EBIT, PAT, EPS Basic, and EPS Diluted, each on quarterly and annual YoY
bases. Each rule accepts only `POTENTIALLY_FAVORABLE` or
`POTENTIALLY_UNFAVORABLE` directionality and is `CALIBRATION_REQUIRED` with no
threshold specification.

Therefore v1 approves **no thresholds** and classifies no runtime movement as
`MATERIAL` or `IMMATERIAL`. A later runtime under an unchanged calibration-gated
rule would have to yield only `UNDETERMINED`; context-dependent,
non-directional, no-directional-change, and not-applicable orientation remain
`NOT_APPLICABLE` for directional materiality.

## Explicit exclusions

No universal percentage, absolute delta, sign-crossing, non-zero-delta,
company-normalization, historical-distribution, or cross-sectional method is
approved. Zero and negative prior bases need a separate scale-aware calibrated
method; no percentage is fabricated and no sign crossing is automatically
material.

This policy implements no materiality interpreter, threshold helper,
persistence, migration, provider/API/runtime surface, Brain integration, score,
Six Gates effect, acceleration, aggregation, thesis/opportunity interpretation,
alert, recommendation, or action behavior.

## Versioning

Any later method, threshold, eligible pair, basis, normalization rule, or
directionality-policy version requires a new materiality policy version and
fingerprint, with its own calibration evidence and human governance approval.
