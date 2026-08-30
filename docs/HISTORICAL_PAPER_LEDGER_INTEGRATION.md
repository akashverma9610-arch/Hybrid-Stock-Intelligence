# Historical paper-to-ledger integration

A paper fill is hypothetical. Once a frozen allocation funds it, the integration emits `HYPOTHETICAL_BUY` into the existing backtest-only ledger. It never creates a real portfolio transaction, broker order, demat interaction, or live-account cash movement.

T1 creates a partial hypothetical sell and a closed outcome creates the residual sell. Ledger cash impacts reconcile to the frozen paper outcome using its canonical cost total; fees are allocated across the ledger legs without charging them a second time. Existing `BacktestPortfolioReplayEngine` reconstructs the resulting cash, holdings, realised P&L, exposure, and marks.

The BUY quantity comes from the frozen sizing specification and actual paper fill, never a planned entry, current account, or live setting. The sizing reference/fingerprint, raw quantity, final quantity, required cash, and fail-closed reason are retained in the immutable paper-ledger link.
