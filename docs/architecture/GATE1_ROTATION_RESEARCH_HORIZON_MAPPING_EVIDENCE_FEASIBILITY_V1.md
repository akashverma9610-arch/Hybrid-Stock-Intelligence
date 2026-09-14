# Gate 1 Research Horizon Mapping Evidence Feasibility V1

Status: `AUDIT_COMPLETE / GOVERNANCE_AND_TESTS_ONLY / RESEARCH_MAPPING_BLOCKED / NOT_ACTIVE`

Slice: `GATE1_ROTATION_RESEARCH_HORIZON_MAPPING_EVIDENCE_FEASIBILITY_V1`

Baseline: `e2b5336bc17788d859dec1f0d3202c2134bbd0c2` on `main`. The audit is **ACCEPTED/CLOSED**; this closes the feasibility question, not the blocked horizon research or product roadmap.

Decision **D — `HORIZON_MAPPING_BOOTSTRAP_BLOCKED`**.

No genuine archived paired rotation origins or mature paired outcomes were found in the canonical stores inspected, and no independently approved numeric horizon mapping exists in the pinned governance chain. Outcomes needing a prebound horizon cannot supply their own initial horizon. Calendar and endpoint gaps independently prevent complete replay. Tooling and descriptive windows do not close this structural bootstrap.

## 1. Authority and scope

The [machine-readable audit](GATE1_ROTATION_RESEARCH_HORIZON_MAPPING_EVIDENCE_FEASIBILITY_V1.json) carries the complete per-source inventory, temporal metadata capture, readiness matrices and 125 LF-normalized source pins. Its content fingerprint covers every field except `artifact_fingerprint`, using the existing canonical JSON convention. It is an integrity checksum, not policy approval, execution authority or a whole-database checksum.

The [horizon proposal](GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.md) remains research-only, unapproved, unregistered and not active. [Authority audit](GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.md), [paired protocol](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.md), [scenario feasibility](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.md) and [economic contract](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.md) remain immutable.

| Artifact | Retained fingerprint |
| --- | --- |
| [GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.json](GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.json) | sha256:090b3a017060f88c04e76dbd9bd69cd9f00fcbdadbea27faac23ca746b2b5864 |
| [GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json](GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1.json) | sha256:aa9d4b211a5a2aba762c0b31af99b2a87fe08e0963865344104e9b87c33b0bb1 |
| [GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json) | sha256:b45af9573b36d727619f630aad5990ba44ff9a7f84c4d9a489a602b6c950a7dd |
| [GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json) | sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3 |
| [GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14 |

`six-gates-production-v1 / v1` remains **ACTIVE**. Proposed `execution-gate-policy-v2-proposed / v2-proposal.4` remains **NOT_ACTIVE**. The independent research-horizon owner is not registered. No RA/governance artifact inspected supplies an approved numeric duration; existence of versioned governance tooling does not supply one.

No application, database, policy selection, portfolio, score, TradePlan, gate, broker/order, data-acquisition or execution behavior changes. No observations, labels, backtests, calibration or scenario economics are run. This report does not approve a seed, method, unit, duration, sample threshold or counting convention.

## 2. Read-only evidence capture and limitations

Count capture: **2026-09-14T17:32:36.916818+00:00**, `data/nse_stock_manager.db`, SQLite URI `mode=ro` plus `query_only`, one read transaction rolled back and closed. Supplementary metadata captures: 2026-09-14T17:38:41.698894+00:00 and 2026-09-14T17:39:17.381212+00:00; these are separate transactions and are not presented as one atomic snapshot.

| Canonical evidence | Observed count / result |
| --- | --- |
| Historical bars / bar conflicts | 2,663,799 / 795 |
| Portfolio rotation evaluations / comparisons / historical rotation evaluations | 0 / 0 / 0 |
| Historical portfolio gate evaluations / backtest portfolio states / paper and signal replay references | All 0 |
| Backtest runs / events / historical manifests / partitions / memberships | All 0 |
| Paper trades / outcomes / performance reports | All 0 |
| Walk-forward plans / runs / window results / aggregates | All 0 |
| Automated research runs / cycle results / future OOS executions / candidate OOS records | All 0 |
| Forward-paper run snapshots | 3; all have admitted=0, entries=0, exits=0, sessions_processed=0 |
| Decision/outcome links | 43; all 43 inspected are SELL_SIDE_DECISION_EVENT, not paired realized outcomes |
| Watch / compounder prospective / inflection prospective snapshots | 12 / 2 / 18; not authentic paired rotation observations |
| NSE security master / NSE session-identity snapshot-family rows | 120,821 / 61,850; heterogeneous records, not dates or distinct trading sessions |
| Security lifecycle / corporate-action / universe-membership snapshot-family rows | 1,340 / 3,886 / 762; not complete PIT interval coverage |
| Canonical quote snapshots | 1; count is not exact-D price coverage |

All relevant counts are retained individually in JSON. A bounded 1,000-bar unordered sample was entirely `1D`, `RAW`, `unknown_existing_source`, with date labels spanning 2023-08-21T18:30Z to 2026-08-21T18:30Z. This is **not** the full dataset date range, a representative sample, strict PIT certification, calibration or proof of absence of other providers/timeframes.

Whitelisted metadata only was exported. Sample master receipts include a 2026-09-11 report first observed 2026-09-13; the date alone cannot confer earlier intraday knowledge. Sample session-point identities retain `KNOWN_FOR_SESSION_D` with `historical_known_at=null`: their approved date-level semantics remain intact, without upgrading to intraday knowledge or a complete calendar. Sample compiled delisting evidence was observed in 2026 with historical-known-at unavailable. Sample action records have historical effective dates, later `as_of`, and missing announcement dates.

One optional latest-row ordered inspection hit its four-second query safety deadline and rolled back. The cheaper bounded unordered inspection succeeded. No latest-row or full historical completeness conclusion is drawn from that sample. Queries did not modify production data; this is not a claim that a hash of the entire 18 GB database was captured or that another process could not change state.

Empty canonical stores demonstrate no eligible origins through the inspected paths. They do not prove that no human ever made a decision or that an undisclosed external archive does not exist. Raw private portfolio data, tokens, prices and credential payloads are not included.

## 3. Evidence classes and authority limits

| Class | Definition | May / may not authorize |
| --- | --- | --- |
| CANONICAL_POLICY_EVIDENCE | Immutable approved version/effectivity within its native scope; current chain supplies structural constraints, not numeric values. | Only its explicitly approved scope; no transitive numeric authority. |
| EMPIRICAL_CALIBRATION_EVIDENCE | Genuine origins and mature outcomes under independently predeclared methodology, PIT and held-out validation. | May justify a future proposal after governance; never self-approve. No qualifying paired dataset found. |
| BACKTEST_ONLY_EVIDENCE | Replayed/simulated outcomes with archived strategy, source and fold provenance. | Research input only; cannot manufacture original decisions or choose a horizon from its own test outcomes. |
| DESCRIPTIVE_ONLY | Labels, technical bar sizes, realized holding periods, operational timers and other-purpose study windows. | Context only, no Gate-1 mapping authorization. |
| INSUFFICIENT | Missing origins, parameters, sample provenance or outcome completeness. | Retain explicit gap; no numeric mapping. |
| INCOMPATIBLE | Different economic purpose, category, venue, return basis or native boundary convention. | Exclude from direct substitution; no convenient window alias. |
| PIT_UNSAFE | Future/unknown selection-time knowledge, unversioned source, later membership or outcome leakage. | Reject from D-time selection; later terminal observation is admitted only under frozen R-time label rules. |

No class automatically authorizes a mapping. In particular, many raw bars, a convenient paper time-stop, realized holding-period median or backtest fold size are not an approved Gate-1 horizon.

## 4. Candidate source inventory

The complete JSON inventory records canonical owner, semantic purpose, numeric presence, class, PIT/replay, sample provenance, calibration validity, category compatibility and suitability for **each** row. Sources are exact existing modules; they are inspected, not changed.

| ID / source | Owner and purpose | Numeric meaning | Evidence class / suitability |
| --- | --- | --- | --- |
| GOVERNANCE_CHAIN: [docs/architecture/GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.json](../../docs/architecture/GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1.json) | Paired-research governance: D, symmetry, empty mapping and independent authority | None; numeric parameters explicitly unset | CANONICAL_POLICY_EVIDENCE: Not suitable for numeric mapping |
| PRE_BREAKOUT: [app/intelligence/hsi_signal_strategy_registry.py](../../app/intelligence/hsi_signal_strategy_registry.py) | Canonical Pre-Breakout governance: Exact CURRENT_VALID_SETUP and approved policy provenance | Policy/setup exists; no paired numeric holding duration | DESCRIPTIVE_ONLY: Available strategy is not available horizon |
| DISCOVERY: [app/intelligence/multi_funnel_discovery_adapters.py](../../app/intelligence/multi_funnel_discovery_adapters.py) | Multi-funnel canonical discovery: POSITIONAL/LONG_TERM categorical intended horizons | No numeric duration | DESCRIPTIVE_ONLY: Category provenance only; ambiguous category fails closed |
| WATCH_ROUTER: [app/intelligence/opportunity_archetypes.py](../../app/intelligence/opportunity_archetypes.py) | Market-Wide Watch and OpportunityArchetypeRouter: Archetypes, routing outcomes and lifecycle | No numeric paired duration | DESCRIPTIVE_ONLY: Reuse provenance only |
| SETUP: [app/production_v1/canonical_setup_activation.py](../../app/production_v1/canonical_setup_activation.py) | Canonical setup activation: Setup readiness; NOT_GOVERNED_FOR_SETUP_OPPORTUNITY time-horizon status | No governed opportunity duration | INSUFFICIENT: Cannot supply a missing numeric horizon |
| PAPER: [app/paper/engine.py](../../app/paper/engine.py) | Paper lifecycle: Optional setup-expiry and time-stop session limits; exit events | Configured operational numbers possible, not horizon authority | INCOMPATIBLE: No direct import of paper window |
| FORWARD_PAPER: [app/forward_paper/service.py](../../app/forward_paper/service.py) | Forward-paper study: Governed setup, expiry/time-stop, sessions held and outcome aggregation | Explicit study limit possible; no default in governed composition | INSUFFICIENT: Operational health is not empirical evidence |
| PERFORMANCE: [app/performance/models.py](../../app/performance/models.py) | Performance measurement: Holding sessions, MFE/MAE, R excursions and target/stop/time-stop flags | Observed durations/statistics only | DESCRIPTIVE_ONLY: Useful future descriptive measurement only |
| GROUPED_MFE_MAE: [app/performance/grouped.py](../../app/performance/grouped.py) | Grouped performance: Average/median excursions and outcome summaries | Existing summary arithmetic, not approved duration choice | DESCRIPTIVE_ONLY: Cannot infer horizon from best excursion |
| ROTATION_HOLDING: [app/rotation/models.py](../../app/rotation/models.py) | Portfolio rotation context: Original evaluation ID/as_of, optional holding_sessions, cooldown context | Holding duration/cooldown possible but retrospective/anti-churn | INCOMPATIBLE: Requires authentic source origin plus missing exact parcel |
| BACKTEST: [app/backtest/models.py](../../app/backtest/models.py) | Backtest replay: Replay boundaries, strategy/config/source versions | Run start/end windows are operational experiment bounds | BACKTEST_ONLY_EVIDENCE: Tools reusable; windows cannot authorize |
| WALK_FORWARD: [app/backtest/walk_forward.py](../../app/backtest/walk_forward.py) | Chronological model evaluation: Train/validation/test/step/purge/embargo sessions and frozen policy versions | Fold lengths exist by configuration, not horizon authority | BACKTEST_ONLY_EVIDENCE: Reuse future evaluation machinery only |
| OOS: [app/backtest/oos_aggregation.py](../../app/backtest/oos_aggregation.py) | OOS aggregation: Stitched held-out observations with source/plan references | No approved holding-duration mapping | INSUFFICIENT: Infrastructure not empirical validation |
| CALIBRATION: [app/calibration/service.py](../../app/calibration/service.py) | Score outcome calibration: Caller horizon label; score buckets and observed win/expectancy statistics | String grouping/observed statistics, not horizon-policy numbers | INCOMPATIBLE: CALIBRATION_POLICY_REQUIRED |
| SELF_IMPROVEMENT: [app/self_improvement/models.py](../../app/self_improvement/models.py) | Diagnostic post-outcome attribution: DiagnosticRuleSet short_horizon_sessions | Configured diagnostic evaluation window only | DESCRIPTIVE_ONLY: No alias or window borrowing |
| MARKET_EXTREMES: [app/crisis/models.py](../../app/crisis/models.py) | Market Extremes forward evidence: ForwardOutcomeReference horizon_sessions and method version | Forward-study descriptor can carry a number | DESCRIPTIVE_ONLY: Not direct mapping evidence |
| COMPOUNDER_BUSINESS: [app/intelligence/compounder_prospective_shadow_validation.py](../../app/intelligence/compounder_prospective_shadow_validation.py) | Compounder prospective research: ONE_YEAR/THREE_YEARS/FIVE_YEARS business outcomes; market outcome unready | Explicit other-purpose business windows, not paired horizon values | INCOMPATIBLE: Do not borrow business windows |
| THESIS: [app/intelligence/long_term_thesis_review.py](../../app/intelligence/long_term_thesis_review.py) | Deep Analysis/Long-Term Thesis Review: Immutable common dossier/family/evidence review | No approved numeric paired duration or review-cadence mapping | DESCRIPTIVE_ONLY: Preserve descriptive taxonomy only |
| RECALL: [app/intelligence/discovery_recall_reference_matching.py](../../app/intelligence/discovery_recall_reference_matching.py) | Discovery recall research: Frozen research match/outcome endpoint supplied by specification | Study-specific endpoint possible; not horizon authority | BACKTEST_ONLY_EVIDENCE: No retrospective reference-label substitution |
| CALENDAR: [app/historical/nse_capital_market_session_evidence_2022_2026.py](../../app/historical/nse_capital_market_session_evidence_2022_2026.py) | Canonical NSE session evidence: Annual holidays, amendments, special phases; prospective ordinary rule | Dates/phase times, not duration-policy numbers | CANONICAL_POLICY_EVIDENCE: Useful conditional counting input, not unit/count approval |
| HISTORICAL_IDENTITY: [app/historical/nse_session_identity.py](../../app/historical/nse_session_identity.py) | Historical Integrity: KNOWN_FOR_SESSION_D point identity, not full interval/intraday knowledge | Session dates only | CANONICAL_POLICY_EVIDENCE: Use within native exact-session scope only |
| LIFECYCLE: [app/historical/bse_lifecycle.py](../../app/historical/bse_lifecycle.py) | Historical Integrity/BSE official evidence: Delist/suspend/reidentify and notice lineage | Lifecycle effective dates, not investment duration | PIT_UNSAFE: Some exact primary notices replayable conditionally; compiled rows cannot repair historical knownness |
| PRICES: [app/market_data/daily_source_temporal_semantics.py](../../app/market_data/daily_source_temporal_semantics.py) | Canonical market-data/Historical Integrity: Provider-versioned daily bar temporal semantics and receipt provenance | Daily intervals and prices, not horizon authority | INSUFFICIENT: Raw price volume alone cannot justify horizon |
| STORAGE: [app/storage/sqlite_repository.py](../../app/storage/sqlite_repository.py) | Existing SQLite repositories: Canonical rotation/backtest/paper/performance and research records | Stored data counts not policy thresholds | INSUFFICIENT: Audit only; no cohort or write |

### PIT, sample and compatibility review

| ID | PIT / replay and sample provenance | Calibration validity / category compatibility |
| --- | --- | --- |
| GOVERNANCE_CHAIN | Immutable version and D-time approval required; proposal is not approval Pinned artifacts reproducible; no empirical sample | Structural only; no approved mapping calibration Both categories conditionally scoped; no durations |
| PRE_BREAKOUT | Native approval/selection validity must hold at Watch cutoff Source references verified; no original paired sample | No horizon calibration in policy lookup Exact PRE_BREAKOUT path only, not all POSITIONAL strategies |
| DISCOVERY | Lead discovery_as_of/known_at and source fingerprints must be verified Immutable lead replay possible, not a genuine rotation decision | Category names are not calibration Compounder LONG_TERM; pre-breakout/sector POSITIONAL; inflection/policy may have both |
| WATCH_ROUTER | Router consumes already-filtered evidence; Watch latest without cutoff uses now and is prohibited here Twelve Watch snapshots counted, not paired outcomes | No duration estimator Archetype does not imply category duration |
| SETUP | Existing setup evidence must be valid at D Source setup identity preserved; no paired sample | No duration policy Setup type alone cannot choose category mapping |
| PAPER | Frozen setup/bar/config required; future exits only R-time outcomes Paper trades/outcomes zero; fixtures not production evidence | Exit-conditioned realized durations, no paired calibration Native > comparisons differ from forward-paper >= semantics |
| FORWARD_PAPER | Study admission and observation must be prospective; realized outcomes not D features Three runs, all zero admission/entry/exit/session; no study-family rows in inventory | No mature studies or paired sample Same horizon must apply to both legs, not each paper exit |
| PERFORMANCE | Archived complete lifecycle, bars, action/cost basis and knownness required Performance reports and paper outcomes zero | No original paired duration study; conditioning on closed trades risks censoring bias Trade R statistics not necessarily paired INR wealth outcomes |
| GROUPED_MFE_MAE | Input lifecycle completeness and predeclared grouping required No persisted report sample; existing tests synthetic | No approved sample adequacy, censoring or duration-selection criteria MFE/MAE extrema do not by themselves define symmetric terminal dates |
| ROTATION_HOLDING | Exact historical context required; no present portfolio read for research Portfolio evaluations/comparisons/historical evaluations all zero | No empirical paired history Incumbent elapsed holding time cannot become challenger forward horizon |
| BACKTEST | Frozen original source manifests and no later membership; simulation is not an authentic decision Backtest runs/events/manifests/partitions zero | No empirical study found; test fixtures remain test-only Training/replay interval is not per-pair holding horizon |
| WALK_FORWARD | Predeclare selection on training/validation; never select on held-out TEST Plans/runs/window/aggregate results zero | Mechanism supports separation but no horizon stability study Fold sizes neither POSITIONAL nor LONG_TERM mappings |
| OOS | Source folds, decision cutoffs and selection freeze must precede OOS assessment Future-OOS execution/candidate records zero | No independently untouched horizon-validation sample Shared OOS across durations cannot later be claimed untouched |
| CALIBRATION | Only D-frozen features with R-mature outcomes; no caller label grants authority No approved paired calibration artifact in pinned chain | Native score calibration does not define numeric horizon stability or sample limits Cannot transfer score-bucket thresholds to either category |
| SELF_IMPROVEMENT | Known-at and frozen rule version required for valid attribution No paired calibration provenance | Different outcome/selection target SHORT_TERM attribution is not POSITIONAL/LONG_TERM horizon authority |
| MARKET_EXTREMES | Event D and subsequent outcome R kept separate No original rotation pair/parcel sample established | No paired duration validation Market event forward return not incumbent/challenger continuation |
| COMPOUNDER_BUSINESS | Prospective source-known observations and mature business evidence required Two compounder snapshot-family records; not paired observations | No calibrated paired market horizon LONG_TERM label does not equate accounting review window to holding duration |
| THESIS | Dossier as-of and verified native lineage required Canonical dossier evidence distinct from realized pair | Family readiness not return calibration Five families differ; no universal horizon score |
| RECALL | Predeclared reference set/endpoint and PIT match required No paired original-parcel provenance | Recall sample selection differs from economic comparison Family-category matches not approved duration mappings |
| CALENDAR | Native source-known/publication and effective interval checks; modern rule forward-only Bounded source-backed 2022-2026 calendar, historical ordinary coverage incomplete | Calendar proves session facts, not optimal durations NSE CM only; security tradability separate |
| HISTORICAL_IDENTITY | Approved exact-session semantics retained; historical_known_at intentionally unavailable 61850 family records including approvals and receipts, not session count | No duration calibration Cannot replace listing/suspension/event-time coverage |
| LIFECYCLE | Sample compiled delisting rows have no historical_known_at; reject as D-time evidence 1340 lifecycle-family rows; sampled late observations only | No paired endpoint cash/entitlement calibration BSE notice/current link is not universal NSE historical tradability |
| PRICES | Native source time meaning, R completion and D/R knowledge required 2663799 bars, 795 conflicts; bounded 1000 sample all 1D RAW unknown_existing_source | No paired study or approved adjustment/endpoint mapping Daily date labels do not provide exact intraday D-price symmetry |
| STORAGE | Read-only capture, explicit dates and no raw private payload export Inspected canonical outcome/origin stores zero | No records to calibrate; absence is not negative performance No new repository or alternate source of truth |

Existing approved Pre-Breakout provenance remains available in its own scope; this does not create an approved duration. Native paper `>` time-stop/expiry and forward-paper `>=` session tests must not be silently unified. Actual holding time, strategy name, signal expiry, cooldown, blackout, business-review cadence and technical bar timeframe remain distinct concepts.

## 5. Category-specific findings

| Category | Evidence meaning | Cross-strategy conflict | Single / range / rule / finding |
| --- | --- | --- | --- |
| POSITIONAL | Canonical discovery category; pre-breakout/sector paths can supply it when source verified. Not an elapsed duration. | Sector leadership, pre-breakout and inflection have different outcome mechanisms; some leads carry both categories. | No / No / No / NO_MAPPING_YET — EVIDENCE_INSUFFICIENT |
| LONG_TERM | Compounder lead category; inflection/policy transmission may also include POSITIONAL. | Business milestones and compounder calendar-year windows are not paired market-wealth endpoints; no one category-wide duration is established. | No / No / No / NO_MAPPING_YET — EVIDENCE_INSUFFICIENT |

SHORT_TERM diagnostic applicability, PRE_BREAKOUT strategy labels and bar timeframes are not additional approved mapping categories; no implicit synonym or default. No multi-category lead may be resolved by arbitrary order, default or best-result selection. A strategy-specific method might ultimately be necessary, but neither category currently has a justified value or method.

## 6. Genuine origins and structural bootstrap

| Required original field | Readiness | Evidence / exact gap |
| --- | --- | --- |
| ORIGINAL_DECISION_ID | SOURCE_NOT_READY | Rotation evaluation stores = 0 Authentic original event missing; do not synthesize from bars. |
| D_CUTOFF | SOURCE_NOT_READY | Models carry as_of_timestamp No archived paired row binding original D. |
| INCUMBENT | SOURCE_NOT_READY | Rotation comparisons = 0 Exact original incumbent reference absent. |
| CHALLENGER | SOURCE_NOT_READY | Rotation comparisons = 0 Exact original challenger reference absent. |
| EXACT_PARCEL | SOURCE_NOT_READY | Economic contract requires parcel; comparison alone insufficient Original selected parcel/capital basis absent. |
| STRATEGY_CATEGORY | SOURCE_NOT_READY | Canonical categorical leads implemented No exact category/strategy closure on a genuine stored pair. |
| ARCHIVED_EVIDENCE | SOURCE_NOT_READY | Historical manifests/memberships = 0 Original pair-specific replay closure unavailable. |

Eligible canonical pairs found: **0**. The original event must bind decision ID, exact D, incumbent, challenger, exact selected parcel/capital basis, strategy/category and archived evidence. A Watch record, sell-side audit link, current holding or raw OHLCV series cannot stand in for this event.

The circular dependency is:

`independent D-valid horizon -> frozen end -> mature paired outcomes -> possible horizon justification`.

There is no independently governed numeric prior in the inspected chain and no authentic archived paired sample. Existing descriptive windows do not break the loop. Therefore Decision D is more precise than a generic data-shortage conclusion.

An authentic decision and raw source archive can exist before its outcome. But it is not an eligible paired research observation until its required independent D-valid horizon is bound. It must not be retrospectively turned into a qualifying sample using a later approval. No origin collector or research-event pipeline is implemented here.

Potential safe approaches for the next governance review, **not approved here**:

- Independently justify a research-only seed or staged convention, with methodology, source, approval and effective version frozen before eligible prospective D; do not optimize it on the outcomes it will generate.
- Specify real origin/parcel/source archive prerequisites. Later authorized collection must retain failed, unresolved and censored cases, not manufacture events from bars.
- Separate seed-protocol data from later held-out evaluation cohorts. A changed mapping is a new prospective version; no relabeling historical bindings.

No option or numeric seed is selected. A pipeline alone does not supply authority, and authority alone does not create historical decisions.

## 7. Empirical and statistical prerequisites

| Requirement | Exact evidence required | Current state |
| --- | --- | --- |
| GENUINE_ORIGINS | Authentic original event ID, D, pair, exact parcel/capital basis and strategy/source archive; bars/signals cannot be relabeled as decisions. | SOURCE_NOT_READY |
| MATURE_PAIRS | Both legs resolved under same independently D-bound horizon; R includes endpoint completion and known price. Pending/censored/unresolved observations retained distinctly. | SOURCE_NOT_READY |
| STRATEGY_REPRESENTATION | Predeclared strategy/version coverage, no aliasing one archetype as all categories. | CALIBRATION_REQUIRED |
| REGIME_SECTOR_TIME | Predeclared regime/sector/subperiod coverage using classifications known at original D. | CALIBRATION_REQUIRED |
| CONCENTRATION | Dependence across repeated issuers, events, overlapping horizons and dates must be measured; no arbitrary concentration cap. | CALIBRATION_REQUIRED |
| SURVIVORSHIP | Include original universe, delisted/suspended/failed/missing endpoints; no current-member or completed-winner-only filter. | SOURCE_NOT_READY |
| ACTION_INTEGRITY | Same economic basis with source-versioned corporate actions and distributions; unresolved transitions not zero returns. | SOURCE_NOT_READY |
| PIT | Freeze original D features, authority and one horizon; future outcomes R cannot repair D selection. | READY |
| CHRONOLOGICAL_OOS | Predeclare train/validation/untouched TEST; future labels unavailable to selection; changed mapping needs new future validation. | SOURCE_NOT_READY |
| UNCERTAINTY_CENSORING | Declare uncertainty estimator, dependence/censoring treatment, sampling frame and adequacy criterion before acceptance. | POLICY_REQUIRED |
| STABILITY | Predeclared subperiod/regime/strategy/OOS and outlier/alternative-duration sensitivity; no best-of search. | CALIBRATION_REQUIRED |
| SAMPLE_THRESHOLDS | Minimum sample, coverage, precision, concentration and stability thresholds have no approved numeric values here. | POLICY_REQUIRED |

Every numeric sample minimum, concentration cap, uncertainty acceptance criterion and stability threshold remains null: **CALIBRATION_POLICY_REQUIRED**. Existing score-bucket or unrelated research thresholds cannot be imported. Genuine source-knownness, survivorship and corporate-action requirements are already necessary invariants, not choices that may be waived to obtain a sample.

## 8. Candidate mapping methodologies — none selected

| Method | Interpretability | Overfit / hindsight risk | Sample / regime sensitivity | Replay / protocol compatibility |
| --- | --- | --- | --- | --- |
| EXISTING_GOVERNED_STRATEGY_DURATION | Most interpretable if same purpose and D-effective scope; no such numeric policy found. | Prior optimized duration may hide selection bias. Validate prior publication/approval before D; no later policy backfill. | Prior sample/method quality still required. Explicit applicability must address regime shifts. | Exact pinned source/version replay is possible in principle. Compatible only with same pair scope and independent authority. |
| MATURE_OUTCOME_MEDIAN_QUANTILE | Simple descriptive summary, not automatically an investment horizon. | Exit-conditioned samples/censoring and quantile search can overfit. Cannot use a pair's later result to pick its original endpoint. | Adequacy/uncertainty/censoring policy absent. Distribution varies by strategy and regime. | Predeclared statistic and immutable source sample required. Circular for initial seed; actual holding/target exits not common fixed paired end. |
| WALK_FORWARD_STABILITY | Interpretable predeclared repeated chronological validation. | Selecting stable/best durations after inspecting many folds overfits. Selection on held-out TEST or reuse of TEST prohibited. | No folds/results or sample adequacy threshold. Subperiod/regime coverage and stability thresholds unresolved. | Frozen plans, methods and source manifests can support replay. Future validation tool, not independent starting duration. |
| REGIME_CONDITIONED | May explain heterogeneity but no approved method. | Many regime-duration combinations and regime redefinitions overfit. Regime must be canonical and visible at D, not retrospective. | Sparse per-regime samples and dependence need treatment. Most exposed to changing regime definitions and transitions. | Pinned D-time regime/policy mandatory. Earlier proposal treats macro/sector as trace-only, not duration drivers; extending requires separate scope approval. |
| STRATEGY_CONDITIONED | Could preserve distinct strategy mechanisms within a category. | Sparse strategy versions and strategy selection can overfit. Exact approved strategy provenance frozen at D. | Per-strategy diversity/precision criteria missing. Cross-regime stability needed for each strategy. | Native strategy/version and predeclared mapping can replay. Scope-compatible candidate but no numeric policy or sample; dual-category conflict must remain closed. |
| TARGET_STOP_RESOLUTION_TIME | Observable duration descriptive of an exit rule. | Optimized targets/stops/censoring select favorable samples. Specific outcome resolution cannot determine its D-time horizon. | No mature original samples; unresolved trades must be retained. Volatility/regime and exit rules materially change duration. | Exact frozen target/stop/bar/config required for descriptive replay. Outcome-dependent endpoints violate identical prebound horizon if used directly; cannot import setup trade parameters here. |

Future selection must be predeclared using chronological training/validation only. Held-out OOS cannot first rank durations and then be advertised as untouched validation. No per-observation future outcome, many-duration best-result search, repeated historical relabeling or post-hoc regime definition may select D-time duration. Alternative-duration sensitivity could be a predeclared research audit, never multiple canonical horizons per pair or winner selection. The existing walk-forward engine supplies separation mechanisms, not a successful horizon study.

## 9. Duration units and counting

| Unit | Readiness | Existing capability / missing approval |
| --- | --- | --- |
| TRADING_SESSIONS | POLICY_REQUIRED | Source-backed calendar and session-aware engines exist; conceptual predecessor preference only Native D partial-session, count and endpoint rules plus complete calendar closure missing. |
| CALENDAR_DAYS | POLICY_REQUIRED | Rotation cooldown and business outcomes use dates Elapsed calendar interval is not an approved paired holding horizon; holiday/terminal alignment unresolved. |
| ELAPSED_TIMESTAMPS | POLICY_REQUIRED | UTC-aware exact D and temporal sources exist Precision tooling does not approve duration or supply price at that instant. |

The predecessor's conceptual preference for trading sessions is retained; **effective unit remains unset**. Exact UTC arithmetic does not approve elapsed time; a calendar-day cooldown does not approve calendar-day investment duration.

| Counting component | Readiness | Existing evidence | Unresolved convention / fail-closed rule |
| --- | --- | --- | --- |
| D_SESSION_ALIGNMENT | DERIVABLE | Canonical calendar resolves visible phases | Missing historical phases remain unknown; do not move start away from D. |
| START_SESSION_TREATMENT | POLICY_REQUIRED | Start = D already frozen | Pre-open/intraday/after-close and session-zero/session-one policy unset. |
| SESSION_COUNTING | POLICY_REQUIRED | Adjacent-session primitive exists | No approved N-count/partial-day/first-inclusion convention. |
| HOLIDAY_HANDLING | DERIVABLE | Versioned annual schedules and amendments | Only exact covered D-visible sources; missing year/version blocks. |
| SPECIAL_SESSIONS | POLICY_REQUIRED | Retained special/Muhurat day and phase sources | Half/special-session weight and missing timing convention not approved. |
| SUSPENSION_HANDLING | SOURCE_NOT_READY | Historical security status/lifecycle contracts | Security-specific tradability history and common endpoint policy incomplete. |
| TERMINAL_SESSION_SELECTION | POLICY_REQUIRED | R-time completion can be verified conditionally | No N/count/phase rule approved. |
| MISSING_BAR_BEHAVIOR | READY | Frozen missing/conflicting evidence fails closed | No nearest bar, forward fill, zero return or date roll; resolution remains unavailable. |
| DELISTING_BEHAVIOR | SOURCE_NOT_READY | Historical lifecycle and corporate-action models | Compiled delisting rows lack historical known-at; no default zero/liquidation endpoint. |
| CORPORATE_ACTION_TRANSITION | SOURCE_NOT_READY | Exact action/identity revision lineage supported | Economic conversion, same basis, PIT and cash-flow closure not proven for paired endpoints. |
| CALENDAR_PROVENANCE | DERIVABLE | Source IDs, native fingerprints, publication/known-at fields | Verify original source and D-visible version, not today's calendar. |
| HISTORICAL_CALENDAR_COMPLETENESS | SOURCE_NOT_READY | Bounded 2022-2026 retained calendar | Ordinary historical sessions before forward-only rule remain incomplete. |
| NEXT_TRADABLE_SESSION | DERIVABLE | Adjacent-session primitive stops on unknown evidence | No inference from a missing security bar; cannot silently roll frozen endpoint. |
| VENUE_ALIGNMENT | POLICY_REQUIRED | NSE cash-equity scope proposed; exact venue/identity required | No BSE cross-listing proxy or alternative-venue fallback. |

Start stays **exactly D**. Whether the D date counts as zero or one, how pre-open/intraday/after-close timestamps consume the first session, and how shortened or special sessions count remain policy questions. Advancing a counting reference must never silently move the economic start. Exchange closure and security-specific non-trading are distinct. There is no BSE/current-symbol fallback.

## 10. Actual calendar and instrument-state coverage

Calendar `nse-capital-market-first-party-2022-2026-v2-ordinary-forward` retains nominal 2022-01-01 through 2026-12-31 coverage. It contains annual first-party holiday circulars, dated amendments and selected special-session phase records, but **historical completeness = INSUFFICIENT / SOURCE_NOT_READY**.

Ordinary weekday and regular-continuous phase evidence is forward-only from effective date 2026-09-05 and known-at **2026-09-05T16:47:00Z**. The existing pure resolver returns unknown ordinary-day state for earlier historical dates, even when queried later. Dates such as 2026-11-08 can have a known Muhurat day but no phase timing. Annual-holiday coverage does not prove every ordinary/special/shortened session or schedule change.

Some source-backed holiday/special facts are bounded and usable under native visibility rules; source recovery might close other ranges but complete reconstruction is **not demonstrated**. Required pair ranges cannot yet be enumerated without real origins and independent horizon approval. Absence of a standalone calendar table is not absence of the implemented calendar; session-identity counts are not calendar completeness.

| Instrument state | Readiness | Canonical reuse | Replay limitation |
| --- | --- | --- | --- |
| ACTIVE | DERIVABLE | Exact NSE session-point identity and historical master contracts | Session-point record is not complete listing interval, intraday known-at or continuously tradable price. |
| SUSPENDED | SOURCE_NOT_READY | HistoricalSecurityStatus and BSE suspension events | No complete security-specific suspension history demonstrated; no nearest non-suspended bar. |
| DELISTED | PIT_NOT_READY | 1340 lifecycle-family records; bounded sampled compiled rows | Observed in 2026 with historical_known_at null; no automatic historical knowledge or zero terminal value. |
| RENAMED_REIDENTIFIED | DERIVABLE | Exact source-backed before/after identifiers and revision chain | Only individually verified transitions, no name/fuzzy-match or current symbol backfill. |
| MERGER_DEMERGER | SOURCE_NOT_READY | Merger/cessation and corporate-action infrastructure | Successor/cash entitlement and PIT economic basis require exact sources; symbol substitution insufficient. |
| SYMBOL_TRANSITION | DERIVABLE | Native session identity and historical identity intervals | Exact per-date bridge required; not universal replay coverage. |
| CORPORATE_ACTION | SOURCE_NOT_READY | 3886 action-family records; sampled announcement_date null | Effective date alone not historical knownness; consistent basis and distributions unresolved. |

Historical Integrity is the canonical owner. Exact dates/identifiers/revisions must be preserved. Native BSE lifecycle notice semantics are not weakened merely because compiled delisting samples are PIT-incomplete. A successor symbol, a current exact link or an effective action date is not sufficient proof of earlier knowledge or economic entitlement.

## 11. Terminal boundary and price alignment

| Candidate endpoint | Readiness | Tooling | Missing policy/data |
| --- | --- | --- | --- |
| NTH_GOVERNED_SESSION_CLOSE | POLICY_REQUIRED | Canonical completed regular/special phase; daily temporal adapters | N, initial inclusion, phase/price and missing-day rules not approved. |
| D_ALIGNED_TIMESTAMP | POLICY_REQUIRED | UTC event-time and intraday readiness primitives | Exact start/end quote/price coverage and precision not established; no daily-close substitute. |
| SESSION_VWAP | SOURCE_NOT_READY | Some bars may expose volume/turnover | No approved Gate-1 endpoint method or completeness proof; close, partial volume or averages cannot stand in for VWAP. |
| OTHER_NATIVE_TARGET_STOP_OR_BUSINESS_ENDPOINT | INCOMPATIBLE | Paper target/stop and business milestone tracking | Outcome-dependent or different-purpose endpoint cannot replace one immutable identical paired horizon. |

Price alignment is **PIT_NOT_READY**. Daily date labels, including 18:30 UTC source boundaries, are not exact intraday D prices. A single quote snapshot and large historical-bar volume do not demonstrate original start/terminal coverage. UNKNOWN adjustment status must not become certified comparable basis.

Both legs require the same immutable binding, compatible INR economic basis, action/distribution lineage, exact source-time interpretation and native fingerprint verification. For the label cutoff R, require R at/after frozen end **and** completed exact governed phase **and** available exact terminal evidence. Future data is allowed only in this separated outcome layer, never to repair D-time selection.

Missing terminal bar, suspension, delisting, action ambiguity, outage or exchange closure leaves the observation pending/unresolved/excluded under a future approved label policy. **No nearest bar, forward fill, date roll, default zero, inferred liquidation price, partial VWAP or active-session completion.** A subsequently discovered closure cannot rewrite a historical frozen endpoint to improve its return.

## 12. Mapping readiness

| Component | Readiness | Evidence | Remaining gap |
| --- | --- | --- | --- |
| POSITIONAL_EVIDENCE | EVIDENCE_INSUFFICIENT | Canonical category and setup/Watch paths | No approved numeric mapping or genuine paired sample. |
| LONG_TERM_EVIDENCE | EVIDENCE_INSUFFICIENT | Canonical compounder/inflection categories and dossiers | Business-outcome windows not comparable paired wealth horizons. |
| STRATEGY_DURATION | POLICY_REQUIRED | Approved Pre-Breakout exists in native scope | No independently approved numeric paired duration. |
| PAIRED_HISTORICAL_OUTCOMES | SOURCE_NOT_READY | All inspected rotation comparison/evaluation stores zero | No exact original decisions or matured paired observations. |
| PAPER_TRADE_EVIDENCE | EVIDENCE_INSUFFICIENT | Paper/MFE/MAE infrastructure; outcomes zero | Paper duration is endogenous to exits and not mapping authority. |
| FORWARD_STUDY_EVIDENCE | EVIDENCE_INSUFFICIENT | Three healthy zero-admission runs | No mature studies or events in counted families. |
| OOS_EVIDENCE | SOURCE_NOT_READY | future_oos_execution_results/research_candidate_oos_records zero | No held-out paired horizon study. |
| WALK_FORWARD_EVIDENCE | SOURCE_NOT_READY | Plans/runs/window/aggregate tables zero | Leak-resistant tools not empirical validation. |
| CATEGORY_MAPPING_METHOD | POLICY_REQUIRED | Candidate methods inventoried | None selected; mixed strategy/category inputs conflict. |
| NUMERIC_DURATION | EVIDENCE_INSUFFICIENT | Policy explicitly unset | No point, range, grid or surrogate approved. |
| DURATION_UNIT | POLICY_REQUIRED | Sessions preferred conceptually only | Effective unit/count/endpoint policy unset. |
| BOOTSTRAP_FEASIBILITY | BLOCKED | No independent prior and no true paired origins | Separate bootstrap governance required; no arbitrary seed. |
| CALIBRATION_THRESHOLDS | POLICY_REQUIRED | Existing score calibration is different-purpose | CALIBRATION_POLICY_REQUIRED; no arbitrary sample minimum. |
| MAPPING_STABILITY | CALIBRATION_REQUIRED | Walk-forward/grouped measurement contracts reusable | No subperiod/regime/strategy/outlier/alternative-duration validation. |
| PRODUCTION_COMPATIBILITY | BLOCKED | V1 ACTIVE; proposed V2 NOT_ACTIVE | No research or production horizon authority registered. |

READY on the missing-bar row means the rejection boundary is already exact, not that prices are available. DERIVABLE means existing conditional tooling can be reused once its sources and approvals close, not automatic permission to construct durations.

## 13. Closure, remaining blockers and validation boundary

Closed by this audit: source inventory, actual canonical zero-origin/outcome checks, category/window non-equivalence, calendar temporal limitations, bootstrap classification and a single bounded follow-up. Remaining blockers: independent numeric authority, genuine original paired decisions, calibration methodology/adequacy, counting/terminal/unit approval, historical calendar and lifecycle/price PIT closure, OOS and mapping stability evidence.

Validation is offline conformance plus relevant governance/calendar/identity/research regression. Tests freeze all predecessor fingerprints and 125 source pins, reject unsupported values and evidence upgrades, and exercise existing fail-closed calendar/PIT witnesses. A separate complete-diff check confirms no runtime change. The immutable recorded data capture is tested as a dated audit receipt; tests do not query or mutate production SQLite.

Completed validation: **189 focused tests passed, 0 failed, 0 warnings**; **1,028 relevant regression tests passed, 0 failed, 2 dependency-deprecation warnings**. Neither run reported skips. The relevant run covers predecessor Gate-1 governance, calendar/session identity, lifecycle, paper/forward-paper, performance and walk-forward foundations. Markdown validation checked **317 local links, 14 tables and 125 source pins**; whitespace and artifact-fingerprint checks passed.

Full backend regression was not run: this slice changes no runtime/shared behavior, as permitted by the task. No prior full-suite result is relabeled as a new full run. The two warnings concern Starlette/httpx and AnyIO compatibility aliases, not this audit.

## 14. Exactly one next frozen continuation

`GATE1_ROTATION_RESEARCH_HORIZON_BOOTSTRAP_GOVERNANCE_V1`

Governance-only independent-bootstrap proposal: assess evidence/source-owner feasibility of a predeclared research-only seed or staged convention and genuine decision/parcel archive prerequisites; keep unsupported values unset. Must break selection/outcome circularity without retroactive D approval, relabeling or fake observations. No collection, calibration, authority registration, activation or runtime implementation is authorized by this audit.

**Not started.** No push. This audit neither activates V2 nor changes active V1.
