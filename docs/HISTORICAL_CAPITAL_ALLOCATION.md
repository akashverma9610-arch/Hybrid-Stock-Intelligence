# Historical capital allocation

Historical capital allocation is a backtest-only `RANK_ORDER` decision. At a replay timestamp, open-position management is processed before new entry opportunities. Candidates rank by frozen score, confidence, risk/reward, then stable signal ID. Cash is reserved once per selected hypothetical fill; rejected signals remain visible with an explicit insufficient-cash or unsupported-sizing reason.

The immutable paper-config snapshot now carries a frozen sizing specification: basis, fixed-notional or fixed-risk capital where applicable, `FLOOR_INTEGER` quantity rule, minimum quantity, fractional-share permission, currency, methodology version, and fingerprint. `UNIT_BASIS` remains one unit. `FIXED_NOTIONAL` divides frozen notional by the actual canonical fill price; `FIXED_R_R` divides frozen risk capital by the actual-fill-to-structural-stop risk. NSE delivery fixtures use integer quantities and never invent fractional shares.

Missing/zero capital, invalid fills/stops, zero risk, unsupported rounding, or a fully unaffordable sized position fail closed. Risk sizing never clips a calculated quantity to remaining cash. Initial capital is not double-counted when an initial-capital ledger event is present.

Allocations, paper-to-ledger links, and ledger events are immutable. A later deposit, exit, signal, or allocation-policy version cannot alter a prior allocation.
