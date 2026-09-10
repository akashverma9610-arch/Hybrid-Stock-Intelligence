# Radar to HSI Diagnostic Orchestration V1

**Status:** `IMPLEMENTATION_READY / RESEARCH_ONLY / WATCH_ONLY / NON_EXECUTABLE / RUNTIME_NOT_ACTIVE`

## Purpose and authority

`RadarToHsiDiagnosticOrchestrator` is the narrow, read-only handoff from one immutable `CanonicalDiscoveryLead` to the existing `app.universe_analysis.service.Canonical61DiagnosticRunner`. It answers only: *what do the existing canonical Rules 1–61 know about this security at this explicit evidence boundary?*

It does not create a second Brain, a Radar rule set, a score, a gate verdict, an opportunity, a setup, a signal, an alert, an order, or a portfolio action. Receipt authority is always `RESEARCH / WATCH_ONLY / NON_EXECUTABLE`.

## Existing architecture reused

| Boundary | Existing entry point reused | Bridge responsibility |
| --- | --- | --- |
| Discovery | `CanonicalDiscoveryLead` and its Multi-Funnel registry | Verify lead identity, fingerprint, family, source lineage, and governed horizon context. |
| Evidence | `AssembledStockEvidence` | Require an injected, already assembled canonical evidence view; do not fetch or assemble providers. |
| Canonical diagnostics | `Canonical61DiagnosticRunner` and `DIAGNOSTIC_RULES` | Delegate all 61 evaluations unchanged and retain their references. |
| Technical readiness | `CanonicalTechnicalDiagnosticInput` | Require its existing current-descriptive contract so named VWAP is explicitly blocked. |
| Rule registry | `diagnostic-registry-v1` | Assert exactly IDs 1–61, once each; no Rule 62. |

The existing Decision Score and Six Gates are downstream and are not invoked. Market-Wide Watch, archetype routing, Shared Brain, portfolio diagnostics, persistence, and API/UI query surfaces are untouched.

## Evaluation boundary and temporal truth

`evaluation_as_of` is required for every evaluation. It is timezone-aware, UTC-normalized, never derived from wall-clock time, and must not precede the lead’s `discovery_as_of` or source-lineage `known_at`. Canonical evidence must match the same security and cutoff. A later lead or lineage is rejected before evidence assembly.

The bridge does not equate an `as_of` field with universal strict historical PIT proof. The current technical adapter is recorded as `CURRENT_DESCRIPTIVE`; its own `STRICT_HISTORICAL_PIT = NOT_READY` limitation remains visible. No evidence is back-projected, and no live or provider call is made.

## Horizon and applicability

The only proven Radar path is existing `PRE_BREAKOUT` discovery with its governed `POSITIONAL` association. `PRE_BREAKOUT` is a discovery/setup type, not a fourth horizon. The bridge requires an explicit canonical horizon supported by the lead; it does not infer `SHORT_TERM`, `POSITIONAL`, or `LONG_TERM`.

`RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1` remains documented as candidate/not-active. The bridge preserves that limitation rather than materializing a runtime applicability matrix. Each Rule remains represented by actual canonical output; future activation requires a separate approved slice.

## Exact 61-rule accounting and preserved limitations

Every accepted receipt contains Rule IDs 1–61 in registry order, with the existing result ID, result vocabulary, eligibility, evidence/input references, and explicit readiness. Missing evidence is retained as `INSUFFICIENT_DATA`; it is never zero-filled, bullish, bearish, or neutralized.

- Rule 6 remains `PARTIAL`: no authoritative peer cohorts are synthesized.
- Rule 14 remains `PARTIAL`: no 15-minute, 30m, 1H, or 4H substitution is allowed. Actual production canonical 15-minute coverage remains `0`.
- Rule 35 is `SOURCE_NOT_READY`: named VWAP/value-area semantics remain unavailable and are not derived here.
- Rule 57 is `SOURCE_NOT_READY`: a discovery lead does not create canonical event materiality or post-event completed-session evidence.
- Rules 15–30 remain in the same canonical Brain. Technical discovery cannot bypass financial, ownership, governance, legal, or company evidence.

## Receipt, replay, and bounded batch behavior

`RadarDiagnosticReceipt` is immutable and links the lead ID/fingerprint, canonical security, family, explicit cutoff, governed horizon, exact registry fingerprint, input-evidence fingerprint, technical temporal state, and all 61 existing rule references. Identity and content fingerprint are distinct. Receipt timestamps are the supplied canonical evaluation boundary; no runtime-created timestamp is fabricated.

Equivalent lead, evidence, policy, horizon, and cutoff replay produces the same receipt. A same-ID lead with different valid content fails closed as a conflict. `evaluate_leads` is bounded to 100 inputs by default and processes qualified leads only; it is not a queue, scheduler, full-universe diagnostic run, or page-load operation.

Each bounded batch retains distinct audit denominators: input leads, accepted
leads, deduplicated leads, rejected leads, evaluated securities, 61-rule
references, per-rule readiness distribution, data-insufficient count,
conflicted count, and canonical-horizon distribution. These counts are never
treated as selected-universe, provider-capacity, or live-15m denominators.

## Current readiness

| Capability | State | Exact reason |
| --- | --- | --- |
| Lead-to-61 bridge | READY | Existing lead and canonical runner are composed read-only. |
| Pre-Breakout end-to-end handoff | READY | Existing immutable lead may enter the same 61-rule runner. |
| Rule horizon runtime matrix | PARTIAL | Candidate policy is not active. |
| Strict historical technical PIT | NOT_READY | Daily/Weekly adapter is current-descriptive. |
| Actual canonical 15m evidence | NOT_READY | Production count is 0. |
| Named VWAP | NOT_READY | Existing named semantics are unavailable. |
| Authoritative peers | NOT_READY | Existing peer cohort count is 0. |
| Event-session Rule 57 evidence | NOT_READY | No event/session path is created by this bridge. |
| Decision Score and Six Gates | NOT_APPLICABLE | Downstream; intentionally not invoked. |
| Runtime scheduling/live production | NOT_READY | No scheduler or live provider activation exists. |

## Non-goals

No execution-shaped output, market-data acquisition, indicator expansion, technical-timeframe synthesis, policy threshold change, persistence migration, API/UI exposure, user output, broker/order call, portfolio access, or security configuration is included.

The next dominant internal boundary after a clean bridge is `61_DIAGNOSTIC_FULL_OPERATIONAL_COVERAGE_CLOSURE_V1`.
