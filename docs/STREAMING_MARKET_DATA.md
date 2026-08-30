# Streaming market-data boundary

`app.market_data.streaming` is a synchronous, provider-neutral live-feed
runtime boundary. It owns subscriptions, explicit connection/reconnect state,
bounded exponential-backoff calculation, heartbeat health, and the hand-off of
validated canonical quotes to the existing append-only `MarketDataSnapshotWriter`.
It deliberately starts no thread, scheduler, polling loop, or network client:
the hosting application must explicitly call `start`, `receive`, `heartbeat`,
`disconnected`, and `retry`.

`app.market_data.kotak_neo_streaming` supplies the V1 Kotak payload adapter.
It maps injected/mock quote frames to the existing `CanonicalQuote` model,
including timestamped `MarketDataProvenance`, session-aware freshness, quality
validation, and immutable local-store writes. Frames must match an active,
explicit provider-token subscription; malformed or mismatched frames are
rejected without creating a fact.

The `KotakNeoLiveStreamingTransport` is an opt-in placeholder. With its default
setting it fails closed as disabled; with opt-in it still fails closed as pending
until an independently validated provider WebSocket contract is approved. No
credential, network, session, WebSocket client, automated retry worker, account
endpoint, order, portfolio mutation, or strategy action is implemented here.

The feed is data collection only. A fresh quote does not create an analysis,
signal, paper trade, promotion, activation, or live-account effect.
