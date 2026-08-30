# Historical backtest portfolio replay

Backtest portfolio state is a separate immutable model and never reads or mutates a user `Portfolio`. V1 begins `CASH_ONLY_START`; no historical holding is invented. Append-only backtest ledger events are deterministic fixture/manual inputs, not signals or fills.

The pure adapter delegates weighted-average cost, partial-sale realized P&L, split/bonus treatment, exposure, and heat coverage to the Phase 6A `PortfolioEngine`. It selects only ledger events effective and known by the replay timestamp and only valid, non-stale price references known at that time. Missing marks produce explicit warnings; no forward fill occurs. Cash cannot become negative.

Each persisted state freezes ledger IDs, corporate-action ledger IDs, and detailed price-mark records (instrument, ID, value, observed/known time). Audit reconstruction rebuilds from exactly those frozen inputs and reports mismatch rather than consulting later prices/events. The persistence wrapper emits only `PORTFOLIO_RECONSTRUCTED` plus `PORTFOLIO_VALUED` or `PORTFOLIO_INSUFFICIENT`.

There is no capital rotation, signal, order, fill, paper trade, performance, or benchmark behavior in this phase.

Frozen portfolio states can be consumed by the separate historical portfolio-context gate adapter. A missing incumbent score, stop/risk coverage, or required friction remains explicit insufficient data; absent exposure in a known sector is correctly a zero existing allocation, not invented risk.

They may also be frozen inputs to historical rotation evaluation, which remains analytical and does not generate a ledger action.
# Paper-fill integration

Historical paper-ledger integration reuses the existing backtest portfolio ledger and replay engine. Hypothetical buys and sells are included in immutable reconstructed portfolio states, with no relationship to a real portfolio account.

Historical equity sampling uses the resulting frozen session-end state; it neither recalculates transactions nor creates an account mutation.

The session-complete valuation path reconstructs that same backtest-only state on no-trade trading sessions from the existing ledger and eligible marks.
