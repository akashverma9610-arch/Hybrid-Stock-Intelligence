# Audit and Reproducibility

Decision audit records contain internal references to as-of data, universe and
portfolio snapshots, versioned registry/score/confidence/gate/rotation policies,
source-status summaries, final public decision, and internal evidence IDs.
Records are append-only Core API snapshots; later paper outcomes/benchmark
results are separate `DecisionOutcomeLink` records and never rewrite the input
explanation.

Internal reconstruction uses frozen IDs and version references, validates record
fingerprints, and has no "latest" fallback. The public API intentionally does
not expose diagnostic IDs, rule inventory, weights, thresholds, gate IDs, or
evidence IDs. Existing detailed audit reconstruction services remain the source
of canonical engine-level verification.
