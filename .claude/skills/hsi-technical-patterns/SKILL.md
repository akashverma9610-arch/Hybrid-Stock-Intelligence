---
name: hsi-technical-patterns
description: Expert workflow for HSI technical indicators, Ichimoku, candlestick and chart patterns, market structure, multi-timeframe setups, breakout confirmation, and quantitative validation.
---

# HSI Technical Analysis & Pattern Engine Expert

## Authority
- Follow project CLAUDE.md, approved HSI contracts, and WATCH_ONLY governance.
- Inspect actual indicator implementations, timeframe definitions, data contracts, and tests.
- Distinguish observed signals, confirmed setups, hypotheses, and backtested evidence.

## Technical analysis
- Evaluate trend, momentum, volatility, liquidity, volume, support/resistance, and market structure.
- Include Ichimoku components, cloud position, Tenkan/Kijun relationships, Chikou confirmation, and timeframe alignment.
- Assess candlestick formations with context, candle quality, volume, and confirmation.
- Assess chart patterns with explicit pivots, geometry, breakout conditions, and invalidation.
- Distinguish continuation, reversal, consolidation, and failed-breakout regimes.
- Handle corporate actions, missing candles, illiquid instruments, and exchange session boundaries.

## Multi-timeframe orchestration
- Map intraday, short-term, positional, and long-term analysis to approved HSI timeframe contracts.
- Avoid mixing unfinished candles with completed-candle confirmation.
- Track setup lifecycle: candidate, watch, confirmed, invalidated, expired.
- Separate deterministic pattern detection from analytical AI explanations.
- Reuse canonical indicators rather than recalculating identical features.

## Quantitative verification
- Use point-in-time data and avoid look-ahead and survivorship bias.
- Define measurable pattern rules and deterministic tests.
- Evaluate false positives, precision, recall, expectancy, drawdown, and regime stability where data permits.
- Include realistic transaction costs, slippage, liquidity, and out-of-sample validation.
- Never invent win rates, probabilities, backtest outcomes, or price targets.

## Delivery
- Provide input requirements, detection logic, confidence limitations, invalidation, and tests.
- Cite relevant repository paths and identify missing dependencies.
- Preserve existing code, untracked files, and approved scoring contracts.
- Never place live orders or modify trading permissions.