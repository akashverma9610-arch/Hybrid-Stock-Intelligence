# Production V1 internal forward-paper studies

U18 records internal research outcomes for already-governed executable setups.
It is not a recommendation, portfolio, broker order, trading alert, or a
real-money position.

Only `FORWARD_PAPER` studies are admitted. A study captures the immutable
governed setup fingerprint, policy/Brain/version context, exact decision
cutoff, trigger, structural stop, target, optional maximum entry, explicit
time stop, execution-model fingerprint, and factual regime/sector/financial
semantic lineage. A score alone is never admitted.

For EOD setups, a bar is eligible only when both its session and its known-at
time are strictly after the decision cutoff. The same decision bar can never
fill. Catch-up processing is chronological and reads stored bars supplied by
the host; the evaluator has no provider client.

The append-only ledger records admission, trigger, entry, session marks,
missed do-not-chase, exits, expiry, ambiguity, invalid data, and corporate
action review. The current study view is rebuilt from those events. Repeated
evaluation is idempotent. Later corrected market data never rewrites original
forward events; it requires an explicit reconciliation outside this ledger.

Execution is versioned. The model makes gap entry, gap stop, target fill,
slippage, round-trip friction, and intrabar ambiguity explicit. The V1 policy
marks a stop-and-target bar `PATH_AMBIGUOUS`; it is reported but excluded from
headline realized-R statistics. Long risk is `entry - structural_stop`; gross
and net R remain separate. Session marks preserve close/high/low, unrealized
R, MFE-R, MAE-R, and sessions held. Gap-through stops use the factual opening
price under the explicit stop-gap rule. Unsupported corporate actions fail
closed into review.

Performance evidence is descriptive only: counts, wins/losses, expectancy,
median/average R and MFE/MAE, profit factor, exit rates, duration, missed,
unfilled, and ambiguity counts. It is grouped only by factual version lineage.
It never changes policies, thresholds, scores, diagnostics, Six Gates,
directionality, materiality, rankings, recommendations, or execution.

The durable store uses the backend-neutral immutable snapshot repository with
separate forward-paper study and event families. It does not write canonical
company/market evidence or real portfolio state. No broker package or order
interface is used.

## Operator runbook

1. Confirm U17 has healthy stored OHLCV, required benchmark evidence, and an
   explicitly composed governed executable-setup source.
2. Freeze an explicit paper execution model and time-stop source.
3. Run `python -m app.runtime paper-trading-status`.
4. Set `PAPER_TRADING_ENABLED=true` only after those dependencies are ready.
5. Run `python -m app.runtime paper-trading-run` or the opt-in worker.
6. Inspect the append-only events and descriptive evidence; verify zero broker
   activity.

This repository intentionally ships the ledger and injected orchestrator but
does not silently compose a live setup discovery/bar source. Until that
explicit stored-only composition is registered, an enabled CLI run reports
`FORWARD_PAPER_SETUP_AND_STORED_BAR_SOURCE_UNCONFIGURED` and writes no outcome.
On failure, disable the worker, repair data/configuration, rerun chronologically,
then verify idempotency before resuming.
