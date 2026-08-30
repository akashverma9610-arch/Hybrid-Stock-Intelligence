# Automated research cycle

The automated cycle executes only an existing human-approved `PLANNED` experiment through an injected canonical executor on explicitly permitted `TRAIN` and `VALIDATION` partitions. Baseline and experimental candidates receive identical partition inputs; returned evidence is immutable and selection remains baseline-relative.

TEST/OOS partitions are rejected before executor invocation. The cycle may create robustness records, a frozen existing `CandidateSelectionResult`, and a provenance-only future-OOS queue entry. A separate `FutureOOSAssignment` may later attach that exact selection to a chronologically future TEST window; it does not rerun research selection. The cycle cannot alter an experiment definition, promote or activate a strategy, or affect a portfolio, broker, or real account.

## Runtime capability boundary

The services in this document remain reusable direct library services for tests,
manual development, and controlled internal use. There is no production
scheduler or runtime orchestrator that invokes them automatically. Any future
runtime must first use `FeatureSettings.require_automated_self_improvement_research_enabled()`.
That feature defaults to disabled, is experimental and deferred, and checking
it has no persistence or governance side effects.
