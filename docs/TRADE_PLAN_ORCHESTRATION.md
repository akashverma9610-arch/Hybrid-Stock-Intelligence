# Trade Plan Orchestration

`TradePlan` consumes existing Rules 40–46 references and retains entry methodology, rule ID (40, 41, or 42), entry price/zone, machine-testable trigger conditions, stop, exact invalidation, targets, R:R, catalyst clock, thesis, risks, management reference, expiry, and horizon. It does not invent market levels.

Supported entry structures are `AGGRESSIVE`, `CONFIRMATION`, and `PULLBACK_RETEST`. Trigger conditions declare type, comparison, threshold/zone, timeframe, confirmation requirement, input reference, and version. An incomplete stop/invalidation/target plan is `INSUFFICIENT_DATA`; a score alone cannot create an entry setup.

The signal-confidence value is separate from Decision Score, data confidence, gate status, and rotation stance. It represents setup completeness only and is never silently folded into the Decision Score.
