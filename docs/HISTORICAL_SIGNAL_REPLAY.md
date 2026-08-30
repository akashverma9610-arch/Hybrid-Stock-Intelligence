# Historical signal replay

Historical signal replay is a point-in-time adapter over the canonical signal lifecycle. A replay reference freezes the run, analytical evaluation, contextual gate, optional rotation evaluation, backtest portfolio state, SignalRecord, signal-config version, and TradePlan reference. Signal lifecycle events append independently; the SignalRecord itself is never rewritten after creation.

Signal generation validates that every frozen analytical, gate, rotation, and portfolio dependency is eligible no later than the generation timestamp. Trigger revalidation uses only observations whose close/known time is eligible at that replay timestamp. This adapter creates no real portfolio mutation, broker order, live order, or performance report.

Audit reconstruction follows the frozen reference chain and rejects missing or timestamp-incompatible dependencies. Signal configuration is resolved through the immutable versioned snapshot rather than a current/latest configuration lookup.

Signal audit now resolves the authoritative immutable signal-config snapshot and verifies its ID, version, and fingerprint. Tampering a frozen signal, analytical, gate, rotation, portfolio, plan, config snapshot, fingerprint, or version fails closed; it never falls back to a newer configuration. Trigger time is passed to the frozen execution-timing boundary; generation time is never used as an execution time.

Waiting, expired, cancelled, and invalidated signals remain immutable `SignalRecord` objects. Their lifecycle transition is represented by a separate append-only event; later favourable bars never reactivate a terminal historical state.

Only a timing-approved, funded hypothetical paper fill can reach the backtest-only ledger. A rotation or cash-deployment analytical result, a waiting signal, or an unfunded trigger never mutates ledger cash or holdings.
