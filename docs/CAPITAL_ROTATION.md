# Capital Rotation

Phase 6B applies the every-rupee-competes principle analytically: capital may remain in the current holding, remain as cash, or have a superior eligible candidate identified. It does not create a signal, order, broker instruction, quantity, reservation, sale, or purchase.

A later signal lifecycle may consume a rotation opportunity, but must separately validate its own setup and trigger requirements. A rotation opportunity with no valid current entry therefore remains a waiting analytical setup, not an entry action.

Candidates must have complete scorecards, sufficient configured confidence, `EXECUTABLE` gate status, valid entry/stop/invalidation structure, required sector support, acceptable structural R:R, portfolio-constraint clearance, and all configured anti-churn/friction conditions. Blocked candidates are retained as blocked and never ranked as deployable.

Holding comparison retains raw Decision Score and the approved Gate 2 capital-velocity adjustment separately. Only their explicit sum is the rotation comparison score; scorecards are never rewritten. A candidate must clear the exact versioned hurdle over the weakest comparable holding. An invalidated holding with no eligible alternative can result in `DEFENSIVE_CASH`, not forced rotation.
