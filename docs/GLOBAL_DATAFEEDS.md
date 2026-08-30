# Global Datafeeds historical adapter

Global Datafeeds is an optional historical-OHLCV provider only. The intended composition is `CURRENT_QUOTES=kotak_neo` and `HISTORICAL_OHLCV=global_datafeeds`; selecting it never replaces Kotak quotes.

The adapter uses the documented `GetHistory` parameters: access key, exchange, explicit instrument identifier, periodicity/period, Unix range, and `AdjustSplits`. The key is held only by the existing secure credential store and is never returned, logged, placed in provenance, or accepted via CLI arguments.

Set `HISTORICAL_DATA_PROVIDER=global_datafeeds` explicitly. A configured profile is not live-validated; default tests use injected transport. Live validation remains opt-in and credentials are intentionally not supplied in this repository. `AdjustSplits` is split adjustment only and is not claimed to be full corporate-action adjustment. No GDFL fundamentals are integrated.
