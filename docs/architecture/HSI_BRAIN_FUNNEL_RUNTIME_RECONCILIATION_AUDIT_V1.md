# HSI Brain / Funnel / Runtime Reconciliation Audit V1

Status: `REPOSITORY_RECONCILIATION_AUDIT / NO_RUNTIME_INTEGRATION / NOT_ACTIVE`

Slice: `HSI_BRAIN_FUNNEL_RUNTIME_RECONCILIATION_AUDIT_V1`

Baseline: `f3dbb065017c1577d1dffdd0c1a3901b561f6ff9` on `main`, initially clean.

Decision **B — `BRAIN_CAPABILITIES_EXIST_RUNTIME_WIRING_INCOMPLETE`**. Audit slice **ACCEPTED/CLOSED**; this does not close its runtime gaps or activate a product.

[Machine-readable audit and complete per-funnel matrix](HSI_BRAIN_FUNNEL_RUNTIME_RECONCILIATION_AUDIT_V1.json).
[Accepted Gate-1 predecessor](GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1.md).
[Registry](MULTI_FUNNEL_DISCOVERY_CONTRACT_AND_REGISTRY_V1.md),
[adapters](MULTI_FUNNEL_DISCOVERY_ADAPTERS_V1.md),
[union](MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md),
[runner](MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md),
[existing Radar bridge](RADAR_TO_HSI_DIAGNOSTIC_ORCHESTRATION_V1.md).

## Evidence and authority boundary

Repository source, explicit call sites, pure contracts and isolated conformance/regression tests establish this audit. No production database contents, scheduler state, provider availability or current live executions were sampled. Database existence was checked only. No acquisition, Brain materialization or portfolio operation ran.

Here **OPERATIONAL means an implemented callable edge in the inspected repository**, with its existing prerequisites; it is not a new production canary claim. Runtime scanner columns refer to the multi-funnel path, not all historical/context-specific HSI commands. Imported types do not prove runtime invocation. Neither module presence nor a registry status proves complete source coverage.

Frozen states remain: `six-gates-production-v1 / v1 = ACTIVE`; Execution Gate V2 `NOT_ACTIVE`; research bootstrap `UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE`; numeric bootstrap seed `UNSET`. No historical artifacts, source pins, investment thresholds, source policies, scoring or activation states are changed.

The JSON pins 196 source/predecessor files using LF-normalized SHA-256 and retains predecessor native fingerprints and authority/parameter fields. Its content fingerprint covers every other field, including the matrix; it is not a runtime policy.

## Executive finding: union really is the stopping point

[orchestrate_whole_market_discovery](../../app/intelligence/multi_funnel_orchestration.py) reads retained source records through an injected reader, dispatches **five** explicit adapter bindings, records all **fourteen** registry entries, then constructs `WholeMarketDiscoveryBatch.candidate_union`. It does not invoke evidence assembly, Brain composition, Canonical61, Decision Score, setup or gates. Searches in application/API/runtime, scripts/tools and frontend found no production call site binding this pure runner. Discovery recall modules consume its audit data, not a production inspection queue.

The exact code state equivalent to documentation's `BRAIN_INSPECTION_CANDIDATES` is **`CandidatePoolStatus.CANDIDATE_FOR_SHARED_BRAIN_INSPECTION`** on `CanonicalDiscoveryPoolItem`. There is no independently persisted queue or implemented downstream consumer of this union.

This is not fourteen missing intelligence engines. The separate [RadarToHsiDiagnosticOrchestrator](../../app/intelligence/radar_diagnostic_orchestration.py) already composes an admitted **lead** with the existing Canonical61 runner. It is not called by discovery, and its `CanonicalRadarEvidenceAssembler.assemble_for_radar` remains an injected protocol with no concrete production implementation found.

## Canonical fourteen-funnel matrix

Registry ID `hsi-multi-funnel-discovery-registry`, version `v1`, native fingerprint `121b6a91d0c7a8f7fdd3da6ae02e11a56575538a876055958cbc5f7dd5e22aec`. IDs below are exact, not remembered strategy names. Display names in JSON are readable labels of those enums, not new canonical identifiers.

Primary classifications (one per row):

- **REUSE** = `ALREADY_IN_BRAIN_ADAPTER_REQUIRED`. Existing adapters may already be present: this class includes shared handoff work, not a claim that each adapter is missing.
- **RESEARCH** = `RESEARCH_BUILT_PROMOTION_REQUIRED`.
- **MISSING** = `ACTUALLY_MISSING_INTELLIGENCE` in sufficient *qualified named-policy* form, not absence of all related primitives.
- **CONTEXT** = `CONTEXTUAL_ONLY`; a contextual contract may itself still be missing.

| Exact funnel ID | Registry source state | Current scope | Real adapter | Primary class |
| --- | --- | --- | --- | --- |
| `COMPOUNDER` | RESEARCH_SHADOW | BOUNDED_MARKET_UNIVERSE | adapt_compounder | RESEARCH |
| `EARNINGS_ACCELERATION` | PARTIAL | BOUNDED_MARKET_UNIVERSE | None | REUSE |
| `EMERGING_COMPOUNDER` | NOT_IMPLEMENTED | BOUNDED_MARKET_UNIVERSE | None | MISSING |
| `FUNDAMENTAL_INFLECTION` | RESEARCH_SHADOW | BOUNDED_MARKET_UNIVERSE | adapt_fundamental_inflection | RESEARCH |
| `HOLDING_STATE_CHANGE` | PARTIAL | PORTFOLIO_CONTEXT_ONLY | None | CONTEXT |
| `MARKET_DISLOCATION` | PARTIAL | OTHER_GOVERNED_SCOPE | None | CONTEXT |
| `MOMENTUM` | PARTIAL | BOUNDED_MARKET_UNIVERSE | None | REUSE |
| `NEWS_CATALYST` | PARTIAL | EVENT_CONTEXT_ONLY | None | REUSE |
| `ORDERBOOK_CAPEX` | PARTIAL | BOUNDED_MARKET_UNIVERSE | None | REUSE |
| `POLICY_TRANSMISSION` | RESEARCH_SHADOW | EVENT_CONTEXT_ONLY | adapt_policy_transmission | RESEARCH |
| `PRE_BREAKOUT` | OPERATIONAL | BOUNDED_MARKET_UNIVERSE | adapt_pre_breakout | REUSE |
| `SECTOR_ROTATION` | OPERATIONAL | BOUNDED_MARKET_UNIVERSE | adapt_sector_rotation | REUSE |
| `VALUATION_RECOVERY` | POLICY_BLOCKED | BOUNDED_MARKET_UNIVERSE | None | MISSING |
| `WATCHLIST_STATE_CHANGE` | NOT_IMPLEMENTED | WATCHLIST_CONTEXT_ONLY | None | CONTEXT |

For **all fourteen** rows: no runtime whole-market scanner, no union-triggered Brain/61/score/setup/gate invocation, no union-origin portfolio/signal/API/UI projection. Five adapters can emit candidates in an explicit isolated invocation when their source-state conditions hold; no live counts are claimed. All eligible emitted leads use the same union.

| Funnel | Existing predicate / evidence and exact remaining work |
| --- | --- |
| `COMPOUNDER` | Prospective observation availability; not positive compounder qualification. Calibration, promotion and shared runtime binding; reuse existing research. |
| `EARNINGS_ACCELERATION` | Existing Router Rule 24 ACCELERATING route, not an independent funnel predicate. Governed trigger and emitter over existing diagnostics; no replacement earnings score. |
| `EMERGING_COMPOUNDER` | No qualified discovery predicate; common readiness contract exists. Missing qualified family policy, not missing common readiness infrastructure. |
| `FUNDAMENTAL_INFLECTION` | ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE receipt; not promoted qualification. Calibration/promotion and source timestamp readiness; retain prospective limitations. |
| `HOLDING_STATE_CHANGE` | Holding composition exists; change emitter absent. Context-bound delta policy/adapter; not a whole-NSE holding scanner. |
| `MARKET_DISLOCATION` | REGIME_CONTEXT_ONLY; no security-level dislocation trigger. Retain regime context; any security discovery needs a separately governed predicate. |
| `MOMENTUM` | Rule 6 LEADING/EMERGING_LEADER route exists; standalone momentum policy absent. Governed lightweight trigger/emitter, not another momentum scoring engine. |
| `NEWS_CATALYST` | Existing verified CATALYST_WATCH route; no independent calibrated discovery emitter. Reuse news/catalyst primitives; govern freshness/trigger and emit exact exposed NSE identities only. |
| `ORDERBOOK_CAPEX` | Rule 27 GROWING route exists; broader capex is not that rule. Governed trigger/emitter; capex interpretation and source sufficiency cannot be invented. |
| `POLICY_TRANSMISSION` | POLICY_DEFINITION_MISSING research receipt may emit an inspection lead, never a qualified beneficiary. Retain research state; policy/calibration/promotion before any qualified discovery. |
| `PRE_BREAKOUT` | Existing CanonicalSetupOpportunity, governed assessment and policy required. Adapter already exists: shared runtime handoff missing, not policy or setup rebuild. |
| `SECTOR_ROTATION` | Existing run.candidate_ids targets; not only valid opportunity_ids. Adapter already exists; reconcile stale registry blocker descriptively and bind shared handoff later. |
| `VALUATION_RECOVERY` | No approved valuation-recovery predicate; quality/fair-value readiness is not recovery policy. Governed recovery semantics genuinely missing; reuse existing valuation/readiness inputs. |
| `WATCHLIST_STATE_CHANGE` | No governed watchlist-state contract or change adapter. Define only context-bound contract later; not an ordinary market-wide scanner. |

The JSON adds every requested field per funnel: purpose, producer, required source/policy, output contract, provenance, deep-diagnostic boundary, emitter/research/adapter/scanner state, every downstream stage, missing edges, provider versus wiring blockers, duplication risk and documentation reference.

## Whole-NSE intent versus actual scope

The frozen product flow intends broad eligible-NSE discovery. Current execution accepts a **supplied** `UniverseSnapshot` plus immutable `NseEquityInstrument` records. [build_universe_snapshot](../../app/universe_analysis/service.py) preserves existing NSE/EQUITY/`main_board is not False` eligibility; the runner verifies checksum, counts, membership, exact `NSE:<ISIN>` and cutoff. Unknown main-board metadata is not reinterpreted here. This validates a population, not that its supplier captured all eligible NSE instruments.

Current Top3 sources cover sector-selected constituent targets, not an unconditional complete-NSE scan. Inflection/compounder sources cover supplied prospective observations. Event/policy sources require exact affected-company exposure. Holding and watchlist entries explicitly require their own contexts; Market Dislocation's output is `REGIME_CONTEXT_ONLY`. The generic registry eligibility text does not turn a regime into per-security discovery.

Thus “all fourteen scan the whole NSE unconditionally” is **not implemented and is inconsistent with contextual registry eligibility**. The resolution is explicit contextual branches within one discovery platform, not silent scope expansion. No second Brain or incompatible final authority was found; this scope clarification and descriptive metadata drift do not by themselves justify decision D.

## Existing Brain capabilities to reuse

| Capability | Repository evidence | Finding / readiness |
| --- | --- | --- |
| TECHNICAL_RELATIVE_STRENGTH | [Canonical61DiagnosticRunner / _evaluate](../../app/universe_analysis/service.py) | PARTIAL: Rules 6/technical diagnostics reuse; peer and timeframe limits retained. No separate momentum score. |
| FUNDAMENTAL_ACCOUNTING | [earnings_acceleration / order_book](../../app/analysis/fundamentals.py) | PARTIAL: Rule 24 is reported revenue YoY classification, not a new multi-period acceleration estimate. Rule 27 consumes order_book/order_inflow/revenue; not universal capex or all-company evidence. |
| FINANCIAL_INPUT_LINEAGE | [StockDiagnosticInputAssembler.assemble](../../app/universe_analysis/service.py) | IMPLEMENTED: Canonical financial/technical/benchmark inputs must match security/as_of; PointInTimeGuard selects observations. Unavailable inputs remain insufficient. |
| EXTERNAL_CATALYST | [CatalystService](../../app/intelligence/catalysts/service.py) | IMPLEMENTED: Event cluster/source/filing lineage; order-to-revenue only with valid inputs; priced-in UNKNOWN, no action. |
| COMPANY_SENSITIVITY | [MacroToEarningsTransmissionEngine](../../app/intelligence/company_sensitivity/service.py) | IMPLEMENTED: Exact supplied profile context; missing driver UNKNOWN; no company fact substituted from sector. |
| MACRO_POLICY | [MacroEvidence.eligible_as_of](../../app/intelligence/macro/service.py) | PARTIAL: Availability/publication/effective-time admission; does not prove complete company policy-to-cash realization. |
| MARKET_EXTREMES | [project_market_extremes_assurance](../../app/intelligence/market_extremes_assurance_projection.py) | IMPLEMENTED: Reusable regime assurance, not a per-security market-dislocation trigger. |
| PRE_BREAKOUT | [GovernedPreBreakoutSetupAssessmentService.assess_prebreakout_setup](../../app/strategies/pre_breakout/setup_assessment.py) | IMPLEMENTED: Selected approved policy + technical/structural/sector evidence; eligibility is not order authority. |
| COMPOUNDER | [run_compounder_prospective_batch](../../app/intelligence/compounder_prospective_shadow_validation.py) | RESEARCH_SHADOW: Prospective research observations; qualification deferred, not absent code. |
| INFLECTION | [run_inflection_accounting_prospective_batch](../../app/intelligence/inflection_accounting_prospective_shadow.py) | RESEARCH_SHADOW: Canonical accounting research; positive promoted family qualification not active. |
| LONG_TERM_READINESS | [_REQUIRED_DOMAINS](../../app/intelligence/long_term_thesis_research_shadow.py) | RESEARCH_SHADOW: Five family readiness domains exist including asymmetric emerging; does not supply missing qualified emerging/recovery policies. |
| HOLDING_INTELLIGENCE | [compose_holding_intelligence](../../app/portfolio/holding_intelligence.py) | CONTEXT_SPECIFIC: Canonical Brain-to-holding composition; scoped holding context, not all-market detection. |
| SHARED_BRAIN_COMPARABILITY | [SharedBrainApplicationService.analyze_stock](../../app/intelligence/shared_brain_application.py) | IMPLEMENTED: Resolves/assembles stored evidence and composes same SharedBrain production snapshot/comparability wrappers; does not call runner/score/setup/gates. |
| DECISION_SCORE | [build_scorecard](../../app/scoring/engine.py) | IMPLEMENTED: Existing component and eligibility rules; rejected/cross-version inputs cannot become zero-score evidence. |
| TRUST_ENVELOPE | [decision_trust_envelope_from_shared_brain](../../app/intelligence/decision_trust_envelope.py) | IMPLEMENTED: Copies compatible persisted Brain/score/setup/gates/thesis into UI-safe read model, not another score authority. |
| SETUP_THESIS_INVALIDATION | [CanonicalSetupOpportunity.from_assessment](../../app/production_v1/canonical_setup_activation.py) | CONTEXT_SPECIFIC: Approved Pre-Breakout structural candidate plus separate holding thesis/invalidation; no universal archetype setup. |

Rule 24 reuse is the existing **reported revenue YoY** diagnostic; its label must not be stretched into a new earnings-acceleration calculation. Rule 27 uses reported order book, inflow and revenue with its existing applicability/insufficiency rules; it does not establish a universal capex strategy. Router predicates reuse result tokens; this audit approves no new thresholds, accounting definitions or corporate-type assumptions.

The existing [OpportunityArchetypeRouter](../../app/intelligence/opportunity_archetypes.py) maps Rule 6 leadership, Rule 24 acceleration, Rule 27 growth, Rule 26 margin, risk and verified external exposure into Watch archetypes. It is distinct from the exact fourteen-funnel registry. There is no permission to make every archetype executable: only approved Pre-Breakout routes to its setup policy; other routes remain unavailable.

## Cheap discovery versus deep diagnosis

The five adapters validate and copy existing observations, not run heavy research. The runner calls retained-record readers, **not** the registry's textual producer entry points. Top3 source runs may independently perform governed setup assessments before discovery; the adapter only consumes them. Research sources may independently perform bounded research; their adapters do not promote results.

Missing Momentum/Earnings/Orderbook/News emitters should reuse existing diagnostic/source states under explicit trigger/freshness policy. “Reuse” does not authorize rerunning all61 for every raw security in every funnel, duplicating scores, inventing confidence, or treating a lightweight hit as final qualification.

## Candidate contract and union

[CanonicalDiscoveryLead](../../app/intelligence/multi_funnel_discovery.py) retains exact instrument, funnel/version, explicit UTC `discovery_as_of`, source layer, trigger codes, readiness, quality, immutable reference ID/fingerprint/kind/known-at lineage, horizons where present, optional issuer/parent and blockers. Lead identity and content fingerprint are reproducible.

No distinct detection timestamp, universal expiry, materiality/confidence scalar, resolved strategy-policy authorization or portfolio relevance is invented. Universe identity/checksum/membership belong to the master batch; an isolated lead alone does not prove whole-universe coverage. Freshness remains source-defined; future exclusion is **not** proof that any arbitrarily old observation is fresh.

[union_discovery_candidates](../../app/intelligence/multi_funnel_candidate_union.py):

- groups by exact canonical security/ISIN, not fuzzy symbols or issuer alone;
- retains all surviving origins, trigger evidence, horizon lineage and blockers;
- collapses exact replay with explicit counts; rejects conflicting identity/fingerprint and future evidence;
- keeps different securities of one issuer separate;
- sorts deterministically by canonical identity, **does not rank**;
- exposes `distinct_funnel_count` descriptively: no score, vote, suppression or priority bonus.

The runner rejects conflicting source fingerprints before calling adapters. A future consumer must preserve that guard, not rely on input-order source selection inside an isolated adapter. Sector ranking reference lineage currently carries the Top3 run fingerprint; it is not an independent native ranking fingerprint. Verify source-native provenance at the handoff rather than repairing historical receipts.

Contract readiness: **ready for isolated deterministic union; runtime handoff adapter missing**. Source storage-knownness is also the injected reader's responsibility.

## Existing Radar-to-61 bridge: reuse, not replacement

The bridge is synchronous, bounded (100 input leads by default), read-only and non-executable. It requires exact active registry family/version, explicit supported horizon, security/cutoff-matched `AssembledStockEvidence` and verified technical input. Registry admission permits OPERATIONAL Pre-Breakout/Sector Rotation entries; the documented proven end-to-end Radar path is Pre-Breakout. The three research families are **not** silently eligible.

Critical limits:

1. `evaluate_leads` deduplicates by **lead ID**, not security. Forwarding every origin can diagnose one security twice. The future handoff must define one canonical inspection identity per security/cutoff/approved context while retaining all origins.
2. Its technical evidence is **current-descriptive READY, strict-historical-PIT NOT_READY**. A timestamp is not universal historical admissibility.
3. `assemble_for_radar` has no concrete production port found. This is not a reason to build a new evidence system.
4. The bridge calls `Canonical61DiagnosticRunner.run(evidence)` without the optional governance argument. Production typed approval/selection/result lineage must be explicitly bound; do not claim that the bridge already persists authorized production diagnostics.
5. Rule/horizon applicability and source insufficiency remain visible. A discovery horizon is not an approved economic scenario duration.

## Downstream path reconciliation

| Transition / stage | State relative to candidate union | Existing entry point and evidence |
| --- | --- | --- |
| EVIDENCE_ASSEMBLY | ADAPTER_MISSING | [StockDiagnosticInputAssembler.assemble](../../app/universe_analysis/service.py): Existing assembler available; concrete CanonicalRadarEvidenceAssembler port and union/security/context binding absent. |
| CANONICAL_61 | IMPLEMENTED_NOT_WIRED | [Canonical61DiagnosticRunner.run](../../app/universe_analysis/service.py): Synchronous exact61 DiagnosticRun with COMPLETE/PARTIAL/UNAVAILABLE; per-rule missing/error fail-closed. Runner does not persist. Governance authorization optional parameter, explicit production binding required. |
| RESEARCH_COMPARABILITY | IMPLEMENTED_NOT_WIRED | [SharedBrainApplicationService.analyze_stock](../../app/intelligence/shared_brain_application.py): Stored canonical evidence to same production Brain/comparability; not invoked by union. |
| DECISION_SCORE | IMPLEMENTED_NOT_WIRED | [build_scorecard](../../app/scoring/engine.py): Existing universe jobs call it after runner; exact-five portfolio activator persists canonical scores; neither consumes union. |
| DECISION_TRUST_ENVELOPE | IMPLEMENTED_NOT_WIRED | [decision_trust_envelope_from_shared_brain](../../app/intelligence/decision_trust_envelope.py): Existing stock query projection; no union binding. |
| SETUP_PREPARATION | CONTEXT_SPECIFIC | [Top3OpportunityFinderService.run](../../app/production_v1/top3_opportunity_finder.py): Stored-sector constituent and portfolio Pre-Breakout paths; source opportunities precede funnel adapters. Not automatically after every score. |
| SIX_GATES | CONTEXT_SPECIFIC | [CanonicalPortfolioSixGatesActivator](../../app/portfolio/canonical_six_gates_activation.py): Existing governed input/evaluation path restricted to portfolio-five; universe service has its own injected gate-input path using same engine. No union path; V2 not active. |
| PORTFOLIO_ROTATION | CONTEXT_SPECIFIC | [PortfolioUniverseRotationService.evaluate](../../app/universe_analysis/service.py): Snapshot/candidate/strategy/score/gate/economic comparability required; score or multi-hit count is not rotation approval. |
| WATCH_SIGNAL | IMPLEMENTED_NOT_WIRED | [MarketWideWatchService._record](../../app/intelligence/market_wide_watch.py): Stored diagnostic/score/setup/gate/external evidence projected through existing Router, not candidate union. |
| HSI_SIGNAL | IMPLEMENTED_NOT_WIRED | [project_watch_to_hsi_signal](../../app/intelligence/hsi_signal_projection.py): Pure P1C Watch + P1B policy resolution; WATCH_ONLY/NON_EXECUTABLE; not live /signals and not funnel union. |
| SELL_SIDE | CONTEXT_SPECIFIC | [evaluate_portfolio_sell_side_action](../../app/portfolio/sell_side_runtime.py): Existing holding policy classification; no new broker authority, no multi-funnel call. |

### Canonical diagnosis and Score

`Canonical61DiagnosticRunner.run` returns one `DiagnosticRun`, all61 registry-ordered evaluations and COMPLETE/PARTIAL/UNAVAILABLE accounting. Missing/error evidence remains insufficient. Its input assembler uses canonical identity, explicit as-of, matching optional financial/technical/benchmark wrappers and PointInTimeGuard. Runner itself has no persistence; existing controlled universe jobs and typed portfolio orchestration own their respective storage paths.

The independent `UniverseAnalysisService.run_next_batch` calls the same runner, then `build_scorecard` and gate evaluation, and stores analysis/candidates. It is **not instantiated by the multi-funnel runner**. Exact-five portfolio activators also reuse core machinery, but their population limits must not be silently expanded.

Score is **ten governed components**, not equal weighting of all61. Mandatory rule requirements are 24, 1, 2, 7, 6, 10, 11, 12, 29+45, and 8 respectively; optional subsets remain in `COMPONENTS`. Some diagnostic rules are not score inputs. Missing mandatory evidence makes a component INELIGIBLE and final score `None / SCORE_INCOMPLETE`; missing optional evidence remains PARTIAL. `classify_score_input` excludes unavailable/unverified/cross-version states; the legacy state-score dictionary's insufficient token is not permission to turn missing evidence into zero. No funnel ID or hit count enters Score.

### Setup, Trust Envelope and Six Gates

Canonical Pre-Breakout opportunity retains approved assessment/policy lineage. Trust Envelope exposes trigger entry, structural stop/invalidation, measured-move **T1**, reference R:R and maximum executable-entry boundary. **T2 and extended target are null.** Opportunity horizon is `NOT_GOVERNED_FOR_SETUP_OPPORTUNITY`; portfolio thesis is separate holding analytics. Catalyst context is not a fabricated setup field.

Existing setup materialization is sector/portfolio-context driven, not a universal automatic consequence of a score. Current adapters consume setup upstream, so the intended logical authority graph must not be implemented as a cyclic regeneration loop.

Six Gates use the existing engine and governed source/score/setup/action context. Missing input factory, current setup, action context, registry/version/PIT or source evidence remains unresolved/insufficient; no gate passage from a discovery hit. Active policy remains V1. Current typed portfolio activator and independent universe-service gate input paths are context-specific. No claim of Execution Gate V2 runtime activation or broker authority is made.

### Portfolio, Watch and signals

`PortfolioUniverseRotationService.evaluate` requires its immutable job/universe/portfolio relationship and comparable qualified candidates before the canonical rotation engine. Existing sell-side policy classification may describe HOLD, EXIT_TO_CASH, ROTATE, REVIEW_REQUIRED or NO_ACTION; this audit creates none. TRIM is not authorized here, HARVEST is not added to that runtime, and a high score or unknown cash cannot supply capital authority.

Market-Wide Watch reads existing diagnostics, canonical scores/gates, setup and verified external evidence, then routes archetypes. Its challenger queue is `CHALLENGER_WATCH_ONLY`, actual rotation-candidate count is explicitly zero; `UNSCORED_NOT_WEAK` is preserved. It does not compute missing full diagnosis or promote a challenger into rotation.

P1C `project_watch_to_hsi_signal` verifies one immutable Watch and P1B registry provenance; outputs remain WATCH_ONLY/NON_EXECUTABLE. Canonical detection/horizon/direction are unavailable when the Watch lacks them. This is not the legacy `/signals` endpoint and has no union origins to project.

## Frontend/API and scheduling

| Surface | Projection class | Funnel provenance | Actual capability |
| --- | --- | --- | --- |
| Market-Wide Watch API and Production Watch page | PARTIAL_PROJECTION | PROVENANCE_MISSING | API maps canonical Watch IDs/fingerprints, diagnostic refs, external evidence, score status/value, setup/gates states and as_of. UI renders archetypes/state/blockers, not the14 source-funnel union/origins. Read returns503 if snapshot unavailable, never launches scan. |
| Stock SharedBrain and Decision Trust Envelope | CANONICAL_PROJECTION | PROVENANCE_MISSING | Canonical stored Brain/score/setup/gate/thesis evidence; public stock APIs expose availability/domain summaries and freshness, not the full private 61-rule inventory or multi-funnel origins. |
| Universe opportunities | PARTIAL_PROJECTION | PROVENANCE_MISSING | Existing universe job opportunity read model; frontend maps symbol/sector/execution/candidate status/warnings but not candidate-union origin lineage. |
| Legacy /signals and paper views | LEGACY_PROJECTION | PROVENANCE_MISSING | Existing SignalQueryService/paper repository route, not P1 HSISignal projection and not union consumer. No new legacy authority authorized. |
| Multi-funnel candidate union / P1 projected signal API/UI | NOT_WIRED | NOT_WIRED | Pure contracts/adapters only; no API, frontend or production runtime caller found. |

Existing UI can display canonical Watch/archetype and evidence references, score/setup/gate state, stock Brain/trust domains, blockers and freshness. It cannot claim fourteen-funnel coverage, union lineage or one completed candidate-to-Brain run. Production UI and Dev Console remain existing projections, not proof of the completed intended product graph.

Exact field coverage: source funnel(s) and candidate-union provenance are NOT_WIRED; diagnosis is availability/domain summary only, not all61 private rule rows. Watch API retains selected rule/artifact references. Score value/status, setup trigger/stop/T1/RR, gate states/outcomes, blockers and as-of/freshness are available through their existing read models. See [stock response schema](../../app/api/schemas/stocks.py) and [read-only stock routes](../../app/api/routes/stocks.py). Neither a UI archetype count nor domain coverage percentage proves all61 evaluation of a funnel candidate.

| Stage | Runtime state | Evidence |
| --- | --- | --- |
| whole-universe acquisition/scanning and cadence | NOT_IMPLEMENTED | No app/api, app/runtime, scripts, tools, frontend caller of orchestrate_whole_market_discovery found. Explicit source-reader batch is not scheduled population scan. |
| five adapter execution + canonical union | IMPLEMENTED_NOT_WIRED | Pure bounded orchestrator; all14 receipts and five source bindings, no runtime/store reader configured. |
| candidate-to-61 evidence assembly | ADAPTER_MISSING | Radar bridge exists; concrete assemble_for_radar port/union consumer absent. |
| independent existing runtime materialization | CONTEXT_SPECIFIC | app/runtime/cli.py provides portfolio diagnostics, sector/Top3 and materialize-market-wide-watch operations; no new scheduler and none executed here. |
| stored output query projections | WIRED_AND_OPERATIONAL | app/api/main.py/dependencies.py wire existing stored read services; not proof new multi-funnel chain has run. |

No cadence, queue, worker or page-load scan is introduced. Existing manual/runtime materializers and stored query services are neither erased nor relabeled as the new whole-market scheduler.

## Actual and intended graphs

Frozen intended logical authority flow:

```text
whole eligible NSE -> 14 discovery funnels -> canonical security union
  -> inspection candidates -> SAME BRAIN -> 61 diagnosis -> Decision Score
  -> setup / thesis / invalidation -> Six Gates
  -> portfolio / rotation / signals / Watch / sell -> API / UI
```

Actual repository edges (statuses are code capability, not live validation):

| From | To | Edge state | Qualification |
| --- | --- | --- | --- |
| retained canonical sources | Brain intelligence primitives | OPERATIONAL | Canonical existing evidence/primitives; actual completeness not measured |
| retained governed setup/Top3 | two active adapters | OPERATIONAL | Conditional pure call only; source produced independently |
| three retained research receipts | three research adapters | SHADOW | Research inspection only |
| remaining nine registry entries | canonical emitted leads | MISSING | No bound adapter; explicit unavailable receipts, not nine absent intelligences |
| five adapters | canonical candidate union | OPERATIONAL | Within pure caller-invoked batch |
| candidate union | same Brain inspection | MISSING | No runtime consumer |
| individual admitted lead + injected assembler | canonical61 via Radar | IMPLEMENTED_NOT_WIRED | Per-lead bridge, not union path |
| existing universe job | canonical61 -> score -> gates -> stored analysis | OPERATIONAL | Independent bounded service requires sources/governance; not union |
| stored canonical artifacts | SharedBrain -> TrustEnvelope / MarketWatch -> Router | OPERATIONAL | Read/composition not computation |
| stored approved assessment | PreBreakout setup opportunity | OPERATIONAL | Existing controlled sector/portfolio path, before source adapter |
| new multi-funnel score | new setup/gates | MISSING | No such materialized score/handoff |
| existing comparable holding/candidate context | rotation and sell-side classifiers | OPERATIONAL | Context-specific evidence only; no new execution authority |
| existing stored query models | API/UI | OPERATIONAL | No funnel-origin projection |
| union provenance | API/UI | MISSING | Existing Watch provenance is not union provenance |
| holding/watchlist/regime context | unconditional whole-NSE security scanner | NOT_APPLICABLE | No silent contextual scope expansion |
| MarketWatch | P1 HSISignal | IMPLEMENTED_NOT_WIRED | Pure projector not HTTP /signals |

**Delta:** discovery terminates at a correctly deduplicated handoff. Independent canonical services already cover most downstream computation/projections, but no shared binding carries this union into them or back out with complete funnel provenance.

No parallel final decision Brain, duplicate funnel score or funnel-specific trade authority was found in the inspected path. Independent services call the same core engines. Per-lead repeated diagnosis, setup-before-discovery ordering and lost native provenance are **future integration hazards**, not evidence that a second production Brain already exists.

## Missing work, kept separate

- **Genuinely missing qualified intelligence/policy:** Emerging Compounder; Valuation Recovery. Common five-family readiness/quality-valuation support exists and must not be rebuilt or mislabeled as qualified policy.
- **Existing intelligence with governed trigger/adapter/shared-wiring work:** Momentum, Pre-Breakout, Earnings Acceleration, Orderbook/Capex, Sector Rotation, News/Catalyst. Only Pre-Breakout and Sector currently have operational-source adapters; the other four still need explicit predicate/freshness governance, not merely a cable.
- **Research/promotion:** Compounder, Fundamental Inflection, Policy Transmission. Existing adapters emit research inspection, including policy-definition-missing receipts, not qualification.
- **Contextual:** Holding State Change, Watchlist State Change, Market Dislocation. News/Policy are event/exposure-conditioned, not unconditional scans.
- **Provider/source versus wiring:** OHLCV/benchmark/peer readiness; comparable official financial periods and company types; filing known-at/timezone; exact exposure and freshness; complete supplied-universe/constituent provenance are independent source limitations. No provider availability was sampled. None can be “fixed” by invoking Brain or inventing data.

The registry's Sector adapter-missing blocker is stale relative to actual code. This audit preserves and records it; it does not edit the registry.

## Priority and preserved Gate-1 child

First freeze the shared security-union handoff contract, reusing Radar/Canonical61/SharedBrain and existing stores/readers. Resolve context/horizon/PIT/native lineage and one-security inspection identity **before** wiring. A separately authorized bounded integration can follow, then existing-intelligence emitters, research promotion, genuinely missing policy, and canonical UI provenance. These are priority recommendations, not initiated slices.

Pending `NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1` remains **PENDING_NOT_STARTED**, retaining predecessor decision `SESSION_PRICE_SOURCE_APPLICABILITY_SOURCE_GAPS`. Schedule it **after one shared handoff-contract slice**. It is independent research-source work, not a prerequisite for descriptive union, and its historical/price authority gaps remain fully binding. No CAS recovery, horizon or bootstrap work is started or closed here.

## Validation and single frozen continuation

Conformance tests verify exact registry/matrix, source pins, preserved Gate-1 artifacts/authority, prohibited bypasses, code call boundaries, per-security union provenance, downstream/UI/scheduler truth, descriptive metadata drift and exactly one next continuation. Relevant existing discovery/Radar/Watch/P1/Brain/Score/setup/governance tests run offline. Full backend is **not required** because no shared/runtime behavior changes. Edited-document link/table/whitespace checks and `git diff --check` are required before commit.

Completed validation: **261 focused passed**; **791 relevant passed / 2 deprecation warnings**. No failures or skips in either run. Relevant warnings concern Starlette/httpx and the AnyIO BlockingPortal alias. No full-suite result is claimed. The four-file change set is this audit Markdown/JSON, its conformance test and one README index link; application code and historical artifacts remain unchanged.

Exactly one next frozen continuation:

**`CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1`**

Document and machine-verify one immutable security-union-to-existing Radar/Canonical61/SharedBrain handoff contract. Reuse existing components; specify one inspection identity per canonical security/cutoff/approved context, all origins, concrete read-only assembler requirements, current-descriptive versus strict PIT admission, policy/version lineage and downstream artifact boundaries. Do not implement runtime wiring, activate research, infer horizons or start CAS recovery in that slice.

**Not started.** No push, runtime integration, funnel promotion, new authority or production mutation is part of this checkpoint.
