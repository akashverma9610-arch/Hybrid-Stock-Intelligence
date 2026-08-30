# Performance Analytics

V1 normalizes frozen paper outcomes into closed, open, and unfilled records. Win rate uses closed outcomes only. Expectancy is average net P&L per closed trade; average/median R use closed trades with defined R. Profit factor is gross profits divided by absolute gross losses and remains unavailable when no losses exist. Equity starts from configured capital and advances at closed net P&L; drawdown is peak-to-trough on that curve.

Sharpe and Sortino use configured risk-free rate and annualization, and return unavailable for sparse/zero-variation data. Small samples carry explicit warnings; results are in-sample observations, never proof of superiority.

Reports are frozen at their evaluation cutoff. Their datasets retain exact trade and benchmark-input IDs; event and retrieval timestamps must both be eligible by that cutoff. A later report may include July inputs, but cannot rewrite a June report.
