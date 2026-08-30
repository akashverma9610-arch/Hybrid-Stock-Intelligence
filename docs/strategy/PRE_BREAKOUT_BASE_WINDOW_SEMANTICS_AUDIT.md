# Pre-Breakout Base Window Semantics Audit

Status: governance audit only. This document neither changes nor interprets the selected policy as an executable strategy configuration.

## Scope and frozen policy state

The selected policy remains `pre-breakout-policy-v1` / `v1.1-draft`, with fingerprint `d61d2c51cf9af96fbee450d35b32354f688b89dc8bccba62592e761cdf39920d`. Its remaining unresolved fields are:

- `BASE_WINDOW_SELECTION_RULE`
- `SUPPORT_PIVOT_SELECTION_RULE`
- `NSE_TICK_SIZE_SOURCE`

This audit makes no policy, governance, database, materializer, scanner, or provider change.

## Existing facts

| Concern | Classification | Existing fact |
| --- | --- | --- |
| Base duration | Explicitly governed | The policy carries a minimum of 20 and a maximum of 60 sessions. It does not explicitly state comparison operators, and no production Pre-Breakout evaluator applies either bound. |
| Pivot shape | Explicitly governed input | The policy carries a 3-left / 3-right pivot setting and says resistance is `HIGHEST_CONFIRMED_PIVOT_HIGH_OR_GOVERNED_BASE_TOP`. It does not define how pivots establish a valid base. |
| Canonical price data | Existing implementation only | The materializer reads canonical resolved daily OHLCV from `HistoricalBarStore` as of the requested timestamp, but materializes no base window. |
| Strict pivots | Existing implementation only | `TechnicalAnalysisEngine.price_structure()` calls `_pivots()`. A strict high/low must exceed/fall below all bars in the configured left and right window. Equal values do not qualify. |
| BBW, ATR, volume, high proximity | Explicitly governed as separate checks | These rules have their own policy values/materialization paths. They are not a governed definition of base validity. The V1.1 volume comparison uses the evaluation session against the previous 20 valid volumes; that reference window is not the structural base window. |
| Generic `valuation_trade.base_pattern` | Generic/unrelated | It uses separate `TradeRules` (including base period, maximum depth, tolerances, stop buffer, cup/ascending-base parameters, and precedence). It is diagnostic-only and is not inherited by Pre-Breakout policy. |

## Questions A–I

### A. Window alignment

**Undefined.** Neither the policy nor the Pre-Breakout engine/materializer says whether a base must end at the evaluation session, may end earlier, or includes the evaluation session. The current materializer's evaluation session is simply the latest resolved daily bar; it does not construct a base window.

### B. Duration

The policy's 20–60 session values are governed. A future rule must make the intended comparison explicit as `20 <= session_count <= 60`; it is not currently executable because no Pre-Breakout base validator exists. No duration may be inferred from the unrelated generic five-session `TradeRules` use.

### C. Session source and missing observations

The materializer's factual source is canonical resolved daily OHLCV admitted by the historical store as of the requested timestamp. It does not define `trading session` for a base, an exchange-calendar continuity rule, or how gaps/non-trading days/missing eligible bars affect base duration. The volume rule separately selects the preceding 20 *valid volume observations*; that does not define base-session missing-data treatment.

### D. Valid-base definition

No production Pre-Breakout policy or implementation defines a valid 20–60 session base. The following classification prevents implementation accidents from becoming policy:

| Candidate criterion | Classification | Finding |
| --- | --- | --- |
| Duration 20–60 | Explicitly governed input, not implemented | Bounds exist but no base validator applies them. |
| Range compression / maximum depth | Undefined for Pre-Breakout | V1 forbids silently adding an arbitrary maximum base-range percentage. Generic `TradeRules.max_base_depth` is unrelated. |
| Pivot highs/lows / repeated resistance tests | Undefined for Pre-Breakout | Pivot parameters and a high-level resistance phrase exist; required count, placement, equality/tolerance, and role in validity do not. |
| Higher lows | Undefined for Pre-Breakout | Generic ascending-base logic is unrelated. |
| ATR contraction | Explicitly governed separate check | It is an evaluation-session indicator rule, not a base-window validity rule. |
| BBW percentile | Explicitly governed separate check | It is a trailing indicator percentile, not a base-window test. |
| Volume | Explicitly governed separate check in V1.1 | It compares evaluation volume with prior 20 valid sessions, not a base aggregate. |
| Delivery, RSI, 52-week proximity | Explicitly governed separate checks | None identifies a base. |
| Close containment, pivot minimum, window quality | Undefined | No Pre-Breakout rule/code establishes these conditions. |

### E. Pivot use and point-in-time eligibility

The technical helper is PIT-safe **when supplied a correctly as-of-bounded snapshot**. For a pivot at session `P` with a 3-right rule, `_pivots()` only visits `P` when the three following bars are present in the series. A snapshot whose observations are all market- and retrieval-visible by `as_of` therefore cannot use a pivot requiring bars after `as_of`.

This is an implementation property, not a Pre-Breakout base policy. The helper does not expose a dedicated confirmation timestamp (`P + 3 eligible bars`), does not define eligibility after missing sessions, and does not select pivots inside a candidate base. The governed materializer does not call it today. No existing critical look-ahead defect was found in this bounded-snapshot use.

### F. Multiple valid windows

**Undefined.** There is no candidate-window construction, validity evaluator, or deterministic tie-break (shortest, longest, latest, earliest, compression, or touch count) for Pre-Breakout.

### G. Zero valid windows

No explicit policy outcome exists. The safe future behavior is `UNAVAILABLE`/`PARTIAL_POLICY_BLOCKED`, not an inferred base, until a governed validity rule is selected. This is consistent with the present materializer's fail-closed treatment of unresolved policy semantics, but is not yet an implemented base result.

### H. Resistance and base top

`HIGHEST_CONFIRMED_PIVOT_HIGH_OR_GOVERNED_BASE_TOP` is a high-level resistance rule only. `governed base top` is not deterministic because no valid-base window, eligible highs set, price field (high versus close), or fallback precedence is defined. **`BASE_TOP_DEFINITION` is a distinct ambiguity.**

### I. Support dependency

The present code does not select a Pre-Breakout base and therefore does not depend on a support pivot to do so. A future base-validity rule can be governed independently of support if it confines itself to base-window construction and base-top/resistance evidence. `SUPPORT_PIVOT_SELECTION_RULE` remains separately required for structural invalidation, target height, and R:R; it must not be silently solved by base selection.

## Dependency graph

```text
canonical daily OHLCV, visible as_of
        |
        +--> candidate-window construction  [undefined]
                    |
                    +--> base validity rule [undefined]
                    |          |
                    |          +--> multiple-window selection [undefined]
                    |                         |
                    |                         +--> governed base top [undefined]
                    |                                      |
                    |                                      +--> resistance
                    |
                    +--> support-pivot selection [separately unresolved]
                               |
                               +--> stop / base height / target / R:R
```

The V1.1 volume statistic is deliberately outside this graph: it measures the evaluation session against its previous 20 valid volume observations and does not choose or validate a base window.

## Outcome and recommended next governance action

**Outcome B — base validity is not fully governed.** The unresolved `BASE_WINDOW_SELECTION_RULE` is not merely a tie-break problem. It cannot safely be resolved on its own because candidate-window alignment, valid-base criteria, zero-window behavior, and base-top meaning are also undefined.

Do **not** create a successor policy from this audit. The recommended next governance-only scope is to introduce, review, and separately approve a typed `BASE_WINDOW_VALIDITY_RULE` before any `BASE_WINDOW_SELECTION_RULE`. It should state at least:

1. candidate-window end convention and whether the evaluation session belongs;
2. explicit inclusive 20–60 canonical-session bounds;
3. exact eligible-session and missing-data policy;
4. PIT pivot eligibility, including confirmation only after the third following eligible session is visible as of evaluation;
5. a minimal, deterministic structural validity predicate that does not add an arbitrary maximum base-range percentage;
6. zero-valid-window result as fail-closed/unavailable; and
7. an explicit base-top definition independent of support/tick semantics.

Only after those semantics are approved should a distinct selection rule define the deterministic tie-break among valid windows. Support and NSE tick-source semantics should remain separate governance items.

## Newly named ambiguities

- `BASE_WINDOW_ALIGNMENT_RULE`
- `BASE_SESSION_ELIGIBILITY_AND_GAP_RULE`
- `BASE_WINDOW_VALIDITY_RULE`
- `BASE_TOP_DEFINITION`
- `BASE_WINDOW_ZERO_MATCH_BEHAVIOR`
- `BASE_WINDOW_SELECTION_RULE` (already recorded)

These names identify governance decisions; they are not implemented fields, runtime behavior, or proposed strategy values.
