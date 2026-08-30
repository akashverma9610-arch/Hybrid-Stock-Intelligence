# Historical capital-rotation replay

Historical rotation replay is an analytical adapter around the canonical Phase 6B `CapitalRotationEngine`. At a replay timestamp it consumes only a frozen backtest portfolio state, historical analytical evaluations, historical holding contexts, contextual gate evaluations, rotation-history contexts, and the exact rotation configuration version recorded by the backtest run.

The adapter does not reproduce weakest-holding selection, candidate qualification, score hurdle, R:R, confidence, sector, friction, cash-alternative, confirmation, cooldown, or ranking logic. Those rules remain owned by the Phase 6B engine. Holdings are ordered by comparison score, confidence, forward R:R, then stable instrument ID. Raw scores remain frozen; only the canonical Gate #2 adjustment can affect a holding comparison score.

Candidate contextual gates are frozen references, never recalculated from newer inputs. Future analytical contexts, portfolio states, gate records, history confirmations, or config versions are rejected. Candidate/holding contexts and final evaluations are immutable, and audit reconstruction reruns the existing engine from the frozen dependency chain.

The result is only an analytical capital-allocation preference. It creates no ledger buy/sell, portfolio mutation, SignalRecord, order, fill, PaperTrade, performance report, or benchmark run.
