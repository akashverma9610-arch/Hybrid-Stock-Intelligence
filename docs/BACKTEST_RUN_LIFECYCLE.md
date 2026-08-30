# Backtest run lifecycle

`BacktestRun` freezes the historical dataset ID/version/fingerprint, optional partition, strategy and all configuration versions, replay schedule and calendar versions, evaluation window, capital, friction references, universe, seeds, quality, evaluation label, warnings, methodology notes, and a deterministic fingerprint. Fingerprints exclude runtime timestamps and status, so identical frozen inputs reproduce the same value.

Run definitions are immutable SQLite records. Their effective lifecycle state is derived from the append-only event stream, rather than rewriting the stored run: `CREATED`/`READY` → `RUNNING` → `COMPLETED`, `FAILED`, `CANCELLED`, or `INSUFFICIENT_DATA`. Terminal states reject further events. This means a failure or cancellation retains all earlier history.

`IN_SAMPLE`, `VALIDATION`, and `OUT_OF_SAMPLE_TEST` are explicit labels. In-sample is never presented as validated performance. Quality is copied from historical-data quality and is separate from any future performance result.

The V1 coordinator validates frozen manifest/partition/config references, records start/step/completion events, invokes only a no-op placeholder handler, and stops on failures, cancellation, or terminal insufficient-data policy. It does not invoke diagnostics, scores, gates, portfolio, rotation, signals, paper trading, performance, or benchmarks.
