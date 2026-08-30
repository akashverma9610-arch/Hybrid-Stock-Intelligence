# Intelligence delta / change detection

`IntelligenceDelta` is a pure, immutable comparison of two already rebuilt
`UnifiedIntelligenceState` artifacts for one canonical instrument.

```
previous UnifiedIntelligenceState + current UnifiedIntelligenceState
  -> IntelligenceDelta -> potentially affected output contexts
  -> future explicit reevaluation layer
```

The comparison requires the same instrument and strict chronological ordering:
`previous.as_of < current.as_of`. It does not reorder inputs. A later state with
the same bounded evidence references, statuses, freshness, versions,
dependencies, and completeness yields `NO_SEMANTIC_CHANGE`; the timestamp alone
does not fabricate a change.

The contract records bounded domain-reference changes only: evidence added,
removed, or replaced; availability, freshness, provenance, integrity,
reliability, warning, dependency, completeness, and version-lineage changes.
It preserves previous/current evidence references and state lineage without
copying provider payloads or asserting a cause.

`IntelligenceDeltaImpactPolicy` maps changed evidence domains to output views
that may need later reevaluation. This routing has no investment meaning:

- Delta is not a recommendation.
- Delta is not an alert or notification.
- Delta is not a trade, order, signal, or execution permission.

Portfolio context is deliberately absent because it is not part of canonical
instrument intelligence. State origin is also non-semantic, so scanner, manual,
or portfolio-request origins do not alter the delta. There is no delta table,
repository, cache, listener, scheduler, worker, provider request, state rebuild,
score calculation, gate execution, or output-projection recomputation.

## Canonical serialization and reconstruction

`intelligence-delta-serialization-v1` serializes every semantic field of a
delta and nested domain delta using explicit enum values, timezone-aware ISO
timestamps, canonical tuples, and bounded evidence-reference lineage.
Deserialization reconstructs the stored historical artifact only: it validates
the nested-domain fingerprint, overall delta fingerprint, and deterministic
delta ID. Unknown fields, enum values, naive timestamps, malformed structure,
and semantic tampering fail closed.

`reconstruct_intelligence_delta(previous_state, current_state, expected_delta)`
explicitly recomputes the supplied state pair and requires exact equality. It
does not rebuild either state, read a repository, or apply today’s impact
policy to reinterpret historical affected-output lineage.

Serialization is not persistence. A serialized delta remains neither an alert,
recommendation, nor trade instruction.

`project_intelligence_delta(delta)` provides a deterministic manual inspection
view of that already-valid delta. It exposes only before/after lineage, typed
domain changes, transitions, dependency changes, and affected-context lineage.
The projection is not interpretation, alerting, recommendation, or automatic
output reevaluation; it has no persistence or background invocation.
