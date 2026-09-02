# Post-V1 Batch 1 — Event/Catalyst and Market-Red Resilience Policy Proposal

**Status: `PROPOSED / POLICY_APPROVAL_REQUIRED / DOCUMENTATION_ONLY / NOT_ACTIVE`.**

## Scope

This is the single approval packet for `EVENT_CATALYST_INTELLIGENCE` and
`MARKET_RED_RELATIVE_RESILIENCE` from the [Strategy Catalogue](POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md).
It selects no policy and creates no runtime, persistence, API, UI, score,
setup, gate, alert, order, broker authority, portfolio mutation, or trade
instruction. Any future implementation remains `WATCH_ONLY / NON_EXECUTABLE`.

## Reusable Core V1 facts and limits

| Boundary | Reusable facts | Limit |
| --- | --- | --- |
| External intelligence | Immutable event/evidence identity, timestamps, materiality, policy stage, sources, exact exposures, deduplication, re-evaluation, and FACT/DATA/INTERPRETATION/INFERENCE. | Not a directional catalyst or trade policy. |
| Watch/router | Immutable PIT Watch lineage and `CATALYST_WATCH`, `POLICY_LED_INFLECTION`, `RELATIVE_STRENGTH_WATCH`, `RISK_WATCH`. | An archetype is not a strategy. |
| Diagnostics and market data | Canonical diagnostics, OHLCV/index data, official delivery, sector RS/breadth, regime/extremes, freshness and quality states. | No approved Batch 1 calculations, thresholds, or direction. |
| P1 / Pre-Breakout | Read-only provenance and the only approved strategy policy. | Cannot be generalized to Batch 1. |

Primary exchange, regulator, government, issuer, and company sources are first.
Reliable business/financial media is secondary research. Social sentiment,
rumours, and GMP-like material are low-reliability context only. Missing,
future, stale, ambiguous, conflicted, low-quality, or non-comparable evidence
must fail closed. No numerical weight, threshold, lookback, cutoff, persistence
window, expiry, or beta approximation is authorized by this document.

## A. `EVENT_CATALYST_INTELLIGENCE`

The proposed output is a descriptive Watch/research classification of a novel,
material, PIT-visible change affecting an exact company, sector, or transmission
chain. It cannot predict price, assert a thesis, create a setup, pass Six Gates,
authorize capital, or execute.

Required provenance: retained primary source; immutable `what_changed` and
duplicate/conflict state; exact canonical identity and verified direct or
supply-chain exposure for a company-level result; named transmission mechanism;
counterevidence and governance/legal-risk state. For policy events the policy
must not skip:

`announcement → legal/rule approval → funding → tender/orders → eligible company capacity → execution → revenue → cash flow`.

Exposure remains direct, supplier/enabler, indirect, or narrative-only.
`priced-in` and price reaction remain `NOT_ASSESSED` until an approved,
PIT-valid reaction method exists. Governance/legal negative risk may only
block/escalate review; it can never automatically exit or sell.

| Decision | Options | Recommended default |
| --- | --- | --- |
| EC-1 primary trigger sources | issuer/exchange; add regulator/government; include media trigger | issuer/exchange plus regulator/government; media context only |
| EC-2 company exposure | direct only; direct plus verified supply-chain; include indirect/thematic | direct plus verified supply-chain |
| EC-3 output vocabulary | no direction; descriptive catalyst/risk; numeric score | descriptive catalyst/risk with unavailable/conflicted states |
| EC-4 materiality | critical/high; include medium; all | existing critical/high; no numeric weight |
| EC-5 freshness/expiry/cancellation | select versioned event-family treatment | historical review required; no universal duration |
| EC-6 reaction/priced-in | unavailable; descriptive method; infer from price | unavailable; price inference prohibited |
| EC-7 legal/governance response | review/block; label; automatic sell | review/block only |

## B. `MARKET_RED_RELATIVE_RESILIENCE`

The proposed output is a descriptive, Watch-only stock-resilience classification
during an approved broad-market weakness condition. It cannot claim sponsorship,
breakout, a setup, a capital decision, or a trade.

Required provenance: explicit benchmark; completed session/window; PIT-valid
index and breadth/regime coverage; aligned stock/benchmark return windows and
adjustment/calendar/method lineage; exact sector mapping; liquidity/delivery/
volume evidence when selected; and approved persistence/staleness. Current
sector RS/breadth/rank/Top-3 cannot be retrojected as historical evidence.
Beta-adjusted abnormal strength remains unavailable without an approved method
and sufficient history. Market extremes/regime are context only.

| Decision | Options | Recommended default |
| --- | --- | --- |
| MR-1 benchmark set | NIFTY 50; NIFTY 50 plus NIFTY 500; sector first | NIFTY 50 plus NIFTY 500, explicit per output |
| MR-2 weak-market definition | return; return plus breadth; regime/extremes | return plus breadth; calibrate thresholds separately |
| MR-3 resilience metric | excess return; beta-adjusted; both | excess return initially |
| MR-4 sector confirmation | none; sector RS; RS plus breadth | sector RS; breadth waits for durable parity |
| MR-5 liquidity/delivery filter | select exact tests | calibrated, versioned filter only |
| MR-6 gap/news treatment | exclude; label; count as resilience | exclude unlinked gap/news |
| MR-7 persistence/expiry | select window/staleness | research and shadow evidence required |
| MR-8 invalidation | define normalization/liquidity/risk treatment | explicit versioned rule or unavailable |

## Required implementation and shadow evidence after approval

Each family must be implemented separately as a pure Watch-only policy/output.
Tests must prove identity, PIT/future exclusion, deterministic ordering,
missing/stale/conflicted handling, source/risk blockers, serialization, and no
broker/order/portfolio side effect. Historical replay and prospective shadow
evaluation must retain policy/evidence identity, benchmark/regime, freshness,
coverage, and a locked outcome method. A migration, retention change, or
execution-adjacent record requires separate persistence approval.

## Approval gate

`HSI_CONTINUOUS_LOOP_PAUSED / POLICY_APPROVAL_REQUIRED / BATCH_1`

All Batch 1 strategies remain `STRATEGY_UNAVAILABLE / NOT_ACTIVE`. To resume,
approve/amend/reject `EC-1`–`EC-7` and `MR-1`–`MR-8` and state:

> Approve Batch 1 Event/Catalyst and Market-Red Resilience policy defaults in
> `POST_V1_BATCH_1_EVENT_CATALYST_AND_RESILIENCE_POLICY_PROPOSAL.md` for
> Watch-only, non-executable implementation. No persistence, API/UI,
> portfolio mutation, broker/order authority, or trade authorization is
> approved.
