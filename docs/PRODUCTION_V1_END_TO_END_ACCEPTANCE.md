# Production V1 end-to-end acceptance

Production V1 is operational readiness, not execution authority. The ordered
loop is approved source refresh → immutable canonical evidence → reconciliation
and health → one Shared Brain → read-only U16 projections → governed stored
executable setup → internal forward-paper study → future stored bars →
descriptive outcome evidence.

`python -m app.runtime production-v1-status` reports each component and every
P0 blocker. `PRODUCTION_V1_READY` is emitted only when each mandatory source
and component is operational, PIT/recovery are proven, and no live-order path
exists. Deterministic tests never make an unconfigured source operational.

The local environment remains `PRODUCTION_V1_NOT_READY` until approved OHLCV,
index, delivery, membership, taxonomy, corporate-action, financial,
shareholding, macro, and news paths are configured, smoke-validated, and
sufficiently covered. No fallback source is invented.

Sector-index source-family health is intentionally separate from its current
consumer. Under the selected
`sector-universe-coverage-policy / v1-approved`, a factual `INDEX_BARS=PARTIAL`
family can support a `DEGRADED` (operational-with-limitation) Production-V1
component when the NIFTY 500 benchmark is ready and the existing Top-3 has at
least three fully evidenced sectors. The report must disclose excluded official
sector indices and their reasons. It never upgrades the raw family to `READY`,
does not imply full NIFTY 500 sector coverage, and blocks again if the
evidence-derived Top-3 minimum is no longer met.

Stored forward-paper composition is durable and provider-free. It accepts only
immutable executable setup artifacts and canonical bars committed before it
runs. It is opt-in and never starts from FastAPI startup.
