# Objective Intelligence-Delta Interpreter

**Status: IMPLEMENTED AS PURE DOMAIN CONTRACT — NOT ACTIVATED.**

`app/intelligence/intelligence_delta_interpretation.py` implements the
deterministic function:

```python
interpret_intelligence_delta(delta, policy=..., typed_evidence=...)
```

It accepts an already-created immutable `IntelligenceDelta` and an explicitly
supplied frozen policy. It makes no reads or writes, calls no provider, and is
not wired into delta creation, Unified State construction, Brain output,
projection, API, scanner, portfolio, alert, or trading paths.

## Frozen policy requirement

Only the exact immutable policy is accepted:

`intelligence-delta-interpretation-policy / v1-approved`

with fingerprint:

`2d0572f2d29daa7e322b6a91495b142fc13a84508573338a4cd9d91ab8239b57`

The function rejects a wrong ID, version, fingerprint, selected state, or active
state. Passing a policy explicitly does not activate it; the frozen policy
remains `selected_for_future_interpreter = false` and `active = false`.

## Artifacts

`IntelligenceDeltaInterpretation` preserves source delta and state identities,
as-of references, policy lineage, sorted domain interpretations, and a
deterministic fingerprint. It has no overall direction, score, confidence,
thesis, opportunity, risk, recommendation, or execution field.

Each `IntelligenceDomainInterpretation` preserves the domain, dimension,
previous/current governed status, objective interpretation, evidence
sufficiency, rule/rationale code, source domain-delta fingerprint, optional
typed-evidence fingerprint, and deterministic fingerprint.

## Evidence sufficiency

| Value | Meaning |
| --- | --- |
| `SUFFICIENT` | The immutable delta or exact typed evidence proves one frozen transition. |
| `INSUFFICIENT` | A conditional rule needs typed evidence not carried by the current bounded delta, such as selected-route proof. |
| `NON_COMPARABLE` | Evidence exists but the approved policy forbids a direction, including conflicts and unsupported combinations. |
| `NOT_APPLICABLE` | A distinct governed dimension owns the change; `STALE ↔ READY` is freshness-only rather than a duplicate reliability result. |

## Typed evidence boundary

Current `IntelligenceDelta` references carry freshness and Unified-State
availability but intentionally do not carry raw `ReliabilityStatus` or native
`HistoricalIntegrityStatus`. Conditional reliability and historical-integrity
rules therefore require immutable `IntelligenceDomainTypedInterpretationEvidence`
bound to the exact `IntelligenceDomainDelta` fingerprint.

Without that evidence, route loss/recovery is `NON_COMPARABLE` with
`INSUFFICIENT` sufficiency; historical fingerprint-only changes are
`NON_COMPARABLE`. The interpreter never reverse-engineers projected historical
`CONFLICTED` into native `INVALID`.

## Non-action boundary

The interpreter emits only vocabulary frozen by the approved policy. It cannot
emit thesis, opportunity, generic investment-risk, bullish/bearish,
recommendation, BUY/HOLD/SELL/TRIM/ROTATE, signal, order, or trade semantics.
Multiple objective interpretations coexist independently; there is no global
positive/negative or overall-improved/degraded collapse.
