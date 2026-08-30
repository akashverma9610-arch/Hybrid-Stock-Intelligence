# Research State Delta Full Observation-Slot Matching

**Status: factual matching hardening only.**

The former matcher grouped by `metric_id`, matched equal identities, then zipped
remaining same-label observations. The zip fallback could incorrectly pair Q1
revenue with Q2 revenue and has been removed.

`research_observation_slot_key(...)` now uses existing generic fields:
dimension, metric ID, value type, source-artifact type/role, unit, scale,
basis, scope, period identity, window, benchmark, and canonical identity
components. Value, artifact fingerprint, timestamps, dependency manifest, and
other mutable lineage are excluded. Methodology and dependency remain existing
pairwise parity checks, producing `NON_COMPARABLE` for a matched slot with drift.

Previous/current observations map by full slot. Exact slots compare; previous-
only slots are `REMOVED`; current-only slots are `ADDED`; duplicate full slots
or duplicate identity-component keys fail closed. Multiple same-metric slots are
valid. Thus Q1 retained at T2 pairs with Q1, while a newly present Q2 is `ADDED`.
Same-slot revised lineage can be factual `LINEAGE_CHANGED`; a value change can
be factual `VALUE_CHANGED`. These are not trajectory or action semantics.

`ResearchMetricDelta.semantic_slot_fingerprint` makes same-metric delta output
unambiguous and drives canonical ordering. This generic hardening does not
integrate financial observations/bundles/wrappers into Brain state. Policy v2
remains approved, unselected, and inactive. No state version, trajectory,
directionality, thesis/opportunity, persistence, provider/API/worker,
recommendation, or execution behavior changed.
