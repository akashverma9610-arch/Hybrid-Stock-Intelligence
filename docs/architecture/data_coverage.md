# Real Data Coverage and Readiness

Code support is not data readiness. `DataCoverageRecord` measures actual,
already-stored canonical evidence for one instrument, universe snapshot, and
`as_of`; it never fetches a provider, generates a missing fact, or scores a
stock. Statuses are `READY`, `PARTIAL`, `MISSING`, `STALE`, `CONFLICTED`, and
`UNAVAILABLE`.

Tracked domains are identity, sector/industry, current quote, historical OHLCV,
historical membership, symbol history, corporate actions, price-adjustment
integrity, fundamentals, filings, ownership, promoter pledge, delivery,
news, catalysts, market/sector/macro context, and company sensitivity. The
summary reports counts and public-safe ready percentages per domain plus a
deterministic engineering gap list and the downstream engines blocked.

Deep-analysis readiness is coverage only—not an opportunity score:
`DEEP_ANALYSIS_READY`, `DEEP_ANALYSIS_PARTIAL`, or
`DEEP_ANALYSIS_UNAVAILABLE`. Pre-breakout and inflection readiness have their
own exact required-data sets. A missing delivery, ownership, gross-block, or
historical-taxonomy fact cannot become a pass.

`python -m app.runtime coverage-report` reads only the persisted local
universe, taxonomy, and canonical quote snapshots. It creates no provider call
or analysis job. Where a canonical source/store has not been composed, that
domain remains missing rather than being inferred.

For the #038D minimum package, historical stock evidence requires 252 stored
daily bars before it is `READY`. Shared market context is read once from
canonical `NIFTY_500`, with the existing `NIFTY_50` identifier retained only as
an explicit fallback. A stock series without a canonical corporate-action
source remains `PARTIAL` for price-adjustment integrity even when raw bars are
present; no raw series is silently described as fully adjusted.

`CURRENT NSE UNIVERSE` is not a `HISTORICAL UNIVERSE`: historical membership
and historical taxonomy need their own effective/PIT records. Likewise, stored
OHLCV bars are not automatically sufficient lookback or full
corporate-action-adjusted history. Delivery data is not inferred from volume.
