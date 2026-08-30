# Liquidity and SMC proxies

Rules 8 and 51 map repeated highs/lows within configured tolerance as buy-side/sell-side liquidity proxies. Pools retain level, origin, first/last confirmation time, touch count, and input IDs. Stop clusters are inferred likely locations only; exact broker stops and quantities are unobserved.

Rule 52 sequences pool → current-bar sweep/break → reclaim or acceptance using timestamps already present by the as-of snapshot. Absorption is unavailable without order-book data and is never asserted as factual.
