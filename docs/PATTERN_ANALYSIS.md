# Pattern and support analysis

Rules 37–38 use transparent configured base duration/depth, prior base boundary, and measured volatility contraction. A support/resistance level records its base-boundary method, timestamp, source IDs, and as-of time. No future pivot is used. If minimum structure is absent, the result is `NO_VALID_BASE` or insufficient rather than a forced label.

Rule 37 V1 Cup & Handle requires configured cup/handle duration, bounded cup depth, an interior trough followed by recovery toward the opening resistance, a handle in the configured upper portion, and bounded handle depth. Prior advance and valid-volume contraction are optional configured requirements; no volume conclusion is fabricated when bars have no volume.

Ascending Base V1 requires the configured number of locally confirmed pullbacks, minimum spacing, strictly higher pullback lows, and bounded correction depth. A simple rising channel without qualifying pullbacks is rejected. When patterns overlap, the explicit resolution policy is `CUP_AND_HANDLE > ASCENDING_BASE > VCP > FLAT_BASE`; all candidate names and quality evidence remain in the output. These are transparent algorithmic approximations, not visual pattern recognition.
