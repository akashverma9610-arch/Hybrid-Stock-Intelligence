# Data Flow and Failure Propagation

1. Provider-neutral adapters normalize only obtained source facts.
2. Readiness/reliability selects a declared source or emits a distilled failure.
3. Historical integrity admits only evidence eligible at `as_of`.
4. Validators enforce schema, identity, numeric, timestamp, cross-field,
   duplicate/conflict, freshness, and lineage rules.
5. Engines consume canonical stores and immutable snapshots, not provider payloads.
6. Macro, sector economics, company sensitivity, and catalysts retain common lineage and point-in-time availability before informing research context.
7. Pre-breakout and inflection scanners consume that stored context and emit only frozen candidate/setup evidence. Their candidates then enter the normal research path; they do not bypass 61 diagnostics, score, confidence, gates, or portfolio comparison.
8. Taxonomy and coverage records are read before sector-dependent research.
   Missing industry/sector, historical membership, delivery, ownership, or
   fundamentals remains explicit; a current classification is never silently
   projected into historical analysis.
9. Historical identity, membership, corporate action, and price-adjustment
   records are evaluated before technical/backtest consumption. A raw series
   spanning a known price-transforming action remains partial, not silently
   adjusted.

`provider failure → reliability DEGRADED/UNAVAILABLE → validation/historical
PARTIAL or INVALID → diagnostic PARTIAL → existing confidence/gate policy →
distilled warning`. No layer is skipped to force a decision. Fallback, stale,
partial integrity, elevated drift, and unavailable audit records remain visible
in public-safe status summaries.

Timestamp control is evidence-specific: observations use `observed_at`, filings
and research use `published_at`, membership/actions use `effective_at`, source
capture uses `available_at`/retrieval, and every historical consumer evaluates
against explicit `as_of`.
