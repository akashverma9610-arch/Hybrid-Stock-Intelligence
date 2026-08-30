# Exchange Calendar

`ExchangeCalendar` is provider-independent. A day is a trading session only when it is a weekday and is not in its explicitly configured holiday set. Gate 2 holding duration and Gate 6 blackout both use this calendar. Tests use deterministic NSE-like weekends and configured holidays; no live holiday source is used.
