# Point-in-Time Data

`BacktestLookaheadGuard` fails closed on future event, publication, retrieval, or effective times. Financial knowledge follows publication rather than period end; restatements and earnings reschedules become visible only when announced. Historical analytical replay applies this guard after the normal validated as-of repository filter; future records cannot enter merely because they are currently stored.

The replay regression matrix covers market, index, sector, financial/restatement, research/crowd, surveillance, earnings-schedule, and universe-membership attacks through the snapshot-builder boundary rather than guard-only unit tests.
