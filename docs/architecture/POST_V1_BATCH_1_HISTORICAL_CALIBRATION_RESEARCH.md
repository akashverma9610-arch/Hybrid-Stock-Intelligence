# Post-V1 Batch 1 — Historical Calibration Research Receipt

**Status: `POLICY_BOUNDARIES_APPROVED / OPERATIONAL_PARAMETERS_UNAVAILABLE / STRATEGY_UNAVAILABLE / NOT_ACTIVE`.**

## Purpose and scope

This is the retained-data calibration receipt for the Event/Catalyst and
Market-Red Relative Resilience policy boundaries in the [Batch 1 policy
proposal](POST_V1_BATCH_1_EVENT_CATALYST_AND_RESILIENCE_POLICY_PROPOSAL.md).
It is research documentation only. It creates no policy implementation,
signal, setup, gate, score, persistence, API, UI, portfolio access, broker
authority, order, or trade action.

The architectural/evidence decisions `EC-1`–`EC-7` and `MR-1`–`MR-8` remain
approved. Their operational parameters remain unapproved. In particular, this
receipt does not turn an absent calibrated value into a default.

## Audit method and as-of boundary

The audit was a read-only inspection of `data/nse_stock_manager.db` at the
repository checkpoint `12869a4afddec9014a63fd9865588c8dba47e293`. It inspected
only retained canonical rows and payload metadata. It did not contact a
provider, resume acquisition, write SQLite, materialize a Watch, or use current
classifications as historical facts.

An event could enter an Event/Catalyst return study only when all of the
following held:

1. a canonical event/evidence version was received on or before the research
   as-of;
2. it had an exact, verified canonical instrument exposure of an allowed type;
3. a completed, aligned stock and declared-benchmark session series existed;
4. the requested forward completed sessions had occurred; and
5. no unresolved duplicate, conflict, cancellation, or overlapping-event
   contamination invalidated the observation.

Market-Red study observations additionally require PIT-comparable historical
benchmark return, breadth, stock, sector, liquidity/delivery, persistence, and
invalidation inputs. Current-only sector rank/RS/breadth is not substituted.

## Data-readiness matrix

| Required retained input | Observed retained coverage | Calibration assessment | Limitation |
| --- | ---: | --- | --- |
| External-intelligence events | 14 canonical events and 14 evidence versions | `INSUFFICIENT_FOR_CALIBRATION` | Receipt range is 2026-09-01T03:16:02.696979+00:00 to 2026-09-02T03:04:59.092334+00:00; no forward completed-session history was retained after the event window. |
| Event families | CAPEX 3; COMMODITY 1; GEOPOLITICAL 4; GOVERNANCE 1; GOVERNMENT_POLICY 2; MACRO_DATA 2; REGULATORY 1 | `INSUFFICIENT_FOR_CALIBRATION` | Every family has too few observations for family-specific lifecycle research. |
| Materiality | CRITICAL 2; HIGH 11; MEDIUM 1 | `INSUFFICIENT_FOR_CALIBRATION` | The approved `CRITICAL`/`HIGH` comparison has only 13 observations before exposure and forward-window filtering. |
| Source class | 12 raw primary-source type labels across 14 events | `INSUFFICIENT_FOR_CALIBRATION` | The retained free-form source-type labels are not a historical, versioned source-hierarchy classification. |
| Event timestamps | `published_at`, `discovered_at`, and `received_at`: 14/14; `effective_at`: 1/14 | `PARTIAL` | Session alignment may use received time only where a separate approved session rule exists; no such Batch 1 rule is approved. |
| Exact verified company exposure | 0 eligible mappings | `INSUFFICIENT_FOR_CALIBRATION` | Two records contain a `DIRECT` exposure row, but both have no canonical instrument ID and `UNVERIFIED_INFERENCE` verification status; the other 12 have no company exposure. |
| Supersession/cancellation | 0 events with multiple retained evidence versions | `INSUFFICIENT_FOR_CALIBRATION` | No typed supersession/cancellation lifecycle sample exists. Counter-evidence is present for 9 events, but it is not a supersession or cancellation marker. |
| Aligned stock prices for eligible events | 0 eligible event/instrument pairs | `INSUFFICIENT_FOR_CALIBRATION` | The exposure precondition prevents stock/benchmark alignment. |
| NIFTY 50 daily bars | 746 rows, 2023-08-27T18:30:00+00:00 to 2026-08-30T18:30:00+00:00 | `PARTIAL` | Retained bar timestamps do not themselves certify completed-session eligibility or provide post-event windows. |
| NIFTY 500 daily bars | 1,673 rows, 2023-08-21T18:30:00+00:00 to 2026-08-30T18:30:00+00:00 | `PARTIAL` | Same session-certification and post-event limitations. |
| Historical breadth | No durable historical breadth artifact found | `UNAVAILABLE` | The approved comparability policy classifies current breadth as current-only. |
| Historical sector-relative strength / breadth | 5 current sector-ranking snapshots; no durable historical parity artifact | `UNAVAILABLE` | Current rank/RS/breadth cannot be retrojected into research observations. |
| OHLCV volume / traded value | 1,545,139 daily bars across 2,561 instruments; volume present for all rows; turnover/trade count present for 48 rows | `PARTIAL` | Coverage and comparability vary by instrument/provider; no approved liquidity filter, adjustment/parity rule, or eligible historical constituent interval was established for this study. |
| Official delivery | 9,122 observations for 2,314 instruments across four trade dates (2026-08-20, 2026-08-27, 2026-08-28, 2026-09-01) | `INSUFFICIENT_FOR_CALIBRATION` | Four non-contiguous dates cannot support historical liquidity/delivery distributions, persistence, or invalidation research. |

The retained historical bars span 2023-08-21T18:30:00+00:00 through
2026-08-31T18:30:00+00:00 across 2,561 instruments. That broad raw-bar count
does not cure the missing exact event mappings, forward observations, historical
breadth, sector parity, or delivery history.

## Event/Catalyst calibration result

The requested 1, 2, 3, 5, and 10 completed-session observation windows each
have **zero PIT-eligible event/instrument observations**. Consequently no
benchmark-relative return, sector-relative return, maximum favourable/adverse
excursion, persistence percentage, timing split, or contamination-adjusted
estimate was calculated.

| Candidate lifecycle parameter | Eligible sample | Result | Evidence strength | Decision |
| --- | ---: | --- | --- | --- |
| Freshness by event family | 0 | No empirical distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Supersession treatment | 0 typed cases | No lifecycle comparison | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Cancellation treatment | 0 typed cases | No lifecycle comparison | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Staleness / expiry | 0 | No persistence estimate | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Receipt-time session alignment | 0 eligible pairs | No before/during/after sample | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Direct versus verified supply-chain exposure | 0 verified pairs | No comparative return sample | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Positive catalyst versus adverse risk | 0 eligible pairs | No classified price study | None | `INSUFFICIENT_FOR_CALIBRATION` |

No price movement is interpreted as causal or priced-in. The retained
`FACT → DATA → INTERPRETATION → INFERENCE` separation, counter-evidence, and
legal/governance review/block boundary remain required safeguards, not a basis
for parameter estimation.

## Market-Red calibration result

No Market-Red candidate can be evaluated without inventing a weak-market
definition, historical breadth, a versioned liquidity/delivery treatment,
persistence, or invalidation semantics. The source data cannot support
research/validation/holdout separation for the requested policy.

| Candidate parameter family | Eligible sample | Result | Evidence strength | Decision |
| --- | ---: | --- | --- | --- |
| NIFTY 50 lower-tail return weakness | 0 PIT-complete breadth intersections | No return-plus-breadth distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |
| NIFTY 500 lower-tail return weakness | 0 PIT-complete breadth intersections | No return-plus-breadth distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Stock-minus-benchmark excess return | 0 eligible historical cohorts | No resilience distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Sector-relative confirmation | 0 comparable historical sectors | Current-only input excluded | None | `UNAVAILABLE` |
| Traded-value / volume filter | 0 eligible historical cohorts | No policy-owned comparable distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Official-delivery filter | 0 sufficient historical cohorts | Four retained dates are inadequate | None | `INSUFFICIENT_FOR_CALIBRATION` |
| One-of-next-two / two-within-three / consecutive persistence | 0 qualifying observations | No sensitivity analysis | None | `INSUFFICIENT_FOR_CALIBRATION` |
| Expiry and invalidation | 0 qualifying observations | No observed lifecycle failure distribution | None | `INSUFFICIENT_FOR_CALIBRATION` |

The empirical candidates named in the policy proposal remain research methods,
not selected thresholds: lower-tail return/breadth quantiles, excess return,
close-location strength, traded value/volume/delivery distributions, and the
three persistence variants. Beta-adjusted return remains unavailable because no
approved beta method, window, or data contract exists.

## False-positive and false-negative trade-offs

Selecting a universal freshness duration from the 14-event intake would create
a false-positive risk by treating unverified or unmapped narrative as a
company-level catalyst. It would also create a false-negative risk by expiring
long implementation-chain policy evidence without a family-specific sample.

Selecting market-weakness, liquidity, persistence, or invalidation parameters
from raw bars alone would create false positives through absent historical
breadth/sector parity and sparse delivery coverage. It would create false
negatives by excluding valid resilient observations with a non-validated
filter. These risks cannot be quantified from the retained dataset.

## Prospective collection requirements

Before another calibration attempt, retain a sufficiently long PIT-safe
prospective corpus with:

1. versioned source-hierarchy classifications and immutable received,
   published, discovered, and effective timestamps;
2. exact, verified direct and supply-chain canonical exposure mappings;
3. typed supersession, cancellation, conflict, and legal/governance-risk
   lifecycle events;
4. exchange-calendar-certified completed sessions and aligned stock, NIFTY 50,
   and NIFTY 500 observations after each eligible receipt;
5. PIT-complete historical breadth and historically comparable sector lineage;
6. sufficient official delivery/traded-value/volume history with source and
   adjustment provenance; and
7. a predeclared chronological research/validation/holdout plan with minimum
   coverage and concentration checks approved before selection.

## Exact next approval decision

No `RESEARCH_SHADOW_V1` parameter value is defensible from the retained data.
The recommended option is to approve a prospective, non-signalling collection
and calibration protocol first; it must not activate either strategy. A later
approval may select versioned values only after the protocol has retained a
PIT-complete sample and reported coverage, stability, sensitivity, turnover,
and concentration.

> Approve a prospective Batch 1 calibration-collection protocol with no
> Event/Catalyst or Market-Red Watch eligibility, no operational parameter
> selection, no persistence migration, no API/UI, no portfolio access, and no
> broker/order or trade authority. Resume parameter selection only after a
> separately reviewed PIT-safe calibration receipt supports exact versioned
> `RESEARCH_SHADOW_V1` values.
