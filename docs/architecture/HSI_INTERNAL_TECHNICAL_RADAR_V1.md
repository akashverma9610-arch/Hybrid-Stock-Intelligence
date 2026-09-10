# HSI Internal Technical Radar V1

**Status:** `IMPLEMENTATION_READY / DISCOVERY_ONLY / RUNTIME_NOT_ACTIVE / LIVE_PRODUCTION_NOT_READY`

## 1. Purpose and permanent authority boundary

HSI Internal Technical Radar is a lightweight HSI-owned discovery mechanism.
It answers only: **which exact canonical securities deserve a later shared-HSI
evaluation?** A lead is never a recommendation, setup conclusion, capital
decision, or user alert.

```text
Canonical market evidence
        -> Internal Technical Radar
        -> existing CanonicalDiscoveryLead
        -> existing shared HSI evaluation / 61 diagnostics later
        -> Decision Score / Six Gates / setup lifecycle later
```

The implementation fixes `RADAR_AUTHORITY = DISCOVERY_ONLY`. It cannot emit a
trade side, position quantity, allocation, entry, stop, target, score, Gate
result, portfolio mutation, broker/order request, signal, alert, API response,
or UI state. It does not schedule itself, run on application import, or let a
normal user trigger a market scan.

This does not create a Technical Brain, a Scanner Brain, or a second technical
ranking authority. `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`,
`SEPARATE_TECHNICAL_BRAIN = FALSE`, and `NO_INDICATOR_EXPANSION = TRUE` remain
unchanged.

## 2. Discovery archaeology and reuse

| Existing component | Radar V1 treatment |
| --- | --- |
| `app.intelligence.multi_funnel_discovery.CanonicalDiscoveryLead` | Reused unchanged as the only emitted lead contract. Radar defines no competing lead, candidate, or persistence model. |
| `DiscoveryFunnelId.PRE_BREAKOUT` and `DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE` | Reused unchanged for the sole active discovery family. |
| `app.intelligence.multi_funnel_discovery_adapters.adapt_pre_breakout` | Reused to verify and adapt an already materialized immutable `CanonicalSetupOpportunity`; Radar never recalculates Pre-Breakout logic. |
| `CanonicalSetupOpportunity` and approved Pre-Breakout governance/selection lineage | The only active V1 trigger. The source already contains the approved policy, selection, assessment, and opportunity lineage. |
| Multi-Funnel candidate union and whole-market orchestration | Intentionally untouched. Radar emits the same lead type and can later be supplied to that existing union; this slice does not modify or invoke it. |
| `OpportunityArchetypeRouter` and Market-Wide Watch | Untouched. They remain separate descriptive/routing consumers of canonical evidence. |
| Canonical 15-minute technical reader | Reused only as the strict prospective-PIT, provider-neutral input contract and coverage evidence. No 15-minute trigger is activated. |
| Existing daily/weekly technical readers | Not substituted and not duplicated. Pre-Breakout retains its own existing governed stored-evidence path. |
| Canonical 61 diagnostics, Rules, Rule 6 sector context, Decision Score, Six Gates | Untouched downstream evidence/decision systems. Radar neither changes nor bypasses any of them. |

The old `app.scanning.TwoStageScanner` remains a separate legacy shortlist
boundary. It is not imported or used because its `prefilter_rank` would be a
second ranking surface.

## 3. Active and blocked V1 discovery families

| Candidate family | V1 state | Governing source | Horizon context | Reason |
| --- | --- | --- | --- | --- |
| `PRE_BREAKOUT` | `ACTIVE_DISCOVERY_ONLY` | Existing governed `CanonicalSetupOpportunity` through `adapt_pre_breakout` | `POSITIONAL` | The existing approved Pre-Breakout policy and immutable setup opportunity provide an exact, non-recalculated discovery condition. |
| Generic technical / breakout formation | `POLICY_BLOCKED` | Canonical technical bars available as inputs only | unavailable | No approved Radar-specific condition or numeric threshold exists. |
| Momentum structure / volume expansion / pullback retest | `POLICY_BLOCKED` | Existing technical evidence only | unavailable | No separate governed discovery policy is selected. |
| 15-minute technical discovery | `POLICY_BLOCKED` or `DATA_INSUFFICIENT` | Canonical prospective 15m reader | `SHORT_TERM` unavailable | The continuity policy remains unset and no 15m discovery condition is approved. |
| 30m, 1h, 4h, MTF orchestration | `NOT_ACTIVE` | none | unavailable | No substitution or inferred timeframe is allowed. |

`SETUP_TYPE != DISCOVERY_FAMILY != HORIZON`. The Radar’s Pre-Breakout lead
does not finalize a setup type. It carries the source’s existing positional
context only; the later shared-Brain/setup lifecycle retains classification.

## 4. Canonical input and temporal contract

`evaluate_internal_technical_radar` is a pure explicit-call batch function. A
single eligible security is a one-security scope; the current complete
eligible universe can be supplied as one bounded scope. It performs no I/O,
provider access, runtime-clock lookup, persistence, retry, or scheduling.

The input scope is immutable and exact:

- canonical selected and eligible `NSE:<ISIN>` identities;
- source universe snapshot ID/fingerprint;
- provider exact-ready and blocked-identity sets, strictly as coverage facts;
- actual live-15m-security set, also strictly a supplied coverage fact.

Provider mapping capacity is not technical evidence and never triggers a
lead. The current known identity accounting can therefore be represented
truthfully as `2,553` selected, `2,287` exact-ready, and `266` blocked when
the full source scope is supplied, without calling a provider or claiming that
those securities were evaluated.

Every Radar run has an explicit aware UTC-normalized `as_of`. The active
Pre-Breakout source is accepted only where its canonical source-as-of is at or
before that cutoff. Its existing `CanonicalDiscoveryLead` adapter retains the
source artifact's decision-as-of timestamp as the lineage known-at value;
Radar does not manufacture a distinct known-at field. A source after the
cutoff is `DATA_INSUFFICIENT`; it cannot influence an earlier result. This
source path is described as **governed stored as-of** evidence, not as a newly
claimed historical-PIT implementation.

The optional 15m input accepts only a
`CanonicalFifteenMinuteTechnicalRead` in `AS_OF_PROSPECTIVE_PIT` mode with a
reader cutoff no later than Radar `as_of`. Current-descriptive reads, raw Dhan
packets, provider-native bars, fuzzy symbols, 30m, 1h, and 4h inputs are not
accepted.

## 5. Continuity and 15m evidence

The existing prospective 15m reader preserves incomplete observations,
conflicts, and no-trade-not-materialized states. Radar preserves those as
input coverage reasons and never forward-fills, interpolates, bridges gaps, or
treats an absent interval as zero/no-trade.

Because the canonical 15m continuity policy is `PARTIAL / UNSET`, a ready
reader result with `CONTINUITY_POLICY_UNSET` remains
`DATA_INSUFFICIENT` for any continuity-dependent future discovery family.
Even a strict, eligible 15m input with no observed interruption is
`INPUT_READY_POLICY_BLOCKED` until an approved 15m discovery policy exists.
No bar condition, threshold, indicator, or 15m Rule activation was added.

## 6. Discovery Lead and state contract

Radar emits the existing immutable `CanonicalDiscoveryLead`, not a new Radar
lead schema. A discovered lead contains the exact canonical security,
`PRE_BREAKOUT` funnel, existing policy version, positional source context, and
the opportunity/assessment/policy lineage fingerprints and known-at values.
That contract supplies deterministic lead identity and dedupe provenance.

The Radar run adds only a non-persistent batch envelope and per-security
outcome. Its bounded states are:

| State | Meaning |
| --- | --- |
| `DISCOVERED` | One verified, existing governed Pre-Breakout source adapted to an existing discovery lead. |
| `NOT_TRIGGERED` | A complete exact source query reported no current governed setup. |
| `DATA_INSUFFICIENT` | The source query was absent, late, incomplete, or the required 15m continuity evidence is unavailable. |
| `EVIDENCE_CONFLICTED` | Tampered or contradictory canonical source lineage was supplied; no lead is emitted. |
| `POLICY_BLOCKED` | A required policy is unavailable; no lead is emitted. |

Thus `NOT_TRIGGERED` is never used for an unevaluable security. Equivalent
replay produces the same lead/run identity and serialization. Exact duplicate
source evidence is idempotent; non-identical duplicate evidence for one
security fails closed. A material canonical source change yields a different
immutable result rather than an endless duplicate lead.

No Radar result is persisted in this slice. Existing immutable discovery and
snapshot patterns are deliberately not extended because no approved retention
or noisy-event lifecycle is required for an internal, caller-owned pure run.

## 7. Coverage accounting and readiness

Each run reports these truthful denominators:

- selected universe;
- canonical eligible input universe;
- provider exact-ready capacity;
- blocked identity count;
- supplied/ready/insufficient/conflicted 15m input coverage;
- evaluated, not-evaluable, data-insufficient, and triggered lead counts;
- explicitly supplied actual live 15m coverage.

Synthetic canonical reader fixtures prove software behavior only. They never
enter production canonical storage and do not increment actual live coverage.
At this checkpoint the production audit remains:

| Item | State |
| --- | --- |
| Actual stored canonical 15m securities / receipts | `0 / 0` |
| Actual live 15m Radar coverage | `0` |
| Live Dhan packet proof | `NOT_EXECUTED_CREDENTIALS_UNAVAILABLE` |
| 15m Rule activation | `NOT_READY` |
| Radar implementation | `READY` |
| Live Radar production | `NOT_READY` |
| Radar runtime scheduler | `NOT_ACTIVE` |

The implementation has a bounded input limit of 3,000 eligible securities,
which covers the present 2,553-security selected universe without invoking a
whole-market scan. It is an in-memory computational safety bound, not an
investment or selection threshold. No synthetic benchmark is represented as
live throughput.

## 8. Explicit non-goals

This slice does not implement a live provider canary, feed, scheduler, 30m,
1h, 4h, MTF orchestration, Rule activation, indicator, technical score,
fundamental/research Brain, catalyst logic, signal lifecycle, API/UI,
notification, portfolio access, rotation, broker execution, security repair,
taxonomy repair, peer synthesis, or Dhan mismatch repair.

Pre-Breakout thresholds, 61 Rules, Rule 6 partial sector/peer evidence,
Decision Score, Six Gates, and all portfolio state remain untouched.

## 9. Validation posture

Focused tests prove the authority boundary, canonical identity, strict
prospective cutoff behavior, future evidence exclusion, no raw-provider input,
Pre-Breakout reuse, no-trigger versus data-insufficient separation,
continuity/no-trade/conflict fail-closed behavior, idempotent replay,
deterministic serialization, coverage denominators, no forbidden action
surface, and absence of provider/API/UI/persistence/broker dependencies.

The final implementation validation additionally runs existing discovery,
Pre-Breakout, 15m reader, daily/weekly reader, rule-horizon, and full backend
regressions; SQLite quick/integrity/FK checks; Markdown links; and
`git diff --check`.

## 10. Next boundary

Radar may feed the existing shared HSI evaluation only through a separately
approved `RADAR_TO_HSI_DIAGNOSTIC_ORCHESTRATION_V1` slice. If live market proof
is required first, the exact next external proof is
`PROSPECTIVE_MARKET_DATA_LIVE_CANARY_V1`. Neither follows automatically from
this discovery-only implementation.
