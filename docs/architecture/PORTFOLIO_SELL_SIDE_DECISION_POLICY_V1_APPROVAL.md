# Portfolio Sell-Side Decision Policy V1 Approval

**Status: APPROVED — NOT SELECTED — NOT ACTIVE — NO ACTION PRODUCER.**

This approval freezes the safe core of the prior proposal. It does not approve
TRIM, alerts, portfolio mutation, broker execution, short selling, strategy or
scoring changes, Six Gates changes, or rotation-threshold changes.

| Field | Approved value |
| --- | --- |
| Policy | portfolio-sell-side-decision-policy / v1-approved |
| Approved fingerprint | 78bef6fc3a5a3373d6ae27f48010ee431b16cf77bcab6a57da56413af579927f |
| Proposal lineage | portfolio-sell-side-decision-policy / v1-proposed |
| Proposal fingerprint | a11e84973ca19f4e0e23a4afc1ca989a9cfe4add1e8451750f333327651d6253 |
| Reviewer | human:Akash-Verma |
| Approval state | APPROVED; selected=false; active=false |
| Thesis states | INTACT, WEAKENED, INVALIDATED, INSUFFICIENT |
| Decisions | HOLD, EXIT_TO_CASH, ROTATE, REVIEW_REQUIRED, NO_ACTION |
| Trim state | TRIM_NOT_AUTHORIZED_V1 |
| Capital efficiency | CAPITAL_INEFFICIENT, descriptive only |

The approved precedence is: REVIEW_REQUIRED; invalidated plus eligible
replacement to ROTATE; invalidated without replacement to EXIT_TO_CASH; future
trim rule unavailable; valid governed rotation to ROTATE; intact thesis to
HOLD; otherwise NO_ACTION. The step-four placeholder cannot authorize TRIM.

EXIT_TO_CASH requires current and sufficient evidence, no material unresolved
conflict, INVALIDATED thesis, and no eligible governed replacement. ROTATE
requires the existing capital-rotation engine and all of its existing edge,
confidence, executable-gate, R:R, friction/tax, portfolio, confirmation/
cooldown, entry/stop/invalidation, and sector-policy requirements. HOLD
requires intact, current/sufficient evidence, no invalidation, no authorized
risk reduction, and no valid rotation. P&L is not an action rule.

Forward-paper intelligence remains descriptive only: it cannot alter thesis,
authorize exit/rotate/trim, alter thresholds, or mutate this policy.

## Governance storage boundary

The repository's persistent approval mechanisms are strategy-specific,
including Pre-Breakout and approved-strategy records, so this portfolio policy
is deliberately not written through them. The approved immutable,
fingerprinted source artifact is app/portfolio/sell_side_policy.py. A separate
future task may add a generic append-only governance-policy repository if
durable database storage is needed; it must not reuse a strategy-specific
approval record.

## Deferred policy gaps

TRIM remains entirely unapproved: trigger, quantity, target/extension,
valuation/euphoria, R:R deterioration, concentration-driven sizing, tax-aware
sizing, and re-entry rules all require later explicit approval.
