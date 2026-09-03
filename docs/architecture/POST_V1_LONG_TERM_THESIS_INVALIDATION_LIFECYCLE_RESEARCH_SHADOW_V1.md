# Long-Term Thesis Invalidation Lifecycle — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

This pure lifecycle receipt consumes the existing Compounder, Inflection, and
Policy Transmission research-shadow receipts for one canonical instrument and
one UTC-normalized as-of time. It preserves their immutable identities and
fingerprints, rejects duplicate family inputs and mismatched PIT lineage, and
never creates a second thesis, portfolio state, score, setup, action, or order.

`DATA_INSUFFICIENT`, `EVIDENCE_CONFLICTED`, and `NOT_APPLICABLE` propagate as
evidence/readiness states only. In particular, `DATA_INSUFFICIENT` and
`POLICY_DEFINITION_MISSING` cannot mean failed thesis, negative evidence,
SELL, downgrade, or invalidation. A conflict is preserved rather than resolved.

There is no structured canonical thesis-assumption schema, thesis-version
supersession rule, family invalidation condition, review cadence, freshness
threshold, materiality rule, recovery/revalidation rule, or temporary-versus-
structural deterioration definition. Thus complete compatible shadows produce
only `POLICY_DEFINITION_MISSING`, including the explicit
`INVALIDATION_CONDITION_UNAVAILABLE` blocker. `INVALIDATION_CONFIRMED` is not
an output in V1.

Rule 46 remains a separate exact `PRICE_STRUCTURE_INVALIDATION` context. It is
not silently relabelled as a long-term assumption invalidation. Legal or
governance evidence can remain upstream evidence but cannot invalidate a thesis
without an approved canonical link. Banks, NBFCs, insurers, unknown and
non-comparable classifications remain as supplied by their shadows; no
non-financial assumption is applied to them.

All output is `WATCH_ONLY / NON_EXECUTABLE / RESEARCH_SHADOW_V1`. No runtime
clock, persistence, provider, API/UI, portfolio, broker/order, `app.signals`,
LLM, market scan, or execution dependency exists.
