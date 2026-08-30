# Walk-Forward Validation

Phase 8B.1 freezes a `WalkForwardPlan`, its deterministic ROLLING or EXPANDING windows, and each `StrategyCandidate` before OOS execution. Plans, candidates, windows, runs, and window results are insert-only records with fingerprints.

V1 supports `FIXED_STRATEGY` only: a selected candidate and its strategy, registry, score, gate, rotation, signal snapshot, paper snapshot, allocation, and performance references are frozen no later than TEST start. Selection evidence may not refer to TEST artifacts.

The run retains deterministic ordinal window order. Completion status and coverage are derived from immutable window results; this avoids rewriting a historical run when later windows finish.

No optimisation, candidate promotion, aggregate OOS analysis, or self-improvement is implemented here.

## TEST-only aggregate closure

The aggregate layer uses TEST results only for performance. TRAIN/VALIDATION data is permitted solely for timestamp-checked degradation comparison. Aggregate coverage always retains planned, valid, insufficient, failed, zero-trade, and benchmark-unavailable windows.

## Controlled experiments

Optional experiment selection occurs before TEST from immutable TRAIN/VALIDATION evidence only. Existing `FIXED_STRATEGY` remains the default; a selected experimental candidate is merely frozen for a future OOS test.

The future-OOS handoff requires a separate immutable assignment with `selection_timestamp < TEST start`, exact candidate fingerprint, and identical TEST partition/timestamps. It reuses this TEST executor and does not inherit TRAIN/VALIDATION signals, trades, holdings, ledger, or capital.
