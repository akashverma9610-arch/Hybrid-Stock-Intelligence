# Earnings Blackout Horizon Calibration Contract V1

**Status:** `CALIBRATION_CONTRACT_READY_DATA_PARTIAL / NOT_ACTIVE / NO_NUMERIC_HORIZON`.

This is a bounded measurement and experiment-design contract for a future Gate-6
V2 event-risk horizon. It follows the conditional [V2 governance approval](EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.md)
and preserves the [repaired V2 proposal](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.md)
as immutable reviewed input. The normative machine record is the
[calibration contract artifact](EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.json).

It does **not** select a blackout duration, configure a candidate grid, change
V1's five-session Gate 6, register a V2 evaluator, collect data, run an
optimization, create a new outcome database, add a broker/order path, or
authorize portfolio action. `EVENT_RISK_HORIZON` remains
`POLICY_UNSET / CALIBRATION_REQUIRED`.

## Identity, authority and research boundary

| Field | Value |
| --- | --- |
| Baseline | `a42860e42074e5e93da982487bac4ed23707baf2` |
| Candidate / parent | `execution-gate-policy-v2-proposed / v2-proposal.2`; `six-gates-production-v1 / v1` |
| Proposal fingerprint | `sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21` |
| Governing approval | `earnings-blackout-policy-v2-governance-approval/v1`; `GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS` |
| Contract identity | `earnings-blackout-horizon-calibration-contract / v1` |
| Review authority | User-delegated bounded calibration-contract review; no human signature or named-person attestation claimed |
| Final result | **A — `CALIBRATION_CONTRACT_READY_DATA_PARTIAL`** |

Earnings disclosures can have discrete reactions, overnight/opening effects and
elevated uncertainty. That supports measuring event risk, not a universal
blackout number or earnings-direction forecast. The existing
[research receipt](EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1.md) already
classifies V1's five sessions as a strategy assumption, not a calibrated optimum.
[Patell & Wolfson (1984)](https://doi.org/10.1016/0304-405X(84)90024-2) documents
intraday, overnight and volatility responses around announcements; [NBER Working
Paper 31360](https://www.nber.org/papers/w31360) supports a risk/opportunity-cost
trade-off. Neither source chooses an Indian-market HSI threshold.

The [NSE compliance calendar](https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board)
provides disclosure context only. Regulation-29 timing is not an event-risk
horizon, does not prove HSI knew a schedule earlier, and cannot supply a
two-working-day substitute.

## Two non-interchangeable calibration layers

| Layer | Population | Question | Explicit exclusion |
| --- | --- | --- | --- |
| `MARKET_EVENT_RISK_CALIBRATION` | Reconciled earnings events with eligible event and market evidence | How large and heterogeneous is intrinsic event risk by pre-event session distance? | Whether HSI had a trade setup |
| `HSI_ACTION_IMPACT_CALIBRATION` | Only genuinely PIT-admitted HSI fresh-entry opportunities | Would an otherwise identical veto reduce risk enough to justify its opportunity cost? | Manufactured hindsight setup, score, gate, or entry |

The layers cannot be pooled, substituted, or silently averaged. Market-layer data
may describe risk even where HSI had no opportunity. Action-layer outcomes require
the exact setup/signal/gate version and decision snapshot that existed at the
decision time. Neither layer predicts an earnings beat, miss, or direction.

## Immutable event and decision contracts

The future non-active record is `EarningsEventCalibrationObservation / v1`; it is
a contract shape, not a new domain class, API, migration, table, repository or
producer. Its identity contains the canonical instrument, reconciled schedule
event and all underlying NSE/BSE source lineages, schedule policy/version/
fingerprint, scheduled date, known-at perspective, HSI first-observed receipt,
revision/reschedule lineage, actual result filing/publication information where
later available, event type/scope, calibration mode and immutable fingerprints.

One reconciled logical event is counted once. Identical dual-exchange evidence is
retained beneath that event; ambiguous or conflicting evidence is rejected or
reported, never resolved by source order. Original schedule, revision, reschedule,
cancellation and final event all retain their own `known_at`. A later amendment
cannot rewrite an earlier decision snapshot.

Every eligible decision snapshot freezes:

- `decision_as_of` and exact decision-session identity;
- only schedule evidence and scheduled date visible then under an explicit
  public-market or HSI-local known-at perspective;
- registry, strategy, Gate-policy ID/version/fingerprint;
- market-data and diagnostic fingerprints;
- setup/signal state and fingerprint, and a portfolio reference only when the
  action layer actually requires it.

The [known-at contract](../../app/filings/earnings_schedule_known_at.py),
[identity bridge](../../app/filings/earnings_schedule_identity.py),
[coverage contract](../../app/filings/earnings_schedule_coverage.py) and
[schedule store/lifecycle](../../app/filings/earnings_schedule_store.py) remain
the sole owners. `STRICT_HISTORICAL_PIT_CALIBRATION` requires exact decision-time
known-at and versioned visible evidence; later-discovered schedules are excluded
and reported, never backfilled. `PROSPECTIVE_SHADOW_CALIBRATION` starts only after
an official collector creates immutable automatic first-observed receipts and
freezes HSI's pre-event state. `CURRENT_DESCRIPTIVE_RESEARCH` is clearly labelled
as non-PIT and can never promote a horizon by itself.

## Realized outcomes do not alter decision truth

The outcome layer may later retain final event date, actual result filing and
known-at, publication/session relationship, final lifecycle and price outcomes.
It must never copy that information into the earlier snapshot.

| Publication evidence | Candidate first tradable reaction session | If unavailable |
| --- | --- | --- |
| Exact pre-open time | Same regular exchange session only when operating-time and session provenance are both known | `TEMPORAL_OUTCOME_INCOMPLETE` |
| Exact during-session time | Intraday reaction only with canonical intraday time/order evidence | `TEMPORAL_OUTCOME_INCOMPLETE` |
| Exact after-close time | Next regular exchange session only when that session is proven | `TEMPORAL_OUTCOME_INCOMPLETE` |
| Date only | None; no intraday time or adjacent session is invented | `TEMPORAL_OUTCOME_INCOMPLETE` |
| Special/non-standard session | Only with exact session class and tradability provenance | `TEMPORAL_OUTCOME_INCOMPLETE` |

`TRADING_SESSIONS_TO_EVENT` is the count of canonical exchange sessions strictly
after the decision session and on or before the exact, mappable scheduled-event
session. It uses exchange sessions—not calendar days. A non-session or unmappable
scheduled date is incomplete, not shifted to a nearby session. The dataset retains
the whole observed integer-distance curve. It preselects neither 2, 3, 5, 7 nor
any post-outcome grid.

## Risk, liquidity and opportunity measurements

Available exact measures are conditional on a proven reaction session and
pre-event canonical observations:

| Metric | Definition | Missing-input result |
| --- | --- | --- |
| Signed opening gap | `(reaction_open - pre_event_visible_close) / pre_event_visible_close` | `UNAVAILABLE` |
| Absolute opening gap | `abs(signed opening gap)` | `UNAVAILABLE` |
| ATR-normalized opening gap | `abs(reaction_open - pre_event_visible_close) / pre_event canonical ATR` | `UNAVAILABLE` |
| Reaction-session return | `(reaction_close - reaction_open) / reaction_open` | `UNAVAILABLE` |
| Absolute reaction-session return | `abs(reaction-session return)` | `UNAVAILABLE` |

ATR must reuse the existing canonical `ATR14` computation and only an input
lineage visible before the decision. This contract creates no ATR formula and no
future leakage. Realized volatility, MFE, MAE, post-event drawdown and volatility
normalization remain `UNAVAILABLE` until a separate policy fixes outcome windows,
reference prices, estimators and missing-data treatment. Zero is never a missing
metric.

Liquidity/volume/turnover can be optional enrichment only with canonical lineage.
Opening liquidity requires suitable provenance; bid/ask spread is never invented.
Slippage is `MEASURED_SLIPPAGE` only from execution or a separately governed
shadow execution model, `PROXY_ONLY` only when explicitly labelled, otherwise
`UNAVAILABLE`.

Action-layer opportunity cost is measured only against an exact versioned,
otherwise identical no-veto opportunity: return/MAE/loss avoided, MFE/profit or
capital-days forgone, missed valid setup and `FALSE_VETO_BURDEN`. A later price
rise alone is not a false veto; any such conclusion needs predeclared combined
risk-and-opportunity criteria. The reuse point is immutable paper/forward-paper
outcomes when complete—not synthetic entries, fills or trades.

## Curve, heterogeneity and anti-overfit rules

The output is a descriptive event-risk curve by observed session distance,
retaining raw distributions, median, tail adverse moves, worst observations and
drawdown distribution. An arbitrary tail quantile, sample minimum or promotion
threshold is not approved. The sample states are `SAMPLE_INSUFFICIENT`,
`RESEARCH_ONLY`, `CALIBRATION_ELIGIBLE`, `OOS_VALIDATED` and
`PROSPECTIVE_VALIDATED`; numeric promotion rules need later governance.

Stable strata may include market regime, liquidity tier, reliably known event
type, broad economic type, market-cap/liquidity class and known-at lateness. Tiny
subgroups and stock-specific horizon optimization are prohibited. Benchmarks reuse
canonical Nifty 50/Nifty 500 and relevant sector evidence where available; no new
benchmark engine. Their purpose is separating market-wide behavior from company
event behavior.

Any later policy comparison freezes strategy/setup logic, other gate logic and
execution model, comparing only `NO_EARNINGS_VETO` with candidate session-distance
veto policies. It must use training/calibration, temporal holdout or walk-forward,
out-of-sample evidence and prospective shadow evidence. It may not choose the
highest historic return, build a grid after observing results, or self-modify an
active rule. Future experiment records reuse the controlled experiment and OOS
governance in [experiments](../../app/backtest/experiments.py),
[self-improvement bridge](../../app/self_improvement/experiment_bridge.py) and
[OOS evidence](../../app/self_improvement/oos_evidence.py); no calibration store
is authorized. Human governance remains the only selection authority.

## Current readiness and explicit gaps

The review used a read-only production schema/count audit, without acquisition or
mutation. The matrix records capability, not a permanent data claim.

| Input | State | Role | Current basis |
| --- | --- | --- | --- |
| Historical schedule PIT | `NOT_READY` | Mandatory | No production schedule-candidate/coverage tables |
| Prospective schedule receipts | `NOT_READY` | Mandatory | Pure first-observed contracts exist, but no activated producer/receipt store |
| Daily bars | `READY` | Mandatory | Canonical 1D OHLCV exists |
| ATR lineage | `PARTIAL` | Mandatory for ATR metric only | Canonical ATR exists; no event-decision binding |
| Actual result publication linkage | `PARTIAL` | Mandatory for realized event linkage | Filing evidence exists; no reconciled schedule→result outcome link |
| Opening prices | `READY` | Mandatory for opening gap only | Daily OHLCV open exists when reaction session is proven |
| Market benchmark | `READY` | Optional enrichment | Canonical Nifty 50/500 1D series exists |
| Sector benchmark | `PARTIAL` | Optional enrichment | Some series exist; event-time PIT mapping/coverage needs audit |
| MFE/MAE-capable path | `PARTIAL` | Optional until outcome window governed | OHLCV exists; reference/window policy absent |
| Slippage evidence | `NOT_READY` | Optional enrichment | No measured execution/bid-ask provenance |
| HSI pre-event setup records | `PARTIAL` | Mandatory for action layer only | Setup assessments exist, but no matched historical signal/gate/paper outcome chain |

Missing mandatory evidence excludes an observation only from its relevant mode and
reports the reason. Missing optional enrichment leaves other eligible metrics
available and itself `UNAVAILABLE`. No new source hunt begins here.

## Boundaries and next step

Retained: `V1_ACTIVE=TRUE`, `GATE_POLICY_V2_ACTIVE=FALSE`,
`SIX_GATES_EXACTLY_SIX=TRUE`, `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`,
`NO_RETROACTIVE_BLACKOUT=TRUE`, `NO_FUTURE_LEAKAGE=TRUE`,
`NO_HORIZON_GUESS=TRUE`, `PILOT_SIMPLICITY_RULE=ACTIVE`,
`AI_DECISION_AUTHORITY=FALSE`. There is no earnings-direction claim, live order,
portfolio mutation, score/gate weight change or V2 execution authority.

The exact next continuation is **`EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1`**,
not started. It must close the mandatory prospective source/receipt boundary
before any shadow collection can be called feasible. It must not choose a horizon
or activate Gate 6 V2.
