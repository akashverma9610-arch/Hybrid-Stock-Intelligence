# Strategy hypothesis generation

Phase 9A.2 turns a frozen eligible recurring pattern into a structured, research-only `StrategyImprovementHypothesis`. It is not a strategy change. The complete boundary is:

`attribution ≠ hypothesis ≠ human approval for experiment ≠ experiment ≠ candidate selection ≠ strategy approval ≠ activation`

Generation uses only immutable runs, patterns, summaries, policies, budgets, and an approved target strategy version. It applies recurrence, OOS, source-quality, breadth, mixed-evidence, and budget checks. Anecdotal or mixed patterns become `REQUEST_MORE_EVIDENCE`; no qualified pattern produces `NO_CHANGE_RECOMMENDED`; data-quality clusters can produce only `DATA_QUALITY_CHANGE`.

Every actionable hypothesis uses an allowlisted configurable target domain, mechanism, expected benefit, and potential downside. PIT, audit, governance, gate-architecture, fairness, and real-account invariants are prohibited targets. Deduplication merges overlapping frozen support; rankings retain transparent support, counterevidence, and complexity factors.

`HypothesisReview` is insert-only and requires an explicitly attested `human:` reviewer plus an exact evidence fingerprint. `APPROVE_FOR_EXPERIMENT` merely permits later controlled research; it does not select, approve, promote, or activate a strategy. No `StrategyExperiment` or candidate delta is created here.
