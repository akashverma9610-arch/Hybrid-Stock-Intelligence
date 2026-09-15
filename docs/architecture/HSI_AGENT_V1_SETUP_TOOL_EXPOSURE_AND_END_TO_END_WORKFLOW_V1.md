# HSI Agent V1 setup tool and composed workflow

Baseline: `2770c49022f93126dc42f07ac8c0cc17f98d3b5c`, `main`.

Status: `IMPLEMENTED / PARTIAL / WATCH_ONLY / NON_EXECUTABLE`.
Decision B: `HSI_AGENT_V1_CORE_WORKFLOW_OPERATIONAL_WITH_SETUP_GAPS`.
Fixture/bounded workflow proof only; not live whole-NSE completeness or a
deployed Agent. Core V1 remains active; Execution Gate V2 remains `NOT_ACTIVE`.
No policy, provider, acquisition, trading or product activation is added.

This extends the existing [Agent facade](HSI_AGENT_V1_MINIMAL_OPENAPI_TOOL_FACADE_V1.md)
and [shared market scan](HSI_AGENT_V1_DHAN_WHOLE_MARKET_SHARED_SCAN_V1.md).

## Canonical machinery inventory and reuse

| Existing implementation | Role and disposition |
| --- | --- |
| `app/strategies/pre_breakout/materialization.py` | Canonical governed technical/structural calculations: base/pivots, confirmation trigger, support, tick-aligned stop, T1, entry reference/ceiling and entry R:R. Reused as stored fields; never invoked by this tool. |
| `app/strategies/pre_breakout/setup_assessment.py` | Canonical assessment combines governance, technical, structural, sector and entry-economics evidence; candidate eligibility is descriptive, not execution authority. |
| `app/storage/sqlite_governance_repository.py` and native `setup_assessment_serialization.py` | Existing exact-security assessment reader validates stored identity/fingerprint during decoding. No new store, schema, write or SQL query. |
| `app/strategies/pre_breakout/governance.py` | Existing approval reconstruction and selection verification; exact policy/selection lineage must match assessment and both nested components. |
| `app/production_v1/canonical_setup_activation.py` | Existing immutable setup opportunity and candidate assembly. Not reconstructed or persisted during the Agent read; assessment reference is retained instead. |
| `app/production_v1/governed_setup_source.py` | Forward-paper setup materialization bridge can write; deliberately not called. |
| `app/signals/models.py`, existing signal/paper query projections | `TradePlan` contains entry/invalidation/T1/T2/extended target and management context. Its existence is not proof that a compatible plan exists for the selected security/as-of. No new TradePlan or grafted values. |
| `app/intelligence/decision_score_evidence.py` | Native canonical stored score reader/adapter reused for lineage only. Shared Brain already consumes score evidence; its public response does not expose a numeric scorecard. No second calculation. |
| `app/intelligence/six_gates_evidence.py` | Native canonical stored gate reader/adapter reused for context-dependent lineage only, including existing source/version guards. No evaluation, capital authorization or V2 economics. |

## Tool contract

`GET /hsi/v1/setup`, operation ID `hsi_get_setup`, requires the existing dedicated
`HSI_AGENT_API_KEY` Bearer authentication. Inputs are exact `NSE:<ISIN>` canonical
security and explicit timezone-aware `as_of`; no caller prices, policies,
portfolio inputs, arbitrary URL, SQL or evidence injection. HTTP query extras
are not consumed. UTC-equivalent cutoffs produce identical results.

The old unexposed `hsi_get_setup_inputs` manifest placeholder is replaced by
`hsi_get_setup`; no previously callable operation is removed. Eight protected
tools now exist. Capabilities reports setup `PARTIAL` when its existing read
repository is bound, otherwise `BLOCKED`; not `READY` merely because routed.

Read latest exact-security assessment with `evaluation_as_of <= request.as_of`.
Equal-time distinct assessments block as ambiguous; no arbitrary input-order
winner. Nested instrument, cutoff and policy/selection provenance must agree.
All stored nested sessions/confirmations must be aware and at/before source
assessment cutoff. Approval reviewed/created and selection selected/effective
times are inclusively bounded by that source cutoff. Missing, corrupt, future
or mismatched required provenance blocks prices; no older-invalid fallback.
Native repository fingerprint checks are not replaced by re-hashing repairs.

The source assessment has no distinct stored known-at receipt/currentness
policy. `temporal_scope=STORED_ASSESSMENT_ONLY`, `freshness=UNKNOWN`, source time
and request cutoff are separate. This is not certified historical PIT nor
current execution validation. No age threshold or expiry is invented.

| Component | Readiness when present | Missing/unsupported behavior |
| --- | --- | --- |
| Entry reference and maximum acceptable/executable reference prices | READY as stored values only | Null; never use trigger or latest quote as entry. No order/fill implication. |
| Breakout-confirmation trigger and native role | READY as stored values only | Null; confirmation is not initial entry. |
| Structural support and native support-breached flag | READY as stored values only | Null; no newly synthesized invalidation rule. |
| Structural stop / T1 / entry risk, reward and R:R | READY as stored values only | Null; no arithmetic, price defaults, recomputation or target extrapolation. |
| Exact invalidation text / T2 / extended target / horizon | BLOCKED | Always null in this assessment projection; compatible TradePlan not bound. |
| Official delivery evidence | PARTIAL | Native percentage/pass copied if present, else null/BLOCKED. Not full liquidity/Gate-3 proof. |
| Decision Score reference | PARTIAL if stored canonical lineage is eligible | BLOCKED if missing/future/invalid; no numeric score calculation or setup compatibility inference. |
| Six Gates reference | PARTIAL if stored canonical lineage is eligible | BLOCKED if missing/future/invalid. Action/portfolio context remains unbound; no eligibility/action output. |

Component readiness means field availability, not policy PASS or execution
permission. Native setup/technical/structural states, candidate-formation flag,
entry economics and blockers are retained. An ineligible native assessment
has outer status `BLOCKED` even if some descriptive levels exist. An eligible
stored assessment is still outer `PARTIAL`. Score/Gates may have distinct native
timestamps; their references explicitly state `NOT_BOUND_TO_SETUP_CONTEXT`.

## Practical workflow inventory

| User workflow | Existing tools and truthful readiness |
| --- | --- |
| Deep stock analysis | Diagnostics + Shared Brain stock intelligence + market context + news. Partial canonical evidence; not an all-domain recommendation. |
| Market opportunities | Retained shared scan -> emitted candidate -> selected-security canonical Rules 1–61. No per-question scan refresh; current-descriptive diagnostics retain strict-PIT/technical-binding gaps. |
| Setup request | Selected stock -> stored governed setup tool. Partial fields and separate stored Score/Gates context, no setup creation. |
| Portfolio analysis | Existing read-only portfolio snapshot + stock intelligence + market context. Stored marks/cash status retained; no mutation. |
| Portfolio rotation research | Portfolio snapshot + shared shortlist + diagnostics may be read together. No automatic rotation, trade action, or Gate-1 V2 economics. |

The backend returns structured evidence. A later Agent may choose which tools
to combine; this slice adds neither conversational recommendations nor an LLM
workflow engine, provider request, web search, live feed, new Brain or UI.

## Validation and safety evidence

`tests/unit/test_agent_setup.py` verifies native nullable fields, source and
governance PIT guards, ambiguity, tamper rejection, reopen durability, UTC
replay, authenticated HTTP, safe error redaction and native stored Score/Gates
reference reuse. It checks no setup/gate recalculation and static read-only
dependencies. Existing Agent OpenAPI/auth compatibility tests cover all tools.

The composed HTTP fixture reads one shared snapshot, selects an emitted exact
security, runs the existing canonical runner once with exactly IDs 1–61, then
reads real Shared Brain, market context, setup and portfolio projections.
Security/request cutoff and native fingerprints correlate; market context
retains mixed native timestamps rather than a fabricated common cutoff.
Two scan reads reuse one operator refresh. Setup repository traces are SELECT
only; external requests and setup recomputation are forbidden in the test;
portfolio snapshot remains identical. No production database or live service
is mutated. This is not `WHOLE_NSE_LIVE_READY`.

Completed validation: focused Agent/setup/shared-scan tests **106 passed**;
relevant setup/governance/Score/Gates/Radar/61/API regressions **134 passed**;
full backend **8,592 passed / 0 failed / 6 skipped / 2 warnings** (402.37 seconds).
Both focused and relevant runs reported the same two dependency deprecation
warnings. Two local Markdown links, whitespace and `git diff --check` passed.
No unrelated Core algorithm or historical governance artifact changed.

Next frozen continuation: `HSI_AGENT_V1_LYZR_CONNECTION_AND_MASTER_THESIS_V1`.
Not started in this slice.
