# Multi-Funnel Discovery Contract and Registry V1

**Status: `ACTIVE_FOUNDATION / READ_ONLY / WATCH_ONLY / NON_EXECUTABLE / WHOLE_MARKET_RUNNER_NOT_ACTIVE`.**

## Purpose and boundary

HSI is one continuously updated evidence Brain.  Multi-Funnel Discovery is its
candidate-recall boundary: independent evidence states may make an exact NSE
security worth **Brain inspection**.  It is not another Brain, a universal
scanner, an opportunity score, candidate qualification, a setup, a Decision
Score, a Six-Gates result, or a portfolio/execution system.

The implemented V1 foundation contains only immutable contracts and a static,
versioned inventory.  It does not invoke any funnel, scan the market,
materialize leads, union securities, query a provider, persist data, or expose
an API/UI.  Therefore `MULTI_FUNNEL_DISCOVERY_FOUNDATION = ACTIVE`, while
`WHOLE_MARKET_MULTI_FUNNEL_RUNNER = NOT_ACTIVE` and
`DISCOVERY_RECALL_AUDIT = NOT_ACTIVE`.

Discovery answers “why inspect this security?”; the shared Brain alone judges
evidence quality, setup, decision, portfolio relevance and any future
governed action.  A lead is neither a good stock nor an investment/portfolio
candidate.  It may later be rejected by the Brain, Decision Score, or Six
Gates.  No stock must pass an unrelated funnel to be discoverable.

## Canonical contract

`app.intelligence.multi_funnel_discovery.CanonicalDiscoveryLead` is an
immutable, deterministic inspection record.  Its identity is a hash of the
contract version, canonical instrument, funnel/version, explicit UTC
`discovery_as_of`, and canonical source lineage.  Its content fingerprint is
separate and covers all descriptive fields.  Both reject tampering.

Required fields are exact canonical instrument, funnel/version, explicit
timezone-aware as-of, source layer, non-empty typed trigger codes, readiness,
data-quality state, and non-empty source lineage.  Every lineage reference has
an ID, fingerprint, kind (`OBSERVATION`, `EVIDENCE`, `RECEIPT`, or `ARTIFACT`),
and `known_at`; evidence learned after `discovery_as_of` is rejected.  Optional
issuer/parent identities, horizons, and blocker codes remain descriptive.
Collections are immutable, sorted and duplicate/conflict rejecting.

Supported lead posture is only:

- `READY_FOR_INSPECTION` for an existing governed factual/interpreted source;
- `DATA_PARTIAL` where the emitting source itself retained partial data; or
- `RESEARCH_INSPECTION` solely for Compounder, Fundamental Inflection, and
  Policy Transmission research shadows.

`RESEARCH_INSPECTION` is evidence inspection, not `COMPOUNDER_CANDIDATE` or
any other qualification.  Each lead preserves the source epistemic layer:
`FACT → DATA → INTERPRETATION → INFERENCE`; layers are never flattened into a
common confidence or score.

There are deliberately no BUY/SELL/HOLD, final/discovery score, Six-Gate,
allocation, quantity, target, stop, broker, order, portfolio, setup, or
candidate-qualification fields.  Lead identity supports a later additive
union, but V1 neither deduplicates across funnels nor ranks/weights them.  The
same security from three funnels must retain three source lineages rather than
become three votes or a summed score.

## Registry and inventory

`MultiFunnelDiscoveryRegistry` is an immutable V1 catalogue with ID
`hsi-multi-funnel-discovery-registry`, version `v1`, and a deterministic
fingerprint.  It has exactly the fourteen target funnels.  Its entry is an
inspectable declaration of current repository truth: status, supported
horizons only where existing semantics support them, required canonical input,
eligibility, source layer, freshness/trigger wording, fail-closed codes,
temporal mode, existing entry point, and governed policy identity when one
exists.  It does not import or execute an entry point.

| Funnel | Existing component / canonical inputs | State | Horizon | Lead semantics / principal blocker |
| --- | --- | --- | --- | --- |
| `MOMENTUM` | Relative-strength diagnostics and router; PIT OHLCV | `PARTIAL` | Positional | Technical inspection only; dedicated momentum trigger policy absent. |
| `PRE_BREAKOUT` | Governed Pre-Breakout setup and Top-3 flow | `OPERATIONAL` | Positional | Governed setup inspection; remains downstream of its existing policy. |
| `FUNDAMENTAL_INFLECTION` | Prospective accounting shadow; PIT quarterly facts/company type | `RESEARCH_SHADOW` | Long-term, positional | Research inspection only; qualification and filing-time coverage blocked. |
| `COMPOUNDER` | Prospective Compounder shadow; PIT annual facts/company type | `RESEARCH_SHADOW` | Long-term | Research inspection only; empirical qualification deferred. |
| `EMERGING_COMPOUNDER` | No independent evaluator/policy | `NOT_IMPLEMENTED` | Long-term | No lead; policy unavailable. |
| `EARNINGS_ACCELERATION` | Canonical diagnostic Rule 24 and router | `PARTIAL` | Positional | Diagnostic inspection only; not an independent second accounting lead. |
| `ORDERBOOK_CAPEX` | Canonical diagnostic Rule 27 / official financial evidence | `PARTIAL` | Positional | Diagnostic inspection only; no approved order-book/capex trigger policy. |
| `SECTOR_ROTATION` | Current sector ranking and exact constituent mapping / Top-3 flow | `OPERATIONAL` | Positional | Sector-to-constituent inspection; adapter must not equate a strong sector with a buy. |
| `NEWS_CATALYST` | Verified external intelligence, exact exposure, Watch router | `PARTIAL` | Unavailable | Fact-based inspection only; calibration/freshness policy still required. |
| `POLICY_TRANSMISSION` | Long-term policy-transmission research shadow, verified exposure | `RESEARCH_SHADOW` | Positional, long-term | Research inspection only; qualification inactive. |
| `VALUATION_RECOVERY` | Existing valuation comparison input is insufficient | `POLICY_BLOCKED` | Long-term | No lead; no approved recovery/mispricing trigger. |
| `MARKET_DISLOCATION` | Market Extremes assurance projection | `PARTIAL` | Unavailable | Regime context only; no security/sector discovery trigger. |
| `HOLDING_STATE_CHANGE` | Existing Holding Intelligence composition | `PARTIAL` | Unavailable | Contextual existing-holding review only; no discovery adapter. |
| `WATCHLIST_STATE_CHANGE` | No governed watchlist-state contract | `NOT_IMPLEMENTED` | Unavailable | No lead; contract unavailable. |

There are 14 registered funnels: 2 `OPERATIONAL`, 6 `PARTIAL`, 3
`RESEARCH_SHADOW`, 1 `POLICY_BLOCKED`, and 2 `NOT_IMPLEMENTED`.  There are no
invented `CONTRACT_ONLY` or `DATA_BLOCKED` entries in this snapshot.  “Operational” describes
the retained Core mechanism, not a current canonical multi-funnel lead adapter.

`EARNINGS_ACCELERATION` is deliberately a diagnostic/routing view of existing
accounting acceleration.  `FUNDAMENTAL_INFLECTION` is the separate,
prospective research-shadow evidence family.  They may not be emitted as two
leads for the same underlying accounting observation without a future,
approved semantic distinction.

All unavailable/blocked entries remain registered with their exact code; a
future scan may never silently omit them.  The approved eligible NSE equity
universe remains the default scope where applicable.  Holding and watchlist
entries are explicitly contextual scopes rather than whole-market scanners.

## Coverage and future batch envelope

`FunnelCoverage` preserves the eligible universe, examined securities,
required-data count, emitted lead IDs, and counts for insufficient, policy
blocked, excluded, conflicted, stale, and unsupported states.  Its state
makes `LEADS_EMITTED`, `EVALUATED_NO_LEADS`, `NOT_EVALUATED`, `POLICY_BLOCKED`,
and `DATA_BLOCKED` unambiguous.  Thus `NO_LEADS` never means the same thing as
“the funnel could not evaluate.”

`MultiFunnelDiscoveryBatch` defines but does not execute the future batch
envelope: explicit as-of, immutable universe snapshot ID/fingerprint,
registry identity/fingerprint, requested/executed/blocked funnel partitions,
per-funnel coverage, and emitted lead identities.  It is deterministic,
requires exact coverage for every executed/blocked funnel, and has no runtime
clock or latest-record fallback.

The future union must retain every funnel origin for a security.  It must not
discard all but a “best” reason, score sources, or use cross-funnel voting.
Discovery Recall Audit can later answer whether a funnel ran, an instrument
was examined, a lead was emitted, or data/policy blocked evaluation.

## Governance and next bounded slice

This foundation activates architecture/contract governance only.  No human
approval of a final opportunity is represented.  Existing policy identities
are references only, and all Strategy Registry, HSI Signal, Decision Score,
and Six-Gates boundaries remain unchanged.

The exact next bounded continuation is
`MULTI_FUNNEL_DISCOVERY_ADAPTERS_V1`: adapt only the registry entries whose
existing source semantics can produce a PIT-valid inspection lead, with no
whole-market runner or union.  Candidate union/identity is later, followed by
whole-market orchestration; Discovery Recall remains deferred until the
foundation is closed.

## Invariants

- Primary source, exact canonical identity, PIT/as-of, immutable lineage, and
  provider independence remain mandatory.
- No universal Decision Score threshold is a discovery filter.
- Decision Score and Six Gates are downstream; discovered-but-rejected remains
  observable.
- No discovery score, ranking, synthetic confidence, or policy/data fallback.
- No portfolio authority, trading authority, broker/order call, or allocation
  mutation.
