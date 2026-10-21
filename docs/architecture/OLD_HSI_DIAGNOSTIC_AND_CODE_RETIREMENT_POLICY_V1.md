# Old HSI — Evidence-Based Diagnostic and Code Retirement Policy V1

Status: OWNER_CLEANUP_DIRECTION_APPROVED / AUDIT_REQUIRED / NO_DELETION_AUTHORIZED_YET

Scope: Old Hybrid-Stock-Intelligence only. Applies to all existing modules, data models, integrations, view components, tests, diagnostic consumers and the canonical D01–D61 rules.

## Decision
Remove truly obsolete, unreachable, superseded or duplicated HSI behavior to simplify the single internal intelligence platform; do not blindly preserve all 61 diagnostic IDs forever. However, NOT_OPERATIONAL, DATA_MISSING or POLICY_BLOCKED does NOT mean obsolete. Determine unique semantic contribution and actual consumer demand before any deletion.

## Evidence required for every deletion or merge
1. Exact symbol/call graph including API, frontend, CLI, scheduled jobs, background workers, dependency injection, dynamic imports/reflection, persisted data, configuration and tests; check local D:\ and GitHub HEAD parity first.
2. Pin calculation owner, input/output shape, source vintage, price/timeframe basis, PIT/known-at meaning, thresholds, parameter/policy version and governance authority.
3. Map every D01–D61 to all 35 lens dependencies (PRIMARY/OPTIONAL/CONFIRMATION) and downstream Decision Score, setup, risk, six gates, portfolio, UI, analytics read consumers. Also retain non-lens research uses.
4. Prove equivalent/stronger canonical producer output for each removed computation using frozen fixtures with lineage and behavior parity, or prove feature is explicitly retired with no production consumer and approved successor.
5. Preserve immutable historical result identity, event/provenance/citation and migration compatibility; never silently re-label old DXX records or modify accepted audit fingerprints.
6. Run unit, integration, frontend build, historical replay, full regression, production-readonly canary and rollback before removing the old code path. A missing test is not proof of dead code.
7. On removal, delete imports, docs, dead config, mocks, registered jobs, tests no longer applicable and unused dependencies only after the necessary tests have been migrated to the canonical owner.

## Decision statuses
- KEEP_OPERATIONALIZE: distinct intelligence or policy need; improve source readiness and runtime wiring.
- MERGE_COMPUTATION: two algorithms compute truly same observable from same authoritative source under compatible semantics; one canonical materialization remains, IDs/consumers may initially remain as thin interpretation aliases until deprecation.
- RETIRE_UNUSED: zero production and dynamic consumers, no unique evidence/history/policy obligation, all compatibility paths audited.
- ARCHIVE_FUTURE: nonactive exploratory behavior with potential later value but no present operational obligation; preserve recoverable source and do not promote to active.
- BLOCKED_REVIEW: ambiguous consumer, conflicting source authority, unknown functional equivalence, missing regulatory/owner approval or unverified local state.

## Known audit candidates — not deletion claims
The historical overlap audit flagged 22 diagnostic paths for potential repeated computations:
D03,D05,D07,D09,D13,D14,D25,D38,D40,D41,D42,D43,D44,D46,D50,D51,D52,D53,D54,D55,D56,D58.
These are STATIC CANDIDATES only; no same-input functional equivalence is established. D35 has named VWAP authority/semantics not ready; D57 lacks certified event-to-session evidence. Both require policy/source review, not automatic deletion. Rules serving the 35 proposed lenses must not be removed until that usage is reconciled and a revised versioned lens dependency catalog is approved.
Existing `app.intelligence.shared_market_scan` and its multi-funnel orchestrator are consumed by the `hsi_scan_market` API and are NOT dead just because another draft assessment exists. Remove duplicate provider-driven funnels when replacement production data path has parity, not before.

## Phased execution
Phase A — Reconcile local and GitHub code and full call graph; capture real runtime metrics (counts, latency, cache hits and duplication).
Phase B — 61x35 dependency crosswalk, extra non-lens consumers, unique-source/nonunique-calculation matrix and safety owners.
Phase C — First consolidate computational primitives under existing canonical owners. Keep stable IDs/adapters where a lens or historical API depends on them.
Phase D — Remove independently verified unreachable paths and redundant source adapters behind feature flag/shadow parity and regression.
Phase E — Only after explicit controlled strategy-registry and stored-history migration, retire any diagnostic **ID** whose semantic function is truly unneeded. New canonical-registry version; no in-place renumbering and no rewriting prior results.
Phase F — Audit other backend/frontend dead code, stale mocks, nonactive experiments, obsolete scripts and dependencies using the same criteria. Production code never derives truth from mock data.

## Audit ledger required for each candidate
Record `path_or_rule_id`, `owner`, `same_input_duplicate?`, `canonical_replacement`, `production_consumers`, `lens_dependencies`, `historical_persistence_refs`, `policy_refs`, `decision`, `proof`, `regression_tests`, `rollback_plan`, `commit`.

## Success criteria
- One producer per canonical calculation and source contract, compute once per compatible evidence fingerprint/version.
- The current approved 61 registry and 35 proposed lenses remain valid until intentionally versioned/deprecated, not silently mutated.
- Verified useful diagnostic/lens coverage, provenance and business behavior not lost.
- Less computation, less maintenance, preserved deterministic replay and no false operational readiness.
- No portfolio write, broker order, gate activation or current-db schema change is authorized by this policy.
