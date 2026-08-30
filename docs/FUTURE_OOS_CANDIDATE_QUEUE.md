# Future OOS candidate queue

Queued candidates are assigned only through an immutable `FutureOOSAssignmentPolicy` and `FutureOOSAssignment`. The assignment preserves the exact research-selected candidate/configuration fingerprint and may only target a chronologically future TEST partition. Queue entries are not rebased onto newer candidates or strategy versions.

An immutable queue entry records a research-selected candidate for a strictly future TEST boundary. It requires `selection_timestamp < earliest_test_timestamp`, preserves the selected candidate fingerprint, and creates no TEST backtest, report, or walk-forward execution. Later scheduling must apply the existing pre-TEST provenance guard and may mark the entry stale rather than rebasing it.
