# VWAP, Value Area, and OBV

Rule 35 uses bar-level typical price `(high + low + close) / 3` weighted by bar volume to calculate VWAP, then reports acceptance above, below, or mixed. This is an OHLCV approximation, not a session-market microstructure model.

Value Area, POC, VAH, and VAL require real volume-at-price data. When that data is absent, this implementation explicitly reports `value_area=UNAVAILABLE`; it does not fabricate profile levels from OHLCV.

Rule 36 calculates cumulative On-Balance Volume: add current volume on an up-close, subtract it on a down-close, and leave it unchanged on an equal close. Over the configured lookback it reports confirmation or price/OBV divergence. Divergence is a price-volume proxy only and never a claim of institutional accumulation.
