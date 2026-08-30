# Paper Fill Model

Historical replay supplies this model a timing-approved entry window. It retains responsibility for whether and how entry, gaps, exits, and same-bar ambiguity are evaluated; the timing adapter never reimplements those rules.

For a conservative same-bar stop/target conflict the stop takes precedence. `UNRESOLVED` keeps the outcome insufficient rather than inferring tick ordering. When the frozen configuration enables it, reaching T1 moves only the residual protective stop to breakeven; the original trade plan is not changed.

Historical allocation sizes after this model has produced the actual fill, preserving gap-price effects in the frozen sizing decision.

V1 supports configured marketable-trigger and limit-zone simulations. A confirmation breakout fills only after its bar close is known. A limit fill requires OHLC range intersection with the configured zone. Entry/exit slippage and per-unit costs are explicit versioned configuration values.

For a long stop gap, `MARKET_OPEN` fills at the available opening price (then exit slippage), not the old stop level. If target and stop are both touched in one daily OHLC bar, the configured same-bar policy decides; V1 supports conservative stop-first, optimistic target-first, or unresolved/lower-timeframe-required behavior. No intrabar tick path is invented.
