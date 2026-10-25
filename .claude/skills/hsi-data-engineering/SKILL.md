---
name: hsi-data-engineering
description: Expert workflow for HSI NSE-universe data ingestion, canonical databases, financial and market data pipelines, incremental updates, data quality, provenance, and reusable derived intelligence.
---

# HSI Data Engineering Expert

## Mission
Design reliable, cost-efficient data infrastructure for the existing HSI repository. Ground recommendations in actual code, schemas, providers, and approved contracts.

## Discovery
1. Read project CLAUDE.md and relevant database and ingestion contracts.
2. Identify existing tables, migrations, providers, jobs, scripts, and tests.
3. Distinguish implemented pipelines from planned capabilities.
4. Trace source to raw evidence, normalized records, derived features, and consumers.
5. Identify missing coverage, duplicate computations, stale dependencies, and bottlenecks.

## Canonical data architecture
- Maintain stable instrument identity, listing status, symbol history, and corporate actions.
- Separate raw immutable evidence, canonical facts, derived features, and research conclusions.
- Preserve source, as-of date, ingestion time, revision, and quality status.
- Support historical backfill and incremental updates with idempotent upserts.
- Detect missing, stale, contradictory, revised, and outlier data.
- Enforce point-in-time correctness to prevent look-ahead bias.
- Version calculations and invalidate dependent features when inputs change.
- Compute reusable indicators once per instrument, timeframe, and input version where practical.

## HSI analytical consumers
- Map datasets to 35 lens dependencies and relevant diagnostics.
- Support technical, fundamental, valuation, liquidity, events, and concall evidence.
- Provide provenance-aware inputs for RAG and analytical AI.
- Separate deterministic calculations from AI interpretation.
- Never claim full NSE coverage without verified audits.

## Reliability and efficiency
- Prefer licensed, documented, and compliant data access.
- Respect provider limits, exchange terms, and redistribution restrictions.
- Design retries, checkpoints, deduplication, reconciliation, and recovery.
- Estimate storage, compute, API usage, and update frequency.
- Justify partitioning, indexing, caching, and batching with measurements.
- Never modify production data or run destructive migrations without approval.

## Delivery
- Report evidence with repository paths.
- Specify data contracts, lineage, dependencies, failure states, and tests.
- Recommend minimal changes and measurable validation.
- Preserve unrelated work and protected untracked files.