# Gate-1 Rotation Paired Scenario Research Protocol V1

Status: `PROTOCOL_DEFINED_WITH_POLICY_BLOCKERS / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE`

**B — `PAIRED_SCENARIO_RESEARCH_PROTOCOL_READY_WITH_POLICY_BLOCKERS`.**

Protocol: `gate1-rotation-paired-scenario-research-protocol / v1`.
Protocol fingerprint:
`sha256:b45af9573b36d727619f630aad5990ba44ff9a7f84c4d9a489a602b6c950a7dd`.
Baseline: `2b303367eddf80697a5cb1bc601bfab3c731911e`, `main`, initially clean.

This is a bounded research-protocol/governance/conformance slice, not a model,
cohort generator, database schema, collection job or runtime integration.
The [machine artifact](GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json)
is the closed wire vocabulary and normative requirements; [offline conformance tests](../../tests/unit/test_gate1_rotation_paired_scenario_research_protocol.py)
demonstrate synthetic admission/rejection witnesses only. No historical event,
paper trade, label, expected return or producer is created in production.

## 1. Immutable predecessors and decision

The [feasibility audit](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.md)
remains `SCENARIO_MODEL_NOT_YET_FEASIBLE`, fingerprint
`sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3`.
The earlier [economic contract](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.md)
remains `gate1-rotation-economic-scenario / v1`, fingerprint
`sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14`.

`six-gates-production-v1 / v1` stays **ACTIVE**. Execution Gate V2 stays
**NOT_ACTIVE**. Same selected parcel, common cutoff/horizon/capital, INR,
independent score advantage >= 1.00 and strictly positive net-INR hurdles,
cost-exclusive endpoints, mandatory tax/slippage and once-only friction remain
unchanged. This protocol's research admission does not evaluate those hurdles.

B is appropriate: the research envelope, two temporal partitions, conditional
admission, immutable labels and rejection accounting can be frozen now.
Named policy dependencies prevent numerical horizon binding and actual cohort
admission. A would obscure these blockers; C would incorrectly imply that even
a responsible conditional research protocol cannot be specified.

## 2. Repository-grounded event-origin audit

The following classifications describe available **contracts**, not admitted
production events. YES means that the source carries the named field, not that
a particular record is authenticated. CONDITIONAL means exact transitive
references must resolve. No candidate currently proves all required paired
inputs, including the selected parcel and common horizon.

| Source | Existing schema / owner | Identity / cutoff | Incumbent / challenger / parcel | Horizon context | PIT / replay | Research use |
| --- | --- | --- | --- | --- | --- | --- |
| `HISTORICAL_ROTATION` | [HistoricalRotationEvaluation + BacktestRun + HistoricalAnalyticalSnapshot/context refs](../../app/backtest/models.py) | YES / YES | CONDITIONAL / CONDITIONAL / NO | CATEGORICAL_OR_CONFIG_ONLY | CONDITIONAL / CONDITIONAL | `CONDITIONAL_ORIGIN_ONLY` |
| `PORTFOLIO_ROTATION` | [PortfolioRotationEvaluation.context / RotationComparison](../../app/rotation/models.py) | YES / YES | CONDITIONAL / YES / NO | PARTIAL | CONDITIONAL / CONDITIONAL | `CONDITIONAL_ORIGIN_ONLY` |
| `WATCH_ROUTER` | [MarketWideWatchRecord + OpportunityArchetypeRouter](../../app/intelligence/market_wide_watch.py) | YES / YES | NO / YES / NO | ARCHETYPE_ONLY | CONDITIONAL / CONDITIONAL | `AUXILIARY_ONLY` |
| `COMPARISON_ASSURANCE` | [FastRotationComparisonCandidate source_evaluation_id/source_comparison_id](../../app/intelligence/fast_rotation_comparison_assurance.py) | YES / YES | CONDITIONAL / YES / NO | PARTIAL | CONDITIONAL / CONDITIONAL | `LINKED_ORIGIN_ONLY` |
| `PAPER_TRADE` | [PaperTrade / PaperOutcome / HistoricalPaperReplayReference](../../app/paper/models.py) | YES / YES | NO / YES / NO | STRATEGY_CONFIG_ONLY | CONDITIONAL / CONDITIONAL | `AUXILIARY_ONLY` |
| `FORWARD_STUDY` | [ForwardPaperStudy.admission / ForwardPaperEvent](../../app/forward_paper/models.py) | YES / YES | NO / YES / NO | TIME_STOP_NOT_ROTATION_HORIZON | CONDITIONAL / CONDITIONAL | `AUXILIARY_ONLY` |
| `DECISION_AUDIT` | [DecisionAuditRecord / DecisionOutcomeLink](../../app/audit/decision.py) | YES / YES | CONDITIONAL / CONDITIONAL / NO | VERSION_REFS_ONLY | CONDITIONAL / CONDITIONAL | `LINKED_ORIGIN_ONLY` |
| `PORTFOLIO_SNAPSHOT` | [PortfolioSnapshot / PortfolioTransaction](../../app/portfolio/models.py) | YES / YES | YES / NO / NO | NONE | CONDITIONAL / CONDITIONAL | `AUXILIARY_ONLY` |
| `BACKTEST_EVENT` | [BacktestEvent / HistoricalSignalReplayReference](../../app/backtest/models.py) | YES / YES | CONDITIONAL / CONDITIONAL / NO | FROZEN_RUN_ONLY | CONDITIONAL / CONDITIONAL | `LINKED_ORIGIN_ONLY` |
| `SIGNAL_HISTORY` | [Signal / TradePlan with exact historical replay references](../../app/signals/models.py) | YES / CONDITIONAL | NO / YES / NO | CATEGORICAL_OR_EXPIRY_ONLY | CONDITIONAL / CONDITIONAL | `AUXILIARY_ONLY` |
| `RAW_PRICES` | [CanonicalOHLCVBar / historical_bars](../../app/market_data/historical.py) | NO / NO | NO / NO / NO | NONE | CONDITIONAL / CONDITIONAL | `INELIGIBLE_ORIGIN` |

Additional source-specific limits:

- **HISTORICAL_ROTATION:** Zero historical_rotation_evaluations in predecessor capture. Retained frozen replay event is simulated, never an actual historical portfolio decision. Resolve exact comparison and original input closure; no re-running today to fill omissions.
- **PORTFOLIO_ROTATION:** Zero stored evaluations/comparisons in predecessor capture. Evaluation ID and cutoff exist; whole holding/allocation is not selected parcel, nor caller expected benefit a label.
- **WATCH_ROUTER:** 12 run artifacts in predecessor capture, not paired events. Portfolio-record membership or same-date Watch does not establish original pairing.
- **COMPARISON_ASSURANCE:** Exact existing incumbent alternative required; cash alternative is not incumbent continuation. Assurance must link authentic comparison, not originate a missing pair.
- **PAPER_TRADE:** Zero stored paper outcomes. Single-instrument fill/PnL and unit/fixed-notional sizing cannot replace paired parcel. An exact original rotation reference would need independent validation.
- **FORWARD_STUDY:** Zero studies/events, three run receipts in predecessor capture. time_stop_sessions is setup/paper policy, not governed common comparison horizon.
- **DECISION_AUDIT:** Audit and internal references may reconstruct an existing comparison; final_public_decision and outcome-link type do not prove a pair/return. Verify original canonical fingerprints and complete dependency closure.
- **PORTFOLIO_SNAPSHOT:** One snapshot/five transactions in predecessor capture. Reuse exact historic ledger; no second portfolio or current-holdings substitution.
- **BACKTEST_EVENT:** ROTATION_EVALUATED plus frozen references may locate existing replay observation; generic signal/event does not synthesize a pair. Simulated population stays separately labelled.
- **SIGNAL_HISTORY:** Signal/entry/expiry/stop/target are not an incumbent, common horizon or expected return. P1 projections likewise do not supply a portfolio parcel.
- **RAW_PRICES:** Bars may supply admitted feature/realized evidence only; neither their abundance nor later scanning creates an original rotation event.

The existing [historical rotation adapter](../../app/backtest/rotation.py) binds
frozen state/context IDs and rejects future contexts. Its results are useful
source candidates, but replay timestamps and a configuration name alone cannot
prove every input was available at D. In particular, holding context summaries
need independent canonical availability and parcel proof. Do not rerun today's
rotation engine to manufacture a missing original comparison.

`ARCHIVED_DECISION` and `FROZEN_REPLAY` are distinct populations. A retained
replay run may have been materialized after its simulated cutoff; it is eligible
as a candidate only with frozen D-visible source closure, historically valid
policies and independently reproducible run lineage. It is never relabelled as
an actual historical portfolio decision. This slice authorizes no new replay
generation or mixing these populations to inflate sample size.

For a retained replay, only its authenticated original-record and run-manifest
creation/knownness may follow simulated D, up to R. These are administrative
provenance, not predictive inputs, and stay outside the decision evidence array.
The run manifest must independently resolve every actual feature/configuration
at D. No feature, outcome or policy approval gets this exception. Archived live
decisions retain the ordinary original-record-known-by-D requirement.

Data evidence is explicitly inherited from the immutable read-only capture at
`2026-09-14T15:30:56.149868+00:00`, not a fresh database inspection. It found
2,663,799 bars, zero stored rotation comparisons/replay evaluations, zero paper
outcomes, zero forward-paper studies/events and zero OOS window results.
Three forward-paper run receipts and 43 decision-outcome links are not 46
return observations. A sampled link was a decision event. Twelve Watch run
artifacts are neither twelve pairs nor proof of parcel history. One portfolio
snapshot and five transactions are not a complete historical incumbent cohort.

## 3. Two time partitions, one frozen decision

Use D = original decision cutoff, E = governed terminal endpoint, R = explicit
research-as-of, and F = later model-fit cutoff. Every instant is timezone-aware,
normalized UTC; NSE sessions retain their canonical market/phase identities.
Require R >= D; neither the host wall clock nor a retrospective record-creation
timestamp may substitute for either cutoff.

**DecisionSnapshot:** authenticated original event, exact pair and parcel,
capital/reference sources, original strategy/regime/sector/volatility/diagnostic
features, policy selections, horizon and required transitive source closure.
All decision inputs must satisfy their exact original source/policy PIT rules at
D. Event/known/effective/approval timestamps are not interchangeable.
No `latest now`, wall clock, later restatement, terminal price, realized return
or future regime can enter this partition.

**Research outcome:** separate immutable evidence known by R, which may describe
events after D and must refer to the exact frozen endpoint/methodology.
A terminal bar's economic endpoint may equal E while its publication/receipt is
later; the label is not available until both maturity and required receipt are
proven. Post-end disclosures/corrections belong only to a later research revision.

The source and decision fingerprints are preserved, never repaired by rehashing
tampered input. Canonical producers/verifiers determine source validity; a
self-hash or request claim is not authority. There is no live outcome consumer.

## 4. Closed observation, label and rejection vocabulary

The following shapes are **specification only**; they add no runtime classes,
repository or SQL schema. Every listed key is required in the wire object;
`?` permits explicit null only with corresponding unavailable/rejection state.
Collections are deterministic immutable representations, not mutable state.
Unknown keys, naive time, nonfinite money, empty IDs and malformed fingerprints
reject. Union alternatives below use slash notation; the JSON uses `|`.

Canonical decimal strings preserve exact values without locale or implicit
currency rounding. Source-specific legacy fingerprint formats retain their
original verifier and exact digest through a lossless namespaced reference;
they are not silently rehashed to appear authoritative.

### SourceRef

| Field | Closed wire type / status |
| --- | --- |
| `id` | `id` |
| `version` | `id` |
| `fingerprint` | `fingerprint` |
| `role` | `id` |
| `event_at` | `utc` |
| `known_at` | `utc` |

### PolicyRef

| Field | Closed wire type / status |
| --- | --- |
| `id` | `id` |
| `version` | `id` |
| `fingerprint` | `fingerprint` |
| `approved_at` | `utc` |
| `known_at` | `utc` |
| `effective_from` | `utc` |
| `effective_to` | `utc?` |
| `selection_ref` | `SourceRef` |

### Origin

| Field | Closed wire type / status |
| --- | --- |
| `kind` | `id` |
| `mode` | `ARCHIVED_DECISION / FROZEN_REPLAY` |
| `record` | `SourceRef` |
| `event_id` | `id` |
| `comparison_ref` | `id` |
| `decision_cutoff` | `utc` |
| `run_ref` | `id?` |
| `run_manifest_ref` | `SourceRef?` |

### DecisionSnapshot

| Field | Closed wire type / status |
| --- | --- |
| `protocol_version` | `id` |
| `origin` | `Origin` |
| `incumbent_id` | `id` |
| `challenger_id` | `id` |
| `parcel_ref` | `SourceRef` |
| `capital_basis_ref` | `SourceRef` |
| `starting_capital_inr` | `positive_decimal` |
| `currency` | `INR` |
| `strategy_context` | `Context` |
| `regime_context` | `Context` |
| `sector_context` | `Context` |
| `volatility_context` | `Context` |
| `diagnostic_context` | `Context` |
| `universe_ref` | `SourceRef` |
| `horizon` | `HorizonBinding?` |
| `methodology` | `PolicyRef?` |
| `funding_quantity_residual_policy` | `PolicyRef?` |
| `precision_policy` | `PolicyRef?` |
| `evidence` | `[SourceRef]` |
| `decision_fingerprint` | `fingerprint` |

### Context

| Field | Closed wire type / status |
| --- | --- |
| `state` | `AVAILABLE / UNAVAILABLE / CONFLICTED` |
| `source_refs` | `[SourceRef]` |
| `reason` | `id?` |

### HorizonBinding

| Field | Closed wire type / status |
| --- | --- |
| `policy` | `PolicyRef` |
| `start` | `utc` |
| `end` | `utc` |
| `calendar_ref` | `SourceRef` |
| `endpoint_rule_ref` | `SourceRef` |
| `fingerprint` | `fingerprint` |

### PairedObservation

| Field | Closed wire type / status |
| --- | --- |
| `observation_id` | `id` |
| `protocol_version` | `id` |
| `decision` | `DecisionSnapshot` |
| `research_as_of` | `utc` |
| `maturity` | `UNRESOLVED / PENDING_MATURITY / MATURE` |
| `completion_evidence` | `[SourceRef]` |
| `outcome` | `Outcome?` |
| `admission` | `INADMISSIBLE / PENDING_MATURITY / EXCLUDED / ADMITTED` |
| `reason_codes` | `[id]` |
| `primary_reason` | `id?` |
| `revision_fingerprint` | `fingerprint` |
| `supersedes_revision` | `fingerprint?` |
| `authority` | `RESEARCH_ONLY` |
| `execution_authority` | `false` |

### Outcome

| Field | Closed wire type / status |
| --- | --- |
| `observation_id` | `id` |
| `horizon_fingerprint` | `fingerprint` |
| `methodology_ref` | `PolicyRef` |
| `capital_basis_ref` | `SourceRef` |
| `currency` | `INR` |
| `incumbent` | `RealizedLeg` |
| `challenger` | `RealizedLeg` |
| `evidence` | `[SourceRef]` |
| `corporate_action_status` | `VERIFIED_COMPARABLE / UNRESOLVED / CONFLICTED` |
| `label_state` | `PARTIAL_EVIDENCE / PAIRED_GROSS_COMPLETE` |
| `incumbent_gross_pnl_inr` | `decimal?` |
| `challenger_gross_pnl_inr` | `decimal?` |
| `paired_gross_advantage_inr` | `decimal?` |
| `auxiliary_return_percentage` | `null` |
| `missing_friction_components` | `[id]` |
| `net_advantage_inr` | `null` |
| `matured_at` | `utc` |
| `label_available_at` | `utc` |
| `outcome_fingerprint` | `fingerprint` |

### RealizedLeg

| Field | Closed wire type / status |
| --- | --- |
| `instrument_id` | `id` |
| `decision_cutoff` | `utc` |
| `horizon_fingerprint` | `fingerprint` |
| `methodology_fingerprint` | `fingerprint` |
| `capital_basis_fingerprint` | `fingerprint` |
| `starting_capital_inr` | `positive_decimal` |
| `start_price_ref` | `SourceRef?` |
| `terminal_price_ref` | `SourceRef?` |
| `terminal_gross_value_inr` | `decimal?` |
| `parcel_transform_refs` | `[SourceRef]` |
| `completeness` | `COMPLETE / INCOMPLETE` |
| `cost_basis` | `COST_EXCLUSIVE` |

### RejectionReceipt

| Field | Closed wire type / status |
| --- | --- |
| `receipt_id` | `id` |
| `protocol_version` | `id` |
| `origin_source_ref` | `SourceRef?` |
| `input_fingerprint` | `fingerprint` |
| `observation_id` | `id?` |
| `research_as_of` | `utc` |
| `reason_codes` | `[id]` |
| `primary_reason` | `id` |
| `disposition` | `INADMISSIBLE / PENDING_MATURITY / EXCLUDED` |
| `alias_of` | `id?` |
| `receipt_fingerprint` | `fingerprint` |

`Context` with AVAILABLE has nonempty verified references and no reason.
UNAVAILABLE has no references and an explicit reason; CONFLICTED retains the
conflicting references and reason. Optional context absence does not create
a default regime/strategy. Any context required by the eventually approved
method must be admitted or the observation fails closed.

`SourceRef.role` distinguishes original-event, decision feature/policy,
start-price, terminal-price, session-completion and corporate-action evidence.
Every reference resolves exact ID/version/fingerprint and original payload;
the role determines its permitted partition. No caller-assigned role converts
a terminal result into a decision feature. `PolicyRef` references are independently
verified approved, selected, effective, applicable, unexpired and unambiguous at
D using the original policy's inclusive/exclusive boundaries.

### Identity and immutable revisions

Observation ID hashes exactly the ordered named identity body in the JSON:
protocol version; original source kind/mode/event/comparison and record
ID/version; D; exact incumbent/challenger IDs; parcel and capital-basis refs;
horizon and outcome-method fingerprints; decision fingerprint.
It excludes R, maturity, future label, revision and outcome fingerprints.

The decision fingerprint covers the complete normalized decision shape except
itself. Outcome fingerprint covers the whole normalized outcome except itself;
revision fingerprint covers the complete observation except itself.
Because the observation ID excludes outcomes, these are not circular.
Each digest is SHA-256 over repository canonical JSON after normalization,
using the full hex digest. HorizonBinding fingerprints exclude only their own
fingerprint field. The protocol fingerprint excludes only protocol_fingerprint.
Observation IDs use `gate1-paired-research:`; retained rejection receipt IDs use
`gate1-paired-rejection:`. These identifiers confer no authority.

Missing origin/pair/parcel/horizon/method binding prevents minting a canonical
observation ID. Retain a `RejectionReceipt` with `observation_id=null`, source
reference where available, exact rejected-input fingerprint, R and all reasons.
Its receipt ID uses the defined receipt identity body; its content fingerprint
excludes only receipt ID and fingerprint. This does not invent a historical
decision identity.

Re-evaluation at later R preserves the same observation ID for unchanged frozen
decision inputs and appends a new revision with supersedes reference; it does
not overwrite earlier evidence. Corrections to original decision inputs require
a separately linked immutable decision version and explicit changed identity,
not hindsight repair. Cohort manifests pin exact revision IDs/fingerprints.

Identical original ID/version/payload aliases count once and retain receipts.
Same ID/version with conflicting content rejects. Do not use set-deduplication
to hide conflicts. All source refs sort by role/ID/version after validation;
reasons use the explicit taxonomy order. Revised labels/versions are not new
independent original decisions.

## 5. Horizon authority remains POLICY_REQUIRED

[B09 and the economic contract](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json)
bind V2 applicability, not numeric comparison duration. The
[horizon candidate](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json)
uses SHORT_TERM/POSITIONAL/LONG_TERM with duration boundaries UNSET and is
NOT_ACTIVE. Paper-study `time_stop_sessions`, setup expiry, candle interval and
calibration collection windows have different semantics and cannot substitute.

No numeric duration or categorical conversion is chosen here.
Future horizon authority must be approved/versioned and selected from D-visible
information, require identical policy/calendar/phase/start/end bindings for both
legs, and define deterministic start/end and exceptional-session rules.
Require D <= start < end. No hindsight shortening, extension or favourable
endpoint selection is allowed.

The [canonical session calendar](../../app/historical/canonical_market_session_event_time.py)
has source-backed holiday/special-day/phase visibility but does not establish an
economic horizon. Original selection uses calendar evidence admissible at D.
Completion proof and later actual closure notices may enter the research
partition at R, never rewrite the decision. An unexpected closure or conflict
against the pinned horizon produces explicit unresolved/excluded evidence.
There is no automatic “next available bar” roll; future exception handling
requires separate policy without mutating existing observations.

## 6. Maturity and admission are separate axes

- Missing/invalid horizon or calendar: maturity UNRESOLVED, no outcome label.
- R < E: PENDING_MATURITY; no realized outcome object or scalar.
- R >= E plus exact canonical proof that the pinned terminal session/phase has
  completed, with that proof known by R: MATURE.
- At R = E, completion is allowed only if that exact proof is already available.
  An active session or passage of a date is not completion evidence.
- A completed horizon with missing terminal price remains MATURE but EXCLUDED
  from paired-label admission. Maturity is not data sufficiency.

INADMISSIBLE denotes invalid required decision/binding evidence; PENDING_MATURITY
retains a valid not-yet-mature pair; EXCLUDED retains a mature but rejected or
duplicate candidate; ADMITTED means **complete gross paired research only**.
The future validator retains all applicable reasons, with the first in the
ordered taxonomy as primary. No discretionary overrides or silent dropping.

## 7. Realized outcomes and economic symmetry

Incumbent continuation is the value of retaining the exact selected parcel,
not zero, cash, an index or unrealized accounting profit.
Challenger is the corresponding capital under separately approved quantity,
funding, residual and price-observation rules. Both use the same outcome-method
family/version, horizon, D, capital basis, currency and protocol.

Only after both terminal gross values are valid and comparable may the
predecessor's conditional accounting identities be used:

```text
incumbent_gross_pnl_inr = incumbent_terminal_gross_value_inr - C
challenger_gross_pnl_inr = challenger_terminal_gross_value_inr - C
paired_gross_advantage_inr =
    challenger_terminal_gross_value_inr - incumbent_terminal_gross_value_inr
```

These do not define how terminal wealth is valued and do not forecast returns.
The same selected-C parcel conservation and partial-parcel boundaries remain.
No whole-position proxy, fractional quantity, perfect fill, fee financing,
supplemental cash or residual-return assumption is introduced.

After verified maturity, isolated leg source evidence can be retained as
PARTIAL_EVIDENCE, with all paired PnL/advantage fields null and admission EXCLUDED.
It is not a calibration sample. PAIRED_GROSS_COMPLETE requires every decision,
price, wealth, quantity, residual, action and precision prerequisite.
Missing funding/residual rules therefore block even a paired gross label.

Missing transaction cost/tax/slippage can remain explicit **only for an otherwise
complete gross-only label**. Cost-exclusive labels do not deduct those components.
All seven missing friction components are enumerated; verified zero requires
real policy/source evidence, never absence. `net_advantage_inr` is always null
in this protocol, even if a later cost source becomes available.
Auxiliary percentage also stays null until a separate denominator/precision
policy exists; INR is never replaced by percent/R/score.

Thus gross research may eventually be useful for calibration, but it never
claims net switching advantage or Gate-1 authorization. No live endpoint,
expected return, outcome model, tax rate or slippage estimate is implemented.

## 8. Prices, actions and survivorship

Future outcome policy must specify exact source/provider/version/normalization,
instrument/session/phase, price field and economic basis. Start/reference
evidence is D-visible; an intraday decision cannot use its later completed
daily close. Terminal evidence is for the exact pinned endpoint and known by R,
not just any later available price.

Reuse [provider-versioned history](../../app/market_data/historical.py),
[daily temporal semantics](../../app/market_data/daily_source_temporal_semantics.py)
and [technical-bar evidence](../../app/market_data/technical_bar_contract.py).
Missing bars, suspension or circuits do not authorize nearest-price substitution,
carry-forward marks, zero return or perfect fill. Exact identity continuity and
source conflicts must be checked, not only prices.

[Technical adjustment integrity](../../app/market_data/technical_price_adjustment_integrity.py)
supports exact split/bonus derivatives when factors are verified. This is not
a complete parcel-wealth model: quantity/price transformations must conserve the
same economic basis without double adjustment. Dividend reinvestment/exclusion,
rights, mergers/demergers, cash consideration and delisting settlement remain
unresolved for paired economic labels. Mixed RAW/ADJUSTED/UNKNOWN series reject.

[Historical security and universe evidence](../../app/historical/security_master.py)
must establish eligibility at D. Current NIFTY membership cannot filter old
decisions. A later failed/delisted company must remain in the original source
denominator; if its outcome cannot be valued responsibly, retain the precise
exclusion. No winner-only cohort or reconstructed price-only candidate list.

## 9. Machine-readable exclusion taxonomy

Taxonomy order defines deterministic primary reporting precedence, not risk
severity. All reasons are retained; primary-count totals are separate from
all-reason incidence to avoid double counting.

| Order | Code | Meaning |
| --- | --- | --- |
| 1 | `INVALID_WIRE` | Malformed, empty, extra or wrongly typed contract field; nonfinite money or naive timestamp. |
| 2 | `SOURCE_TAMPERED` | Exact source identity/version/content fingerprint fails original verification; never repair by rehashing. |
| 3 | `SOURCE_CONFLICT` | Conflicting values/versions or incompatible equal-time provenance; no arbitrary tie-break. |
| 4 | `ORIGIN_NOT_AUTHENTIC` | No retained decision-origin record and input closure; price-only, invented, AI or analyst origin. |
| 5 | `CUTOFF_MISSING` | Original canonical decision cutoff is absent. |
| 6 | `INCUMBENT_MISSING` | Exact original incumbent cannot be established. |
| 7 | `CHALLENGER_MISSING` | Exact original challenger cannot be established. |
| 8 | `IDENTITY_AMBIGUOUS` | Collision, fuzzy mapping, same security on both sides or unresolved continuity. |
| 9 | `PARCEL_MISSING` | No exact decision-bound selected incumbent parcel/capital proof; whole holding is not a default. |
| 10 | `UNSUPPORTED_EVENT` | Source kind/security unsupported by the applicable admitted research policy. |
| 11 | `PAIR_MISMATCH` | Cutoff, capital, protocol, horizon or methodology differs between sides; benchmark substitute. |
| 12 | `DECISION_PIT_VIOLATION` | Decision source/policy unavailable, future-effective or future-known at original cutoff. |
| 13 | `FUTURE_LABEL_LEAKAGE` | Realized outcome, later restatement or outcome-derived feature enters frozen decision evidence. |
| 14 | `HORIZON_POLICY_MISSING` | No exact approved/effective horizon authority at decision cutoff. |
| 15 | `HORIZON_AMBIGUOUS` | Multiple incompatible horizons or categorical-to-duration mapping unresolved. |
| 16 | `HORIZON_CHANGED` | Hindsight extension, shortening or calendar rebinding of a frozen observation. |
| 17 | `CALENDAR_UNRESOLVED` | Required session/phase coverage missing or contradictory, including unexpected closure. |
| 18 | `NON_MATURE` | Pinned terminal session/phase not yet proven completed at explicit research as-of. |
| 19 | `INSUFFICIENT_HISTORY` | Method-required historical source coverage is not proven. |
| 20 | `START_PRICE_MISSING` | Exact governed start/reference evidence absent; no nearest/last/average fallback. |
| 21 | `TERMINAL_OBSERVATION_MISSING` | Exact governed terminal observation absent at research as-of. |
| 22 | `OUTCOME_NOT_YET_KNOWN` | Required realized evidence not visible by research as-of, even if horizon completed. |
| 23 | `CORPORATE_ACTION_AMBIGUOUS` | Split/bonus/cash/complex action treatment, coverage or economic conservation unresolved. |
| 24 | `PRICE_BASIS_MISMATCH` | Mixed/unknown/undocumented adjustment or return basis. |
| 25 | `SUSPENSION_OR_CIRCUIT_UNRESOLVED` | Endpoint/tradeability/fill interpretation not governed for this suspension/circuit. |
| 26 | `DELISTING_UNRESOLVED` | No governed terminal economic treatment; no zero, last-price or winner-only deletion. |
| 27 | `UNITS_INVALID` | Non-INR capital/endpoints or auxiliary percentage substituted for INR. |
| 28 | `FUNDING_QUANTITY_RESIDUAL_UNSET` | Missing funding/quantity/residual proof; fractional shares or cash assumptions prohibited. |
| 29 | `OUTCOME_METHOD_UNSET` | No versioned paired realized-wealth/precision methodology; no ad hoc arithmetic admission. |
| 30 | `GROSS_LABEL_INCOMPLETE` | Only one side or incomplete input closure; partial evidence not a paired label. |
| 31 | `SURVIVORSHIP_FILTER` | Present-day membership/winner filter or missing failed-origin denominator. |
| 32 | `DUPLICATE_ORIGIN` | Exact logical origin already represented; retain alias receipt, count once. |
| 33 | `SAMPLING_POLICY_REQUIRED` | Representativeness, dependence or adequacy policy unresolved; no calibrated claim. |
| 34 | `SPLIT_POLICY_REQUIRED` | No frozen chronological split/overlap/purge/embargo/adequacy policy. |
| 35 | `OOS_LEAKAGE` | Test data used in fit/selection; future-matured labels or shared event/dependent interval leaks across split. |
| 36 | `AUTHORITY_UNAVAILABLE` | Claimed research/AI/self-hash provenance cannot confer Gate-1 scenario authority. |

A canonical source error retains its original safe reason alongside the matching
protocol reason in supporting source evidence. It cannot convert a rejected
source into an admitted input. No raw secrets or private payload are logged.

## 10. Cohort, dependence and calibration/OOS boundary

Report true distinct origin count separately from bars, receipts, aliases,
pending/excluded/admitted labels, revisions and per-reason counts. Preserve
strategy/archetype, regime, sector, instrument/pair concentration, temporal
coverage and missing-context groups. No arbitrary sample minimum, numerical
news weight, confidence multiplier or implied empirical adequacy is supplied.
Adequacy remains `CALIBRATION_POLICY_REQUIRED`.

Exact aliases are one observation. Distinct events sharing a security across
intersecting inclusive decision-to-label-maturity intervals are flagged as
dependent; retain their identities and report overlap groups. Dependence can
also exist outside overlaps. Do not silently discard “near” events or invent
a proximity threshold/weight. Cohort and split policies must handle dependence
and concentration explicitly before calibration.

Use chronological or [existing walk-forward](../../app/backtest/walk_forward.py)
architecture; no random leakage-prone split. Freeze split ID/version/fingerprint,
cohort and exact label revisions, time-boundary conventions, fit cutoff F,
training/validation/evaluation windows, model version and selection time.
All fit/selection labels must be mature **and available** by F. Freeze model and
selection strictly before TEST start, matching existing walk-forward selection
semantics. Validation is selection evidence, not untouched OOS.
Require F <= model/selection freeze < TEST start; each evaluated decision D must
also know that exact frozen model version. A model frozen before its claimed
training cutoff cannot consume labels disclosed later.

Do not share aliases or dependent overlapping information/outcome intervals
between selection and evaluation without a separately approved exclusion/purge
policy. Numeric window lengths, train/test percentages, purge, embargo and
minimum observations remain unset, not zero. Existing generator parameters
cannot be filled with arbitrary defaults.

OOS decisions use their own D-visible inputs and frozen model; their future
labels become visible only after maturity. Later recalibration is a new model
and cohort revision at a new F; it never rewrites earlier predictions or
labels to improve performance. This slice performs no fit, split, backtest or
prospective collection.

## 11. Readiness and unresolved policy dependencies

| Component | State | Remaining proof |
| --- | --- | --- |
| `EVENT_ORIGIN` | `SOURCE_NOT_READY` | Candidate schemas exist; no verified complete paired-origin population or parcel capture in predecessor audit. |
| `PAIRED_IDENTITY` | `DERIVABLE` | Exact existing canonical identities/comparison references reusable only when resolved; no currently certified observation. |
| `PARCEL` | `POLICY_UNSET` | No exact selected-parcel selection/funding authority supplied. |
| `HORIZON_AUTHORITY` | `POLICY_REQUIRED` | B09/categorical route/paper time stop do not define common numeric duration. |
| `PRICE_ENDPOINTS` | `SOURCE_NOT_READY` | Exact policy-bound start/end and eligible paired history unproved. |
| `CORPORATE_ACTIONS` | `SOURCE_NOT_READY` | Verified split/bonus technical factors are not complete economic wealth/complex-action treatment. |
| `PORTFOLIO_REPLAY` | `DERIVABLE` | Existing immutable snapshot/ledger replay conditional on complete historical known-at closure. |
| `OUTCOME_LABEL` | `POLICY_REQUIRED` | Protocol admission requirements defined; horizon/wealth/funding/precision prerequisites absent, no real paired label. |
| `FUNDING_QUANTITY_RESIDUAL` | `POLICY_UNSET` | No fractional/default quantity or residual/fee financing inferred. |
| `TRANSACTION_COSTS` | `SOURCE_NOT_READY` | No complete historical applicable tariff/source admission. |
| `TAX` | `POLICY_UNSET` | Mandatory tax policy/lots/context unresolved; no rate invented. |
| `SLIPPAGE` | `AUTHORITY_NOT_REGISTERED` | Mandatory two-leg calibrated source absent; never zero fallback. |
| `CALIBRATION_COHORT` | `HISTORICAL_COVERAGE_INSUFFICIENT` | Raw bars not genuine paired events; zero observed stored paper outcomes/studies/events/OOS results in predecessor capture. |
| `OOS_EVALUATION` | `CALIBRATION_REQUIRED` | Walk-forward support exists; split/sample/overlap/adequacy policy unapproved. |
| `AUTHORITY_REGISTRATION` | `AUTHORITY_NOT_REGISTERED` | Research references and hashes confer no scenario authority; no producer registered. |

No currently admitted pair or model-ready cohort is claimed. The exact open
policy dependencies are:

- `COMMON_NUMERIC_HORIZON_AUTHORITY`
- `ORIGINAL_SELECTED_PARCEL_AND_EVENT_CAPTURE`
- `PAIRED_REALIZED_WEALTH_AND_PRICE_PRECISION`
- `FUNDING_QUANTITY_RESIDUAL`
- `CORPORATE_ACTION_ECONOMIC_TREATMENT`
- `COST_TAX_SLIPPAGE_SOURCES`
- `SAMPLE_DEPENDENCE_AND_ADEQUACY`
- `CHRONOLOGICAL_SPLIT_PURGE_EMBARGO`
- `FUTURE_SCENARIO_MODEL_AND_AUTHORITY`

The protocol closes the two-time-partition specification, conditional paired
admission/exclusion vocabulary, and immutable revision/sampling boundary.
**Zero operational model/source blockers are closed.**

## 12. Ownership and safety

Future paired research evidence belongs under existing `app/rotation`, with
measurement and frozen evaluation support from `app/calibration` and
`app/backtest`. Existing canonical sources remain the sole truth. There is no
second Brain, portfolio, Decision Score or scenario repository here.

Independent [GateSourceAuthority](../../app/gates/source_authority.py) remains
the future gate admission boundary. Research admission, successful backtests,
source hashes and AI summaries cannot grant producer/gate authority.
AI may explain or assist extraction but cannot create historical events,
horizons, labels, probabilities, admission decisions or policy overrides.

No application source, schema/migration, API/UI, runtime, provider, credentials,
portfolio state, trade plan, score, gate reducer or Gate 1/2/3/4/5/6 is changed.
No actual research observations are persisted or generated. V1 remains ACTIVE;
V2 remains NOT_ACTIVE. No push is authorized.

## 13. Validation and closure

Required checks are focused offline protocol witnesses, relevant predecessor,
source/horizon/calendar/adjustment/rotation/paper/walk-forward regressions,
documentation links/whitespace, frozen fingerprints and `git diff --check`.
Synthetic conformance timestamps and values are test-only examples, never
approved horizon durations, fake historical events or sample thresholds.

No runtime/shared behavior changes, so the explicitly conditional full-backend
run is not required. This protocol may be ACCEPTED/CLOSED with decision B
without closing the model feasibility or activation blockers.

Completed validation:

- Focused protocol conformance: **173 passed, 0 failed, 0 skipped, 0 warnings**.
- Relevant regression: **780 passed, 0 failed, 0 skipped, 2 existing dependency
  deprecation warnings** (Starlette/httpx and AnyIO BlockingPortal).
  Coverage includes predecessor feasibility/economic/governance artifacts,
  gate authority/V1 behavior, historical sources/adjustments, canonical session
  timing, horizon governance, portfolio/rotation, paper and walk-forward support.
- Documentation: **305 local links, 13 tables**; targets, fences, table columns
  and whitespace passed. All **82 inspected file fingerprints** remain unchanged.
- `git diff --check`: passed. Full backend: **not run**, because only this
  document, its governance JSON, offline tests and a README link change.
- Defensive review refined replay administrative provenance versus D-visible
  features, stable observation versus revision identity, strict model-freeze
  chronology, rejection receipts and future completion-evidence exclusion.
  None of these test witnesses authorizes a real policy or observation.

## 14. Exactly one next frozen continuation

**`GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1`**.

Resolve the named research-horizon authority gap through existing governance:
audit permissible categorical routing, numeric/session endpoint authority and
exceptional-session requirements; freeze only supportable policy definitions
and explicit unavailable states. Do not borrow paper time stops or invent a
duration to advance the roadmap. **This continuation has not been started.**
