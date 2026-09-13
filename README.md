# NSE Stock Manager v2.1

NSE Stock Manager is a private, AI-assisted research and paper-trading system for Indian equities (NSE/BSE). Its purpose is to help assess whether capital is allocated to the strongest available **risk-adjusted** opportunities.

## Eligible NSE equity opportunity orchestration

The controlled opportunity pipeline uses canonical stored data only:
ingestion → eligible NSE equity universe → 61-diagnostic input assembly and
registry execution → existing Decision Score → confidence → six gates →
candidate qualification → existing portfolio rotation comparison → distilled
read-only output. It does not fetch providers per diagnostic, create a manual
shortlist, promote/activate a strategy, or place trades.

The supported population scope is **NSE main-board equity shares** imported from
an approved local official export or canonical instrument mapping. ETFs, bonds,
REITs, InvITs, preference shares, warrants, rights, suspended/delisted
instruments, and unsupported SME securities are excluded with retained reasons.
`FULL` coverage means the bound immutable universe snapshot completed its
eligibility, analysis, and candidate-materialization stages. Otherwise the UI
uses “best candidate among analyzed opportunity set,” never “best NSE stock.”

It is being built incrementally. The current repository contains a provider-independent Python foundation that uses fixed mock data only. It has no market-data provider, live-trading connection, autonomous order execution, or investment-performance guarantee.

## Guiding principles

- Treat facts, source data, interpretation, and inference as distinct layers.
- Retain provenance, timestamps, freshness, validation status, and data quality for material observations.
- Start with mock/test data and provider-independent boundaries.
- Keep diagnostic decisions, strategy versions, and paper-trade outcomes auditable.
- Validate proposed strategy changes before they can become a new production version.
- Treat future OOS results as immutable evidence, never as automatic promotion, approval, or activation.
- Cash is a valid portfolio allocation.

## Documentation

### Hardened brain architecture (canonical detailed specification)

- [Brain Architecture v2.2-hardened](docs/architecture/brain_architecture.md)
- [Brain contract](docs/architecture/brain_contract.md)
- [Defensive engines](docs/architecture/defensive_engines.md)
- [Data flow and failure propagation](docs/architecture/data_flow.md)
- [Decision flow](docs/architecture/decision_flow.md)
- [Model governance and drift](docs/architecture/model_governance.md)
- [Audit and reproducibility](docs/architecture/audit_reproducibility.md)
- [Versioning and change control](docs/architecture/versioning_and_change_control.md)
- [Post-V1 Product Architecture — One Brain, Multiple Signal Windows](docs/architecture/POST_V1_PRODUCT_ARCHITECTURE.md)
- [P1 Watch-only HSISignal Foundation acceptance](docs/architecture/POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md)
- [Post-V1 Strategy and Signal-Window Catalogue](docs/architecture/POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md)
- [Batch 1 Event/Catalyst and Market-Red Resilience policy proposal](docs/architecture/POST_V1_BATCH_1_EVENT_CATALYST_AND_RESILIENCE_POLICY_PROPOSAL.md)
- [Batch 1 historical calibration research receipt](docs/architecture/POST_V1_BATCH_1_HISTORICAL_CALIBRATION_RESEARCH.md)
- [Long-Term Thesis Family policy approval pack](docs/architecture/POST_V1_LONG_TERM_THESIS_FAMILY_POLICY_PROPOSAL.md)
- [Long-Term Evidence Dossier reuse and policy-readiness receipt](docs/architecture/POST_V1_LONG_TERM_EVIDENCE_DOSSIER_REUSE_AND_READINESS.md)
- [Post-V1 Long-Term Thesis Review Foundation](docs/architecture/POST_V1_LONG_TERM_THESIS_REVIEW_FOUNDATION.md)
- [Long-Term Thesis Families Research Shadow V1 readiness](docs/architecture/POST_V1_LONG_TERM_RESEARCH_SHADOW_V1.md)
- [Long-Term Quality at Fair Value Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_QUALITY_FAIR_VALUE_RESEARCH_SHADOW_V1.md)
- [Long-Term Fundamental Compounder Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_FUNDAMENTAL_COMPOUNDER_RESEARCH_SHADOW_V1.md)
- [Long-Term Fundamental Inflection Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_FUNDAMENTAL_INFLECTION_RESEARCH_SHADOW_V1.md)
- [Fundamental Inflection Policy Research Proposal V1](docs/architecture/FUNDAMENTAL_INFLECTION_POLICY_RESEARCH_PROPOSAL_V1.md)
- [Inflection Testable Derived Metrics and Event Alignment V1](docs/architecture/INFLECTION_TESTABLE_DERIVED_METRICS_AND_EVENT_ALIGNMENT_V1.md)
- [Inflection Event-Session and Market-Reaction Policy Proposal V1](docs/architecture/INFLECTION_EVENT_SESSION_AND_MARKET_REACTION_POLICY_PROPOSAL_V1.md)
- [Canonical Market Session and Event Time V1](docs/architecture/CANONICAL_MARKET_SESSION_AND_EVENT_TIME_V1.md)
- [Canonical NSE Ordinary Session Identity and Close Evidence V1](docs/architecture/CANONICAL_NSE_ORDINARY_SESSION_IDENTITY_AND_CLOSE_EVIDENCE_V1.md)
- [Technical Diagnostic Timeframe and Data Readiness V1](docs/architecture/TECHNICAL_DIAGNOSTIC_TIMEFRAME_DATA_READINESS_V1.md)
- [Canonical Technical Bar Timeframe and Completeness Contract V1](docs/architecture/CANONICAL_TECHNICAL_BAR_TIMEFRAME_AND_COMPLETENESS_CONTRACT_V1.md)
- [Canonical Weekly Technical Bar Derivation V1](docs/architecture/CANONICAL_WEEKLY_TECHNICAL_BAR_DERIVATION_V1.md)
- [Daily/Weekly Existing Technical Diagnostics Operationalization V1](docs/architecture/DAILY_WEEKLY_EXISTING_TECHNICAL_DIAGNOSTICS_OPERATIONALIZATION_V1.md)
- [Canonical 61 Diagnostic Operational Coverage Closure V1](docs/architecture/DIAGNOSTIC_61_OPERATIONAL_COVERAGE_CLOSURE_V1.md)
- [Canonical Financial Diagnostic Input Comparability Closure V1 — Rules 16–20, 24–26, 29](docs/architecture/CANONICAL_FINANCIAL_DIAGNOSTIC_INPUT_COMPARABILITY_CLOSURE_V1.md)
- [Canonical EBITDA / EBIT Source Audit and Annual-History Acquisition V1](docs/architecture/CANONICAL_EBITDA_EBIT_AND_ANNUAL_HISTORY_ACQUISITION_V1.md)
- [Official Company-Level EBITDA / EBIT Source Feasibility V1](docs/architecture/OFFICIAL_COMPANY_LEVEL_EBITDA_EBIT_SOURCE_FEASIBILITY_V1.md)
- [EBITDA / EBIT Diagnostic Policy Alternatives Research V1](docs/architecture/EBITDA_EBIT_DIAGNOSTIC_POLICY_ALTERNATIVE_RESEARCH_V1.md)
- [Fundamental Diagnostic Policy Resolution Research V1](docs/architecture/FUNDAMENTAL_DIAGNOSTIC_POLICY_UNRESOLVED_V1.md)
- [Fundamental Diagnostic Registry V2 Proposal (not active)](docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSAL.md)
- [Fundamental Diagnostic Registry V2 Governance Approval (activation blocked)](docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.md)
- [Fundamental Diagnostic Registry V2 Isolated Shadow V1 (not active)](docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_SHADOW_IMPLEMENTATION_V1.md)
- [Fundamental V2 Downstream Fail-Closed Safety V1 (V2 not active)](docs/architecture/FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_ADAPTER_V1.md)
- [Fundamental V2 Brain / Portfolio Lineage V1 (observational only)](docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1.md)
- [Fundamental V2 Six Gates Version Compatibility V1 (shadow rejected)](docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1.md)
- [Fundamental V2 Six Gates Provenance Repair (source binding; activation still blocked)](docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR.md)
- [Fundamental V2 Six Gates Source Authority Repair 2 (independent score/holding authority; remaining sources blocked)](docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_2.md)
- [Final Six Gates authority routing closure (B08 compatibility closed; production source readiness separate and blocked)](docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_3.md)
- [Gate 3 Surveillance Source Readiness V1 (official NSE source feasibility; source-semantics repair required)](docs/architecture/GATE3_SURVEILLANCE_SOURCE_READINESS_V1.md)
- [Gate 3 Surveillance Policy / Source Repair V1 (complete-list evidence; status/temporal admission unresolved; no collector)](docs/architecture/GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.md)
- [Gate 3 Source Repair 2 (three formula inputs; source-status role resolved; approved timing requires versioned proposal)](docs/architecture/GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_2.md)
- [Gate 3 V2 / Composite .3 Proposal (PIT-visible effective surveillance; exact Gate-6 carry-forward; reviewed proposal input, not active)](docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.md)
- [Composite Execution Gate Policy V2 Governance Approval (one governed successor; Gate-3 timing and Gate-6 veto semantics; activation blocked)](docs/architecture/EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.md)
- [Gate 3 Prospective Source Collector V1 (immutable live capture; completeness/effectiveness blocked; no gate activation)](docs/architecture/GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1.md)
- [Gate 3 Surveillance Source-Capture Completeness Repair V1 (price-band file proof; ASM/GSM official-export feasibility is recorded separately; no gate activation)](docs/architecture/GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.md)
- [Gate 3 ASM/GSM Official Complete-Export Identity Feasibility Decision V1 (known official UI exports are not machine-verifiable; current APIs remain discovery-only; no gate activation)](docs/architecture/GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.md)
- [Official Earnings Calendar Source Governance V1 (candidate non-active; Gate 6 still not ready)](docs/architecture/EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1.md)
- [Official NSE/BSE Earnings Calendar Adapters V1 (bounded parsers/storage; live coverage partial; Gate 6 unwired)](docs/architecture/OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1.md)
- [Official Earnings Calendar Discovery Repair (exact joins; scoped coverage and strict PIT still blocked)](docs/architecture/OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_REPAIR.md)
- [Alternative Official Earnings Calendar Source Research V1 (source available; canonical identity bridge blocked)](docs/architecture/EARNINGS_CALENDAR_ALTERNATIVE_OFFICIAL_SOURCE_RESEARCH_V1.md)
- [Earnings Calendar Canonical Identity Bridge V1 (read-only identity resolved; known-at/window clearance remains unproven)](docs/architecture/EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1.md)
- [Earnings Calendar Known-at Semantics V1 (source-public versus HSI-first-observed; Gate 6 unwired)](docs/architecture/EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1.md)
- [Earnings Calendar Coverage / Window Policy V1 (non-active coverage/absence contract; five-session notice mismatch)](docs/architecture/EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1.md)
- [Earnings Blackout Horizon Policy Research V1 (V1 unchanged; source-aware V2 proposal required)](docs/architecture/EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1.md)
- [Earnings Blackout Policy V2 Proposal .2 (not active; veto/no-veto distinct from clearance, horizon unset, V1 immutable)](docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.md)
- [Earnings Blackout Policy V2 Governance Approval (conditional semantics only; activation blockers open, horizon unset, V1 unchanged)](docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.md)
- [Earnings Blackout Horizon Calibration Contract V1 (non-active measurement design; no numeric horizon, data partial)](docs/architecture/EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.md)
- [Prospective Earnings Schedule Receipt Readiness V1 (one bounded collector/receipt repair required; Gate 6 remains unchanged)](docs/architecture/EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1.md)
- [Prospective Earnings Schedule Receipt Collector V1 (immutable forward-only official evidence; Gate 6 V2 remains inactive)](docs/architecture/EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1.md)
- [Earnings Horizon Prospective Shadow V1 (Layer-1 observations; waiting for a live event; no selected horizon or Gate 6 activation)](docs/architecture/EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1.md)
- [Canonical Benchmark / Sector Technical History Closure V1](docs/architecture/CANONICAL_BENCHMARK_SECTOR_TECHNICAL_HISTORY_CLOSURE_V1.md)
- [Official NSE Index OHLC Availability Feasibility V1](docs/architecture/OFFICIAL_NSE_INDEX_OHLC_AVAILABILITY_FEASIBILITY_V1.md)
- [Official NSE Index OHLC Source-Name Reconciliation V1](docs/architecture/OFFICIAL_NSE_INDEX_OHLC_SOURCE_NAME_RECONCILIATION_V1.md)
- [Canonical Sector-Index Identity and Close Lineage Completion V1](docs/architecture/CANONICAL_SECTOR_INDEX_IDENTITY_AND_CLOSE_LINEAGE_COMPLETION_V1.md)
- [Canonical Sector-Index OHLC Lineage Remainder Closure V1](docs/architecture/CANONICAL_SECTOR_INDEX_OHLC_LINEAGE_REMAINDER_CLOSURE_V1.md)
- [Technical Peer Cohort Policy V1 candidate](docs/architecture/TECHNICAL_PEER_COHORT_POLICY_V1.md)
- [Rule Horizon / Timeframe Applicability Policy V1 — frozen definition; runtime partial](docs/architecture/RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1.md)
- [Canonical Security-to-Sector-Index Mapping Coverage Governance V1](docs/architecture/CANONICAL_SECURITY_TO_SECTOR_INDEX_MAPPING_COVERAGE_GOVERNANCE_V1.md)
- [Canonical Security Taxonomy Coverage, Source, and Identity V1](docs/architecture/CANONICAL_SECURITY_TAXONOMY_COVERAGE_SOURCE_AND_IDENTITY_V1.md)
- [NSE All-Listed Security Taxonomy Source Feasibility and Acquisition Policy V1](docs/architecture/NSE_ALL_LISTED_SECURITY_TAXONOMY_SOURCE_FEASIBILITY_AND_ACQUISITION_POLICY_V1.md)
- [NSE First-Party Quote Taxonomy Access and Schema Proof V1](docs/architecture/NSE_FIRST_PARTY_QUOTE_TAXONOMY_ACCESS_AND_SCHEMA_PROOF_V1.md)
- [NSE Quote Taxonomy Published Machine Contract Proof V1](docs/architecture/NSE_QUOTE_TAXONOMY_PUBLISHED_MACHINE_CONTRACT_PROOF_V1.md)
- [Canonical Daily Technical Bar Known-at and Completeness Evidence V1](docs/architecture/CANONICAL_DAILY_TECHNICAL_BAR_KNOWN_AT_AND_COMPLETENESS_EVIDENCE_V1.md)
- [Canonical Daily Source Session and Publication Semantics V1](docs/architecture/CANONICAL_DAILY_SOURCE_SESSION_AND_PUBLICATION_SEMANTICS_V1.md)
- [Canonical Technical Price Adjustment and Corporate-Action Integrity V1](docs/architecture/CANONICAL_TECHNICAL_PRICE_ADJUSTMENT_AND_CORPORATE_ACTION_INTEGRITY_V1.md)
- [Canonical Technical Source-Basis and Action-Coverage Decision V1](docs/architecture/CANONICAL_TECHNICAL_SOURCE_BASIS_AND_ACTION_COVERAGE_DECISION_V1.md)
- [Prospective Dhan Live-Bar Foundation V1](docs/architecture/PROSPECTIVE_DHAN_LIVE_BAR_FOUNDATION_V1.md)
- [Canonical Intraday Timeframe Derivation Policy V1 candidate](docs/architecture/CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1.md)
- [Canonical Prospective 15m Bar Derivation V1](docs/architecture/CANONICAL_PROSPECTIVE_15M_BAR_DERIVATION_V1.md)
- [Prospective Market-Data Runtime Orchestrator V1](docs/architecture/PROSPECTIVE_MARKET_DATA_RUNTIME_ORCHESTRATOR_V1.md)
- [Canonical 15m Technical Reader Activation V1](docs/architecture/CANONICAL_15M_TECHNICAL_READER_ACTIVATION_V1.md)
- [HSI Internal Technical Radar V1](docs/architecture/HSI_INTERNAL_TECHNICAL_RADAR_V1.md)
- [Radar to HSI Diagnostic Orchestration V1](docs/architecture/RADAR_TO_HSI_DIAGNOSTIC_ORCHESTRATION_V1.md)
- [NSE Canonical Corporate-Action Coverage Backfill V1](docs/architecture/NSE_CANONICAL_CORPORATE_ACTION_COVERAGE_BACKFILL_V1.md)
- [NSE Canonical Daily Price-History Source Feasibility V1](docs/architecture/NSE_CANONICAL_DAILY_PRICE_HISTORY_SOURCE_FEASIBILITY_V1.md)
- [NSE UDiFF Final Bhavcopy Archive and Basis Proof V1](docs/architecture/NSE_UDIFF_FINAL_BHAVCOPY_ARCHIVE_AND_BASIS_PROOF_V1.md)
- [NSE UDiFF Canonical Daily Price-History Backfill V1](docs/architecture/NSE_UDIFF_CANONICAL_DAILY_PRICE_HISTORY_BACKFILL_V1.md)
- [NSE UDiFF Daily History Integrity and Continuity Closure V1](docs/architecture/NSE_UDIFF_DAILY_HISTORY_INTEGRITY_AND_CONTINUITY_CLOSURE_V1.md)
- [NSE UDiFF Identity and Conflict Semantics: Storage Repair Checkpoint](docs/architecture/NSE_UDIFF_CONFLICT_SEMANTICS_AND_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_V1.md)
- [NSE UDiFF Series-Aware Observation Storage Repair V1](docs/architecture/NSE_UDIFF_SERIES_AWARE_OBSERVATION_STORAGE_REPAIR_V1.md)
- [NSE UDiFF Historical Security Identity Continuity Promotion V1](docs/architecture/NSE_UDIFF_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_PROMOTION_V1.md)
- [NSE UDiFF Daily Technical Eligibility and Continuity Certification V1](docs/architecture/NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1.md)
- [NSE UDiFF Effective-Dated Identity and Action-Window Coverage Completion V1](docs/architecture/NSE_UDIFF_EFFECTIVE_DATED_IDENTITY_AND_ACTION_WINDOW_COVERAGE_COMPLETION_V1.md)
- [NSE UDiFF Daily Technical Read Activation V1](docs/architecture/NSE_UDIFF_DAILY_TECHNICAL_READ_ACTIVATION_V1.md)
- [NSE UDiFF Resolved-Conflict Eligibility Repair V1](docs/architecture/NSE_UDIFF_RESOLVED_CONFLICT_ELIGIBILITY_REPAIR_V1.md)
- [HSI Storage Footprint and Repository-Size Audit V1](docs/architecture/HSI_STORAGE_FOOTPRINT_AND_REPOSITORY_SIZE_AUDIT_V1.md)
- [Canonical Filing Timestamp Timezone Provenance V1](docs/architecture/CANONICAL_FILING_TIMESTAMP_TIMEZONE_PROVENANCE_V1.md)
- [Inflection Accounting-only Prospective Shadow V1](docs/architecture/INFLECTION_ACCOUNTING_ONLY_PROSPECTIVE_SHADOW_V1.md)
- [Multi-Funnel Discovery Contract and Registry V1](docs/architecture/MULTI_FUNNEL_DISCOVERY_CONTRACT_AND_REGISTRY_V1.md)
- [Multi-Funnel Discovery Adapters V1](docs/architecture/MULTI_FUNNEL_DISCOVERY_ADAPTERS_V1.md)
- [Multi-Funnel Candidate Union and Identity V1](docs/architecture/MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md)
- [Whole-Market Multi-Funnel Orchestration V1](docs/architecture/MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md)
- [Discovery Recall Audit Contract and Outcome Classification V1](docs/architecture/DISCOVERY_RECALL_AUDIT_CONTRACT_AND_OUTCOME_CLASSIFICATION_V1.md)
- [Discovery Recall Reference Outcome and Matching V1](docs/architecture/DISCOVERY_RECALL_REFERENCE_OUTCOME_AND_MATCHING_V1.md)
- [Discovery Recall Per-Security Evaluation Trace V1](docs/architecture/DISCOVERY_RECALL_PER_SECURITY_EVALUATION_TRACE_V1.md)
- [Long-Term Policy Transmission Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_POLICY_TRANSMISSION_RESEARCH_SHADOW_V1.md)
- [Long-Term Thesis Invalidation Lifecycle Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_THESIS_INVALIDATION_LIFECYCLE_RESEARCH_SHADOW_V1.md)
- [Long-Term Portfolio Observation Adapter Research Shadow V1](docs/architecture/POST_V1_LONG_TERM_PORTFOLIO_OBSERVATION_ADAPTER_RESEARCH_SHADOW_V1.md)
- [Long-Term Compounder Policy Research Proposal V1](docs/architecture/POST_V1_LONG_TERM_COMPOUNDER_POLICY_RESEARCH_PROPOSAL_V1.md)
- [Long-Term Compounder Canonical Annual Facts V1](docs/architecture/POST_V1_LONG_TERM_COMPOUNDER_CANONICAL_ANNUAL_FACTS_V1.md)
- [Compounder Testable Derived Metrics V1](docs/architecture/POST_V1_COMPOUNDER_TESTABLE_DERIVED_METRICS_V1.md)
- [Compounder Backtest Universe Readiness and PIT Dataset V1](docs/architecture/POST_V1_COMPOUNDER_BACKTEST_UNIVERSE_READINESS_AND_PIT_DATASET_V1.md)
- [Compounder Backtest Panel Readiness V2](docs/architecture/COMPOUNDER_BACKTEST_PANEL_READINESS_V2.md)
- [Compounder Prospective Shadow Validation V1](docs/architecture/COMPOUNDER_PROSPECTIVE_SHADOW_VALIDATION_V1.md)
- [Historical Security Identity and Lifecycle Primary Evidence V1](docs/architecture/HISTORICAL_SECURITY_IDENTITY_AND_LIFECYCLE_PRIMARY_EVIDENCE_V1.md)
- [PIT Company-Type Classification Research and Contract V1](docs/architecture/PIT_COMPANY_TYPE_CLASSIFICATION_RESEARCH_AND_CONTRACT_V1.md)
- [PIT Company-Type Classification Activation V1](docs/architecture/PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1.md)
- [PIT Regulator Company-Type Evidence Ingestion V1](docs/architecture/PIT_REGULATOR_COMPANY_TYPE_EVIDENCE_INGESTION_V1.md)
- [Regulator–Issuer Exact Legal-Name Correspondence Policy Proposal V1](docs/architecture/REGULATOR_ISSUER_EXACT_LEGAL_NAME_CORRESPONDENCE_POLICY_PROPOSAL_V1.md)
- [Regulator–Issuer RAW_EXACT Linkage Activation V1](docs/architecture/REGULATOR_ISSUER_RAW_EXACT_LINKAGE_ACTIVATION_V1.md)
- [Historical Regulator Company-Type Evidence Acquisition V1](docs/architecture/HISTORICAL_REGULATOR_COMPANY_TYPE_EVIDENCE_ACQUISITION_V1.md)
- [NSE Taxonomy Company-Type Code-Map Proposal V1](docs/architecture/NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_PROPOSAL_V1.md)
- [NSE Taxonomy Company-Type Code-Map Activation V1](docs/architecture/NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_ACTIVATION_V1.md)
- [Historical NSE Taxonomy Assignment Acquisition V1](docs/architecture/HISTORICAL_NSE_TAXONOMY_ASSIGNMENT_ACQUISITION_V1.md)
- [Issuer / Legal-Entity ↔ Listed-Security Identity Bridge — Primary Evidence V1](docs/architecture/ISSUER_LEGAL_ENTITY_SECURITY_IDENTITY_BRIDGE_PRIMARY_EVIDENCE_V1.md)
- [Exact Issuer-Identifier Primary Acquisition V1](docs/architecture/EXACT_ISSUER_IDENTIFIER_PRIMARY_ACQUISITION_V1.md)
- [BRSR Primary Issuer-Identifier Backfill V1](docs/architecture/BRSR_PRIMARY_ISSUER_IDENTIFIER_BACKFILL_V1.md)
- [ISIN ↔ Issuer Bridge Continuity Policy Proposal V1](docs/architecture/ISIN_ISSUER_BRIDGE_CONTINUITY_POLICY_PROPOSAL_V1.md)
- [BRSR Issuer Anchor Session-Master Backfill V1](docs/architecture/BRSR_ISSUER_ANCHOR_SESSION_MASTER_BACKFILL_V1.md)
- [ISIN Issuer Bridge Continuity Activation V1](docs/architecture/ISIN_ISSUER_BRIDGE_CONTINUITY_ACTIVATION_V1.md)
- [Sell/Risk, Profit-Harvesting and Fast-Rotation policy approval pack](docs/architecture/POST_V1_SELL_PROFIT_ROTATION_POLICY_PROPOSAL.md)
- [Post-V1 primary-source policy research pack](docs/architecture/POST_V1_POLICY_RESEARCH_PACK.md)
- [Post-V1 Fast-Rotation comparison foundation](docs/architecture/POST_V1_FAST_ROTATION_FOUNDATION.md)
- [Live-readiness hardening candidate (not approved)](docs/architecture/live_readiness_candidate.md)
- [Economic and news intelligence](docs/architecture/economic_news_intelligence.md)
- [Controlled real-Brain trial](docs/architecture/real_brain_trial.md)
- [Minimum viable real-data package](docs/architecture/minimum_real_data_package.md)

Repository documentation and tested code are authoritative over chat or memory.
The hardened architecture is additive: it reuses existing engines and never
turns a diagnostic, score, gate, rotation result, self-improvement observation,
or API read into autonomous execution.

- [Master specification](docs/NSE_STOCK_MANAGER_V2_1_MASTER_SPEC.md)
- [Development roadmap](docs/ROADMAP.md)
- [Foundation architecture](docs/ARCHITECTURE.md)
- [Strategy governance](docs/STRATEGY_GOVERNANCE.md)
- [Technical analysis](docs/TECHNICAL_ANALYSIS.md)
- [Market regime](docs/MARKET_REGIME.md)
- [Crisis and market-dislocation engine](docs/CRISIS_MARKET_DISLOCATION_ENGINE.md)
- [Market extremes and upside euphoria engine](docs/MARKET_EXTREMES_ENGINE.md)
- [Market-data architecture](docs/MARKET_DATA_ARCHITECTURE.md)
- [Data-provider integration boundary](docs/DATA_PROVIDER_INTEGRATION.md)
- [Streaming market-data boundary](docs/STREAMING_MARKET_DATA.md)
- [Historical market-data ingestion](docs/HISTORICAL_MARKET_DATA.md)
- [Market breadth aggregation](docs/MARKET_BREADTH.md)
- [Runtime pipeline](docs/RUNTIME_PIPELINE.md)
- [Data-source architecture](docs/DATA_SOURCE_ARCHITECTURE.md)
- [Corporate filings](docs/CORPORATE_FILINGS.md)
- [NSE official-export import](docs/NSE_OFFICIAL_IMPORT.md)
- [Global Datafeeds historical adapter](docs/GLOBAL_DATAFEEDS.md)
- [yfinance secondary historical adapter](docs/YFINANCE.md)
- [Canonical fundamentals](docs/FUNDAMENTALS.md)
- [Data freshness and quality](docs/DATA_FRESHNESS.md)
- [Relative strength](docs/RELATIVE_STRENGTH.md)
- [Diagnostic registry](docs/DIAGNOSTIC_REGISTRY.md)
- [Scoring policy](docs/SCORING_POLICY.md)
- [Execution gates](docs/EXECUTION_GATES.md)
- [Execution-gate engine](docs/EXECUTION_GATE_ENGINE.md)
- [Friction model](docs/FRICTION_MODEL.md)
- [Portfolio heat](docs/PORTFOLIO_HEAT.md)
- [Portfolio model](docs/PORTFOLIO_MODEL.md)
- [Portfolio accounting](docs/PORTFOLIO_ACCOUNTING.md)
- [Portfolio snapshots](docs/PORTFOLIO_SNAPSHOTS.md)
- [Capital rotation](docs/CAPITAL_ROTATION.md)
- [Public capital-rotation API contract](docs/FRONTEND_API_CONTRACT.md#endpoint-inventory)
- [Rotation matrix](docs/ROTATION_MATRIX.md)
- [Anti-churn](docs/ANTI_CHURN.md)
- [Signal lifecycle](docs/SIGNAL_LIFECYCLE.md)
- [Trade-plan orchestration](docs/TRADE_PLAN_ORCHESTRATION.md)
- [Paper trading](docs/PAPER_TRADING.md)
- [Paper fill model](docs/PAPER_FILL_MODEL.md)
- [Paper outcomes](docs/PAPER_OUTCOMES.md)
- [Earnings blackout](docs/EARNINGS_BLACKOUT.md)
- [Exchange calendar](docs/EXCHANGE_CALENDAR.md)
- [Backtest engine boundary](docs/BACKTEST_ENGINE.md)
- [Backtest replay clock](docs/BACKTEST_REPLAY_CLOCK.md)
- [Backtest run lifecycle](docs/BACKTEST_RUN_LIFECYCLE.md)
- [Backtest event log](docs/BACKTEST_EVENT_LOG.md)
- [Walk-forward validation](docs/WALK_FORWARD_VALIDATION.md)
- [Out-of-sample validation](docs/OUT_OF_SAMPLE_VALIDATION.md)
- [OOS aggregation](docs/OOS_AGGREGATION.md)
- [OOS stability analysis](docs/OOS_STABILITY_ANALYSIS.md)
- [Controlled strategy experiments](docs/CONTROLLED_STRATEGY_EXPERIMENTS.md)
- [Parameter robustness](docs/PARAMETER_ROBUSTNESS.md)
- [Candidate selection](docs/CANDIDATE_SELECTION.md)
- [Future OOS candidate queue](docs/FUTURE_OOS_CANDIDATE_QUEUE.md)
- [Future OOS execution](docs/FUTURE_OOS_EXECUTION.md)
- [Feature flags and runtime capabilities](docs/FEATURE_FLAGS.md)
- [API architecture](docs/API_ARCHITECTURE.md)
- [API reference](docs/API_REFERENCE.md)
- [Frontend API contract](docs/FRONTEND_API_CONTRACT.md)
- [Stock and portfolio frontend contract](docs/FRONTEND_API_CONTRACT.md#endpoint-inventory)
- [Google AI Studio frontend specification](docs/FRONTEND_GOOGLE_AI_STUDIO_SPEC.md)
- [Local backend setup](docs/LOCAL_BACKEND_SETUP.md)
- [Promotion evidence package](docs/PROMOTION_EVIDENCE_PACKAGE.md)
- [Strategy promotion governance](docs/STRATEGY_PROMOTION_GOVERNANCE.md)
- [Strategy versioning and activation](docs/STRATEGY_VERSIONING_AND_ACTIVATION.md)
- [Strategy rollback](docs/STRATEGY_ROLLBACK.md)
- [Historical execution timing](docs/HISTORICAL_EXECUTION_TIMING.md)
- [Historical capital allocation](docs/HISTORICAL_CAPITAL_ALLOCATION.md)
- [Historical paper-ledger integration](docs/HISTORICAL_PAPER_LEDGER_INTEGRATION.md)
- [Historical performance integration](docs/HISTORICAL_PERFORMANCE_INTEGRATION.md)
- [Historical benchmark integration](docs/HISTORICAL_BENCHMARK_INTEGRATION.md)
- [Historical equity series](docs/HISTORICAL_EQUITY_SERIES.md)
- [Historical analytical replay](docs/HISTORICAL_ANALYTICAL_REPLAY.md)
- [Historical backtest portfolio replay](docs/HISTORICAL_PORTFOLIO_REPLAY.md)
- [Historical portfolio-context gates](docs/HISTORICAL_PORTFOLIO_GATES.md)
- [Historical capital-rotation replay](docs/HISTORICAL_ROTATION_REPLAY.md)
- [Historical signal replay](docs/HISTORICAL_SIGNAL_REPLAY.md)
- [Historical paper-trade replay](docs/HISTORICAL_PAPER_TRADE_REPLAY.md)
- [Research policy](docs/RESEARCH_POLICY.md)
- [Benchmark policy](docs/BENCHMARK_POLICY.md)
- [Diagnostic evaluation](docs/DIAGNOSTIC_EVALUATION.md)
- [Sector analysis](docs/SECTOR_ANALYSIS.md)
- [Volume analysis](docs/VOLUME_ANALYSIS.md)
- [Ichimoku and multi-timeframe analysis](docs/ICHIMOKU.md)
- [VWAP and OBV](docs/VWAP_OBV.md)
- [Fundamental data](docs/FUNDAMENTAL_DATA.md)
- [Financial metrics](docs/FINANCIAL_METRICS.md)
- [Earnings acceleration](docs/EARNINGS_ACCELERATION.md)
- [Ownership analysis](docs/OWNERSHIP_ANALYSIS.md)
- [Order-book analysis](docs/ORDER_BOOK_ANALYSIS.md)
- [Research intelligence](docs/RESEARCH_INTELLIGENCE.md)
- [Source reliability](docs/SOURCE_RELIABILITY.md)
- [Claim model](docs/CLAIM_MODEL.md)
- [Guidance tracking](docs/GUIDANCE_TRACKING.md)
- [Catalyst engine](docs/CATALYST_ENGINE.md)
- [Valuation analysis](docs/VALUATION_ANALYSIS.md)
- [Pattern analysis](docs/PATTERN_ANALYSIS.md) — transparent V1 VCP, Flat Base, Cup & Handle, and Ascending Base approximations
- [Trade structures](docs/TRADE_STRUCTURE.md)
- [Risk/reward](docs/RISK_REWARD.md)
- [Thesis invalidation](docs/THESIS_INVALIDATION.md)
- [Liquidity and SMC proxies](docs/LIQUIDITY_SMC.md)
- [Wyckoff analysis](docs/WYCKOFF_ANALYSIS.md)
- [Smart-money proxies](docs/SMART_MONEY_PROXIES.md)
- [Trap detection](docs/TRAP_DETECTION.md)
- [Volume climax](docs/VOLUME_CLIMAX.md)
- [Crowd sentiment](docs/CROWD_SENTIMENT.md)
- [Crowd confidence](docs/CROWD_CONFIDENCE.md)
- [Contrarian engine](docs/CONTRARIAN_ENGINE.md)
- [Post-news reaction](docs/POST_NEWS_REACTION.md)
- [Risk engine](docs/RISK_ENGINE.md)
- [Trading thesis](docs/TRADING_THESIS.md)
- [Investment thesis](docs/INVESTMENT_THESIS.md)
- [Scenario engine](docs/SCENARIO_ENGINE.md)
- [Decision Score](docs/DECISION_SCORE.md)
- [Scoring components](docs/SCORING_COMPONENTS.md)

Decision Scorecards and execution-gate evaluations are persisted immutably with their dependencies and can be audit-reconstructed. They remain analytical artifacts only.

## Current status

The project uses Python 3.12+, frozen dataclasses and enums for domain models, SQLite from the Python standard library, and pytest for tests. No production dependency is required. Phase 9A is complete. Phase 9B is partially complete and deferred for automatic production orchestration: its future runtime capability defaults to disabled, while the reusable research/OOS services remain available for tests and controlled manual use.

The #027A market-data foundation is provider-neutral and currently includes only
a deterministic static/mock provider. It defines canonical identity, facts,
normalization, quality, freshness, provenance, capabilities, and local storage;
it does not call an external provider, open a WebSocket, use credentials, expose
a live-data endpoint, or connect to a broker.

Kotak Neo is the first read-only adapter behind that boundary. It is selected
only with `MARKET_DATA_PROVIDER=kotak_neo`, has no live market-data FastAPI route or background
activation, and supports only explicitly mapped current quote/index/VIX facts.
It cannot place/modify/cancel orders, access a portfolio/demat account, or open
a WebSocket. See [Kotak Neo integration](docs/KOTAK_NEO_INTEGRATION.md).

Normal local provider configuration can instead use the secret-free connection
profile API backed by the OS credential manager; PowerShell variables remain a
developer fallback. See [connection management](docs/CONNECTION_MANAGEMENT.md).
This local/private settings flow can save, test, and clear data-provider
credentials but cannot access an account, trade, promote/activate a strategy,
or mutate a portfolio.

Performance reports and benchmark inputs are immutable as-of artifacts: newer paper trades or market observations create newer reports rather than changing prior historical reports.

The implemented flow is:

`mock data → validated as-of snapshot → deterministic diagnostics → immutable Decision Scorecard → execution gates → portfolio state → rotation comparison → non-executable signal lifecycle → future paper-trading layer`

### Candidate strategy setup

The candidate setup layer has separate positional pre-breakout and fundamental
inflection modules. They consume frozen market/macro/sector/company/catalyst
evidence and can produce only a research candidate with Setup Quality,
structural trigger/invalidation/target, R:R, horizon, coverage, and warnings.
Setup Quality is not Decision Score, confidence, a gate, or a final action.
Every candidate still proceeds through the canonical 61 diagnostics, score,
confidence, gates, portfolio comparison, and execution boundaries. See
[pre-breakout and inflection architecture](docs/architecture/pre_breakout_inflection.md).

### Real-data taxonomy and coverage

The project distinguishes current NSE universe membership from historical
membership, sectors from macro themes, and code support from actually stored
data. The append-only taxonomy import is ISIN-first and local-file-only;
`python -m app.runtime coverage-report` shows evidence coverage and data-engineering
gaps without contacting a provider or scanning the universe. See
[taxonomy](docs/architecture/taxonomy.md) and
[data coverage](docs/architecture/data_coverage.md).
The first-party source and exact-identity coverage boundary is recorded in
[Canonical Security Taxonomy Coverage, Source, and Identity V1](docs/architecture/CANONICAL_SECURITY_TAXONOMY_COVERAGE_SOURCE_AND_IDENTITY_V1.md).

### Historical security integrity

Historical identity, universe membership, corporate actions, and price
adjustment basis are separate from today’s NSE universe. The historical security
master keeps effective-date provenance and rejects mixed or raw-across-split
price series as technical inputs rather than silently changing history. See
[historical security master](docs/architecture/historical_security_master.md).
The bounded official NSE dated-security-master boundary is documented in
[NSE Historical MII Security Master Snapshot Acquisition V1](docs/architecture/NSE_HISTORICAL_MII_SECURITY_MASTER_SNAPSHOT_ACQUISITION_V1.md).
The follow-on same-session identity interpretation remains a non-active,
human-approval-gated proposal in
[NSE Security Master Session-Knownness Policy Proposal V1](docs/architecture/NSE_SECURITY_MASTER_SESSION_KNOWNNESS_POLICY_PROPOSAL_V1.md).
Its separately recorded approved activation is limited to discrete session
observations in
[NSE Session-Known Security Identity Activation V1](docs/architecture/NSE_SESSION_KNOWN_SECURITY_IDENTITY_ACTIVATION_V1.md);
it does not create listing intervals or survivorship-safe historical coverage.

The initial FastAPI boundary exposes `/health`, `/api/v1/system/status`,
`/api/v1/system/version`, and read-only portfolio snapshot, holdings, and
summary routes, plus injected read-only market-regime and sector routes.
OpenAPI is available at `/openapi.json` and `/docs`. It does not mutate
portfolios, start research, calculate new analytics, connect to live data, or
invoke a broker.

The primary stock-detail route is `/api/v1/stocks/{symbol}/analysis`. It maps
existing analysis only; its data can be partial/stale, preserves score and
confidence separately, and does not turn smart-money proxies into institutional
facts.

Read-only signal and simulated paper-trade views are available at
`/api/v1/signals`, `/api/v1/signals/{signal_id}`, `/api/v1/paper-trades`,
`/api/v1/paper-trades/{trade_id}`, and `/api/v1/paper-trades/performance` when
an application composition layer injects stored records. These routes never
generate, execute, fill, or exit a trade; output performance is stored
canonical simulated-paper evidence, and open trades can have legitimately
incomplete outcome fields.

Historical replay currently stops at deterministic calendar scheduling, immutable run metadata, and append-only placeholder events. It does not replay a strategy or execute analytical/trading layers.

Historical analytical replay can build frozen snapshots and persist diagnostic, Decision Scorecard, and gate artifacts. It creates no signals, orders, paper trades, performance reports, or benchmark results.

Historical replay regression fixtures verify that future market, index, sector, financial/restatement, research/crowd, surveillance, earnings-schedule, and universe records do not retrospectively change an earlier evaluation.

All 61-rule V1 diagnostic wrappers and the deterministic Decision Score are implemented. Gates determine analytical eligibility only; they do not execute orders or create signals.

## Install and run

Create and activate a virtual environment, then install the development test dependency:

```sh
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the verification suite:

```sh
python -m pytest
```

Start the local HTTP backend:

```sh
python -m uvicorn app.api.main:app --reload
```

Run a small mock-data foundation demonstration:

```sh
python -m app.testing.foundation_demo
```

The local runtime boundary is explicit and disabled by default. Once a local
host has composed stored data plus an explicit universe, `python -m app.runtime
run-once --universe <id>` runs one cycle; add `--dry-run` to prevent snapshot
publication. `python -m app.runtime status` reads safe process-lifetime runtime
health only. The optional `worker` command requires an explicit enabled setting
and does not start from FastAPI.

`GET /api/v1/data-sources/status` exposes sanitized source readiness for local
development. It distinguishes stored data from live providers, labels mock only
when explicitly configured, and does not claim a Kotak historical endpoint.

## Current limitations

- The crisis/dislocation engine is a provider-neutral policy and domain
  foundation only. It has no live market/breadth/VIX/liquidity feed, calibrated
  thresholds, runtime activation, API endpoint, broker/order behavior, or
  automatic strategy change. It treats cash as deliberate optionality, not a
  missing BUY, and does not encode blanket liquidation or blind dip buying.
- The market-extremes upside tail is also architecture-only. Euphoria is
  evidence-based risk context, not proof of a top or an automatic sell. It has
  no live price/IPO/news/social inputs, calibrated thresholds, provider, broker,
  API endpoint, automatic rotation, or strategy mutation.

- Self-improvement observation is deterministic and association-only. It can summarize frozen recurring evidence but cannot claim causal attribution, generate a hypothesis or experiment, modify a strategy, approve/activate a version, or affect any account.
- Structured self-improvement hypotheses and human research reviews are immutable and research-only. A human `APPROVE_FOR_EXPERIMENT` review is not an experiment, candidate selection, strategy promotion, or activation.
- A reviewed hypothesis may create one immutable, budget-bounded `PLANNED` controlled-experiment draft. Draft creation does not execute an experiment, generate evidence, select a candidate, promote, or activate a strategy.
- There is no automatic self-improvement scheduler. `AUTOMATED_SELF_IMPROVEMENT_RESEARCH` is an experimental, deferred, disabled-by-default future-runtime capability; enabling it only permits a future orchestrator and does not itself start research or change strategy/governance records.

- SQLite is a local-development adapter only; PostgreSQL is intentionally deferred behind the repository interface.
- Fixtures are deterministic and contain mock values only.
- Technical analysis is limited to deterministic SMA, EMA, RSI, ATR, ADX, pivots, trend, market regime, relative performance, sector-return proxies, RVOL, Ichimoku, VWAP, and OBV using mock fixtures.
- Sector rotation and OBV/RVOL outputs are observable price-volume proxies, not factual fund-flow or institutional-activity conclusions. Value Area is unavailable unless real volume-at-price data is supplied.
- There are no data-provider adapters, position sizing, paper-trade fills/outcomes, broker APIs, real-money workflows, or autonomous trading.
- The HTTP API has no signal/paper mutation route, broker/demat access, live
  order behavior, or real-account mutation. Its paper-trade endpoints expose
  simulations only.
- Read-only performance, benchmark, and governance endpoints expose stored
  immutable records only. Benchmark unavailable states and TRAIN/VALIDATION/
  TEST/OOS identities remain visible; approved strategy is not active without
  an explicit activation. There is no API promotion, approval, activation,
  rollback, backtest, or benchmark execution endpoint.
- Validation fails closed: only explicitly `VALID` observations are eligible for downstream analysis.
- Strategy governance stores record structures and approval history only; it does not approve, activate, or calculate a real strategy automatically.
- Replay orchestration supports daily-close scheduling only. It has no chronological strategy replay, diagnostics/gates/signal integration, fills, outcomes, backtests, benchmarks, optimization, or walk-forward validation.

The next task should be selected from the roadmap; it must not introduce live execution until that capability is explicitly approved and safely designed.

## API foundation status

**PHASE 10 / #026A — PRODUCTION API FOUNDATION: COMPLETE.** The FastAPI
architecture and read-only domain endpoints are stable for local/private
development. This is not a public production deployment: SQLite is
development-oriented, and authentication/user tenancy, providers/current market
data, mutation APIs, broker integration, OpenAI runtime, automated Phase 9B
runtime, and frontend work remain deferred. Do not expose it publicly.

## Database foundation

SQLite remains the safe local/test default. PostgreSQL is now an explicit lazy
production-persistence option with Alembic infrastructure and one representative
immutable approved-strategy-version adapter. See
[`docs/POSTGRESQL_SETUP.md`](docs/POSTGRESQL_SETUP.md) and
[`docs/DATABASE_ARCHITECTURE.md`](docs/DATABASE_ARCHITECTURE.md). The app builds
the configured read repository lazily in its lifespan and no route runs a
migration; full repository migration, production PostgreSQL validation, provider
wiring, and live behavior remain deferred.

Core Phase 10 API read models are persisted as immutable versioned snapshots
through either SQLite or PostgreSQL adapters. At FastAPI lifespan startup, the
default read facades use that configured repository; explicit injected facades
remain supported for tests and local composition. SQLite is the local-safe
default, while PostgreSQL is explicit and lazy. Empty stores fail safely and
there is no API snapshot writer, live provider, research runner, governance
mutation, broker, or account effect. Broader normalized historical/Phase 9B
migrations and real PostgreSQL-server validation remain out of scope.

**#026B — PRODUCTION PERSISTENCE FOUNDATION: COMPLETE FOR V1 READ PATH.** This
is not a public deployment or a claim that every repository family is migrated.
### Optional secondary news

The backend can optionally ingest provider-returned GNews metadata for research context.  Configure it separately from `CURRENT_QUOTES` (Kotak Neo) and `HISTORICAL_OHLCV` (Global Datafeeds).  GNews is not a primary filing feed, does not fetch article pages, may be delayed depending on plan, and cannot change a score, gate, order, or active strategy.
### Primary-market evidence

Official NSE-supplied IPO/issue exports can be imported locally for factual issue, subscription, and listing context. Fresh issue and OFS are preserved separately. This is optional evidence for the existing Market Extremes input boundary—not a market-top, trading, or scoring engine.

### Dashboard market breadth, extremes, and crisis

The Dashboard consumes distilled, read-only persisted snapshots at
`/api/v1/market/breadth`, `/api/v1/market/extremes`, and
`/api/v1/market/crisis`. They expose only public canonical state and factual
summary fields plus timestamp/freshness/warnings; they never call a provider or
re-run market analytics on request. Missing data is shown as unavailable, not
NORMAL. Euphoria is elevated speculation/chase-risk context rather than a
market-top or SELL call, and crisis is a risk overlay rather than an automatic
liquidation or dip-buying instruction.

### Signals, paper trading, performance, and benchmark frontend

The remaining market-review pages consume only their read-only API contracts.
Signals and paper trades show public lifecycle, distilled plan or outcome fields,
warnings, and safe stock links; they cannot execute or change a trade.
Performance reports and benchmark comparisons require explicit selectors and
display backend-computed KPI summaries only. Browser code does not calculate
scores, indicators, performance metrics, or time series, and public responses
exclude audit provenance/evidence IDs and diagnostic/gate internals.

### Portfolio screenshot import

The Portfolio page accepts a bounded set of JPG/PNG/WebP broker screenshots as
a temporary extraction draft. Each row is provisional and must be reviewed and
explicitly confirmed before entering the canonical append-only portfolio
repository. Raw screenshots, unrelated account text, and OCR text are not kept
in the draft or exposed by the API. The default extractor is unavailable until
an approved server-side provider is configured; no provider key belongs in the
frontend. Screenshot LTP never replaces canonical market data. `MERGE` is not
supported yet; confirmation requires explicit `REPLACE`.

### Controlled portfolio analysis

After confirmation, `Analyze Portfolio` can queue a job pinned to the exact
portfolio snapshot. It is holdings-only and enters the existing backend
analysis/runtime boundary; it does not scan NSE, invent external candidates, or
place orders. Job completion is separate from diagnostic completeness. The
registry has 61 canonical definitions, but the current live orchestration does
not assemble every rule’s required inputs, so unavailable evidence remains
partial rather than being treated as a complete 61-diagnostic result.

### Stored NSE universe opportunity pipeline

The read-only opportunity workflow uses an official/stored NSE universe,
coverage preflight, eligibility, all-61 canonical analysis, Decision Score,
confidence, six gates, candidate materialization, and the existing capital
rotation engine. Data coverage is separate from stock scoring: missing history,
fundamentals, filings, research, ownership, market, or sector context remains
visible as `PARTIAL`/`MISSING`. A full-coverage claim is made only when the
entire intended eligible universe completed analysis and materialization;
otherwise candidates are explicitly “among the analyzed opportunity set.” This
workflow has no broker, order, demat, promotion, approval, or activation effect.

### Real-data readiness and controlled NSE imports

`python -m app.runtime import-nse-universe <official-local-csv> [--dry-run]`
accepts only an explicit local official NSE equity export.  It reports raw,
eligible, excluded, duplicate, and missing-sector/industry counts; a non-dry
run freezes an immutable `UniverseSnapshot`.  It never downloads or scrapes a
universe. `python -m app.runtime data-readiness` (or `universe-status`) reports
declared source configuration/readiness without testing a provider or printing
credentials. A configured source is not a validated source.

The intended real-data flow is: official NSE universe → canonical identity and
provider mappings → explicit provider/official ingestion → canonical stores →
coverage preflight → 61 diagnostics → score/confidence/gates → opportunity set
→ existing capital rotation. Kotak Neo remains the current-quote source and
Global Datafeeds and Upstox Historical Candle V3 remain independently
selectable historical-OHLCV sources. Upstox uses an exact official instrument
key and retains unknown adjustment semantics unless separate action evidence
proves more. Neither source is selected as a silent fallback.
Missing mappings, history, fundamentals, filings, ownership, news, or market
context block a full scan rather than being fabricated. No full live NSE scan,
broker action, or automatic strategy change is started by these commands.

For a first local dataset: (1) obtain an official NSE equity-universe CSV and
save it locally, (2) run `python -m app.runtime import-nse-universe <file>
--dry-run`, (3) rerun without `--dry-run`, then (4) run `python -m app.runtime
universe-status` and `python -m app.runtime data-readiness`. Runtime commands
default to the relative persistent SQLite path `data/nse_stock_manager.db`
unless an explicit `DATABASE_URL` selects SQLite or PostgreSQL. Neither command
contacts a provider or accepts credentials.
