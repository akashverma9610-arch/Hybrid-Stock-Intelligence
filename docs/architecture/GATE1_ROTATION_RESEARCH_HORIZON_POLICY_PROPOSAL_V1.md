# Gate 1 Rotation Research Horizon Policy Proposal V1

## Decision and governance identity

`PROPOSED_WITH_UNRESOLVED_PARAMETERS / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE`

**Decision B — `RESEARCH_HORIZON_POLICY_PROPOSAL_READY_WITH_UNRESOLVED_PARAMETERS`.**

Policy: `gate1-rotation-research-horizon-policy / v1-proposed`. Baseline: `328458da03756099dcc9da0d1a5f25cfcd827d22`, branch `main`.

The structure is ready for review, **not complete parameter approval or activation**. Numeric mapping, first-counted-session treatment, terminal/precision conventions, historical source closure and independent authority remain unresolved. No duration is populated.

Canonical [machine-readable proposal](GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.json) and [offline conformance tests](../../tests/unit/test_gate1_rotation_research_horizon_policy_proposal.py) accompany this document. The proposal fingerprint is repository canonical-JSON SHA256 of the complete artifact excluding only `policy_fingerprint`; it is content integrity, not approval.

Proposed owner: HSI paired-research policy governance, with a future deterministic read-only resolver using canonical routing and calendar facts. No owner/producer is registered. Approval reference, approved/effective timestamps and actual resolution remain null; activation is `NOT_ACTIVE`. No legal/RA mandate is inferred.

## Frozen predecessors

| Predecessor | Preserved fingerprint |
| --- | --- |
| [docs/architecture/GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json](GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json) | `sha256:aa9d4b211a5a2aba762c0b31af99b2a87fe08e0963865344104e9b87c33b0bb1` |
| [docs/architecture/GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json) | `sha256:b45af9573b36d727619f630aad5990ba44ff9a7f84c4d9a489a602b6c950a7dd` |
| [docs/architecture/GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json) | `sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3` |
| [docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | `sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14` |

The immediate predecessor remains `NEW_HORIZON_AUTHORITY_POLICY_REQUIRED`. This successor proposes structure, not closure of that authority requirement.

`six-gates-production-v1 / v1` stays **ACTIVE**. Execution Gate V2 stays **NOT_ACTIVE**. B09 remains V2 diagnostic-applicability compatibility, not numeric duration. Start=D, same parcel/capital/method/INR, independent score/economic hurdles and friction-once semantics remain unchanged. Gate-1 V1, Gates 2–6, TradePlan and Decision Score are untouched.

The JSON pins 115 baseline source files including all predecessor pins and newly inspected routing sources. Evidence is repository-only: no new DB capture, production coverage claim, acquisition, empirical study or calibration.

## Scope and exclusions

Only the common research comparison horizon of an authentic paired rotation event: incumbent continuation versus challenger comparison. `ROTATE_IN` is an inherited source-event classification, not an action emitted here. No horizon or action result is created.

Proposed instrument scope: exact-source NSE cash equities for both legs. Actual approved scope rows remain empty until mapping approval establishes strategy/archetype and both instrument/state compatibility. Dataclass default `security_type="EQUITY"`, current membership or ticker spelling is not historical identity proof. No indexes, derivatives, funds or fuzzy substitutions are added.

This is not signal expiry, actual holding duration, TradePlan duration, a generic backtest/calibration window, catalyst timing or long-term thesis horizon. Scope is **RESEARCH_ONLY**. Eventual conceptual live compatibility needs **separate explicit production approval/activation**.

## Proposed decision-time input boundary

Conditional admission does not prove usable historical data exists. Require native verification, exact canonical identity/version, original-event linkage and D-visible source closure; source files and hashes alone do not supply those facts.

| Input / source | Role | Fields / purpose | Admission and PIT/replay |
| --- | --- | --- | --- |
| ORIGINAL_DECISION — [app/rotation/models.py](../../app/rotation/models.py) | CONDITIONALLY_ALLOWED_BINDING | PortfolioRotationEvaluation.evaluation_id / RotationEvaluationContext.as_of_timestamp; exact comparison reference — Freeze original D and pair; never current review time or generated event. | Archive/replay event is authentic under predecessor; exact original comparison/pair/source closure. Original event and source references verified at D; later replay metadata is administrative only. |
| INSTRUMENT_STATE — [app/universe_analysis/models.py](../../app/universe_analysis/models.py) | CONDITIONALLY_ALLOWED_APPLICABILITY | NseEquityInstrument.instrument_id / isin / security_type / exchange / data_as_of / provenance_reference — Confirm exact canonical identities and a supported instrument/venue/state scope. | Both legs have original D-visible identity/type/listing lineage; dataclass defaults are not source proof. Historical master/membership/source version closure required; no today-membership, fuzzy symbol or default EQUITY inference. |
| STRATEGY_PROVENANCE — [app/intelligence/hsi_signal_strategy_registry.py](../../app/intelligence/hsi_signal_strategy_registry.py) | CONDITIONALLY_ALLOWED_APPLICABILITY | WatchStrategyRoutingContext + StrategyRegistryResolution — Exact original strategy ID/version/fingerprint and applicability context; not duration authority. | Use native verification/approval/selection at D. For Pre-Breakout, exact CURRENT_VALID_SETUP routing and policy path still required. No current lookup or claim that other archetypes have executable policies. Horizon policy is independently approved. |
| WATCH_ROUTER — [app/intelligence/opportunity_archetypes.py](../../app/intelligence/opportunity_archetypes.py) | CONDITIONALLY_ALLOWED_APPLICABILITY | OpportunityArchetype / RoutingResult; opportunity-archetype-routing-policy/v1 — Verify existing originating archetype, setup routes and evidence, not assign a numeric horizon. | Exact original Watch/run linkage and full input closure known at D; pure router expects evidence already PIT filtered. Router output alone lacks its own cutoff/known-at envelope. Do not rerun with current data or call latest() without explicit D. |
| CATEGORY_ROUTING — [app/intelligence/multi_funnel_discovery.py](../../app/intelligence/multi_funnel_discovery.py) | CONDITIONALLY_ALLOWED_MAPPING_KEY | CanonicalDiscoveryLead.intended_horizons; multi-funnel-discovery/v1 — Carry a unique already-declared category, never infer it from an archetype name. | Exact lead.verify(), source/funnel version, instrument and original event linkage; every lineage known_at <= D; discovery_as_of <= D. One distinct category required in proposed first scope. A lead existing today does not establish original decision-time availability. |
| SETUP_TYPE — [app/production_v1/canonical_setup_activation.py](../../app/production_v1/canonical_setup_activation.py) | CONDITIONALLY_ALLOWED_APPLICABILITY | CanonicalSetupOpportunity / time_horizon_status — Verify exact originating setup type/policy, not price or time-stop inputs. | Retained canonical setup and its approval/selection closure at D; no new setup calculation. time_horizon_status remains NOT_GOVERNED_FOR_SETUP_OPPORTUNITY; no duration implied. |
| PORTFOLIO_CONTEXT — [app/rotation/models.py](../../app/rotation/models.py) | ORIGIN_ONLY_NOT_DURATION_DRIVER | Original evaluation/comparison IDs and frozen pair references — Bind the authentic research pair only. | Consume already-frozen predecessor origin envelope; do not read current portfolio, allocations or holdings. Elapsed holding, cash, average holding period and review schedule cannot select duration. |
| MARKET_REGIME — [app/intelligence/macro_news_evidence.py](../../app/intelligence/macro_news_evidence.py) | TRACE_ONLY_NOT_DURATION_DRIVER | Canonical stored macro/market evidence references, if original and PIT-verifiable — Preserve optional original context, not a regime-conditioned duration. | Do not admit descriptive text/AI inference as an authoritative routing field. An adaptive regime-to-duration policy has no approved mapping; not included in first proposal's selector. |
| SECTOR_CONTEXT — [app/intelligence/sector_economics/service.py](../../app/intelligence/sector_economics/service.py) | TRACE_ONLY_NOT_DURATION_DRIVER | SectorEconomicImpact / SectorSensitivity.lag / original ranking lineage — Preserve optional original context only. | No free-text lag or current sector ranking can override original category. Typed/canonical source closure is necessary for trace; no sector-dependent horizon mapping approved. |
| CATALYST_EVENT — [app/intelligence/catalysts/service.py](../../app/intelligence/catalysts/service.py) | TRACE_ONLY_NOT_DURATION_DRIVER | CatalystEvent.expected_time_horizon / event and evidence lineage — Preserve FACT/DATA/INTERPRETATION/INFERENCE boundaries and original references only. | No expected lag, narrative, freshness or priced-in inference selects duration. Future event realization and retrospective impact are forbidden selection inputs; event-specific numeric policy deferred. |
| TACTICAL_OR_SHORT_LABEL — [docs/architecture/RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json) | REJECTED_AS_MAPPING_KEY | SHORT_TERM diagnostic candidate versus tactical product prose — Audit vocabulary without inventing a new category or synonym. | No supported DiscoveryHorizon.SHORT_TERM/TACTICAL route currently exists. B09 candidate is not active; no tactical-to-short-term or bar-timeframe-to-duration conversion. |
| DESCRIPTIVE_OR_FUTURE_VALUES — [app/calibration/service.py](../../app/calibration/service.py) | REJECTED | OutcomeSample.horizon and other unrelated windows identified by predecessor audit — No duration selection. | Reject paper expiry, actual holding duration, outcome windows, unverified strings, self-hashes and AI/user arbitrary values. No future label, best return, later calibration or runtime time may affect D's choice. |

Important distinctions:

- `RoutingResult` is pure classification with caller-filtered PIT inputs, but no independent decision/known-at envelope. Require retained Watch/run and original input closure.
- Existing `MarketWideWatchStore.latest(as_of=None)` uses current time for public reads. Leave it unchanged; horizon research must never invoke implicit-now retrieval or substitute a current Watch.
- P1 HSISignal projection leaves horizon unavailable. Do not repair/populate it here.
- Pre-Breakout approval plus `CURRENT_VALID_SETUP` can establish setup/strategy provenance, never duration. Other native research funnels remain useful without executable policies.
- Portfolio use is limited to the predecessor's frozen origin/pair references, not access to current holdings, quantities or allocation.
- Macro, sector and catalyst context is optional trace only if canonical and D-visible. No descriptive lag, narrative, priced-in interpretation, regime adaptation or numerical news weighting may select duration.

## Existing categories, not invented synonyms

| Category / origin | Semantics / native uses | Historical/strategy qualification | Mapping status |
| --- | --- | --- | --- |
| POSITIONAL — [app/intelligence/multi_funnel_discovery.py](../../app/intelligence/multi_funnel_discovery.py) | DiscoveryHorizon.POSITIONAL; exact CanonicalDiscoveryLead.intended_horizons. Existing positional inspection/routing context; no economic duration. Pre-Breakout and sector adapters emit this category. Inflection and policy-transmission adapters may emit it alongside LONG_TERM. | Conditional on original lead and full source closure; no retrospective reconstruction. UNSET; actual mapping rows must name exact supported strategy/archetype/policy refs. Native funnel membership does not activate those strategies. | PROPOSED_INTERMEDIATE; no numeric meaning; mapping required |
| LONG_TERM — [app/intelligence/multi_funnel_discovery.py](../../app/intelligence/multi_funnel_discovery.py) | DiscoveryHorizon.LONG_TERM; exact CanonicalDiscoveryLead.intended_horizons. Existing long-term business/research inspection context; no common numeric wealth period. Compounder adapter emits this category. Inflection and policy-transmission adapters may also emit POSITIONAL. | Conditional on original lead and full source closure; business outcome maturity cannot backfill D. UNSET; no long-term family becomes a positive or executable policy through this category. | PROPOSED_INTERMEDIATE; no numeric meaning; mapping required |
| SHORT_TERM — [app/intelligence/radar_diagnostic_orchestration.py](../../app/intelligence/radar_diagnostic_orchestration.py) | CanonicalDiagnosticHorizon.SHORT_TERM and frozen rule-horizon candidate. Existing diagnostic context vocabulary, not an available discovery-lead category or tactical-duration synonym. Radar maps only the existing POSITIONAL and LONG_TERM DiscoveryHorizon values; applicability remains POLICY_UNSET. | Diagnostic context/candidate document is insufficient authority. UNAVAILABLE_IN_FIRST_PROPOSED_SCOPE | NOT_ADMITTED_IN_FIRST_SCOPE; no numeric meaning; mapping required |

First proposed category keys: **POSITIONAL, LONG_TERM**, exactly the existing DiscoveryHorizon values. The broader CanonicalDiagnosticHorizon enum does not add a SHORT_TERM discovery producer. Tactical prose is not a SHORT_TERM synonym; B09 candidate applicability/bar timeframes remain separate.

Native adapters emit POSITIONAL for Pre-Breakout/sector, LONG_TERM for Compounder, and both for Inflection/Policy Transmission. These are source metadata, not horizon approvals. Multiple categories stay ambiguous: no first-item, shortest/longest or best-return selection.

## Numeric duration and empty mapping contract

Numeric problem choice **B: future separately approved mapping table**. Existing values cannot responsibly supply a numeric paired horizon. Table structure can be proposed; rows remain empty.

`HORIZON_MAPPING_POLICY_REQUIRED`. No duration, range, grid or effective unit. No paper count, expiry, average holding, business-outcome year window, blackout, categorical midpoint, forecast or convenient forward-return window is borrowed.

Mapping: `gate1-rotation-research-horizon-category-mapping / v1-proposed`, status `EMPTY_UNAPPROVED_NOT_ACTIVE`. **Rows: empty.** This closed field specification is documentation, not a runtime model or database schema.

| Field | Proposed constraint |
| --- | --- |
| mapping_id | nonempty canonical identifier |
| mapping_version | nonempty immutable version |
| row_id | unique row identity within mapping version |
| category | POSITIONAL \| LONG_TERM, exact canonical origin reference mandatory |
| category_source_contract_ref | nonempty verified source contract ID/version/fingerprint scheme |
| supported_strategy_refs | nonempty ordered exact ID/version/fingerprint references; no wildcard or placeholder executable policy |
| supported_archetypes | nonempty ordered exact current OpportunityArchetype values |
| supported_instrument_state_refs | nonempty ordered canonical applicability references for both legs |
| numeric_duration | null in proposal; positive integer only if TRADING_SESSIONS becomes approved, never a default |
| unit | null until independently approved; conceptual preference TRADING_SESSIONS is not an effective unit |
| counting_rule_ref | null until independently approved; defines first-counted session and partial/special session treatment |
| terminal_rule_ref | null until independently approved; defines phase/boundary and non-tradable exceptions |
| precision_rule_ref | null until independently approved; exact timezone-aware instant representation |
| justification_refs | ordered original methodological/empirical sources with identity/fingerprint and known-at |
| approval_ref | null until independent human policy approval; includes scope and approving authority |
| selection_ref | null until exact historical selection independently verified |
| effective_version | null until approved version is selected; must equal exact mapping_version when resolved |
| effectivity_verifier_ref | null until exact native approval/selection validity semantics are established |
| activation_status | NOT_ACTIVE here; future activation requires separate authorized successor |
| supersedes_ref | optional exact immutable prior version reference; no overwrite |
| fingerprint | content fingerprint of complete normalized row excluding only fingerprint; self-hash is not approval |

Populated fields cannot confer authority. Future effective rows require independent approval/selection, exact scope/validity and methodological evidence. Reject unknown fields, wildcard scopes, placeholder executable policies, boolean counts and default-to-zero conversions.

Match exact category, original strategy/policy/archetype and both instrument/state scopes. Zero effective rows is unavailable; multiple distinct applicable rows conflict. No arbitrary priority or latest-now tie-break. Preserve exact duplicate source aliases once under predecessor receipts; conflicting same-ID/version records fail before category collapse.

## Duration-unit evaluation

| Candidate | Recommendation | Repository rationale | Unresolved |
| --- | --- | --- | --- |
| TRADING_SESSIONS | PREFERRED_CONCEPT_ONLY | Both comparable market outcomes require canonical session/phase evidence; factual calendar already distinguishes trading and non-trading days. | No approved number, first-counted-session rule, partial/special-session weight, terminal phase or instrument-exception rule. |
| CALENDAR_DAYS | NOT_SELECTED | Represents elapsed calendar dates, including non-trading days; not equivalent to market opportunity. | Would need separate strategy justification and explicit tradable-terminal rule; cannot borrow cooldown days. |
| ELAPSED_TIMESTAMP_DURATION | NOT_SELECTED | Represents elapsed time, not trading-session exposure. | Would require independent rationale, timezone/precision and terminal market alignment; no simple timedeltas or nearest-price default. |

**Trading sessions are the conceptual preference, not an effective unit.** They align comparable market observations with canonical session/day/phase infrastructure. Calendar days and elapsed time represent different exposures requiring independent justification. Ease of implementation is not evidence.

Partial decision-session counting, special/half-session counting, terminal phase and precision all remain null. No hidden count or weighting convention is selected.

## Start and end-boundary proposal

**Start = exactly D**, inherited from the economic contract. No next-session, later fill, next close or arbitrary bar replaces it. Missing D-visible executable-price/capital alignment is a separate blocker, not permission to move D.

Conditional structure, not an implemented or approved duration algorithm:

> If an independently approved mapping supplies N trading sessions and an approved counting/terminal policy, form the unique ordered eligible terminal sequence from D-visible canonical calendar/phase evidence under that policy. End is its Nth terminal, strictly after D.

N is symbolic, not a supplied number. No first-counted-session rule, partial/special weight, phase, precision or endpoint is approved. Missing prerequisites prevent resolution. The adjacent-session helper's native behavior is not automatically economic counting policy.

| Case | Proposed treatment |
| --- | --- |
| NORMAL_TRADING_SESSION | Use exact selected phase/precision and frozen approved count convention; missing rule prevents resolution. |
| HOLIDAY | Not a trading session in a future session-count policy; exact first-party D-visible schedule required. No calendar-day duration silently rolled. |
| WEEKEND | Use source-derived weekday and special-day resolution, not hard-coded Monday-Friday arithmetic. |
| SPECIAL_OR_HALF_SESSION | Use exact first-party day/phase; whether/how counted remains POLICY_REQUIRED. No unit weight or normal close invented. |
| SUSPENDED_INSTRUMENT | Exchange session does not prove security tradability. Freeze common end; retain missing exact instrument outcome as unavailable/excluded. |
| MISSING_BAR | No nearest later/prior bar, carry-forward or zero return. No complete label. |
| DELISTING | Require governed terminal entitlement/value and canonical identity lineage under predecessor wealth methodology, otherwise excluded without dropping the originating event. |
| CORPORATE_ACTION | Preserve horizon; require canonical comparable parcel/adjustment lineage for each leg, no endpoint change. |
| CLOSURE_OR_OUTAGE | Later unexpected closure cannot rewrite frozen D-selected endpoint. Missing completion remains unresolved/pending or excluded; no data-driven extension. |

No naive weekday arithmetic or automatic non-trading-date roll. Unexpected closure learned after D cannot rewrite D's endpoint. No nearest prior/future bar, carry-forward, invented settlement or zero return. Preserve delisted/suspended origin events and missingness; do not remove inconvenient outcomes.

## Calendar authority audit

Supporting capability **DERIVABLE**; historical coverage **SOURCE_NOT_READY**.

Reuse [CanonicalMarketSessionCalendar](../../app/historical/canonical_market_session_event_time.py), `canonical-market-session-calendar-and-event-time/v1`, NSE/CAPITAL_MARKET, Asia/Kolkata. Existing methods: `resolve_trading_day`, `phases_for`, `adjacent_trading_session`.

Pin calendar ID, source-set fingerprint, contract version, coverage and individual holiday/weekday/special/phase source references. Do not invent a mutable calendar-version field.

- Explicit as-of and injected first-party evidence; no runtime fetch.
- Visibility follows existing known-at, otherwise exact published-at, otherwise date-only publication strictly before D's local date. No fabricated intraday visibility.
- Native calendar convention/phase date boundaries are inclusive at defined ends. Do not import this as unrelated horizon-approval interval semantics.
- Unknown/out-of-coverage/conflicting days or missing phases are unavailable; adjacency stops at UNKNOWN.
- Regular/special/Muhurat results are factual days, not approved special-session economic weights.
- No general governed N-session economic resolver, universal historical coverage or security-specific tradability/terminal-price proof exists in this calendar.

It is a suitable conditional factual resolver, not the duration authority. An open exchange does not establish that a particular instrument trades.

## Pair symmetry and immutable provenance

Both legs must share one complete immutable binding with:

- `horizon_policy_id`
- `horizon_policy_version`
- `policy_fingerprint`
- `approval_selection_effectivity_refs`
- `original_event_comparison_and_pair_refs`
- `decision_cutoff`
- `routing_source_refs_and_fingerprints`
- `selected_category`
- `mapping_id_version_row_fingerprint`
- `numeric_duration_if_approved`
- `unit_if_approved`
- `counting_terminal_precision_refs`
- `resolved_start`
- `resolved_end`
- `calendar_contract_id_calendar_id_and_fingerprint`
- `calendar_source_refs`
- `resolution_fingerprint`

No leg-specific category, duration, counting rule, endpoint or calendar. Verify full normalized content and fingerprint, not just a category or number/unit.

Preserve predecessor PolicyRef, SourceRef, HorizonBinding and DecisionSnapshot wire contracts. Added mapping/category provenance requires an explicitly versioned future wrapper; do not edit old hash inputs or omit new semantics from the fingerprint. Current binding is null.

Verify raw source fingerprints under native schemes before UTC/ordered-reference normalization. Content hashes cover the full body excluding only their own digest. Identity and integrity remain distinct/non-circular; no future outcomes or research runtime choose either. A hash or caller assertion never establishes policy authority.

## Multi-horizon and conflict rules

Proposed first version: **EXACTLY_ONE_CANONICAL_HORIZON_PER_PAIR**. No separate-observation fan-out or numeric grid. Multiple applicable categories remain unresolved until separately governed selection/multi-observation design exists. A future design must freeze all choices and original-event grouping/splits before forward outcomes.

No majority of duplicates, lexical order, current strategy, shortest/longest interval or favorable return resolves a conflict. Exact aliases count once; conflicting versions/lineage reject. No new precedence between disagreeing strategy and archetype is invented.

Ordered proposal conformance codes below are reporting precedence only. Retain every applicable reason; the first cannot override another blocker. They are not installed runtime enums.

- `SOURCE_TAMPERED`
- `INPUT_AFTER_CUTOFF`
- `POLICY_AUTHORITY_UNAVAILABLE`
- `ROUTING_SOURCE_MISSING`
- `ROUTING_SOURCE_CONFLICT`
- `CATEGORY_UNSUPPORTED`
- `CATEGORY_AMBIGUOUS`
- `STRATEGY_CATEGORY_CONFLICT`
- `HORIZON_MAPPING_POLICY_REQUIRED`
- `MAPPING_AMBIGUOUS`
- `MAPPING_VERSION_INVALID`
- `CALENDAR_UNRESOLVED`
- `END_BOUNDARY_POLICY_REQUIRED`
- `TERMINAL_OBSERVATION_UNAVAILABLE`
- `PENDING_MATURITY`

Missing policy, source, mapping or calendar means no complete admission and null label. Descriptive or unsupported categories are not substitutes.

## Research maturity and PIT replay

Reuse predecessor maturity/admission unchanged:

- Unresolved horizon: inadmissible/unresolved, no complete observation or guessed waiting duration.
- Valid frozen horizon before end: `PENDING_MATURITY`.
- R at/after end: require exact canonical session/phase completion known by R and eligible outcome evidence known by R.
- Completed session without exact terminal evidence still cannot yield a complete label.
- No outcome enters D's selection. OOS also requires predecessor frozen methodology/splits/admission.

Pin original event/pair, D, policy/mapping/routing versions, source/approval/effectivity fingerprints, category, duration/unit if approved, counting/terminal/calendar closure and both boundaries. Later policies are immutable successors, never historical rewrites.

**Approval after original D cannot authorize a past observation under the frozen protocol.** Later replay administration is not D-time approval. Prospective applicability or separately authorized governance is a genuine prerequisite; no retrospective exception is introduced.

## Evidence before numeric mapping approval

No empirical support or sample-size sufficiency is claimed here. Candidate values/grids must be independently justified; no sample, lookback, purge, embargo, significance or performance threshold is invented.

| ID | Evidence class | Minimum requirement | Repository basis |
| --- | --- | --- | --- |
| ME01 | Exact strategy-specific research question and existing governed horizon definition if any | Separate planned comparison period from exit/expiry and business-fact observation. Establish relevance to both legs, not only the challenger. | [docs/architecture/GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json](GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json) |
| ME02 | PIT-safe original setup/event cohorts and historical identities with calendar coverage | Original cutoff/features/version closure, non-survivor inclusion, revisions, conflicts and missingness accounted for. Bars alone are insufficient. This slice generates no cohort. | [docs/architecture/GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json) |
| ME03 | Predeclared strategy-specific duration/counting hypotheses and independent test design | No retrospective best-return duration. Any candidate values/grid and reporting multiplicity need separate evidence justification and approval; none supplied here. | [app/backtest/walk_forward.py](../../app/backtest/walk_forward.py) |
| ME04 | Walk-forward/OOS evidence, maturity and overlap controls | Frozen train/validation/test separation, leakage/overlap treatment, held-out review and sensitivity/stability across relevant regimes; no sample, purge or embargo number invented. | [docs/architecture/GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json) |
| ME05 | Paired economic relevance and uncertainty/missing-data audit | Same parcel/capital/horizon/method/INR; realized paired evidence and frictions separated. Single-leg win rate, self-improvement window or average holding duration is not sufficient. | [docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) |
| ME06 | Independent authorized policy review and exact approval/selection provenance | Record reviewer/authority/scope, evidence fingerprint and effective version. RA approval only where separately established as applicable; this proposal makes no new legal requirement. Approval is not performance proof. | [app/intelligence/hsi_signal_strategy_registry.py](../../app/intelligence/hsi_signal_strategy_registry.py) |

Historical bars alone cannot establish original decision/strategy provenance, independent duration choice or economic suitability. Post hoc best returns, average holding periods and single-leg paper outcomes likewise do not confer authority.

Human policy approval is distinct from a user-entered arbitrary duration. RA-approved policy is relevant only where applicable authority has separately been established; no new legal assertion or performance guarantee is made.

## Policy readiness

READY means exact proposal identity or inherited structural invariant, never activation/coverage.

| Component | State | Evidence / limitation |
| --- | --- | --- |
| POLICY_IDENTITY | READY | Proposal identity/version and content scheme defined, not registered authority. |
| SCOPE | POLICY_PROPOSED | Research-only paired comparison; no implicit production or holding-period scope. |
| ALLOWED_DECISION_INPUTS | POLICY_PROPOSED | Closed roles, original D/source verification mandatory; no duration drivers from descriptive/future data. |
| ROUTING_SOURCE | DERIVABLE | Existing Watch/lead/strategy provenance reusable only with exact original event closure. |
| CATEGORICAL_SOURCE | DERIVABLE | POSITIONAL/LONG_TERM already exist; multi-category ambiguity fails closed; SHORT_TERM not admitted. |
| NUMERIC_DURATION | POLICY_UNSET | No numeric duration, range, average or grid supplied. |
| DURATION_UNIT | POLICY_PROPOSED | TRADING_SESSIONS is conceptual preference; effective unit remains null pending counting/terminal policy. |
| CATEGORY_MAPPING | POLICY_REQUIRED | Future versioned table structure proposed; rows empty; HORIZON_MAPPING_POLICY_REQUIRED. |
| DECISION_BINDING | READY | Inherited structural constraint: original D mandatory, selection inputs all D-visible. |
| START_BOUNDARY | READY | Inherited start exactly D, not next session/fill/close. |
| END_BOUNDARY_CONVENTION | POLICY_REQUIRED | Counting origin, phase, precision and security/closure exception rules unresolved. |
| CALENDAR_AUTHORITY | DERIVABLE | Existing factual resolver is suitable supporting capability; not a general economic N-session counting policy. |
| PAIR_SYMMETRY | READY | One complete immutable resolution and fingerprint shared by both legs. |
| MULTI_HORIZON | POLICY_PROPOSED | Exactly one selected category and bound horizon; no fan-out/grid authorized. |
| MATURITY_INTEGRATION | DERIVABLE | Reuse exact endpoint plus canonical completion/known-at proof; no labels generated. |
| PIT_REPLAY | SOURCE_NOT_READY | Original event/lead/approval/mapping/calendar closure not proved for historical pairs. |
| CONFLICT_PRECEDENCE | POLICY_PROPOSED | Reject conflicting applicable source categories/versions; no arbitrary winner or fallback. |
| PRODUCTION_COMPATIBILITY | BLOCKED | Future compatibility possible only with independent live governance/activation; no authority inherited. |
| ACTIVATION_AUTHORITY | AUTHORITY_NOT_REGISTERED | No approval, effective time or registry registration created. |
| CALENDAR_HISTORY | SOURCE_NOT_READY | No new historical coverage capture; exact D-visible schedules/phases and instrument terminal evidence still required. |

Closed: dedicated identity/scope, input roles/category distinctions, empty mapping shape, conceptual unit comparison and symmetry/conflict/maturity proposal.

Remaining: numeric evidence/approval; first/partial/special-session counting; terminal phase/precision/exceptions; historical original event/routing/calendar closure; no retrospective approval; instrument/capital-price alignment; unregistered research authority; separate live compatibility. Other predecessor parcel, economics, tax, friction and calibration blockers remain unchanged.

## Validation and boundary

Tests verify artifact and predecessor fingerprints, source pins, explicit unresolved values, input/category rejection, cutoff/mapping/calendar/conflict failure, symmetry, no historical rewrite, maturity and absence of authority/runtime changes. Synthetic conformance witnesses stay in tests: no economic duration resolver, real observation or registration.

Run focused/relevant regressions, edited Markdown links/tables/whitespace, source pins and `git diff --check` before commit. Full backend is required only if runtime/shared behavior changes; none is proposed. Changes are restricted to this document, its JSON, focused tests and README. No DB, portfolio, broker/order, API/UI, provider, model or Gate-1 integration.

## Exactly one next frozen continuation

`GATE1_ROTATION_RESEARCH_HORIZON_MAPPING_EVIDENCE_FEASIBILITY_V1`

Audit actual source/methodology feasibility for future mapping values and counting/terminal conventions, including original decision-time authority and historical versus prospective applicability. Keep unsupported values unset. No cohort/label generation, calibration, producer registration or activation. **Not started in this slice.**
