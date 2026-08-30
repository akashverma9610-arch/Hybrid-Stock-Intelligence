# Portfolio Accounting

V1 uses the explicit `weighted-average-cost-v1` methodology for delivery holdings. A buy/add increases cost basis by gross amount plus recorded fees and taxes. Average cost is total cost basis divided by quantity. A partial sell/reduction removes sold quantity at the same current weighted-average cost; realized P&L is net proceeds (gross less fees/taxes) minus that removed cost. The remaining position retains the same average cost. FIFO, LIFO, and tax-lot accounting are not silently substituted.

A split multiplies quantity by its configured ratio and leaves aggregate cost basis unchanged. A bonus multiplies quantity by `1 + ratio`, also preserving aggregate cost basis; V1 therefore reduces per-share average cost deterministically. Both are separate append-only corporate-action records. Dividends are separate cash flows, not unrealized price P&L.

Mark-to-market P&L is market value minus remaining cost basis. Realized P&L and dividends are reported separately.
