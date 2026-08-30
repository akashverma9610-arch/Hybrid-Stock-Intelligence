# Financial Metric Trajectory Policy v1

**APPROVED — NOT SELECTED — NOT ACTIVE**

`financial-metric-trajectory-policy / v1-approved` is a passive factual policy
approved by `human:Akash-Verma`, with lineage `v1-proposed -> v1-approved`.
It follows U14D-6V factual-chain QA readiness and authorizes no builder.

Fingerprint:
`15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7`

Its future canonical input is one same-as-of
`FinancialResearchObservationBundle`; raw facts, providers, wrappers, and
`ResearchStateDelta` are not trajectory inputs. Same-period revisions are
knowledge revisions, never period movement.

Approved future bases are `SEQUENTIAL_QUARTER`, `YEAR_OVER_YEAR_QUARTER`,
`YEAR_OVER_YEAR_ANNUAL`, and `POINT_IN_TIME_SEQUENTIAL`. They require COMPLETE
period identity, exact representation parity, one knowledge cutoff, and proven
fiscal/date relationships. Q4→Q1 requires explicit fiscal metadata; period
end is the economic date for point-in-time facts. Cash-flow sequential pairing
requires explicit `QUARTER_ONLY`; no cumulative reconstruction, YTD, or TTM is
approved. EPS requires share-basis/normalization proof.

Future arithmetic is factual only: exact Decimal `current - previous`; relative
delta is `(current - previous) / previous` only for a strictly positive prior
base. Zero/negative prior bases retain values, absolute delta, numeric-domain,
and neutral sign-transition classification without a relative percentage.

No builder, pairing engine, Brain/delta change, materiality, persistence,
directionality, thesis/opportunity meaning, alert, recommendation, or execution
is implemented or activated by this policy.
