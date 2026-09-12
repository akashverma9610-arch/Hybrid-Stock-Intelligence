# Fundamental V2 Brain / Portfolio Version Propagation V1

Status: **IMPLEMENTED_SHADOW_PROPAGATION / V1_ACTIVE / V2_SHADOW_ONLY / V2_NOT_ACTIVE**.
Source checkpoint: `01593df3d89c57d982f67b25bf8819281474d9ff`.
Authority: bounded user-approved B07 safety propagation, not financial-policy or product activation.

## Canonical references

- [Prior downstream safety](FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_ADAPTER_V1.md).
- [Immutable V2 governance approval](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.md).
- [Machine-readable runtime dependency inventory](FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_INVENTORY.json).
- [Stored-evidence comparison receipt](FUNDAMENTAL_V2_BRAIN_PORTFOLIO_COMPARISON_RECEIPT.json).
- [Typed lineage boundary](../../app/diagnostics/brain_lineage.py).
- [Bounded read-only proof](../../scripts/audit_fundamental_v2_brain_portfolio.py).
- [Focused boundary and replay tests](../../tests/unit/test_fundamental_v2_brain_lineage.py).

## Measured flow and exclusions

The production service remains `SharedBrainApplicationService.analyze_stock`.
Its financial selector, bundle, trajectories, directionality, materiality, Unified
State, snapshot and public projection are unchanged. The existing name
`BrainResearchComparisonStateV2` denotes a research-state contract, **not**
Fundamental Diagnostic Registry V2 and not an implicit V2 activation.

Stored `DiagnosticResult` has strategy/as-of and optional canonical fingerprints
but no registry field. Its existing production meaning remains V1. The
research-diagnostic adapter and portfolio rehydrator now reject non-record shadow
objects before looking at legacy attributes or assigning transient V1 identity.
Canonical records must retain the existing exact canonical strategy reference,
semantic fingerprint and their original result fingerprint. Generic records
cannot carry contradictory canonical lineage. No records are rewritten.

The stored diagnostic adapter still selects the latest eligible bundle among
its already supplied legacy V1 strategy/as-of groups. Exact-as-of governance
sources continue to constrain normal application wiring. This is **not**
latest-registry selection: a newer V2 object is rejected, not substituted.
Research comparison requires the exact same instrument and as-of, with no
newer/older evidence fallback.

Portfolio holding composition guards both the Brain argument and diagnostic
tuple before generating existing HoldingAnalytics. Rotation, sell and ledger
analytics reject research objects before rank, thesis, stop, cash, allocation or
heat computation. Legacy rotation configuration labels such as `registry-v1`
remain opaque historical labels; this slice does not reinterpret that older
configuration API. Explicit V2 and research objects are always rejected.
The new Brain registry resolver accepts only canonical versions and never
uses these opaque labels as aliases.

Profit harvesting already requires `MarketExtremesAssuranceProjection`;
the new sidecar fails that existing nominal check. Sell/Risk review, long-term
dossiers, Fast Rotation assurance and Market-Wide Watch/challenger projections
receive no new inputs, adapters or wiring. They do not become V2 consumers.

## Minimal typed sidecars

`BrainDiagnosticResearch` is immutable and fingerprinted. It carries:

| Field | Meaning and invariant |
| --- | --- |
| `canonical_instrument_id` | Exact nonempty NSE identity from the supplied verified source; never fuzzy matching |
| `as_of` | Explicit aware UTC cutoff; source cutoff must match; no clock |
| `registry_version`, `mode` | Existing exact resolver; V1 ACTIVE or V2 SHADOW only |
| `strategy_version` | Exact unique V1 source reference; V2 explicitly `None` |
| `policy_version` | V2 source evaluator version; legacy V1 explicitly `None` because its dependencies are unversioned |
| `sources` | Complete original V1 evaluated records or all six verified V2 shadow envelopes; never mixed |
| `diagnostic_result_fingerprint` | Hash of complete ordered source envelopes, not an invented source-native fingerprint |
| `production_brain_fingerprint` | Original V1 snapshot reference when available; always absent for V2 |
| `production_brain_blocker` | Explicit V1 unavailable status instead of a fabricated production snapshot; absent for V2 |
| `purpose` | Fixed `OBSERVATIONAL_RESEARCH_ONLY` |
| Eligibility flags | `score_eligible=false`, `execution_eligible=false`, `portfolio_action_eligible=false` for the sidecar in both modes |
| `fingerprint` | Complete canonical payload, excluding only its own fingerprint field |

These flags describe the **sidecar**, not a change to the original V1 score or
execution eligibility. The sidecar is never an active Brain/action object.
Canonical result fingerprints remain intact even where legacy timestamp strings
use different offsets; outer serialization normalizes aware timestamps to UTC.

V2 envelopes reuse the prior `ShadowDiagnosticEnvelope` and retain policy approval
fingerprint, source result fingerprint, component readiness, measurements,
blockers, source fact/evidence references and all source authority flags.
All six rules must share instrument/as-of/input/entity context. Only Rule 29
owns optional market lineage; unrelated rules are not assigned its market data.
Duplicate/missing rule IDs, mixed registries, tampering, future inputs and
conflicting contexts fail closed. Input ordering cannot select a winner.

The explicit service method `diagnostic_research` requires an as-of.
Its V1 branch delegates to the existing production assembler and binds its
unchanged snapshot fingerprint. Its V2 branch accepts an **exact canonical ID**
and supplied verified shadow outputs; it does not invoke resolver, financial
assembler, paper projector, production view or runtime clock.
No API route or UI entry point is added.

`FundamentalPortfolioObservation` contains only a verified V2 research sidecar,
optional opaque holding reference, fingerprint and fixed
`portfolio_action_eligible=false`. It never loads a holding or snapshot.
It has no action, allocation, quantity, position size, heat, price, entry,
stop, target, sell instruction or harvest instruction. It is not persisted.

## Production firewalls and policy preservation

- V1 Brain/holding paths reject explicit V2 and research wrappers with
  `CROSS_REGISTRY_BRAIN_CONSUMPTION_FORBIDDEN` or
  `CROSS_REGISTRY_PORTFOLIO_CONSUMPTION_FORBIDDEN`.
- Score assembly still rejects these non-V1 nominal objects without numbers.
  Original V2 objects retain `V2_SHADOW_SCORE_FORBIDDEN`; new sidecars are
  unverified diagnostic inputs, not implicit V1 records.
- Prior higher-order/thesis guards remain unchanged; no supportive text,
  scenario probability or bullish interpretation is generated from the sidecar.
- A pre-evaluation Six Gates guard rejects shadow objects and the explicit V2
  registry with `V2_SHADOW_GATE_CONSUMPTION_FORBIDDEN`. All six gate methods,
  definitions, configuration, thresholds and weights remain unchanged.
  This is **not** B08 version-aware gate activation or approval.
- No portfolio snapshot, action-policy, rotation hurdle, ledger semantics,
  persistence schema, API, UI, provider, runtime configuration or credential
  change is made. No provider request or acquisition occurs.
- Historical replay fixtures retain their original V1 values. The prior B03–B06
  receipt's source preservation is checked at its immutable checkpoint;
  current score/thesis behavior is still executed, and this slice independently
  checks the exact permitted source diff and unchanged policy implementations.

## Bounded stored-evidence proof and limitation

The proof pins `2026-08-31T18:21:20.437011+00:00`, an existing exact 61-rule
production diagnostic cutoff shared by the five stored holdings. It uses only
stored facts, filings, canonical identity, classification and price evidence
eligible at that cutoff. Later-acquired facts do not backfill knowledge at this
earlier time. It does not rerun the V1 diagnostic runner or any production
portfolio decision. Optional non-financial Brain sources not supplied in this
bounded proof remain unavailable; this is not a full current runtime refresh.

| Holding | Frozen-baseline and current V1 result | V2 research isolation |
| --- | --- | --- |
| APARINDS | Same pre-existing `SHARED_BRAIN_SNAPSHOT_UNAVAILABLE` | All six boundary checks reject |
| DEEPINDS | Identical PARTIAL view and holding composition | All six boundary checks reject |
| GENUSPOWER | Same pre-existing `SHARED_BRAIN_SNAPSHOT_UNAVAILABLE` | All six boundary checks reject |
| GLAND | Same pre-existing `SHARED_BRAIN_SNAPSHOT_UNAVAILABLE` | All six boundary checks reject |
| ICICIBANK | Identical PARTIAL view and holding composition | All six boundary checks reject |

The three failures have the identical underlying
`RESEARCH_METRIC_DIRECTIONALITY_EXACT_RULE_REQUIRED` in the frozen and current
assembler. No exact-rule policy is invented to bypass it. The new observational
V1 reference preserves this unavailable status and the existing diagnostic
lineage; production `analyze_stock` still fails exactly as before. Full healthy
five-holding Brain availability is **not** claimed.

All five V2 references retain source fingerprints and fail portfolio, rotation,
sell, harvest, pre-gate and cross-version substitution checks. Comparison replay
is identical with reversed source ordering. No recommendation or actual action
is evaluated on production holdings. The portfolio snapshot and financial source
fingerprints are unchanged; SQLite is opened `mode=ro` with `query_only=ON`.

Comparison receipt:
`sha256:0c47e872586b94cd7a0fbaf8e2f03b74a3eeb4a37a1d228e5bf20107b2cf23e8`.

## Governance and next boundary

| Blocker | Status |
| --- | --- |
| B07 shadow propagation | CLOSED_FOR_SHADOW_PROPAGATION |
| B07 production activation | STILL_BLOCKING_ACTIVATION |
| B03 / B05 / B06 | PARTIALLY_CLOSED, prior safety retained |
| B04 | CLOSED_FOR_ACTIVATION_SAFETY, prior scoped numeric-default repair retained |
| B08 / B09 / B14 | STILL_BLOCKING_ACTIVATION |

No historical snapshot migration is required for these in-memory sidecars.
Future production activation must define explicit version-aware stored
Brain/portfolio rehydration, diagnostic references and approved action semantics.
A sidecar cannot supply that authority. BANK/NBFC/INSURER policies remain blocked.
The unrelated stored-corpus directionality gap is explicitly retained.

Preserved: ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY=TRUE; V1_ACTIVE=TRUE;
V2_ACTIVE=FALSE; V2_SHADOW_ONLY=TRUE; NO_SILENT_REGISTRY_REWRITE=TRUE;
NO_SYNTHETIC_REPORTED_FACTS=TRUE; UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE=TRUE;
NO_SILENT_SCORE_WEIGHT_RENORMALIZATION=TRUE; AI_DECISION_AUTHORITY=FALSE.
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 remains FROZEN;
DATA_BUILD_VS_BUY_AUDIT_V1 remains mandatory before material financial acquisition
and is not triggered by this read-only slice.
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 remains ACTIVE.

Exactly one next continuation:
**FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1**. Not started.

## Final validation

- Final new focused tests: **55 passed / 0 failed / 2 warnings**.
- Combined focused/affected regression: **740 passed / 0 failed / 2 warnings**.
- One completed authoritative full backend suite: **3,995 passed / 0 failed /
  6 skipped / 2 warnings**, exit 0, 261.75 seconds. No full-suite rerun was needed.
- SQLite integrity: **ok**; FK violations: **0**. Database bytes and modification
  timestamp unchanged. Protected counts unchanged: FinancialFacts=6,118;
  CorporateFilings=455; portfolio snapshots=1; paper trades=0; trade plans=0;
  generic strategy_versions=0; generic diagnostic_results=0;
  canonical strategy definitions=1; canonical diagnostic results=2,074.
- Current-corpus sidecar replay and comparison receipt fingerprints passed.
  The three pre-existing V1 directionality-policy failures above remain visible.
- Local Markdown links/anchors, JSON parsing, new-whitespace checks, secret-pattern
  scan, source/private-path checks and `git diff --check` passed.

Defensive corrections before the full run: lazy V2-domain loading avoided an
import cycle; legacy rotation version labels were preserved; rule-specific
market lineage stayed on Rule 29 only; unavailable V1 Brain evidence received
an explicit blocker instead of a fictitious fingerprint; raw/generic canonical
lineage contradictions and shadow-mode/V1-label mixtures were rejected.
Historical source-pin checks were updated only for this authorized successor
slice; original approval/receipt artifacts and all economic-policy assertions
remain intact. No implementation changes were made during the full suite.

## Intended checkpoint files

- [README.md](../../README.md)
- [app/diagnostics/brain_lineage.py](../../app/diagnostics/brain_lineage.py)
- [app/gates/engine.py](../../app/gates/engine.py)
- [app/intelligence/research_diagnostic_evidence.py](../../app/intelligence/research_diagnostic_evidence.py)
- [app/intelligence/shared_brain_application.py](../../app/intelligence/shared_brain_application.py)
- [app/portfolio/canonical_diagnostics_orchestration.py](../../app/portfolio/canonical_diagnostics_orchestration.py)
- [app/portfolio/engine.py](../../app/portfolio/engine.py)
- [app/portfolio/holding_intelligence.py](../../app/portfolio/holding_intelligence.py)
- [app/portfolio/sell_side_runtime.py](../../app/portfolio/sell_side_runtime.py)
- [app/rotation/engine.py](../../app/rotation/engine.py)
- [docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_COMPARISON_RECEIPT.json](../../docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_COMPARISON_RECEIPT.json)
- [docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_INVENTORY.json](../../docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_INVENTORY.json)
- [docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1.md](../../docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1.md)
- [scripts/audit_fundamental_v2_brain_portfolio.py](../../scripts/audit_fundamental_v2_brain_portfolio.py)
- [scripts/audit_fundamental_v2_downstream.py](../../scripts/audit_fundamental_v2_downstream.py)
- [tests/unit/test_fundamental_v2_brain_lineage.py](../../tests/unit/test_fundamental_v2_brain_lineage.py)
- [tests/unit/test_fundamental_v2_downstream.py](../../tests/unit/test_fundamental_v2_downstream.py)
- [tests/unit/test_fundamental_v2_downstream_audit.py](../../tests/unit/test_fundamental_v2_downstream_audit.py)
