# Portfolio Snapshots

`PortfolioEngine.reconstruct` uses only transactions and corporate actions whose effective and known timestamps are both at or before the requested as-of timestamp. It selects only valid price and analytics records whose observed/as-of and known timestamps are also eligible.

Thus later buys, sells, prices, splits, bonuses, scores, gates, stops, targets, or sector labels cannot change earlier snapshots. Missing prices produce partial valuation rather than a fabricated LTP. Missing analytics remain unavailable; missing sector maps to `UNKNOWN` and remains in the exposure denominator.

Snapshots retain cash, active holdings, price references, P&L, allocations, sector exposure, heat coverage, analytics, methodology version, and source ledger cutoff. The repository persists them immutably and audit reconstruction returns the historical state with its eligible ledger window.
