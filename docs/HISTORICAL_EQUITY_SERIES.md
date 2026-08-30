# Historical equity series

Each historical equity point samples the persisted session-end `BacktestPortfolioState`: cash plus its frozen marked holding value. Points retain the exact portfolio-state and mark IDs, realized/unrealized P&L, exposure, costs, warnings, and deterministic fingerprint. No weekend interpolation or current/latest mark lookup is used.

For `DAILY_CLOSE`, the session-complete builder obtains every frozen trading session from `ReplayClock`, reconstructs a valuation-only portfolio state from unchanged eligible ledger events plus that session's marks, and then samples after session-end effects. No-trade sessions therefore create a state and equity point but never a synthetic ledger event.

The series is ordered by evaluation timestamp and feeds portfolio return and drawdown into the existing performance-report adapter. Trade expectancy, R, profit factor, and MFE/MAE remain separate normalized-trade metrics. Open holdings remain marked at run end; they are never forced closed to report portfolio equity.

Consecutive session equity observations supply volatility, Sharpe, and Sortino inputs. A missing/stale mark retains existing portfolio valuation warnings rather than using a future or current price.
