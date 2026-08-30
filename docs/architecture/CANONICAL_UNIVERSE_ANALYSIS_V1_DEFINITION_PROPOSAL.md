# Canonical Universe Analysis v1 — Definition Proposal

## Status and scope

This is a **PROPOSED** semantic definition for `canonical-universe-analysis / v1`.
It is **not registered**, **not approved**, and **not active**. It records the
behaviour currently extracted from the repository; it does not change that
behaviour. In particular, it does not create a strategy version, lifecycle
event, approval, database row, runner change, threshold change, score change,
or execution authority.

The proposed future reviewer is `human:Akash-Verma`. That is a review-routing
fact only, not an approval.

## Audit basis

| Subject | Observed source | Finding |
| --- | --- | --- |
| Runner identity and defaults | `app/universe_analysis/service.py` | `Canonical61DiagnosticRunner` defaults to `StrategyVersionReference("canonical-universe-analysis", "v1")` and `NIFTY_50`. It evaluates IDs 1–61, but defers 32 and 34 until all other IDs have run. |
| Rule universe | `app/registry/canonical.py` | The complete canonical universe is IDs 1–61 and has registry version `diagnostic-registry-v1`. |
| Input assembly and point-in-time controls | `app/universe_analysis/service.py`, `app/historical/guard.py` | `StockDiagnosticInputAssembler` uses `BacktestLookaheadGuard` and records `canonical-stored-data;point-in-time-guard`; neither component has a separately declared semantic version. |
| Higher-order semantics | `app/diagnostics/synthesis.py` | `SynthesisRules.version` is `higher-order-v1`; the required, strengthening, and invalidating rule sets are specified below. |
| Existing governance model | `app/domain/models.py`, `app/storage/sqlite_governance_repository.py` | `StrategyDefinition` has no field for a typed diagnostic-runner configuration or a configuration fingerprint. Saving it does not bind its generic configuration to this runner. |

The only direct literal reference to `canonical-universe-analysis` is the
runner's default strategy reference. There is no existing immutable definition,
fingerprint, approved lineage, or registration for it.

## Proposed canonical definition

| Field | Proposed value |
| --- | --- |
| Strategy identity | `canonical-universe-analysis / v1` |
| Analysis kind | `canonical-universe-diagnostics` |
| Runner identity | `Canonical61DiagnosticRunner / canonical-61-runner-v1` |
| Default benchmark | `NIFTY_50` |
| Benchmark override | An explicit constructor argument may override the default. Its configuration identity is `UNVERSIONED_DEPENDENCY`; it must be bound explicitly by any future registered definition. |
| Registry | `diagnostic-registry-v1`, full IDs 1–61 |
| Evaluation order | `1..31, 33, 35..61, 32, 34` |
| Failure semantics | Missing evidence yields `INSUFFICIENT_DATA`; future evidence is excluded; an evaluator exception yields the runner's standard missing diagnostic. |
| Input semantics | Stored evidence only, point-in-time guarded, using `canonical-stored-data;point-in-time-guard`. |

### Rule-set semantics

The full canonical rule universe is:

`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]`

The higher-order policy uses these exact sets:

| Purpose | Rule IDs |
| --- | --- |
| Comparable investment evidence | `16, 17, 18, 19, 23` |
| Required trading evidence | `43, 45, 46` |
| Strengthening evidence | `4, 6, 10, 37, 38, 41` |
| Invalidation evidence | `46` |
| Red-flag results | `SEVERE_CONCERN`, `STRESSED`, `TRIGGERED` |

Rule 46 result `TRIGGERED` makes the trading thesis `INVALIDATED`.

### Extracted configuration values

These are literal values already passed by the runner; they are not proposed
new thresholds.

| Component | Exact configuration |
| --- | --- |
| Market regime | `fast_sma_period=2`, `slow_sma_period=3`, `atr_period=2`, `return_lookback=3`, `strong_bull_minimum_return=0.2`, `bull_minimum_return=0.1`, `selective_bull_minimum_return=0.02`, `selective_bear_maximum_return=-0.02`, `bear_maximum_return=-0.1`, `panic_maximum_return=-0.4`, `panic_atr_percent=0.3` |
| Trend | `fast_sma_period=3`, `slow_sma_period=5`, `require_price_structure=true`, `pivot_window=1` |
| Relative strength | `lookback=3`, `leader_minimum_excess_return=0.1`, `emerging_leader_minimum_excess_return=0.03`, `laggard_maximum_excess_return=-0.03` |
| Sector health/rotation | `lookback=3`, bullish excess return `0.03`, bearish excess return `-0.03` |
| Weinstein | `long_ma_period=3`, `slope_lookback=2` |
| Market structure | `pivot_window=1` |
| Volume | `lookback=3`, `rvol_high=1.5`, `low_volume_ratio=0.5` |
| Ichimoku and Chikou | conversion `2`, standard `3`, leading span `4`, displacement `1` |
| Fundamentals | `healthy_growth=0.1`, `weak_growth=-0.1`, `return_ratio_healthy=0.1`, `leverage_elevated=1.5`, `coverage_stressed=2`, `margin_change=0.02`, `roce_method=equity_debt_cash_v1`, annual days `365`, quarterly days `90` |
| Valuation | `attractive_pe=15`, `expensive_pe=35`, `peg_growth_method=reported_revenue_cagr_v1` |
| Trade | base period `5`, max base depth `0.35`, entry tolerance `0.03`, stop buffer `0.02`, minimum R `2`; cup min duration `8`, max depth `0.35`, handle duration `2`, max handle depth `0.12`, upper portion `0.5`, recovery tolerance `0.05`, prior advance `false`; ascending pullbacks `2`, max depth `0.2`, min spacing `1` |
| Indicator layer | RSI period `3`, overbought `70`, oversold `30`; stochastic oversold `20`; ADX period `2`; MACD fast period `3` |
| OBV | `lookback=3` |
| Liquidity | `equal_tolerance=0.01`, `min_touches=2`, `rvol_high=1.5`, `wide_range_factor=1.5` |
| Crowd | bearish `-0.2`, bullish `0.2`, extreme bearish `-0.6`, extreme bullish `0.6`, high confidence `0.7`, medium confidence `0.4` |

## Dependency identity audit

| Dependency | Identity | Relation | Classification |
| --- | --- | --- | --- |
| Canonical diagnostic registry | `diagnostic-registry-v1` | Direct | Versioned |
| Higher-order synthesis | `higher-order-v1` | Direct | Versioned |
| Runner reporting version | `canonical-61-runner-v1` | Direct runner identifier | Versioned |
| Input assembler | `StockDiagnosticInputAssembler` | Direct | `UNVERSIONED_DEPENDENCY` |
| Lookahead guard | `BacktestLookaheadGuard` | Direct | `UNVERSIONED_DEPENDENCY` |
| Evaluator wrappers | `DeterministicDiagnosticEvaluators` | Direct | `UNVERSIONED_DEPENDENCY` |
| Benchmark configuration | `NIFTY_50` default / constructor override | Direct | `UNVERSIONED_DEPENDENCY` |
| Evidence persistence | `DiagnosticResult` / `SQLiteStrategyGovernanceRepository` | Direct persistence interface | `UNVERSIONED_DEPENDENCY` |
| Decision scoring policy | `decision-score-policy-v1` | Downstream; not invoked by this runner | Versioned, out of runner scope |
| Execution gates | `execution-gate-registry-v1` | Downstream; not invoked by this runner | Versioned, out of runner scope |
| Research policy | `research-policy-v1` | Research input policy is not bound by the runner | Versioned policy with unbound runtime relationship |

There is no present version identity for the inline technical, fundamental,
valuation, trade, liquidity, crowd, or freshness policy implementations. The
proposal therefore freezes their observed values in its payload and labels the
implementation linkage `UNVERSIONED_DEPENDENCY`; it does not pretend that a
versioned policy already exists.

## Canonical serialization and fingerprint

The canonical payload is the following JSON value. Its serialization is UTF-8,
`ensure_ascii=true`, lexicographically sorted object keys, and separators
`(',', ':')`; no timestamps, absolute paths, environment values, reviewer, or
lifecycle status participate. SHA-256 is taken over those exact UTF-8 bytes.

```json
{"analysis_kind":"canonical-universe-diagnostics","assembler":{"identity":"StockDiagnosticInputAssembler","point_in_time_guard":{"identity":"BacktestLookaheadGuard","version":"UNVERSIONED_DEPENDENCY"},"snapshot_source":"canonical-stored-data;point-in-time-guard","version":"UNVERSIONED_DEPENDENCY"},"benchmark":{"default_instrument_id":"NIFTY_50","override_contract":"explicit_constructor_argument_only","version":"UNVERSIONED_DEPENDENCY"},"diagnostic_registry":{"rule_ids":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61],"version":"diagnostic-registry-v1"},"execution_order":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,33,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,32,34],"failure_semantics":{"evaluator_exception":"standard_missing_diagnostic","future_evidence":"excluded","missing_evidence":"INSUFFICIENT_DATA"},"policy_dependencies":{"decision_score":{"identity":"decision-score-policy-v1","relation":"downstream_not_invoked_by_runner"},"diagnostic_evaluators":{"identity":"DeterministicDiagnosticEvaluators","version":"UNVERSIONED_DEPENDENCY"},"evidence_persistence":{"identity":"DiagnosticResult/SQLiteStrategyGovernanceRepository","version":"UNVERSIONED_DEPENDENCY"},"execution_gate":{"identity":"execution-gate-registry-v1","relation":"downstream_not_invoked_by_runner"},"research":{"identity":"research-policy-v1","relation":"research_input_policy_not_bound_by_runner"},"synthesis":{"identity":"higher-order-v1","relation":"direct"}},"runner":{"identity":"Canonical61DiagnosticRunner","version":"canonical-61-runner-v1"},"strategy":{"id":"canonical-universe-analysis","version":"v1"},"thresholds":{"crowd":{"bearish":-0.2,"bullish":0.2,"extreme_bearish":-0.6,"extreme_bullish":0.6,"high_confidence":0.7,"medium_confidence":0.4},"fundamental":{"annual_period_days":365,"coverage_stressed":2,"healthy_growth":0.1,"leverage_elevated":1.5,"margin_change":0.02,"quarterly_period_days":90,"return_ratio_healthy":0.1,"roce_method":"equity_debt_cash_v1","weak_growth":-0.1},"ichimoku":{"conversion_period":2,"displacement":1,"leading_span_period":4,"standard_period":3},"indicator_layer":{"adx_period":2,"macd_fast_period":3,"rsi_overbought":70,"rsi_oversold":30,"rsi_period":3,"stochastic_oversold":20},"liquidity":{"equal_tolerance":0.01,"min_touches":2,"rvol_high":1.5,"wide_range_factor":1.5},"market_regime":{"atr_period":2,"bear_maximum_return":-0.1,"bull_minimum_return":0.1,"fast_sma_period":2,"panic_atr_percent":0.3,"panic_maximum_return":-0.4,"return_lookback":3,"selective_bear_maximum_return":-0.02,"selective_bull_minimum_return":0.02,"slow_sma_period":3,"strong_bull_minimum_return":0.2},"market_structure":{"pivot_window":1},"obv":{"lookback":3},"relative_strength":{"emerging_leader_minimum_excess_return":0.03,"laggard_maximum_excess_return":-0.03,"leader_minimum_excess_return":0.1,"lookback":3},"sector_health_rotation":{"bearish_excess_return":-0.03,"bullish_excess_return":0.03,"lookback":3},"synthesis":{"invalidation_rule_ids":[46],"red_flags":["SEVERE_CONCERN","STRESSED","TRIGGERED"],"required_investment_rule_ids":[16,17,18,19,23],"required_trading_rule_ids":[43,45,46],"strengthening_rule_ids":[4,6,10,37,38,41],"version":"higher-order-v1"},"trade":{"ascending_max_depth":0.2,"ascending_min_pullbacks":2,"ascending_min_spacing":1,"base_period":5,"cup_handle_duration":2,"cup_max_depth":0.35,"cup_max_handle_depth":0.12,"cup_min_duration":8,"cup_recovery_tolerance":0.05,"cup_upper_portion":0.5,"entry_tolerance":0.03,"max_base_depth":0.35,"minimum_r":2,"require_prior_advance":false,"stop_buffer":0.02},"trend":{"fast_sma_period":3,"pivot_window":1,"require_price_structure":true,"slow_sma_period":5},"valuation":{"attractive_pe":15,"expensive_pe":35,"peg_growth_method":"reported_revenue_cagr_v1"},"volume":{"lookback":3,"low_volume_ratio":0.5,"rvol_high":1.5},"weinstein":{"long_ma_period":3,"slope_lookback":2}}}
```

`sha256:3144ec1e9452f24a1e9f3776c77e33cbd59f31459c3e2f7d734c4924bb2b9ee3`

This is a proposal fingerprint, not a registered runtime fingerprint.

## StrategyDefinition compatibility audit

| `StrategyDefinition` concern | Classification | Rationale |
| --- | --- | --- |
| `strategy_id`, `version`, `name`, `description` | Directly compatible | The proposed identity and description can be represented. |
| `rule_definition_version` | Directly compatible | Maps to `diagnostic-registry-v1`. |
| `risk_configuration_version` | Mappable | `higher-order-v1` is relevant to rules 31–34, but is not a complete risk-configuration version. |
| `benchmark_configuration_version` | Governance gap | The default benchmark exists, but has no versioned benchmark configuration identity and can be overridden at construction. |
| Generic `StrategyConfiguration` | Partially mappable | It has no typed location for the 61-rule runner's complete technical/fundamental/evidence contract. Reusing scoring or execution fields would misrepresent semantics. |
| `scoring_configuration_version` and `execution_gate_configuration_version` | Not semantically applicable to the runner | Scoring and gates are downstream and not invoked by `Canonical61DiagnosticRunner`. |
| `status`, approval, validation, lifecycle dates | Not semantically applicable to this static proposal | Persisting any value would create governance state. The proposal remains outside the lifecycle. |
| `author_reviewer` | Mappable, not exercised | The future reviewer could be recorded as `human:Akash-Verma`; no review is requested or inferred. |
| Semantic fingerprint | Governance gap | The model and SQLite schema have no fingerprint field. |
| Parent strategy version | Not semantically applicable | No preceding canonical-universe definition exists. |

The smallest future adjustment is to extend the existing immutable
`StrategyDefinition` persistence contract with a typed
`canonical_analysis_definition` payload and its `configuration_fingerprint`.
That preserves the existing governance model; it does not require a separate
promotion framework. A future registration must also bind the benchmark and
all currently unversioned dependencies explicitly.

## Future approval, validation, and registration boundary

No action is requested now. Before any registration, a human reviewer must
decide whether to:

1. approve the extracted payload and its `UNVERSIONED_DEPENDENCY` disclosures;
2. approve the benchmark binding, including the treatment of caller overrides;
3. approve the smallest schema/contract adjustment for typed payload plus
   fingerprint; and
4. define validation evidence and lifecycle semantics for this definition.

Only after those decisions may a future task propose a persisted definition.
It must not silently treat this document, the fingerprint, or a runner default
as approval.

## Validation performed for this proposal

- Recomputed the canonical JSON with sorted keys and compact separators and
  obtained the fingerprint above.
- Compared the payload's 61 IDs, deferred execution order, synthesis sets, and
  literal parameter values to the current runner and registry.
- Performed documentation-only work: no database connection or mutation, no
  registration, approval, lifecycle event, runner edit, score edit, threshold
  edit, or test execution.

`CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL_READY`
