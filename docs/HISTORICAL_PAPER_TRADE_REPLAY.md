# Historical paper-trade replay

Historical paper replay delegates creation and simulation to the canonical `PaperTradingEngine`. The immutable replay reference records the source signal, paper trade/outcome IDs, frozen bar IDs, paper-config version, cost-model version, fill method, same-bar policy, gap policy, and final state. PaperTrade forecast fields are immutable; fills, lifecycle events, and PaperOutcome are separate append-only/immutable records.

The canonical engine handles trigger, expiry, cancellation, same-bar ambiguity, adverse stop gaps, targets, invalidation, time stop, MFE, and MAE. Bars are filtered by their known timestamp before simulation; later bars cannot enter a persisted frozen reference. No backtest ledger mutation, real-account change, broker request, performance report, or benchmark run is produced in this phase.

Paper audit resolves the authoritative immutable paper-config snapshot and checks its ID, version, fingerprint, cost model, fill method, same-bar policy, and gap policy against redundant frozen replay fields. A mismatched trade, outcome, snapshot, policy, cost model, or bar ID is an explicit audit failure. Historical timing supplies only the first legal entry bar and retains later legal bars for canonical outcome management.

Chronology fixtures cover T1/T2, structural and adverse-gap stops, configured breakeven residuals after T1, post-entry invalidation, and time stops. `PaperTrade` keeps its original plan and configuration references; fills, lifecycle events, and `PaperOutcome` are separate immutable/append-only records.

When explicitly funded by the historical allocation layer, paper fills are mirrored only into `BacktestPortfolioLedgerEvent`; no real-account object is involved.

Gap fills are also the sizing price: fixed notional and fixed risk-R never calculate quantity at a more favourable planned entry.
