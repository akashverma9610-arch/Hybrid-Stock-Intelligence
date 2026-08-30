# Benchmark Engine

The V1 registry defines eight transparent benchmarks: Nifty 50, Nifty 500, mapped sector index, fixed momentum, fixed moving average, seeded random selection, frozen previous strategy version, and trader-like baseline. Price versus total-return semantics are explicit; dividends are never assumed. Random results retain seed and distribution. Mock static universes carry a survivorship limitation.

Benchmark runs retain frozen historical input IDs. Rebalances, MA state, universe membership, and prior-strategy outcomes are selected as-of the report cutoff; later observations cannot enter an earlier run.
# Historical integration

Historical benchmark runs use only point-in-time source series frozen to the same report window. Missing source data is recorded as unavailable; current index levels, constituents, or configurations are never used as a fallback.
# OOS session alignment

OOS benchmark evidence is valid only for frozen timestamped sessions that align with the strategy TEST sessions. Partial or unavailable coverage is explicit and does not alter strategy metrics.

Experiment comparisons retain existing canonical benchmark references where available. Benchmark results never enter TEST candidate selection.
