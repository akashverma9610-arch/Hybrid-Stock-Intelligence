# SenseEdge — 35 Opportunity Lenses Frontend Contract

Status: CATALOG_UI_IMPLEMENTED / LIVE_LENS_RESULTS_NOT_WIRED / NO_STRATEGY_ACTIVATION
Owner scope: Old HSI only; Daily/Weekly/Monthly first, intraday later.

## Current frontend changes
- `frontend/src/components/senseedge/OpportunityLensCatalogue.tsx`: searchable 35-lens catalogue in six disjoint research families, design-only states, filtering and details.
- `frontend/src/components/senseedge/SenseEdgePages.tsx`: mounted into existing Opportunities route above canonical Watch records, without replacing the Watch consumer.
- The catalogue is static design metadata, NOT a new source of truth for lens policies, input readiness or stock results. It does not fabricate matches, coverage counts or opportunity returns.

## Live backend contract required before turning on results

The existing canonical storage and read-only API must expose a paginated, immutable, versioned snapshot per explicit cutoff:

```text
lens_catalog_version, lens_catalog_fingerprint, universe_snapshot_id,
universe_eligible_count, universe_evaluated_count, evaluation_as_of,
computation_completed_at, historical_pit_mode,
lenses[]: {lens_id, definition_version, activation_status, family,
           horizon, required_data_domains, required_named_evidence,
           readiness_counts{ready,partial,stale,missing,conflicted,policy_blocked},
           assessed_stock_count, matching_stock_count_or_null},
candidates[]: {canonical_instrument_id, symbol, exact_source_as_of,
               lens_assessments[]:{lens_id, data_readiness, policy_status,
                                   fit_status, mandatory_blockers[],
                                   contradiction_reasons[], evidence_lineage[]},
               distinct_discovery_origins[], existing_score_ref_or_null,
               existing_gate_ref_or_null, stock_analysis_snapshot_ref}
```

All enums and evidence references must use existing canonical owners; this sketch is an interface proposal, not approval for a second score or mandatory threshold. MATCH is permitted only when governed lens-fit policy is active for evaluation and all required data certified. A blocked lens must have its own reasons, not be silently dropped.

## UX mapping
- **Opportunities → Lens Explorer:** all 35 lenses, group search/filter and readiness counts from the authoritative backend when available.
- **Opportunities → Stock Results:** one stock row per exact NSE:ISIN, multi-lens chips, source as-of, data readiness, distinct score/gate state and evidence-backed blockers. Empty/partial results visibly identified.
- **Stock Detail → Lens tab:** each lens's fit, required inputs and source provenance; clicking a lens filter only shows certified stored assessments.
- **Portfolio → Thesis coverage:** run same per-lens read-only interpretation for current holdings, with independent portfolio/sell/rotation governance.
- **Dev Console → Lens Health:** domain readiness heatmap, 61-rule dependency chart, G01–G21 blockers and last completed certified snapshots.

## Acceptance gates
1. 35 IDs visible, six non-overlapping families, correct search/filter and keyboard use.
2. Before backend live binding, NO guessed matches, counts, READY status, scores or signals.
3. After binding, missing 1M or 1D/1W financial/event evidence never reported READY.
4. Stock matching 3 lenses appears once and retains all 3 source-backed labels.
5. Existing Watch route unchanged, existing `hsi_scan_market` API unaffected; UI read never launches provider fetch/scans.
6. Responsive layout and TypeScript lint/build pass; blocked/no-data and API unavailable states explicitly tested.
7. Lens definitions and policy activation from governed backend catalogue, not the frontend static list.
8. No broker order or portfolio mutation.

Implementation remaining: governed backend read API, actual lens-fit evaluators, data coverage jobs, Stock Detail/Portfolio/Dev views and complete frontend build verification. The current connector-based commits did not run build or tests.
