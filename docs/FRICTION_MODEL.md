# Friction Model

Gate 1 applies only to `ROTATE_IN`. It compares the candidate raw Decision Score with a supplied current/weakest comparison score against the strategy-versioned `min_score_advantage`; it never invents a comparison holding. A cash-funded fresh entry is marked applicable-as-pass in the decision detail.

The friction model version is mandatory. Expected incremental return, charges, slippage, and tax treatment are optional inputs, not permanent statutory facts. When a configuration requires the net-economic check, missing expected return or modeled friction returns `INSUFFICIENT_DATA`; it is never treated as zero.
