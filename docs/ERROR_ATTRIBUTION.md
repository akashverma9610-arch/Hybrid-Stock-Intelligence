# Error attribution

Phase 9A classifies frozen observations as deterministic associations, never proven causes. Each result retains the source observation, its source class, frozen provenance, ruleset ID, and an evidence strength of `ASSOCIATED_WITH`, `LIKELY_CONTRIBUTOR`, or `INSUFFICIENT_EVIDENCE`.

The V1 rules cover observable false-breakout, high-score, weak-RS, sector/regime mismatch, reward/risk, volume-confirmation, stop-width counterfactual, entry-timing, friction, capital-velocity, and rotation-underperformance patterns. A missing, stale, PIT-ineligible, or audit-invalid observation becomes `DATA_QUALITY_FAILURE` and is excluded from strategy-quality pattern conclusions.

Precedence is fail-closed: out-of-run/version/source-policy observations are skipped; invalid data produces only a data-quality association; otherwise several independent associations may be retained. No artificial root cause is selected.
