# Gate 1 Rotation Research Horizon Authority Policy V1

## Decision and governance

`AUDIT_CLOSED_WITH_POLICY_BLOCKERS / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE`

**Decision C — `NEW_HORIZON_AUTHORITY_POLICY_REQUIRED`.** The audit is closed; numeric horizon authority is not. For a historical `ROTATE_IN`, no inspected existing authority can responsibly decide the common incumbent/challenger comparison horizon. A new independently approved and registered research-horizon policy is required. This document records necessary requirements, not that registration or an approved duration.

Baseline: `c75dc4f2b7ab3182ca3ff3541b7a83fb6fce1123`, branch `main`. Canonical machine artifact: [horizon authority audit](GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json). Conformance witnesses: [offline tests](../../tests/unit/test_gate1_rotation_research_horizon_authority_policy.py).

A is rejected because no approved numeric paired policy exists. B is rejected because categorical labels and a candidate applicability policy do not provide a sufficient approved economic basis for a mechanical mapping: purpose, unit, counting, terminal rules and duration still need policy. D is not the primary conclusion: historical coverage gaps exist, but do not prevent identifying the required authority boundary. No policy is manufactured to advance the roadmap.

This is one bounded slice. No cohort, label, calibration, model, resolver, registration, runtime wiring, portfolio/DB mutation or live authority is created. No downstream continuation is started.

## Accepted chain and scope of evidence

| Predecessor | Exact fingerprint |
| --- | --- |
| [docs/architecture/GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json) | `sha256:b45af9573b36d727619f630aad5990ba44ff9a7f84c4d9a489a602b6c950a7dd` |
| [docs/architecture/GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json) | `sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3` |
| [docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | `sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14` |

All historical artifacts remain immutable. The [composite V2 approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2.json) is not activated. `six-gates-production-v1 / v1` remains **ACTIVE**; Execution Gate V2 remains **NOT_ACTIVE**. Gate-1 V1, Gates 2–6, Decision Score, TradePlan, independent score/economic hurdles, common parcel/capital/method/INR and one-time friction accounting remain unchanged.

Evidence is a repository-source audit, not a new production database capture. Source pins are LF-normalized SHA256 of 108 inspected baseline files in the JSON. They include the inherited preservation set and the additional horizon owners. An artifact fingerprint verifies content, never registration, policy approval or historical source completeness.

## Horizon distinctions

| Concept | Purpose | Relationship |
| --- | --- | --- |
| RESEARCH_COMPARISON | Observe both future realized wealth legs over one D-bound period. | Requires new research authority; not linked by default to other windows. |
| LIVE_ECONOMIC_SCENARIO | Future estimates compare same parcel/capital/method/INR over a common period. | Eventual conceptual alignment subject to separate production scope/approval; NOT_ACTIVE. |
| SIGNAL_EXPIRY | Validity lifetime of a detected setup/signal. | Separate; no automatic derivation. |
| ACTUAL_HOLDING | Elapsed or realized time in position, affected by exits. | Separate; cannot select future research duration using outcome. |
| CALIBRATION_FORWARD_WINDOW | Statistical observation or partition methodology. | Separate until independently approved joint research design; no convenience alias. |

Temporal intervals, bar resolution, risk restrictions and realized holding duration must not be conflated merely because each uses the word horizon. No implicit derivation is approved.

## Existing horizon-concept inventory

The identifier column names actual contracts or fields. Where a field has no independent policy version, the baseline source pin is explicitly used as audit identity, **not** invented runtime authority. All entries retain their native authority; rejecting them as paired-horizon selectors does not mark working Core capabilities unavailable.

| Concept / owner | Identifier or version | Purpose / representation | Native authority | Paired use / exclusion reason |
| --- | --- | --- | --- | --- |
| `B09` — [docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json) | fundamental V2 approval / activation_blockers[B09] | Versioned V2 diagnostic applicability, entity-branch compatibility; blocking activation. — BLOCKER_NOT_A_DURATION | BLOCKING GOVERNANCE; not a comparison-horizon policy | EXCLUDED_AS_AUTHORITY: Cannot turn an open applicability blocker into numeric ROTATE_IN authority. |
| `RULE_HORIZON_CANDIDATE` — [docs/architecture/RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json) | rule-horizon-timeframe-applicability-policy / v1-candidate | 61-rule horizon/timeframe applicability proposal — SHORT_TERM / POSITIONAL / LONG_TERM; duration boundaries UNSET | CANDIDATE_NOT_ACTIVE | CONTEXT_ONLY: 15m/30m/1H/4H/1D/1W/1M are bar timeframes, not holding durations. |
| `WATCH_ARCHETYPE` — [app/intelligence/market_wide_watch.py](../../app/intelligence/market_wide_watch.py) | MarketWideWatchRecord + OpportunityArchetypeRouter; version pinned in Watch | Detection/routing and current setup provenance — ARCHETYPE / ROUTING_STATE | Implemented descriptive routing, not numeric authority | CONTEXT_ONLY: Current valid setup does not define paired future wealth period. |
| `RADAR_HORIZON` — [app/intelligence/radar_diagnostic_orchestration.py](../../app/intelligence/radar_diagnostic_orchestration.py) | CanonicalDiagnosticHorizon / RuleHorizonApplicabilityState; baseline source pin | Map eligible discovery context to diagnostic request — SHORT_TERM / POSITIONAL / LONG_TERM; applicability POLICY_UNSET | Implemented context validation; applicability unset | CONTEXT_ONLY: Accepted contextual mapping is not activation or duration resolution. |
| `STRATEGY_HANDOFF` — [app/strategies/pre_breakout/research_handoff.py](../../app/strategies/pre_breakout/research_handoff.py) | StrategyCandidate.horizon + ResearchHandoff.horizon; baseline source pin | Strategy research handoff — String PRE_BREAKOUT in existing producer | Descriptive strategy label | CONTEXT_ONLY: No number, unit, endpoint, approval or paired mapping. |
| `TACTICAL_POSITIONAL` — [docs/architecture/POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md](POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md) | Approved product-scope catalogue; STRATEGY_POLICIES_NOT_APPROVED / NOT_ACTIVE | Separate strategy windows and product taxonomy — Qualitative tactical / positional / long-term | Product scope only except existing Pre-Breakout policy availability | CONTEXT_ONLY: A universal duration or midpoint would invent economics and erase strategy distinctions. |
| `P1_SIGNAL` — [app/intelligence/hsi_signal_projection.py](../../app/intelligence/hsi_signal_projection.py) | HSISignal P1 projection; baseline source pin | Watch-only canonical provenance projection — horizon=null / UNAVAILABLE; no approved expiry | Implemented non-executable projection | CONTEXT_ONLY: Cannot fill absent horizon from runtime time, signal creation or expiry. |
| `SIGNAL_EXPIRY` — [app/signals/engine.py](../../app/signals/engine.py) | SignalConfig.version / expiry_sessions | Signal revalidation and expiry — Optional configured sessions; expires when native count > expiry_sessions | Native signal-lifecycle authority only | EXCLUDED_AS_AUTHORITY: Expiry is permission-to-remain-valid, not paired economic observation period; preserve strict >. |
| `TRADEPLAN` — [app/signals/models.py](../../app/signals/models.py) | TradePlan.time_horizon / expiry_condition | Stored plan description — Optional strings | No verified duration-selector authority | EXCLUDED_AS_AUTHORITY: A plan field or existing execution-oriented name supplies neither approval nor a numeric comparison policy. |
| `TARGET_STOP` — [app/strategies/common/models.py](../../app/strategies/common/models.py) | StrategyCandidate.trigger / structural_stop / realistic_target | Price-structure setup boundaries — Price/event boundaries, not duration | Existing setup semantics only | EXCLUDED_AS_AUTHORITY: Future stop/target hit or executable fill cannot choose start, end or holding duration. |
| `CANONICAL_SETUP` — [app/production_v1/canonical_setup_activation.py](../../app/production_v1/canonical_setup_activation.py) | CanonicalSetupOpportunity.time_horizon_status | Immutable approved Pre-Breakout setup provenance — NOT_GOVERNED_FOR_SETUP_OPPORTUNITY | Governed setup, explicitly no horizon authority | CONTEXT_ONLY: Approved setup policy is not approved research horizon. |
| `PAPER_WINDOWS` — [app/paper/models.py](../../app/paper/models.py) | PaperTradingConfig setup_expiry_sessions / time_stop_sessions; config version | Single-instrument simulated admission/holding lifecycle — Optional explicit session counts | Native paper simulation only | EXCLUDED_AS_AUTHORITY: Engine uses native > expiry/time-stop; do not borrow its values or alter counting. |
| `FORWARD_PAPER` — [app/forward_paper/models.py](../../app/forward_paper/models.py) | PaperStudyAdmission.time_stop_sessions + setup policy fingerprint | Prospective paper observation lifecycle — Positive configured session count | Native paper-study authority only | EXCLUDED_AS_AUTHORITY: Service uses native >= waiting/holding comparison. Runtime setup builder deliberately has no default; not a paired policy. |
| `WALK_FORWARD` — [app/backtest/walk_forward.py](../../app/backtest/walk_forward.py) | WalkForwardPlan / StrategyCandidate frozen version refs | Train/validation/test/step/purge/embargo partitions — Explicit session configuration | Implemented research-partition governance | EXCLUDED_AS_AUTHORITY: Partition length is not per-event forward wealth horizon. |
| `CALIBRATION_WINDOW` — [app/calibration/service.py](../../app/calibration/service.py) | OutcomeSample.horizon / CalibrationObservation.horizon | Measurement grouping of supplied outcomes — Optional caller string | Descriptive grouping | EXCLUDED_AS_AUTHORITY: Cannot select period after returns, or turn a label into D-time authority. |
| `OOS_DIAGNOSTIC_WINDOW` — [app/self_improvement/models.py](../../app/self_improvement/models.py) | DiagnosticRuleSet.short_horizon_sessions / version | Post-outcome attribution/diagnostic research window — Configured session count | Research attribution only | EXCLUDED_AS_AUTHORITY: Not an independent approved incumbent/challenger horizon. |
| `PORTFOLIO_REVIEW` — [app/portfolio/holding_intelligence.py](../../app/portfolio/holding_intelligence.py) | Holding intelligence composition; baseline source pin | Read-only thesis/status review at supplied cutoff — Review as-of, not a future duration | Implemented intelligence composition | CONTEXT_ONLY: Review cutoff can identify D only when exactly the original event cutoff, never replace it. |
| `HOLDING_STATISTICS` — [app/rotation/models.py](../../app/rotation/models.py) | RotationHoldingState.holding_sessions / known_at / as_of_timestamp | Elapsed incumbent holding descriptive state — Optional observed count | Descriptive past duration | EXCLUDED_AS_AUTHORITY: Past elapsed holding is not future continuation; average duration would be a new policy. |
| `ROTATION_COOLDOWN` — [app/rotation/engine.py](../../app/rotation/engine.py) | RotationConfig.cooldown_days / config_version | Anti-churn rotation eligibility — Optional calendar-day cooldown | Existing eligibility only | EXCLUDED_AS_AUTHORITY: A backward-looking cooldown cannot supply either leg's forward horizon. |
| `CATALYST_EVENT` — [app/intelligence/catalysts/service.py](../../app/intelligence/catalysts/service.py) | CatalystEvent.expected_time_horizon / evidence_ids | Event expected impact timing — Optional string | Descriptive evidence, not policy | CONTEXT_ONLY: Event date or asserted impact lag cannot become numeric duration without explicit governed mapping. |
| `MACRO_SECTOR_LAG` — [app/intelligence/sector_economics/service.py](../../app/intelligence/sector_economics/service.py) | SectorSensitivity.lag / SectorEconomicImpact.time_horizon / profile.version | Macro-to-sector transmission lag — Optional source/profile string | Descriptive transmission context | CONTEXT_ONLY: No legal basis for economic horizon from narrative lag. |
| `LONG_TERM_THESIS` — [app/intelligence/long_term_thesis_review.py](../../app/intelligence/long_term_thesis_review.py) | long-term-thesis-review/v1; invalidation research-shadow companion | Five-family dossier lineage and readiness — Family enum; review cadence undefined where no governed policy | Implemented immutable readiness; no universal duration | CONTEXT_ONLY: LONG_TERM label and milestone cadence are not paired terminal-time selection. |
| `COMPOUNDER_BUSINESS_WINDOW` — [app/intelligence/compounder_prospective_shadow_validation.py](../../app/intelligence/compounder_prospective_shadow_validation.py) | BusinessOutcomeHorizon / prospective contract source pin | Prospective business-outcome readiness — ONE_YEAR / THREE_YEARS / FIVE_YEARS | Implemented research readiness, not realized market-economic authority | EXCLUDED_AS_AUTHORITY: All horizons initially IMMATURE; MARKET_OUTCOME_NOT_READY. Do not choose one or convert business years to trading sessions. |
| `DISCOVERY_RECALL_WINDOW` — [app/intelligence/discovery_recall_reference_matching.py](../../app/intelligence/discovery_recall_reference_matching.py) | ReferenceOpportunitySpecification.outcome_horizon_semantics_id / ReferenceEventTimeObservation | Independent discovery recall outcome/deadline methodology — Categorical family plus explicit observed endpoints | Implemented research matching only | EXCLUDED_AS_AUTHORITY: Outcome matching and same-category routing do not approve Gate1 comparison duration. |
| `MARKET_EXTREMES_FORWARD` — [app/crisis/models.py](../../app/crisis/models.py) | ForwardOutcomeReference.horizon_sessions / methodology_version | Market-extreme forward outcome reference — Supplied integer sessions | Descriptive outcome linkage | EXCLUDED_AS_AUTHORITY: No independent paired selection/effective approval. |
| `GATE6_BLACKOUT` — [app/gates/engine.py](../../app/gates/engine.py) | GateConfig.blackout_sessions / earnings blackout V2 governance | Pre-earnings restriction — V1 configured sessions; V2 value/unit/precision unset | Existing V1 gate active; V2 blackout policy unset | EXCLUDED_AS_AUTHORITY: Pre-event restriction, not post-D wealth period; earnings local B09 is not fundamental B09. |
| `ECONOMIC_RESEARCH_CONTRACT` — [docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | gate1-rotation-economic-scenario/v1 + paired protocol/v1 | Same-horizon future paired research/economics requirements — Common explicit start/end required, number/unit UNSET | Accepted non-active governance contract, not a registered producer | REQUIREMENTS_ONLY: start_at_decision already binds start=D; no numeric selector exists. |
| `SESSION_CALENDAR` — [app/historical/canonical_market_session_event_time.py](../../app/historical/canonical_market_session_event_time.py) | canonical-market-session-calendar-and-event-time / v1 | First-party factual NSE days, phases and event-time resolution — Dates/timestamps, explicit trading-day states | Factual session authority, not horizon policy | SUPPORTING_SOURCE_ONLY: No duration selector or guaranteed historical/instrument trading coverage; UNKNOWN when sources absent. |

### Decision-time and historical qualifications

In this table, **conditional closure** means deterministic only for exact retained inputs; historical PIT and replay must be proved per original event/version rather than inferred from today's working implementation. Availability of a source file is not availability of its historical runtime value.

| Concept | Available at original D? | Deterministic / PIT / replay | Strategy-specific? |
| --- | --- | --- | --- |
| B09 | OPEN; no resolved V2-compatible authority | DOCUMENT_DETERMINISTIC / NO_RESOLVED_DECISION_RESULT / ARTIFACT_REPLAY_ONLY | Rule/entity dependent |
| RULE_HORIZON_CANDIDATE | CANDIDATE_NOT_ACTIVE | DETERMINISTIC_ARTIFACT / STRICT_HISTORICAL_PIT_NOT_READY / ARTIFACT_REPLAY_ONLY | Rule-specific profiles |
| WATCH_ARCHETYPE | Conditional: exact original Watch known by D | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Yes, archetype |
| RADAR_HORIZON | Conditional: exact retained lead/cutoff | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Lead horizon compatibility |
| STRATEGY_HANDOFF | Conditional: original candidate/scan_as_of | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | PRE_BREAKOUT |
| TACTICAL_POSITIONAL | Scope document exists, individual duration policy absent | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Yes; preserve differences |
| P1_SIGNAL | Watch as-of is available, detection time distinct unavailable | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Source Watch only |
| SIGNAL_EXPIRY | Conditional: exact original configuration | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Signal configuration |
| TRADEPLAN | Conditional on original plan closure | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Plan-specific |
| TARGET_STOP | Conditional on original candidate | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Strategy-specific |
| CANONICAL_SETUP | Exact setup provenance may exist; numeric horizon absent | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Pre-Breakout |
| PAPER_WINDOWS | Only if original config was retained | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Study/config-specific |
| FORWARD_PAPER | Original admission input; absent setup time-stop remains blocked | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Governed study input |
| WALK_FORWARD | Plan/selection must predate evaluation use | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Strategy family / experiment |
| CALIBRATION_WINDOW | Only supplied retained label; outcome itself is future | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Measurement family |
| OOS_DIAGNOSTIC_WINDOW | Original ruleset may be pinned; diagnostics often ex post | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Ruleset/experiment |
| PORTFOLIO_REVIEW | Conditional on retained composition evidence | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Holding context |
| HOLDING_STATISTICS | Conditional: known_at <= D | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Incumbent-specific |
| ROTATION_COOLDOWN | Conditional: exact config and last rotation at D | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Rotation context |
| CATALYST_EVENT | Conditional on event/publication/retrieval closure | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Company/event |
| MACRO_SECTOR_LAG | Conditional; as_of object alone is not PIT proof | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Sector/driver |
| LONG_TERM_THESIS | Dossier/evidence explicit as-of | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Five separate families |
| COMPOUNDER_BUSINESS_WINDOW | Plan can be retained at D; future facts remain immature | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Fundamental Compounder |
| DISCOVERY_RECALL_WINDOW | Depends on frozen specification; forward outcome is not D-feature | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Short catalyst / positional market / long business |
| MARKET_EXTREMES_FORWARD | Methodology may preexist; realized event outcome cannot be D-feature | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Extreme-event study |
| GATE6_BLACKOUT | Conditional on original calendar/earnings/config | CONDITIONAL_ON_EXACT_RETAINED_INPUTS / CONDITIONAL_NOT_PROVEN_FOR_EVERY_HISTORICAL_EVENT / CONDITIONAL_ON_RETAINED_VERSION_AND_SOURCE_CLOSURE | Entry/event risk scope |
| ECONOMIC_RESEARCH_CONTRACT | Constraint exists; resolved authority not registered | DETERMINISTIC_CONSTRAINT / CONDITIONAL_INPUT_CLOSURE / CONDITIONAL_NO_ADMITTED_HORIZON | Explicit paired applicability required |
| SESSION_CALENDAR | Only exact first-party schedules/phase evidence visible by D | DETERMINISTIC_INJECTED_SOURCES / PIT_CHECKED_WHEN_COVERED / REPLAYABLE_WITH_EXACT_SOURCE_CLOSURE | Exchange/segment not investment strategy |

For every row: a retained original version must not be mutated after D; later records must be distinct. Caller strings/configuration without original version closure cannot prove that immutability. No row currently supplies future live Gate-1 horizon authority: a separate approved scope and source closure are mandatory. The machine inventory records these two qualifications on each row explicitly.

## B09: exact namespace, authority and limitations

The authoritative reference is [fundamental V2 governance](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json), collection `activation_blockers`, key `blocker_id=B09` (a keyed collection selector, not an array JSON Pointer).

- Topic: **Versioned horizon-policy reference**; resolution **OPEN**; blocking scope **ALL_V2_RUNTIME**.
- It requires an explicit V2-compatible horizon/applicability version with entity-branch awareness. It does not authorize automatic activation or timeframe change.
- Its [frozen candidate](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json) is `rule-horizon-timeframe-applicability-policy / v1-candidate`, `CANDIDATE_NOT_ACTIVE`, pinned `sha256:bc1f7548b372738d69b72c2e54afdc34c9f10929aee9a10d834ce99cb8d43d8a`.
- It supplies SHORT_TERM/POSITIONAL/LONG_TERM applicability categories and bar timeframes. Duration boundaries remain **UNSET**; strict historical PIT is **NOT_READY**.
- Reproducing the candidate document proves immutable content, not a resolved approved decision-time policy.
- `ROTATE_IN` can eventually need B09 as V2 diagnostic-applicability compatibility when that registry is used. It cannot use B09 as a numeric wealth horizon.
- Giving both legs the same category does not establish equal numeric/session endpoints. No valid category-to-session mapping exists in this authority.
- Reinterpreting B09 as duration would change its original semantics.
- Earnings-blackout approval's local B09 (outcome-calibration compatibility) and composite CV24B09 are separately namespaced. They do not close fundamental B09. The composite explicitly separates fundamental compatibility from numeric rotation horizon.

## Required authority rules

These are necessary admission constraints inherited or clarified by this audit, not newly approved parameter values or an implemented validator.

| Rule | Topic | Normative requirement |
| --- | --- | --- |
| HA01 | Independent authority | Admit only an independently registered, approved, versioned horizon policy with exact identity, content fingerprint, selection and effectivity evidence; a number, caller assertion or self-hash is not authority. |
| HA02 | Cutoff | Original decision cutoff D is mandatory. Selection, approval, applicability, routing and decision-input event/known times must be <= D. Research run time R never selects the horizon. |
| HA03 | Effective selection | Use the exact predecessor/native policy validity verifier, including its documented inclusive/exclusive end semantics. No new universal effective-to convention; unavailable convention fails closed. Equal eligible conflicts cannot be selected by input order. |
| HA04 | Start | Resolved start equals original D. The economic contract's start_at_decision is stricter than the paired protocol's D <= start constraint; satisfying both means start=D. Future executable fills, signal detection and next-session timestamps cannot replace D. |
| HA05 | End | Endpoint must be strictly after D, uniquely derived by the approved D-bound unit/mapping/counting/precision/terminal policy and D-visible calendar closure; none are silently supplied here. |
| HA06 | Symmetry | A pair pins one exact full HorizonBinding, reused identically by both legs. Challenger tactical context and incumbent elapsed holding cannot select separate horizons. |
| HA07 | No fallback | No expiry, paper window, actual holding period, calibration window, review cadence, event lag, Gate6 blackout or bar timeframe can automatically provide the duration. |
| HA08 | Mapping | Categorical routing can be evidence only. Without an explicit approved applicability/unit/value/counting mapping emit HORIZON_MAPPING_POLICY_REQUIRED, not a guessed duration or midpoint. |
| HA09 | Strategy scope | A future authority must name supported strategy/archetype/routing/signal/instrument/state scope and same-horizon suitability for both legs. Unsupported or missing original routing fails closed. No universal horizon is approved. |
| HA10 | Historical versions | Pin original policy ID/version/fingerprint, input closure, D and resolution. Later policy versions/corrections cannot rewrite existing observations or reselect after outcomes; retain immutable successors with distinct lineage. |
| HA11 | Multi-horizon | Current protocol requires one selected bound horizon per paired observation. No numeric grid/fan-out is authorized here. Any future multiple-observation design must freeze all horizon selections and grouping/splits before forward outcomes; never choose the best realized result. |
| HA12 | Maturity | Only after R >= exact endpoint, canonical terminal session/phase completion proof known by R, and eligible outcome evidence known by R may the predecessor admit a label. Missing exact terminal evidence remains pending/unresolved/excluded with null label, never zero-return fallback. |
| HA13 | Research separation | Research-only approval must be explicitly scoped. Conceptual common-horizon consistency with future live economics is desirable, but registration for research cannot activate V2 or grant scenario/producer/broker authority. |
| HA14 | Integrity | Validate raw source identities/fingerprints with their native schemes before normalization. Reject tampering and conflicting lineage; retain exact duplicate aliases once under predecessor receipts, not as multiple authorities. |
| HA15 | Administrative replay | A later frozen replay run/receipt may exist only under predecessor administrative-metadata rules; it cannot backdate approval, supply future decision features, mint an original portfolio event or repair missing horizon authority. |
| HA16 | No arbitrary staleness | No new TTL is invented. Check exact policy validity, revocation, supersession and source freshness as of D under approved rules; undefined/ambiguous validity cannot become authority. |

### Selection time and version semantics

D is the exact original comparison decision cutoff. At D, the chosen policy identity/version, approval, selection, applicability, strategy/routing and all decision evidence must be fixed and independently verifiable. Approval and known-at and selection event/known-at checks are inclusive at D. Effective-to boundaries must use the actual canonical policy's documented verifier; this audit does not introduce an inclusive or exclusive expiry convention.

Multiple effective records cannot be chosen by arbitrary input order. A unique result requires a governed selection rule with exact provenance; identical repeated source records follow predecessor alias/receipt semantics once, while conflicting same-ID/version records reject. No present-day “latest” lookup, later version, revocation discovery or calibration result rewrites the original resolution.

Later frozen replay administrative metadata is distinct from D-time evidence. It cannot make a policy approved after D historically approved, or fabricate an original portfolio event. The original event/pair/parcel and source closure requirements from the predecessor still apply.

### Start boundary: already constrained

The economic contract explicitly requires `start_at_decision`. The paired protocol requires `D <= start < end`. Their intersection is **start = D**, with end strictly after D. This reconciles—not edits—the predecessors.

The next valid market session, later executable price/fill, signal detection time or a different review cutoff is rejected as a replacement for D. A portfolio-review timestamp can identify D only if it is demonstrably the original comparison's D. Start = D is not a claim of an executable fill or available current price: original D-visible capital/price basis remains a separate source requirement.

### Numeric mapping and unit: unresolved

`HORIZON_MAPPING_POLICY_REQUIRED`. No selected policy, numeric duration, range, grid, unit, precision, calendar instance or endpoint is populated.

A future proposal must justify supported routing/instrument/state branches, choice of trading sessions versus calendar days/timestamps, categorical-to-numeric mapping (if used), counting convention, precision, terminal phase, calendar ownership, cutoff selection and evidence/calibration basis. No duration is borrowed from paper studies, business-year windows, signal expiry, Gate6 or average holding statistics. No tactical/positional midpoint or convenient forward window is approved.

A universal horizon can erase distinctions among catalyst, tactical, positional and long-term theses. The audit does not claim a universal horizon is intrinsically impossible; it states that no such mapping or justification is governed here. Any authority must explicitly establish applicability to both the incumbent continuation and originating challenger context.

## Factual calendar support and terminal boundaries

Reuse [canonical market-session calendar and event-time](../../app/historical/canonical_market_session_event_time.py), contract `canonical-market-session-calendar-and-event-time / v1`. It is an implemented immutable, source-injected factual resolver, not a holding-period policy. It accepts explicit as-of and first-party NSE/SEBI source evidence, including annual holidays, weekday conventions, special/Muhurat days and effective phase timings. Missing dates, phases, adjacent sessions or conflicting evidence remain UNKNOWN/unavailable. Date-only publication must follow the existing conservative visibility rule; never fabricate an intraday known-at.

Calendar infrastructure is **DERIVABLE** as a supporting input, not universal historical coverage. An open exchange does not establish that a specific security trades. A simpler weekday-minus-holidays calendar in another subsystem is not an automatic substitute.

| Terminal/session case | Required treatment |
| --- | --- |
| NORMAL_SESSION | Exact approved counting and terminal phase, D-visible calendar and R-visible completion; no implicit close time. |
| WEEKEND_OR_HOLIDAY | Use only approved unit/conversion policy with exact calendar. No naive date addition or automatic next/previous trading day. |
| SPECIAL_OR_HALF_SESSION | Require exact first-party day and applicable phase timing. No generic half-session enum assumed; unrepresented timing fails closed. |
| SUSPENDED_OR_NON_TRADING_INSTRUMENT | Market open does not prove instrument tradability. Preserve horizon; unavailable exact terminal observation excludes label. |
| MISSING_TERMINAL_BAR | Null outcome/unavailable, not nearest future price, carry-forward or zero return. |
| DELISTING | Require exact canonical terminal entitlement/value under separately governed methodology; do not drop delisted losers or invent cash settlement. |
| CORPORATE_ACTION | Existing immutable parcel/adjustment/identity lineage and comparable terminal evidence required; no horizon shortening/extension. |
| EXCHANGE_CLOSURE_OR_OUTAGE | Later unexpected closure cannot rewrite frozen D-bound endpoint. Completion/outcome unresolved or excluded until governed evidence exists; any alternative terminal convention needs separate prospective policy. |

No naive wall-clock date arithmetic where session semantics are required. No assumed regular close, nearest future bar, nearest prior bar, carry-forward price or zero return. Half/special timing is usable only if the exact day and phase can be represented and verified; the existing calendar does not imply a generic half-session economic counting rule.

Unexpected later closures can supply R-time factual completion/availability evidence but must not rebind D's endpoint. In the absence of a separately governed prospective exception policy, the frozen observation stays unresolved/excluded. This deliberately preserves truthful non-maturity rather than silently moving a losing or winning endpoint.

## Symmetry, multiple horizons and maturity

One admitted pair pins **one identical complete horizon resolution**, including policy/selection, original D, routing/input fingerprints, representation, start/end and calendar/endpoint rule provenance. Both legs carry the same fingerprint and exact content. An incumbent's elapsed holding or review cadence cannot produce a different continuation window.

Existing Compounder business-outcome ONE_YEAR/THREE_YEARS/FIVE_YEARS and diagnostic multi-timeframe contexts demonstrate distinct native uses of multiple windows, not Gate1 authorization. No numeric grid or fan-out is authorized here. Any future multi-horizon design must predeclare all selections, identities, multiplicity reporting and original-event grouping/splits before observing returns. No best-return choice, post-loss shortening, post-gain extension or post-calibration relabelling.

Maturity requires `R >= end` **and** exact terminal session/phase completion known by R. Only outcome evidence known by R is label-visible; it cannot enter D's features. Completed session without an eligible terminal observation still cannot yield a complete paired label. OOS consumption also requires predecessor methodology, admission and frozen split rules. Missing/unresolved horizons cannot enter a complete cohort or an OOS result.

## Provenance and content integrity

Reuse predecessor `PolicyRef`, `SourceRef`, `HorizonBinding` and `DecisionSnapshot`; do not introduce a runtime schema or change their wire format. Required future explicit provenance includes:

- `authority_id`
- `authority_version`
- `policy_fingerprint`
- `approval_ref`
- `selection_ref`
- `effectivity_verifier_ref`
- `strategy_routing_refs`
- `instrument_state_refs`
- `input_fingerprints`
- `decision_cutoff`
- `resolved_representation`
- `resolved_start`
- `resolved_terminal`
- `calendar_source_version_refs`
- `endpoint_precision_rule_ref`
- `resolution_fingerprint`

Raw identities and fingerprints must verify under their original schemes before any wrapper or UTC normalization. Preserve source references, exact duplicate aliases and conflicting records; do not “repair” incoming fingerprints.

The predecessor observation identity and HorizonBinding content fingerprint remain unchanged. HorizonBinding hashes its **entire normalized body excluding only its fingerprint**. Any later expanded routing/mapping representation needs an explicitly versioned scheme. A future resolution identity should bind original event/comparison, pair, D, policy version and verified ordered inputs; its exact new wire algorithm is deferred with that future policy. It must not consume its own content fingerprint, runtime/research time or outcomes. A content hash is tamper evidence, not an authority signature.

## Fail-closed outcomes

These are audit conformance reason codes, **not new runtime enums**. Each prevents admission as complete and leaves its label null; retain reasons/evidence through predecessor rejection/pending/exclusion conventions. When multiple conditions apply retain them in the machine artifact's deterministic listed order; do not let reporting precedence imply eligibility.

| Code | Condition | Readiness |
| --- | --- | --- |
| HORIZON_AUTHORITY_MISSING | No independently verified horizon authority | AUTHORITY_NOT_REGISTERED |
| HORIZON_AUTHORITY_CONFLICTED | Multiple distinct eligible authorities/selections without a governed unique selector | BLOCKED |
| HORIZON_MAPPING_POLICY_REQUIRED | Category exists but approved numeric/session mapping absent | POLICY_REQUIRED |
| HORIZON_STRATEGY_UNSUPPORTED | Strategy/archetype/signal/instrument/state outside explicit applicability | BLOCKED |
| HORIZON_ROUTING_UNAVAILABLE | Required exact decision-time routing closure missing | SOURCE_NOT_READY |
| HORIZON_POLICY_STALE | Native D-time validity/revocation rule rejects policy; no new TTL | BLOCKED |
| HORIZON_POLICY_VERSION_INVALID | ID/version/fingerprint/approval/selection inconsistent | BLOCKED |
| HORIZON_EFFECTIVITY_UNVERIFIABLE | Validity boundary semantics or original approval/effectivity proof missing | POLICY_REQUIRED |
| HORIZON_CALENDAR_UNRESOLVED | Exact D-visible calendar/segment/phases insufficient or conflicted | SOURCE_NOT_READY |
| HORIZON_INPUT_AFTER_CUTOFF | Approval/selection/routing/decision input event or known time after D | BLOCKED |
| HORIZON_INPUT_TAMPERED | Source lineage cannot verify under original scheme | BLOCKED |
| HORIZON_START_MISMATCH | Start not original D | BLOCKED |
| HORIZON_PAIR_MISMATCH | Incumbent and challenger bindings differ | BLOCKED |
| HORIZON_MULTI_SELECTION_UNGOVERNED | Multiple horizons without predeclared approved design | POLICY_REQUIRED |
| HORIZON_TERMINAL_UNAVAILABLE | Exact terminal session/bar/instrument/adjustment lineage unavailable | SOURCE_NOT_READY |
| HORIZON_NOT_MATURE | R before endpoint or canonical completion not yet proved | BLOCKED |

A stale policy means native as-of validity, not an invented TTL. Unknown temporal convention is unverifiable. Future approval or selection, even if accompanied by a genuine content hash, remains after-cutoff evidence.

## Readiness matrix

READY below labels an established **structural constraint only**, never an operational policy or observation. DERIVABLE means reusable mechanism conditional on exact inputs; it does not imply historical data exists.

| Component | State | Evidence / limitation |
| --- | --- | --- |
| B09_AVAILABILITY | POLICY_REQUIRED | Fundamental V2 B09 is OPEN; candidate exists, not a resolved V2 applicability policy. |
| B09_AUTHORITY | BLOCKED | B09 never provides numeric comparison authority; preserve its original V2 blocker. |
| STRATEGY_ROUTING | DERIVABLE | Exact original Watch/lead/setup routing may be reusable as inputs only; require D-time closure. |
| CATEGORICAL_HORIZON | DERIVABLE | Existing categories are contextual. P1 projection specifically leaves horizon unavailable. |
| NUMERIC_HORIZON | POLICY_UNSET | No approved duration, range, grid or universal value for the paired comparison. |
| CATEGORY_MAPPING | POLICY_REQUIRED | HORIZON_MAPPING_POLICY_REQUIRED; category-to-duration is not arithmetic derivation. |
| DECISION_CUTOFF_BINDING | READY | Structural requirement only: original D mandatory; selection and source closure D-bound, no live admission claimed. |
| SESSION_CALENDAR | DERIVABLE | Source-injected factual calendar exists; exact D-visible coverage, segment and phases must be verified per observation. |
| START_BOUNDARY | READY | Structural requirement only: start=D inherited from economic contract; no next-fill or next-session substitution. |
| END_BOUNDARY | POLICY_REQUIRED | Unit, precision, counting, terminal phase and non-tradable exception rules absent. |
| MULTI_HORIZON | POLICY_REQUIRED | No Gate1 fan-out/grid authorization. Single bound result per admitted pair; any future multi-study design must be predeclared. |
| PAIR_SYMMETRY | READY | Structural requirement only: both legs bind the identical full horizon fingerprint and common D. |
| HISTORICAL_REPLAY | SOURCE_NOT_READY | Mechanism requirements exist; no universal proof of D-visible original horizon, event, parcel or calendar closure. |
| OUTCOME_MATURITY | DERIVABLE | Predecessor maturity contract reusable only after legitimate endpoint and exact completion/known-at proofs exist. |
| POLICY_VERSIONING | DERIVABLE | Reuse immutable identity/fingerprint/effective selection conventions; no horizon registration here. |
| RESEARCH_AUTHORITY | AUTHORITY_NOT_REGISTERED | No approved, registered numeric paired-horizon source found. |
| FUTURE_PRODUCTION_COMPATIBILITY | BLOCKED | Research does not grant live scenario authority or close V2/B09/source blockers. |
| INSTRUMENT_TERMINAL_COVERAGE | SOURCE_NOT_READY | Calendar days do not prove suspension, delisting, corporate-action or exact tradable terminal observations. |

## What closes and what remains

Closed: distinction among horizon concepts; B09 namespace and non-numeric scope; inherited start=D; explicit independent authority, symmetry, cutoff, replay and terminal proof requirements.

Remaining: separate approval/registration; research justification for unit, supported strategy mapping and numeric duration; counting/precision/terminal and instrument-exception policy; exact D-visible calendar and historical origin/input closure; any multi-horizon design; independent future production compatibility. Existing parcel, economics, tax, slippage, methodology and calibration blockers remain unchanged; this audit does not solve them.

Recommended future owner: Gate1 paired-research governance, consuming existing canonical routing and factual calendars. No new Brain/calendar, authority producer or scenario model is installed. Research-only horizon governance must not activate Execution Gate V2. V1 remains ACTIVE; V2 remains NOT_ACTIVE.

## Validation and preservation

Offline conformance tests pin the full artifact and predecessor chain; audit all inventory/readiness rows; verify no numeric parameter or fallback is supplied; exercise synthetic necessary-condition witnesses for exact D, identical paired binding, tampering, future inputs, missing/ambiguous authority, version pinning and terminal maturity. Synthetic test bindings are not real policies, research observations or source receipts and are never persisted. These tests do not implement a resolver or claim sufficiency of a future production authority check.

Focused and relevant regressions, edited Markdown links/tables, whitespace and `git diff --check` must pass before the documentation/test-only commit. No full backend suite is required unless runtime/shared behavior changes. Source pins and final allowed-file diff prove unchanged implementation; no DB read/write or external acquisition is needed.

## Exactly one next frozen continuation

`GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1`

Research and propose the missing independent paired-research horizon authority: strategy compatibility, evidence-backed unit/mapping/counting/terminal conventions, approval/effectivity and historical feasibility. Leave unjustified numeric values unavailable. Do not generate cohorts, labels, models, runtime registration or live authority. **Not started in this slice.**
