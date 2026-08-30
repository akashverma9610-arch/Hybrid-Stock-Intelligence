# Frozen Brain Research Comparability Policy v2

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

## Identity

| Field | Value |
| --- | --- |
| Policy ID | `brain-research-comparability-policy` |
| Version | `v2-approved` |
| Fingerprint | `1e6926fd84dcf82958a831674701afb28bf3a76a15e9fe19bbfe5d5f28df79d3` |
| Approver | `human:Akash-Verma` |
| Selected / active | `false / false` |
| Mode | `KNOWLEDGE_AT_THE_TIME` |
| Proposal lineage | `v2-proposed -> v2-approved` |
| Predecessor | `v1-approved / 361a2f7e8cd9a5acd7a2731d10a56c32ae52227c7fd412fbd2f1967b37ca1bc2` |

v2 retains all v1 source rules, domain rules, evidence preconditions,
non-comparable cases, exclusions, knowledge-at-the-time behavior, and
dimension-local failure semantics. v1 remains immutable historical governance.

## Frozen financial-observation requirements

Future numeric financial comparison requires exact compatible lineage for:

```text
Bundle: financial-research-observation-bundle-schema / v1-approved /
aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89
Observation: financial-metric-observation-schema / v1-approved /
6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf
Selector: financial-fact-vintage-selection-policy / v1-approved /
862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13
```

Different required bundle, observation, or selector lineage is
`NON_COMPARABLE`. No cross-schema or cross-policy bridge exists.

For each future state input:

```text
selection_as_of == bundle.as_of == Brain state as_of
visible_as_of <= Brain state as_of
```

Missing selector-cutoff attestation is `INSUFFICIENT`; contradictory attestation
is invalid financial-dimension input. `visible_as_of` is never equated with or
rewritten to the selection cutoff.

## Frozen slot and representation rules

The full deterministic slot is: canonical instrument, fact kind, metric,
statement scope, period type/basis/start/end, fiscal year/quarter when supplied,
value dimension, currency, unit, scale, normalization identity, period
fingerprint, source role, and observation-schema identity.

`source_fact_id`, source-fact semantic fingerprint, and observation fingerprint
are lineage/tamper identities, not pair keys. A later selected revision can
therefore remain the same Q1 slot under exact parity.

`COMPLETE` periods may be numeric-comparison candidates. `PARTIAL` periods are
factual artifacts but numeric comparison is `INSUFFICIENT`. `INSUFFICIENT`
periods cannot enter a valid observation/bundle. There is no conversion across
scope, period type/basis, currency, unit, scale, dimension, normalization,
share basis, or cash-flow basis.

## Frozen future matching requirement

A later matcher must use the full slot key: exact key pairs factually,
previous-only is `REMOVED`, current-only is `ADDED`, no metric-label or
same-label zip fallback, and duplicate full key fails closed. Thus retained Q1
pairs only with Q1; a newly present Q2 is `ADDED`.

Same-slot revisions may later be factual `VALUE_CHANGED`, `LINEAGE_CHANGED`,
or both. This is not QoQ, YoY, trajectory, growth, favorability, thesis, or
opportunity semantics.

Financial evidence references and numeric wrappers are distinct source roles
and cannot pair as one observation. Bundle failures remain typed financial
input-sufficiency lineage, never numeric values or zeroes.

## Boundary

Future financial-integrated Brain state v2 must bind to policy v2; state v1
remains bound to policy v1. v1-to-v2 is foundationally `NON_COMPARABLE` and no
cross-version comparator exists. Within valid v2 states, financial failures are
dimension-local unless bundle input violates a foundational invariant.

This artifact does not change `ResearchStateDelta`, Brain state, generic
wrappers, bundle building, selection, materialization, trajectory,
directionality, thesis/opportunity, alerts, recommendations, persistence,
providers, APIs, workers, schedulers, or execution.
