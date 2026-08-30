# Anti-Churn

Rotation configuration explicitly carries a minimum score advantage, required consecutive qualifying confirmations, and cooldown days. No values are silently assumed. A candidate that has not met the confirmation count is blocked before ranking; an active cooldown leaves the outcome at `NO_ROTATION` even when a comparison otherwise clears.

This mechanism is analytical hysteresis only. It does not execute or schedule a trade.
