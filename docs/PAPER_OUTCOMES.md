# Paper Outcomes

Paper outcomes retain fill state, entry/exit, gross and net hypothetical P&L, original-risk R multiple, T1/T2, stop, invalidation, expiry, MFE, MAE, and price-bar references. MFE/MAE use only bars from entry through simulated closure.

The original forecast—entry, stop, targets, thesis, score, and confidence—is immutable. Actual simulated outcomes are separate records. Strategy-wide statistics, benchmarking, and self-improvement are intentionally deferred.
# Historical chronology safeguards

Outcome MFE and MAE begin at the hypothetical fill bar and stop at closure. Time stops use exchange-calendar sessions rather than calendar days. Stale or invalid bars fail closed and cannot manufacture a fill, target, stop, or excursion update. A later corrected bar belongs to a new historical input/run, not a rewrite of the stored outcome.
