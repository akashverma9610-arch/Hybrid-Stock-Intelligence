# Earnings Blackout Horizon Policy Research V1

**Status:** `RESEARCH_COMPLETE / EXECUTION_GATE_POLICY_V2_REQUIRED / V2_NOT_ACTIVE / GATE6_V1_UNCHANGED / NON_EXECUTABLE`.

This is a policy-governance record, not a new gate. It follows the [coverage/window policy](EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1.md) and preserves `V1_ACTIVE=TRUE`, `V2_ACTIVE=FALSE`, `V2_SHADOW_ONLY=TRUE`, `B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY`, `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`, `NO_AI_PREDICTED_EARNINGS_DATE=TRUE`, and `NO_HISTORICAL_RESULT_DATE_AS_FUTURE_SCHEDULE=TRUE`.

No Gate 6 implementation, five-session value, trading-calendar arithmetic, schedule ingestion, score weight, portfolio policy, API/UI, broker/order capability, or V2 activation changes in this slice.

## Risk intent, separate from a number

Gate 6 exists to keep a **fresh entry** from crossing a known binary financial-results event without an explicit risk decision. The architectural objective is to limit unexpected event-gap/slippage exposure, thesis invalidation immediately before new fundamental information, and the possibility that a structural stop is crossed by an event gap. It is not to forecast results, predict their date, label a company bearish, or prevent management of an existing position.

The five-session value is an implementation parameter, not that architectural objective. Current V1 already leaves `HOLD_EXISTING`, `REDUCE_EXISTING`, `EXIT_EXISTING`, and `RISK_MANAGEMENT` available; it is a fresh-entry gate only. [Earnings Blackout](../EARNINGS_BLACKOUT.md)

## Event-risk research boundary

Earnings announcements are information events. Established empirical work observes rapid price responses, return-variance disturbances that persist for hours and into the next trading day, and overnight/opening effects around earnings announcements. [Patell & Wolfson, *Journal of Financial Economics* (1984)](https://doi.org/10.1016/0304-405X(84)90024-2) Research also reports that firm beta rises on earnings-announcement days and reverts over roughly two to five days in that sample; it is not a prescription for an HSI blackout duration. [Patton & Verardo, *Review of Financial Studies* (2012)](https://doi.org/10.1093/rfs/hhs073)

Institutional investors reducing exposure before earnings in one empirical study, and global evidence linking earnings-announcement uncertainty with idiosyncratic volatility, support treating a known earnings event as risk context. They do **not** validate a particular Indian-market horizon, entry rule, or performance claim. [NBER Working Paper 31360](https://www.nber.org/papers/w31360) and [CFA Institute research digest](https://rpc.cfainstitute.org/research/cfa-digest/2013/11/the-earnings-announcement-premium-around-the-globe-digest-summary)

The research supports an event-risk control, not an optimised five-session parameter. Any numeric horizon needs its own Indian-market, source-known-at, trading-cost, missed-opportunity, drawdown, gap, and false-block calibration under B14.

## Authoritative notice reality

The current NSE Main Board compliance calendar describes Regulation 29 prior intimation as at least **two working days** in advance, excluding the intimation and meeting dates. It also says the calendar is indicative and directs issuers to the current consolidated regulations. [NSE Compliance Calendar](https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board)

Therefore, **NO**: an authoritative Regulation 29 notice cannot guarantee schedule knowledge by `T-5` trading sessions. A source can be perfectly fresh after a late notice without making the preceding three sessions knowable.

Historical replay needs an effective-dated rule. SEBI's 2020 circular records the earlier five-day financial-results rule and a temporary two-day relaxation; SEBI material from 2023 still described the then-five-day results notice, while the later regulatory path is reflected in the current NSE two-working-day calendar. This slice does not infer an exact universal switch date. [SEBI 2020 circular](https://www.sebi.gov.in/sebi_data/attachdocs/apr-2020/1587109438485.pdf), [SEBI 2023 board material](https://www.sebi.gov.in/sebi_data/meetingfiles/apr-2023/1681702875120_1.pdf), and [SEBI 2024 review material](https://www.sebi.gov.in/sebi_data/meetingfiles/mar-2024/1711019079991_1.pdf).

Regulation 33 filing deadlines remain results-season context, never a verified scheduled-meeting date. New listings, delayed results, reschedules, special audits, financial-year changes, extraordinary meetings, and regulatory extensions reinforce why cadence or a reporting deadline cannot manufacture a schedule.

## Existing five-session origin

Repository history shows the configured-sessions design in the migrated baseline `d64bb98`; the exact value `5` was formally materialised in the human-approved `six-gates-production-v1` policy at `9c9af08`. The master specification and execution-gate registry describe the same value, but no primary regulation, empirical calibration record, or strategy research source for `5` is retained.

Classification: **`STRATEGY_ASSUMPTION` with historical provenance `UNKNOWN`**. It is neither a Regulation 29 requirement nor a documented research-based optimum. This is not a criticism of V1; it is the reason a material change must not be silently edited.

## Policy families

| Family | Safety and PIT truth | Source feasibility / pilot practicality | Failure mode | Governance conclusion |
| --- | --- | --- | --- | --- |
| 1. Verified-schedule hard blackout | Strong once exact schedule is known; cannot retroactively protect `T-5` through `T-3` after a `T-2` notice. | Requires a trusted prospective future-event producer; presently unavailable. | Late notice yields less lead-time protection. | Necessary hard control, but not sufficient alone. |
| 2. Reporting-season risk context | Honest only if labelled broad context, not a schedule or clearance. | Regulation 33 can identify a broad season; no exact event/PIT date follows. | Can be over-read as a forecast if exposed as a hard gate. | Optional evidence outside Gate 6; no score, size, or confidence parameter is approved here. |
| 3. Unknown schedule always blocks entry | Conservative and PIT-safe. | Likely impractical while notices commonly arrive shortly before events and coverage remains incomplete. | Can freeze valid fresh-entry eligibility for most/all issuers. | Not recommended without measured pilot/usability evidence. |
| 4. Source-aware dynamic blackout | Blocks from trusted `known_at` onward, preserving causal truth. | Requires a source-backed future schedule, known-at/revision lineage, and a separately governed horizon. | Does not supply pre-notice protection. | Best hard-control pattern after policy versioning and calibration. |
| 5. Earlier authoritative source | Could support a longer verified horizon only if identity, known-at, revision/cancellation, and complete coverage are proven. | No HSI-verified source currently guarantees `T-5` for all relevant issuers. | A partial corporate calendar would create false confidence. | Not a current authority; no analyst, broker, AI, or cadence estimate may substitute. |

Company-published calendars, exchange event calendars, and formally announced investor calendars may later be researched as first-party source candidates. None is currently established as a complete, exact, revision-aware authority that guarantees `T-5`; this record makes no universal claim that none can ever exist.

## Hard gate, soft context, and three-state semantics

The proposed future architecture is a separation, not a change in this slice:

1. **Hard verified-event block:** only a trusted, exact, prospective results schedule can support a Gate 6 block. A later `known_at` starts protection only then; it never backdates knowledge.
2. **Soft results-season context:** a reporting deadline may be displayed as broad `ELEVATED_EARNINGS_RISK_WINDOW` context outside Gate 6. It cannot supply a schedule, clearance, score change, sizing instruction, or execution authority without separately approved policy.
3. **Three state clearance:** `BLOCKED`, `CLEAR`, and `UNKNOWN` must be distinct. Current sources can support neither a clear state nor a complete absence certificate. `NO_NOTICE_FOUND != NO_EARNINGS_EVENT` remains binding.

`BLOCKED` is supported only by a verified event inside the future governed window. `CLEAR` would require separately approved complete, fresh, exact, revision-aware authoritative coverage. `UNKNOWN` is the required state for missing, partial, stale, failed, conflicted, or not-yet-known schedule evidence.

The recommended minimum for a safe 25–30 user pilot is: trusted positive schedules block; unknown is visibly surfaced; no fabricated clear state; no predicted date; no historical backdating. This is sufficient to preserve research usefulness while withholding execution eligibility when the gate input remains unknown. It does not require perfect historical schedule reconstruction; the prospective source-first model is enough for a future pilot.

## Entity and analysis boundaries

Regulation 29 schedule semantics are common listed-entity disclosure mechanics in the evidence inspected; this research finds no basis for distinct bank, NBFC, insurer, or industrial blackout numbers. Entity-specific financial interpretation does not justify a different schedule rule here.

A missing schedule should **not** block the entire HSI research analysis. It should block only `ENTRY_READY` / execution authority through an `UNKNOWN` Gate 6 state, while leaving the research result descriptive and complete only to its own evidence boundaries.

Non-active SenseEdge wording should be factual:

```text
Earnings Event: VERIFIED — <source date>
Earnings Risk: SCHEDULE NOT VERIFIED
Earnings Clearance: UNAVAILABLE
```

This describes evidence availability, not a bearish judgement, trade instruction, or investor recommendation.

## Option comparison

| Option | Risk protection | Source feasibility / PIT safety | Pilot usability | Complexity / calibration | Versioning impact |
| --- | --- | --- | --- | --- | --- |
| A — `KEEP_FIXED_5_SESSION_HARD_GATE` | Full only if an earlier schedule is known. | Current Regulation 29 cannot guarantee it; PIT-safe only for observed schedules. | Low if unknown blocks broadly; otherwise false-clear risk. | Existing number remains uncalibrated. | No change, but conflict remains. |
| B — `VERIFIED_SCHEDULE_DYNAMIC_HARD_BLOCK` | Reduces risk from verified `known_at` onward. | Feasible only after trusted schedule producer; causal and PIT-safe. | Better than A but no broad season context. | Horizon still requires B14 calibration. | `EXECUTION_GATE_POLICY_V2` required. |
| C — `VERIFIED_HARD_BLOCK_PLUS_SOFT_RESULTS_SEASON_CONTEXT` | Same hard protection as B; transparently supplies non-authorising broad context. | Hard input must be verified; soft context is never a schedule. | Best research/pilot clarity without false clearance. | Horizon and any soft interpretation remain calibration/policy work. | `EXECUTION_GATE_POLICY_V2` plus separate optional context policy required. |
| D — `UNKNOWN_SCHEDULE_ALWAYS_BLOCKS_ENTRY` | Maximum avoidance of unknown event risk. | Does not need a positive source, so PIT-safe. | Poor until coverage/methods improve; may over-block. | Pilot false-block and missed-opportunity study required. | `EXECUTION_GATE_POLICY_V2` required. |
| E — `EARLIER_AUTHORITATIVE_SOURCE_REQUIRED` | Could protect the full intended interval. | Not currently source-proven. | Cannot pilot as an authority now. | Requires source coverage and calibration first. | Source-authority versioning; Gate V2 only if semantics or horizon change. |

## Decision, versioning, and calibration

Final decision: **`C. VERIFIED_HARD_BLOCK_PLUS_SOFT_RISK_CONTEXT_RECOMMENDED`**.

The future hard component is source-aware and dynamic from verified `known_at`; it does not select a new horizon in this research. The soft component is optional descriptive risk context outside Gate 6 and cannot create a block, clearance, score, sizing, or trade action.

Any material Gate 6 horizon or clearance change requires an explicit immutable `EXECUTION_GATE_POLICY_V2` (or equivalently governed versioned gate policy), new source lineage, tests, shadow evidence, and B14 calibration. Six Gates remain exactly six; no seventh gate is introduced.

Calibration must measure source-known-at timing, schedule revision/cancellation, event gaps, post-event volatility/drawdown, slippage, missed opportunity, false blocks, and pilot usability. It must separate new listings/irregular reporting and avoid treating observed late notices as early historical knowledge.

The [machine-readable policy receipt](EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1_RECEIPT.json) is a deterministic record of the research conclusion. Its tests prove source-policy fields, historical-version guard, option ordering/content identity, non-active states, and receipt replay.

Exact next continuation, not started: `EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL`.
