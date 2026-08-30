# Signal Lifecycle

A signal is an immutable analytical setup candidate, never an order or broker instruction. `WAITING_FOR_TRIGGER` means a complete setup exists but its machine-testable entry condition has not occurred. `TRIGGERED_ANALYTICALLY` records that the condition later occurred; it does not mutate cash/holdings, reserve capital, create a transaction, or execute anything.

Signals retain their original score, confidence, gate/rotation references, trade plan, evidence, and configuration versions. Later revalidation creates append-only lifecycle events for trigger, gate block, invalidation, cancellation, expiry, or unchanged setup state. Original records are never overwritten.

`WAIT_SETUP` and `CASH_SETUP` are valid outcomes when no stock setup is usable. Exit/reduce setups require explicit structural evidence; an unrealized loss alone is insufficient.

Phase 7A may turn a retained signal into a separate hypothetical paper-trade experiment. It never changes the original signal or creates a real portfolio action.
