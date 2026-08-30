# Upstox Historical Candle V3

`upstox` is an optional, historical-only provider. It is independent from
`CURRENT_QUOTES=kotak_neo` and never enables an order, account, portfolio, or
streaming capability.

The adapter implements the official V3 daily-candle contract:

`GET /v3/historical-candle/{instrument_key}/days/1/{to_date}/{from_date}`

It accepts official BOD JSON instrument records and persists mappings only when
an NSE equity has exactly one `NSE_EQ` record with the same ISIN. The stored
provider reference is the official `instrument_key` (for example,
`NSE_EQ|<ISIN>`), not an exchange token. Broad and sector indices require one
exact `NSE_INDEX`/`INDEX` identity; NIFTY 50 is never substituted for NIFTY
500.

The local/private connection card accepts one secret `access_token`. It is held
only by the existing OS credential store. API responses, snapshots, audit rows,
the browser, and provenance expose only the configured boolean—not the token.
“Test Historical Data” is one bounded daily-history request. It resolves one
test instrument through the official BOD master using exact ISIN first and an
exact unambiguous NSE symbol only as a controlled fallback. It performs no
scan, diagnostics, account read, or trading call.

V3 returns candle arrays in timestamp, OHLC, volume, and optional open-interest
order. OHLCV is normalised to canonical bars with timezone-aware timestamps,
Decimal prices, provider/retrieval provenance, and duplicate/conflict handling
through `HistoricalIngestionService` and `HistoricalBarStore`.

Upstox's V3 historical-candle documentation does not establish a full
corporate-action adjustment guarantee. Therefore this implementation writes
`AdjustmentStatus.UNKNOWN` and `UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED`; it
does not claim raw, split-adjusted, or fully corporate-action-adjusted history.
Historical integrity can remain partial until separate corporate-action evidence
is available. The existing canonical OHLCV contract has no open-interest field;
returned OI is explicitly flagged as non-analytical rather than fabricated.

Live validation and bounded frozen-cohort ingestion are explicit local actions.
They are not scheduled, never run from diagnostics, and stop at the frozen 40
stocks plus an exact NIFTY 500 mapping when configured.

## Frozen-40 population

After an Upstox access token has been saved through the local Connections page,
an operator may run exactly one bounded population command:

```powershell
python -m app.runtime ingest-upstox-frozen-cohort --years 3
```

The command reuses the already persisted frozen 40-stock real-Brain cohort; it
does not select replacements and it does not inspect the remainder of the NSE
universe. It downloads the official NSE BOD master only to resolve those 40
identities plus an exact `NIFTY 500` index record. Equity mapping is exact ISIN
plus `NSE_EQ` first, then an exact unambiguous cash-equity symbol fallback.
Unmatched and ambiguous records remain explicit. The master URL/checksum are
retained with each immutable provider mapping, and each history request flows
through `HistoricalIngestionService` into `HistoricalBarStore`.

At least 252 stored daily bars are reported as sufficient for technical
lookbacks. Missing sessions, malformed rows, duplicate/conflicting bars, and
possible extreme price discontinuities remain quality signals. A discontinuity
does not create a synthetic adjustment: corporate-action integrity remains
partial until independent corporate-action evidence is present. The command
fails closed with `UPSTOX_ACCESS_TOKEN_REQUIRED` before downloading the master
or contacting the provider when no locally secured token is configured.

The subsequent real-Brain command is a separate stored-data action. It makes
zero provider calls. NIFTY 500 is supplied to Rule #6 relative-strength input
only when at least 252 eligible stored benchmark bars exist; market-regime
context continues to use its canonical NIFTY 50 input where present.

## Official NSE sector-index backfill

Task 38's official NSE sector/index registry remains the classification source.
Upstox only supplies licensed daily market history for the exact identities
already mapped there. The operator must run the non-persisting three-index
probe first, then may run the bounded mapped-index backfill:

```powershell
python -m app.runtime probe-upstox-sector-indices --years 3
python -m app.runtime ingest-upstox-sector-indices --years 3
```

The probe makes at most three V3 calls: exact NIFTY 500, an exact mapped
Healthcare index when present, and an exact mapped FMCG (or next deterministic
mapped) sector. Both commands filter the BOD master strictly to
`segment=NSE_INDEX` and `instrument_type=INDEX`. Official-to-Upstox resolution
is exact or case/whitespace/punctuation-normalized exact only; ambiguity stays
unresolved. Mapping evidence is written to
`reports/upstox_nse_index_mapping.json` and `.csv`.

Index volume and open interest are optional. A missing provider volume remains
canonical `null`, never zero. The historical store is immutable: an existing
conflicting Yahoo bar is retained alongside the Upstox observation; it is
never rewritten by the backfill. Canonical stored reads resolve one session
centrally by source policy (official exchange evidence, then licensed Upstox,
then Yahoo research history), while raw provider observations remain auditable.
An existing conflicting *same-provider* session remains a
`PROVIDER_REVISION_CONFLICT` and is never overwritten. Stored replay remains
network-free. The following status command performs no credential read and no
provider request; it reports raw Yahoo/Upstox observations and the central
canonical selection for exact NIFTY 500 and mapped Task 38 indices:

```powershell
python -m app.runtime upstox-sector-index-status
```

Current sector
breadth may use current membership with historical closes, but that does not
make the current constituent set valid for historical/PIT breadth.

## Current sector rotation readiness and bounded constituent history (U07)

The current/forward sector route is a stored-data composition over the existing
Mansfield relative-strength helper and the existing Pre-Breakout sector scan;
it is not a second sector-rotation engine.  It uses exact NIFTY 500 and exact
Task 38 sector-index identities, then uses only the current official NSE
constituent snapshots.  Current constituents are resolved to canonical NSE
equities by exact ISIN first and an exact unambiguous symbol only if no ISIN
match exists.  There is no company-name matching and no historical membership
backfill.

The status command has no credential read, provider request, or mutation.  It
uses canonical provider-resolved bars, reports 20/60/120-session Mansfield
relative strength, measures current constituent close history, and writes
auditable reports:

```powershell
python -m app.runtime current-sector-rotation-status
python -m app.runtime plan-upstox-sector-constituent-backfill
```

The Pre-Breakout Mansfield helper requires exactly its configured lookback of
aligned positive closes: 20, 60, or 120 sessions.  Consequently a 198-session
sector history is sufficient for its 20/60/120 measures, though it is not
sufficient for 200DMA breadth.  Canonical BBW needs 139 closes under the
existing 20-period band plus 120-session percentile convention.  Delivery
data is not manufactured: technical readiness can be reported while full
Pre-Breakout eligibility remains false when the existing required delivery
input is unavailable.  The Inflection route likewise remains unavailable
until its existing non-technical inputs are materialized.

Current breadth is a present-state calculation using today’s official
constituents and their stored closes (`last close > exact 50DMA/200DMA`). It
is marked `READY` only when every resolved current constituent has both
lookbacks, `PARTIAL` when only some do, and `INSUFFICIENT` when none do.  It is
explicitly **not** a historical/PIT breadth series.  No coverage threshold is
invented or used to make a partial sector eligible.

Only after the stored plan shows a genuine gap may an operator make the
separate explicit, sequential backfill call:

```powershell
python -m app.runtime ingest-upstox-sector-constituents --years 2
```

It considers only the plan’s insufficient, already canonical current
constituents; already-sufficient and unresolved identities are not fetched.
It maps the downloaded BOD master by the same exact identity rules, stores
immutable Upstox provider mappings and provider-versioned bars through the
existing ingestion service, and stops on an authorization/provider failure or
same-provider revision conflict.  It does not fetch fundamentals, select an
alternative universe, call diagnostics, or alter decision score, gates,
promotion, activation, portfolio, or trading state.  A later
`current-sector-rotation-status` refresh and the separate stored-only frozen
Brain trial are the only appropriate follow-up actions.

When only a subset of official sector indices has the existing 120-session
aligned production RS ready, a first bounded pass can be restricted to that
subset without altering any rotation formula or sector eligibility rule:

```powershell
python -m app.runtime plan-upstox-sector-constituent-backfill --rs-ready-only
python -m app.runtime ingest-upstox-sector-constituents --years 2 --rs-ready-only
```

`--rs-ready-only` is a stored-only routing filter. It chooses sectors solely
from the existing RS readiness result, deduplicates shared current constituents
by ISIN, excludes sufficient and unresolved identities, and prints both the
raw per-sector membership counts and the unique request estimate.  The default
commands retain the broader current-constituent plan.  On a stopped run, a
repeat recomputes the same stored plan; constituents that have since reached
the 200-session breadth minimum are skipped rather than fetched again.

### Partial current sector universe

The selected `sector-universe-coverage-policy / v1-approved` permits the
current Top-3 consumer to use only the evidence-derived subset when NIFTY 500
is ready and at least three sectors meet the existing aligned 20/60/120 RS and
`READY` breadth requirements. It does not change RS, breadth, or ranking
formulas. `INDEX_BARS` remains `PARTIAL` when any exact official index lacks
canonical history; Production-V1 reports its consumer as `DEGRADED` with the
explicit excluded sector/index/reason list rather than hiding the limitation.
No name proxy, fuzzy match, synthetic bars, or zero-score fallback is allowed.
Recovery and degradation are automatic from later stored evidence at the
requested `as_of` cutoff.

## Known U04 follow-ups

The following Analytics presentation issues are explicitly deferred and do not
alter canonical facts: some quarterly oldest/newest-period summaries need an
ordering repair, and corporate-action event dates can be present in
`event_details` while summary availability flags remain false. Also, provider
quarterly `net profit` is not globally promoted to canonical PAT: APOLLOHOSP
and SAFARI reconciled in the observed anchor probe while ORIENTTECH did not.
