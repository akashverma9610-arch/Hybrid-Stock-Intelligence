---
name: hsi-lens-diagnostics
description: Expert workflow for HSI 35 analytical lenses, 61 diagnostics, dependency mapping, scoring, deduplication, evidence quality, and validation.
---

# HSI Lens & Diagnostics Expert

## Authority and discovery
- Follow project CLAUDE.md and approved repository contracts.
- Identify actual lens and diagnostic definitions, consumers, schemas, and tests.
- Never assume all 35 lenses or 61 diagnostics are implemented or operational.
- Distinguish active, proposed, duplicate, obsolete, conflicting, quarantined, and unknown components.

## Lens dependency workflow
1. Identify the lens, analytical purpose, timeframe, and stock universe.
2. Map required data fields, providers, freshness, and quality gates.
3. Trace reusable calculations, indicator versions, and dependencies.
4. Specify missing-data behavior, provenance, and deterministic outputs.
5. Trace findings to research, setup detection, and portfolio consumers.
6. Define unit, integration, regression, and point-in-time tests.

## Diagnostic reconciliation
- Build a consumer-to-diagnostic matrix from verified code and contracts.
- Detect equivalent computations, conflicting definitions, and unused artifacts.
- Preserve quarantined or disputed components until governance resolves them.
- Propose retirement only with evidence, impact analysis, migration plan, and approval.
- Prefer one canonical computation reused by multiple lenses.

## Quantitative discipline
- Avoid look-ahead bias, survivorship bias, and double-counted evidence.
- Validate missing values, timeframe alignment, and corporate actions.
- Separate measurement, scoring, and investment decisions.
- Never invent weights, thresholds, metrics, or backtest results.
- Respect approved scoring contracts and WATCH_ONLY governance.

## Delivery
- Provide dependencies, source paths, calculations, consumers, risks, and tests.
- Identify implemented, blocked, missing, and unverified components.
- Protect existing untracked files and unrelated changes.
- Do not delete diagnostics, change scoring weights, or merge without approval.