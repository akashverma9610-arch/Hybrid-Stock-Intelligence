# Earnings Blackout

Gate 6 blocks `FRESH_ENTRY` when a verified scheduled result lies within the configured number of trading sessions. It counts sessions through `ExchangeCalendar`, not calendar days. Unknown or not-yet-verified schedules are `INSUFFICIENT_DATA` for fresh entries.

`HOLD_EXISTING`, `REDUCE_EXISTING`, `EXIT_EXISTING`, and `RISK_MANAGEMENT` pass this blackout because the gate must not prevent management of an existing position. No earnings provider is included.
