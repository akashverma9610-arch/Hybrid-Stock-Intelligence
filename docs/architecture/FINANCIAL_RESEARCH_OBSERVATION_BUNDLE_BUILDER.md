# Financial Research Observation Bundle Builder

`build_financial_research_observation_bundle(...)` is a pure, deterministic
assembler for one instrument at one explicit, timezone-aware knowledge cutoff.
It accepts only already-materialized `FinancialMetricObservation` artifacts,
their already-created `FinancialResearchObservationAttestation` artifacts, and
typed `FinancialResearchInputFailure` summaries.

The builder validates the exact frozen
`financial-research-observation-bundle-schema / v1-approved` lineage, checks
each supplied artifact fingerprint, canonically orders the inputs, and builds
the immutable `FinancialResearchObservationBundle`.  The frozen bundle contract
then enforces exact same-`as_of` selection cutoffs, observation/attestation
coverage, one-instrument scope, lineages, duplicate rejection, semantic
collision rejection, and observation/failure contradiction rejection.

Bundle building is not fact-vintage selection, observation materialization,
Brain-state integration, generic research wrapping, trajectory construction, or
interpretation.  It does not access a database, store, provider, network,
filesystem, environment, clock, or persistence layer.  It does not calculate
directionality, thesis/opportunity semantics, alerts, recommendations, or
actions.

`COMPLETE` and `PARTIAL` period identities are preserved as factual inputs.
`INSUFFICIENT` remains inadmissible.  Supplied multiple accounting periods for a
metric remain independent bundle entries; no latest-only or history-horizon
selection occurs.
