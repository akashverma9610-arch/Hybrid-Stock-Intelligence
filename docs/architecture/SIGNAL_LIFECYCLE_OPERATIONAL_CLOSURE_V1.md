# Signal Lifecycle operational closure audit V1

Baseline: `26f0efb1847d6c3789e1c11ab0b50d402219d253`, branch `main`, clean.
Repository: `D:\nse-stock-manager`. No remote push or production data access.

**Closure status: BLOCKED. Audit/proof checkpoint complete, not operational closure.**

Decision C: `SIGNAL_LIFECYCLE_FOUNDATION_READY_RUNTIME_BINDING_INCOMPLETE`.
The missing binding is **governance-dependent**, not merely an API adapter:
P1 has no independent transition/terminal policy or durable lifecycle contract.
No safe wiring can import those semantics implicitly from legacy trade plans.

V1 remains ACTIVE; Execution Gate V2 remains NOT_ACTIVE. CAS and Lyzr/Agent work
remain parked. ONE deterministic HSI Brain remains the analytical authority.
No broker/order authority is added. All P1 values remain WATCH_ONLY /
NON_EXECUTABLE. The accepted [opening/overnight predecessor](OPENING_GAP_OVERNIGHT_INTELLIGENCE_OPERATIONAL_CLOSURE_V1.md)
and Catalyst/Event closure are unchanged.

## Authority and reuse map (inspected before changes)

The [P1 acceptance record](POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md), sections
1, 3, 5, 7 and 10, explicitly establishes pure on-demand projection, no
independent lifecycle/expiry, no P1 persistence and no import of `app.signals`.
The [product architecture](POST_V1_PRODUCT_ARCHITECTURE.md) preserves that split.
The present request authorizes minimal lifecycle closure **using existing
governed semantics**; it does not supply the deferred cross-Watch policy.
No historical approval document is rewritten by this audit.

| Component | Existing owner | Classification | Verified scope / gap |
| --- | --- | --- | --- |
| Canonical P1 contract | [hsi_signal.py](../../app/intelligence/hsi_signal.py) | OPERATIONAL | Immutable internal value, identity/fingerprint verification, exact Watch lineage; not a lifetime aggregate. |
| Strategy Registry | [hsi_signal_strategy_registry.py](../../app/intelligence/hsi_signal_strategy_registry.py) | OPERATIONAL | Read-only v1 policy provenance; only PRE_BREAKOUT can resolve, conditionally. |
| P1 projector | [hsi_signal_projection.py](../../app/intelligence/hsi_signal_projection.py) | OPERATIONAL | Pure single-Watch projection, NOT a transition-event/current-state reducer. |
| Runtime emission/query | Existing P1 callable; no production caller found outside its module/tests | IMPLEMENTED_NOT_WIRED | No default scheduler, P1 query/API or automatic emission. |
| Watch source and storage | [market_wide_watch.py](../../app/intelligence/market_wide_watch.py), CoreApiSnapshot repository | OPERATIONAL | Immutable Watch runs, repeat-save no-op, explicit-as-of latest reads and reopen; no signal-event storage. |
| Router / lifecycle flags | [opportunity_archetypes.py](../../app/intelligence/opportunity_archetypes.py) | OPERATIONAL | Per-evaluation capability flags, not temporal transitions or terminal states. |
| Pre-Breakout approval/selection | Existing governance service/commands and SQLite governance repository | OPERATIONAL | Verified immutable provenance, CURRENT_STORED_SCAN context and explicit PIT selection. |
| Approved setup origin | [canonical_setup_activation.py](../../app/production_v1/canonical_setup_activation.py), governed setup assessment | PARTIAL | Setup opportunity retains assessment/policy fingerprints; Watch retains summary state/routes, not an exact setup-instance reference. |
| Independent P1 lifecycle | No P1 owner or approved transition table | POLICY_BLOCKED | Lifetime identity, previous/next state, terminal, re-arm and transition evidence semantics undefined. |
| P1 persistence | No P1 writer, schema or event repository | NOT_IMPLEMENTED | Source Watch/governance durability is not independent lifecycle durability. |
| P1 invalidation / expiry | P1 source status/flags; expires_at=None | POLICY_BLOCKED | No automatic structural/news/price invalidation mapping or approved expiry duration. |
| Supersession / retirement | No P1 link or transition rule | POLICY_BLOCKED | New projections have new identities; no predecessor/successor or retirement treatment. |
| Concurrent lifecycle writes | No lifecycle writer | NOT_IMPLEMENTED | Concurrent independent projection readers are tested; no exactly-once writer claim. |
| P1 PIT/replay | Watch cutoff, lineage, registry checks and serializer | PARTIAL | Exact retained source replay works; references alone cannot prove all underlying historical known-at data. |
| Legacy analytical lifecycle | [signals/models.py](../../app/signals/models.py), [signals/engine.py](../../app/signals/engine.py) | PARTIAL | Separate SignalRecord/TradePlan/SignalLifecycleEvent implementation; not P1. |
| Legacy storage/reconstruction | SQLiteStrategyGovernanceRepository, AuditReconstructionService | OPERATIONAL | Retained record/plan/event reconstruction; duplicate insert rejects. Not proof of P1 lifecycle. |
| Legacy query / paper replay | SignalQueryService, HistoricalSignalPaperReplayService | PARTIAL | Separate trade-plan/paper consumers, not an admissible P1 bridge. |
| Brain / diagnostics lineage | Watch diagnostic/external references | PARTIAL | Read provenance retained; no new Brain or rule. No P1 reevaluation binding. |
| Decision Score | Separate Watch/Brain score | OPERATIONAL | P1 requires no new score threshold; score readiness is not trade permission. |
| Six Gates | Separate canonical gate evidence | OPERATIONAL | No new evaluation or PASS. Router SIX_GATES_READY means evaluated, NOT passed. |
| Portfolio / Watch consumption | Source Watch portfolio_records and downstream existing views | PARTIAL | Watch is upstream of P1; no P1 lifecycle portfolio/watchlist consumer proven. |
| Event / overnight / regime / sector | Existing contextual Brain paths | PARTIAL | No approved generic signal transition from news, gap or contextual change. |
| Alert consumer / scheduler | No P1 transition delivery boundary | NOT_IMPLEMENTED | No notifications, scheduler or Alerts work performed. |

## Exact identity, creation and registry truth

The existing projector takes a verified `MarketWideWatchRecord`, one routed
`OpportunityArchetype` and the P1 registry. No new creation boundary is installed.
It returns a normalized descriptive P1 value even when its strategy resolution
is STRATEGY_UNAVAILABLE. Such a value is **not an approved strategy emission**.
Do not erase existing unsupported-archetype projections or call them activated
strategies to satisfy the requested registry boundary.

PRE_BREAKOUT resolves only with CURRENT_VALID_SETUP and the exact
PRE_BREAKOUT_POLICY route plus validated approval/selection provenance. The
registry checks effective_from and selected_at <= watch_as_of, approval
created_at/reviewed_at <= watch_as_of, ambiguity/duplicates and native policy
verification. Existence of a policy alone is insufficient. The registry resolves
provenance; it neither calculates the strategy nor certifies a TradePlan.
All other ten current OpportunityArchetype values remain STRATEGY_UNAVAILABLE.
Fixtures use synthetic, locally approved governance records; this audit does
not inspect or alter production policy selections or prove live emissions.

Identity is the existing `hsi-signal:` digest of canonical instrument, Watch
ID/fingerprint/as-of, optional canonical detection/horizon/direction state and
references, archetype/routing version, complete strategy resolution, ordered
diagnostic/evidence lineage and P1 contract version. UTC normalization and
stable serialization are reused. Content fingerprint additionally covers
descriptive status/flags, blockers and fixed authority/unavailable fields.
No symbol-only identity or runtime-clock timestamp is introduced.

Changing Watch/as-of, retained evidence or policy provenance changes the P1
identity. Therefore a later evaluation is **not a transition on the original
signal ID**. No implementation may coalesce these IDs into a lifetime, infer
supersession, or transfer another security's history without a defined policy.
An earlier serialized projection remains unchanged. Registry changes are read
at the original Watch cutoff; lifecycle retirement/re-arming is still undefined.

## Vocabulary reconciliation: preserve, do not merge

P1 copies WatchStatus exactly:
WATCH_ACTIVE, WATCH_DATA_PARTIAL, WATCH_RISK, WATCH_NO_LONGER_QUALIFIES.
These are evaluation descriptions; WATCH_NO_LONGER_QUALIFIES is not a governed
irreversible P1 terminal state.

Router flags are DISCOVERED, WATCH, CONFIRMED_EVIDENCE,
SETUP_POLICY_ELIGIBLE, SETUP_AVAILABLE, DECISION_SCORE_READY and
SIX_GATES_READY. They describe the same evaluation's available capabilities.
Their ordering is not an event log or transition history. No new state is added.

Legacy SignalStatus is DRAFT, ELIGIBLE, WAITING_FOR_TRIGGER,
TRIGGERED_ANALYTICALLY, INVALIDATED, EXPIRED, CANCELLED, BLOCKED and
INSUFFICIENT_DATA. Legacy SignalEventType includes creation, revalidation,
trigger met/lost, gate blocking, invalidation, expiry and cancellation.
Its SignalConfig requires score/confidence/R:R, gate, entry-type, expiry,
confirmation and cooldown values. None supplies missing P1 parameters.
Pre-Breakout setup has NOT_GOVERNED_FOR_SETUP_OPPORTUNITY horizon semantics;
its structural support/stop evidence is not an approved P1 lifetime invalidator.

Legacy source review also prevents an unsafe mechanical bridge:

- `SignalOrchestrator.revalidate` accepts prior_events but does not reduce them
  or enforce terminal absorption from that history. It is not a validated P1
  terminal/out-of-order reducer.
- Legacy creation ID includes instrument/type/as-of, not the P1 policy/evidence
  identity dimensions. Legacy events lack P1's complete fingerprint/version and
  previous-state provenance requirements.
- Legacy SQLite rejects duplicate signal/event inserts, whereas WatchStore
  returns False for identical source saves. Neither proves idempotent P1
  transition submission under concurrent writes.
- Legacy reconstruction returns retained signal/plan/events, not a P1 state
  reducer. Legacy replay can proceed into paper simulation; P1 must not call it.
- Generic SIGNAL snapshot capacity and existing `/signals` views are not
  authorization to store/serve P1 under legacy semantics.

These are compatibility findings, not permission to patch frozen Core or a
claim that two intentionally separate models constitute a second Brain.

## Supported proof versus blocked lifecycle requirements

| Requested fixture | Evidence established | Honest limit |
| --- | --- | --- |
| A creation | Synthetic approved Pre-Breakout selection plus retained routed Watch produces one deterministic P1 projection | Not live setup acquisition or lifetime creation |
| B duplicate | Same source yields same ID/fingerprint; repeated Watch save is False | No new signal rows or transition deduplication |
| C valid transition | Changed Watch/status produces a distinct immutable projection | Cross-Watch transition policy absent; not claimed |
| D invalid transition | Tampered Watch, future aggregate evidence and wrong registry provenance reject in focused/relevant tests | No P1 transition API exists to test illegal edges |
| E invalidation | Missing CURRENT_VALID_SETUP makes subsequent resolution unavailable; original value unchanged | Not a terminal invalidation event or portfolio instruction |
| F expiry | expires_at remains None, EXPIRY_POLICY_UNAVAILABLE | No synthetic days/sessions/horizon |
| G future evidence | Explicit Watch cutoff and P1/registry checks exclude known future inputs | Watch references do not independently carry every source known-at or exact setup ID |
| H out of order | Persist later Watch before earlier; explicit-as-of retrieval replays each deterministically | Equal-time conflicting runs/lifetime transition ordering require policy; do not repurpose latest run-ID tie-break as transition authority |
| I reopen/retry | Reopen both Watch and governance SQLite stores, project byte-identical result; synthetic projection interruption leaves saved Watch intact | Source durability only; no P1 event journal/current-state rebuild |
| J gates | P1 remains WATCH_ONLY/NON_EXECUTABLE with UNSCORED and gates NOT_EVALUATED | No gate PASS or execution capability |
| Concurrent reads | Separate connections produce identical P1 values | Not a writer race or exactly-once scheduler guarantee |

All database fixtures are isolated temporary stores. They assert legacy signal,
signal-event, paper-trade and trade-plan counts remain zero for P1 projection.
No production database, credentials, provider, API or notification is used.

Source Watch evidence IDs/fingerprints and policy approval/selection references
remain reproducible. Strict historical source availability is still domain-
dependent; the accepted reported-opening projection cannot be relabelled as
opening-time PIT evidence. Raw news or gap signs do not become transition reasons.
Current setup provenance is only summarized by Watch: a future binding must
verify exact historical setup instance/policy linkage rather than assume that
the selected policy at a later cutoff necessarily produced that setup.

## Safety and closure disposition

SIGNAL != BUY; SIGNAL != SELL; ACTIVE SIGNAL != EXECUTABLE;
ACTIVE SIGNAL != SIX GATES PASS; INVALIDATED SIGNAL != automatic portfolio sale;
EXPIRED SIGNAL != proof that a thesis was wrong. These are authority boundaries,
not newly introduced lifecycle states. No score, setup, gate, portfolio, Watch,
provider, schema, runtime or source implementation changed in this checkpoint.

Closed by this audit: authoritative model distinction; exact identity and
registry truth; persisted-source reopen/retry proof; source-order-independent
projection; explicit downstream and legacy boundaries.

Still blocking operational lifecycle: approved persistent lifetime identity and
cross-Watch linkage; exact transition/terminal/invalidation/expiry/supersession
and registry-retirement semantics; exact setup-instance/evidence provenance;
durable transition retention, concurrent idempotency and deterministic current-
state read/rebuild binding. No terminal or positive strategy policy is invented.

## Validation

Focused audit: 11 passed. The initial new fixture omitted two existing Watch-run
counter fields from its native fingerprint inputs; supplying those explicit
zero counters corrected the fixture only. No production implementation changed.

Relevant regressions: **193 passed, 0 failed, 2 warnings** across P1A/P1B/P1C,
Watch, Pre-Breakout approval/selection/setup/candidate, legacy lifecycle/storage/
historical references/query, Brain, Decision Score, Six Gates and accepted
Catalyst/Opening tests. Warnings are existing TestClient/httpx and anyio
deprecations. Full backend
rerun is not required by this slice's conditional rule: only audit documentation
and isolated tests are added, with no shared/runtime/persistence behavior change.
The predecessor's 8,643 passed / 6 skipped / 2 warnings is historical evidence,
not a claimed full-suite run for this checkpoint. Local links, whitespace and
staged diff checks are required before commit.

## Exactly one next frozen continuation (not started)

`SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_DEFINITION_V1`

Define and obtain explicit approval of the missing P1 lifetime/transition and
retention compatibility contract against the existing Watch/registry/setup
provenance, preserving P1A-P1D and legacy models. It must settle cross-Watch
identity, admissible evidence, terminal/re-arm behavior, absence of expiry,
retirement, equal-cutoff conflicts and durable replay ownership before runtime
binding. Prefer existing storage only after compatibility is demonstrated.
This recommendation does not authorize its implementation here. Alerts cannot
claim a lifecycle producer before this blocker is resolved.
