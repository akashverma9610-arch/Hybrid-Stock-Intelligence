# Long-Term Fundamental Inflection — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

## Purpose

This is a fail-closed evidence/readiness projection for
`LONG_TERM_FUNDAMENTAL_INFLECTION`. It consumes only the existing immutable
Long-Term Thesis Review and Research Shadow receipt. It does not calculate an
inflection, earnings surprise, acceleration, revision, confirmation, price
reaction, score, recommendation, or action.

The only output states are `DATA_INSUFFICIENT`, `EVIDENCE_CONFLICTED`,
`POLICY_DEFINITION_MISSING`, and `NOT_APPLICABLE`, always with
`WATCH_ONLY / NON_EXECUTABLE / RESEARCH_SHADOW_V1`. There is intentionally no
positive or negative qualification vocabulary.

## Current canonical evidence

| Dimension | Existing canonical capability | V1 result |
| --- | --- | --- |
| Revenue/profit facts and factual trajectories | PIT-selected facts and same-basis trajectories can be constructed when supplied | A factual delta is not momentum, acceleration, or inflection. |
| Period/scope/revision lineage | Fact-vintage policy retains explicit revision links and rejects later-restatement repair | Usable provenance only; no approved revision interpretation. |
| Earnings surprise | No canonical PIT consensus/estimate snapshot | `POLICY_DEFINITION_MISSING`. |
| Guidance and estimate revisions | No canonical guidance/estimate/revision observation contract | `POLICY_DEFINITION_MISSING`. |
| Announcement alignment | Filing publication/receipt times may be retained | No approved event-time alignment policy. |
| Price/volume confirmation or reaction | Historical bars exist subject to independent integrity/policy rules | No approved event window, benchmark, price basis, or reaction definition. |
| Confirmation, base effect, one-off handling | No approved inflection policy | `POLICY_DEFINITION_MISSING`. |

The frozen fact-vintage policy remains `KNOWLEDGE_AT_THE_TIME`: a later filing
or revision cannot repair an earlier as-of result. Incompatible statement scope,
basis, unit, scale, period, revision, source or PIT visibility is
non-comparable, never neutral.

## Research lineage and deferred definitions

Academic work on post-earnings-announcement drift and revenue/earnings
surprises motivates subsequent research, but does not select HSI’s event window
or threshold: [Jegadeesh and Livnat](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=903767)
and the [review record](https://doi.org/10.1016/j.jbef.2020.100446) are
methodological lineage only. SEBI Regulation 33 provides financial-results
disclosure context, not an HSI surprise, confirmation, price-reaction, or
qualification definition.

The following require separate approval and PIT-calibration before any future
calculation: revenue/earnings/margin acceleration formula; surprise source and
consensus vintage; confirmation count; exceptional-item and base-effect
treatment; revision/guidance semantics; event timestamp; benchmark and price/
volume reaction window; persistence, staleness, invalidation and shadow-outcome
methodology. No industry-standard convention is silently adopted.

## Branches and exact propagation

- Bank, NBFC, insurer, unknown, and structurally non-comparable entities are
  `NOT_APPLICABLE`; industrial revenue/margin/cash concepts are not applied.
- Conflicted selected coverage produces `EVIDENCE_CONFLICTED`.
- Missing, stale, non-comparable, temporally invalid, or unverifiable source
  coverage produces `DATA_INSUFFICIENT`.
- A valid non-financial receipt produces `POLICY_DEFINITION_MISSING` with
  every missing definition listed. It does not imply a favourable or adverse
  company condition.

The implementation has no repository, provider, persistence, API/UI,
portfolio, broker/order, `app.signals`, runtime-clock, score, market scan, or
paper-trading dependency. It is deleted as one isolated module/test pair for
rollback.
