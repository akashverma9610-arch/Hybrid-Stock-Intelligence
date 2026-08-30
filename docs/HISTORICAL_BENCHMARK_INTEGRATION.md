# Historical benchmark integration

Historical benchmark comparison reuses the Phase 7B benchmark registry and comparison model. Each supplied series is frozen to the report window and persisted with its report. A missing Nifty, sector, momentum, moving-average, random, previous-version, or trader-like source is unavailable—not substituted with current data.

All comparisons are in-sample evidence only. They do not optimize, promote, or change a strategy.

Where a historical equity series is available, relative return uses the strategy's portfolio equity return rather than realized-trade P&L alone.

Comparability requires the benchmark series to share the same eligible session dates; missing benchmark sessions must remain explicit warnings.
# Walk-forward linkage

Walk-forward uses a canonical benchmark comparison only when the exact TEST interval has frozen point-in-time benchmark inputs. Otherwise the window result remains valid with an explicit benchmark-unavailable warning. Current/latest index values are never substituted.

Timestamped `HistoricalBenchmarkObservation` records retain benchmark run, session, source observation, value, and seed where relevant. Missing sessions are partial/unavailable; they are never silently forward-filled.
