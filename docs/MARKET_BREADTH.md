# Market breadth aggregation

`BreadthAggregator` derives provider-neutral breadth facts from explicit,
timestamped universe membership and canonical current quotes. It compares a
fresh last price with previous completed close: greater is advance, lower is
decline, and exact equality is unchanged. Missing previous close is unclassified;
missing or stale quotes reduce coverage and are never treated as zero.

The result reuses `MarketBreadthObservation` and adds a low-volume
`MarketParticipationSnapshot` with coverage, stale/missing counts, A/D and
volume ratios where available, new-high/low availability, and raw leadership
concentration. It is data only—not a regime, crisis, euphoria, or trading score.
Historical constituent membership is resolved as-of the aggregation timestamp.
If point-in-time membership is absent, output retains an explicit limitation.

`IndexObservationService` retrieves canonical latest index/VIX observations and
historical index bars through the dedicated historical-bar store. These facts
can later feed Regime, Crisis, Euphoria, and sector rotation; no provider,
network, scheduler, API endpoint, portfolio, governance, or order path exists.
