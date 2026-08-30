# Portfolio State Model

Phase 6A models historical capital state only: immutable `Portfolio`, `CashPosition`, append-only `PortfolioTransaction` and `CorporateAction` records, derived `PortfolioHolding`, `HoldingAnalytics`, exposure/risk summaries, and immutable `PortfolioSnapshot` records.

Cash is an explicit active position. A portfolio with no holdings and cash is `ALL_CASH`; it is not forced into a security. Closed holdings leave the active snapshot while their ledger history and realized P&L remain auditable.

The engine intentionally has no recommendation, rotation, buy, sell, sizing, broker, order, paper-trade, or provider interface.

The separate Phase 6B rotation layer may consume immutable portfolio snapshots as one input. It does not alter the portfolio state, cash, holdings, or ledger, and its analytical preference is not an execution instruction.
