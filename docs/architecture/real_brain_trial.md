# Controlled Real-Brain Trial

`#038C` adds one explicit local command for measuring the current canonical
store against a bounded real NSE sample:

```powershell
python -m app.runtime real-brain-trial --sample-size 40
```

The sample size is constrained to 30–50 (default 40). The selector binds to an
immutable `UniverseSnapshot`: it round-robins across already-persisted taxonomy
sectors when more than one is available, then uses a stable snapshot-scoped
hash. If taxonomy is absent it uses only the hash. It never invents a sector,
uses a strategy shortlist, or favors candidate quality.

For an evidence before/after comparison, `--frozen-cohort` repeats the latest
compatible stored cohort exactly; `--frozen-cohort-trial <trial-id>` binds to a
specific prior trial. A taxonomy update therefore cannot silently change the
40-stock cohort being compared.

The command has a strict stored-data boundary. It reads existing canonical
OHLCV, quote, taxonomy, historical-security, and coverage records; it opens no
provider client and performs zero provider requests. It preloads only the
bounded sample plus already-stored market-context IDs, not the 2,553-stock
universe. Test fixtures cannot satisfy the `canonical_stored_only` source
marker used by the real-trial service.

For each selected stock the service composes frozen coverage, runs the existing
canonical 61-diagnostic registry, preserves missing/unavailable outputs, and
uses the existing Decision Score builder only. A score or confidence is exposed
only when that existing policy returns a valid value. The trial does not
renormalize scoring, calculate a replacement confidence, execute the six
gates, select candidates, rotate capital, or create an order. Consequently a
registry walk does not make a sparse real analysis complete.

The append-only internal audit records retain the universe snapshot/checksum,
sample, as-of timestamp, per-stock coverage/evidence references, diagnostic
counts, score/confidence only when valid, historical-integrity status, warnings,
blocker counts, and observed runtime. The records deliberately retain no public
diagnostic inventory and contain no alpha/performance fields such as win rate,
CAGR, predictive accuracy, or “best stock.” Public API contracts are unchanged.

`COMPLETE` requires full registry completion and ready evidence coverage.
`PARTIAL` requires some real non-identity evidence but incomplete coverage.
`UNAVAILABLE` means the registry may have been walked, but no meaningful real
input domain exists. Typical blockers are `NO_HISTORY`, `NO_TAXONOMY`,
`NO_FUNDAMENTALS`, `NO_OWNERSHIP`, `NO_DELIVERY`, and `NO_MARKET_CONTEXT`.
Those counts are an ingestion-engineering priority, never a stock ranking.

The first local run is an evidence-availability measurement only. It makes no
claim about returns, edge, forecasts, or suitability for trading.
