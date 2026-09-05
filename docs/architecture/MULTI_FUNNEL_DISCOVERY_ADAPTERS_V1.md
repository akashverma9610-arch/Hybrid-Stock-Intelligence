# Multi-Funnel Discovery Adapters V1

**Status: `ACTIVE_READ_ONLY_ADAPTERS / WATCH_ONLY_INSPECTION / NON_EXECUTABLE / NO_UNION / NO_RUNNER`.**

## Scope

This slice adapts only already-materialized, PIT-valid HSI source contracts to
the canonical `CanonicalDiscoveryLead` inspection contract.  It contains no
new threshold, ranking, setup, materiality, momentum, valuation, order-book,
or market-dislocation policy.  It does not fetch a provider, persist leads,
create a market-wide runner/scheduler, deduplicate across funnels, qualify a
candidate, calculate Decision Score/Six Gates, or read/mutate a portfolio.

An adapter is a source-contract verifier, not a funnel evaluator.  It receives
an explicit timezone-aware `as_of`; source availability after that cutoff is
`STALE`, malformed/tampered lineage is `EVIDENCE_CONFLICTED`, and unresolved
security identity is `IDENTITY_BLOCKED`.  No runtime clock or latest-now
fallback is permitted.

## Common adapter result

`DiscoveryAdapterResult` contains exact funnel/as-of, zero or more immutable
canonical leads, and one deterministic `DiscoveryAdapterCoverage`.  Coverage
records source observations and securities examined, emitted lead IDs, and
explicit `DATA_BLOCKED`, `IDENTITY_BLOCKED`, `POLICY_BLOCKED`, `CONFLICTED`,
`NO_LEAD`, and `STALE` counts.  Its state is one of `LEADS_EMITTED`,
`EVALUATED_NO_LEADS`, `NOT_EVALUATED`, `DATA_BLOCKED`, `POLICY_BLOCKED`,
`IDENTITY_BLOCKED`, `SOURCE_NOT_OPERATIONAL`, `EVIDENCE_CONFLICTED`, or
`STALE`.

An identical replay of one source identity/fingerprint cannot create a second
lead.  A conflicting replay fails closed.  Separate source observations in a
single funnel remain separate lead origins.  The active read-only
[candidate-union layer](MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md)
now groups those origins by exact canonical security without scoring or
discarding them.

## Adapted sources

| Funnel | Adapter state | Existing source contract | Lead trigger and posture | Fail-closed boundary |
| --- | --- | --- | --- | --- |
| `PRE_BREAKOUT` | `ADAPTER_ACTIVE` | `CanonicalSetupOpportunity` from existing governed Pre-Breakout assessment | `GOVERNED_PREBREAKOUT_SETUP_AVAILABLE`; positional inspection | Requires valid source fingerprint, exact instrument, source policy/version/fingerprint, and source as-of. No setup recalculation. |
| `SECTOR_ROTATION` | `ADAPTER_ACTIVE` | Stored `Top3OpportunityFinderRun` candidate IDs from exact constituent mapping | `SECTOR_ROTATION_STATE`; positional constituent inspection | Only stored exact candidate IDs; sector strength does not create arbitrary constituent leads. |
| `FUNDAMENTAL_INFLECTION` | `ADAPTER_PARTIAL` | `InflectionAccountingProspectiveObservation` | `INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE`; `RESEARCH_INSPECTION` | Requires the actual accounting-observation state, Revenue/PAT receipts, reporting basis, company-type receipt, and source as-of. It never means confirmed inflection or market reaction. |
| `COMPOUNDER` | `ADAPTER_PARTIAL` | `CompounderProspectiveObservation` | `COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE`; `RESEARCH_INSPECTION` | Requires an actual prospective observation; annual facts/non-financial classification alone are insufficient. |
| `POLICY_TRANSMISSION` | `ADAPTER_PARTIAL` | `PolicyTransmissionResearchShadow` | `POLICY_TRANSMISSION_RESEARCH_OBSERVATION`; `RESEARCH_INSPECTION` | Only the existing `POLICY_DEFINITION_MISSING` state with exact primary policy, scope, and verified exposure path can lead. It does not call an issuer a beneficiary, bullish, or a winner. |

All adapted leads retain `FACT → DATA → INTERPRETATION → INFERENCE` source
layer lineage and remain inspection-only.  Research-shadow adapters preserve
their posture; adaptation never upgrades them into an active strategy.

## Explicit non-adapters

| Funnel | Source state | Adapter state | Leads possible today? | Main blocker |
| --- | --- | --- | --- | --- |
| `MOMENTUM` | PARTIAL | `ADAPTER_PARTIAL` | No | No approved distinct factual momentum trigger. |
| `EARNINGS_ACCELERATION` | PARTIAL | `ADAPTER_PARTIAL` | No | It is not independently distinct from underlying Fundamental Inflection accounting evidence. |
| `ORDERBOOK_CAPEX` | PARTIAL | `ADAPTER_PARTIAL` | No | No approved factual change/trigger policy. |
| `NEWS_CATALYST` | PARTIAL | `ADAPTER_PARTIAL` | No | Adapter freshness/materiality policy remains unavailable; no generic headlines. |
| `MARKET_DISLOCATION` | PARTIAL | `ADAPTER_PARTIAL` | No | Current Market Extremes assurance is market/regime context, not a security trigger. |
| `HOLDING_STATE_CHANGE` | PARTIAL | `ADAPTER_PARTIAL` | No | No canonical material holding/thesis-change event contract. |
| `EMERGING_COMPOUNDER` | NOT_IMPLEMENTED | `NOT_IMPLEMENTED` | No | Policy/source absent. |
| `VALUATION_RECOVERY` | POLICY_BLOCKED | `SOURCE_BLOCKED` | No | No approved valuation/recovery trigger. |
| `WATCHLIST_STATE_CHANGE` | NOT_IMPLEMENTED | `NOT_IMPLEMENTED` | No | Governed watchlist-state contract absent. |

The source-funnel status in the [foundation registry](MULTI_FUNNEL_DISCOVERY_CONTRACT_AND_REGISTRY_V1.md)
is intentionally unchanged by this adapter implementation.  Adapter readiness
only states whether a source can be transformed faithfully; it neither
activates a strategy nor makes a partial/research source operational.

## Current read-only audit method

A manual audit may read immutable existing source stores at one explicit,
source-derived cutoff and invoke each pure adapter.  It must report each
funnel separately and never union, rank, persist, or rescan sources.  The
five-holding report is source lineage only: no lead is a stock judgment.

## Next boundary

`MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1` is active as a pure,
read-only exact-security composition boundary.  The next bounded slice is
`MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1`; it and Discovery Recall Audit
remain not active.
