# Inflection Testable Derived Metrics and Event Alignment V1

**Status: `RESEARCH_ONLY / NOT_APPROVED / NOT_ACTIVE / WATCH_ONLY / NON_EXECUTABLE`.**

## Purpose

`INFLECTION_TESTABLE_DERIVED_METRICS_AND_EVENT_ALIGNMENT_V1` is the bounded
factual precursor described by
[Fundamental Inflection Policy Research Proposal V1](FUNDAMENTAL_INFLECTION_POLICY_RESEARCH_PROPOSAL_V1.md).
It creates deterministic, point-in-time receipts for separately observed
quarterly Revenue and PAT year-over-year change and, only when both exact YoY
observations are comparable, their raw arithmetic difference.

```text
PIT quarterly FinancialFacts
  -> selected-vintage FinancialMetricObservations
  -> exact YEAR_OVER_YEAR_QUARTER trajectories
  -> Revenue/PAT acceleration observation
  -> exact financial-result filing lineage
  -> calendar-date readiness
```

This is `FACT -> DATA` only. It neither creates an Inflection candidate nor
converts accounting change into an expectation surprise, confirmation, market
reaction, score, setup, portfolio decision, or action.

## Exact accounting observations

For one non-financial issuer, one explicit statement scope, and one explicit
UTC-normalized `as_of`:

- Revenue YoY requires exact reported quarterly `Revenue_t` and
  `Revenue_t-4` through the frozen `YEAR_OVER_YEAR_QUARTER` trajectory policy.
- PAT YoY requires exact reported quarterly `PAT_t` and `PAT_t-4` under the
  same policy.
- A metric's acceleration is recorded only as
  `YoYGrowth_t - YoYGrowth_(t-1)`, requiring `t`, `t-1`, `t-4`, and `t-5`.
- No annual observation, inferred quarter, scope preference, currency/unit
  conversion, or same-period restatement repair is allowed.
- Revenue and PAT are independent receipts. No combined confirmation, score,
  threshold, direction, ranking, or favorable/unfavorable interpretation is
  produced.

The factual output states are:

| State | Meaning |
| --- | --- |
| `ACCELERATION_OBSERVED` | Both independently valid YoY trajectories exist; a raw arithmetic difference is retained. |
| `YOY_OBSERVED` | Current valid YoY exists but the prior-quarter YoY cannot be formed. |
| `DATA_INSUFFICIENT` | Required PIT-visible complete quarterly evidence is absent. |
| `EVIDENCE_CONFLICTED` | Exact selected-vintage or supplied lineage is conflicted/tampered. |
| `NON_COMPARABLE` | Period, basis, representation, or economic denominator semantics prohibit the observation. |
| `NOT_APPLICABLE` | The exact PIT company type is not `NON_FINANCIAL`. |

PAT explicitly preserves `LOSS_TO_PROFIT`, `PROFIT_TO_LOSS`, `LOSS_TO_LOSS`,
and `ZERO_BASE` as non-comparable outcomes. `NEAR_ZERO_BASE` remains a named
unavailable reason only: the repository has no approved numerical epsilon, so
this layer does not invent one. `RESTATEMENT_CONFLICT`, `BASIS_CHANGED`, and
`PERIOD_ALIGNMENT_MISMATCH` likewise remain explicit fail-closed reasons.

## Exact result-event lineage and calendar readiness

The current-quarter selected observation can link only through its exact
`FinancialFact.filing_id` to an official BSE or NSE `FINANCIAL_RESULTS` `CorporateFiling`
whose instrument, scope, reporting period, source quality, and PIT visibility
all agree. A result stores the filing identity/fingerprint, source provenance,
period, announced and received timestamps, and revision identity when present.
It never matches by company name or subject text.

The injected existing calendar is asked only whether the UTC-normalized filing
date is a trading date and for its adjacent canonical trading dates. The
receipt therefore exposes:

- `TRADING_DATE_IDENTIFIED` or `NON_TRADING_DATE` where the calendar can
  decide the date;
- prior and next canonical trading dates when available; and
- unconditionally `INTRADAY_EVENT_SESSION_UNRESOLVED`.

There is no canonical intraday session-hours contract in this slice. It must
not call a timestamp before-open, during-market, or after-close, and it does
not calculate price/benchmark/sector/volume reaction. Those domains remain
`PRICE_REACTION_POLICY_NOT_ACTIVE` and `VOLUME_REACTION_POLICY_NOT_ACTIVE`.

## Scope, persistence, and replay

The evaluator consumes supplied immutable facts, filings, company-type receipt,
and calendar at an explicit cutoff. It has no repository, database, API, UI,
provider, portfolio, broker, order, discovery, or runtime-clock dependency.
Receipts are not persisted by V1; identical supplied inputs deterministically
reproduce equal IDs, fingerprints, and stable serialization. No replay can
create an equivalent stored record because V1 has no store.

Only an exact PIT-classified `NON_FINANCIAL` issuer is supported. Bank, NBFC,
and insurer evidence remains `NOT_APPLICABLE` pending separately approved
sector-specific financial Inflection policy.

## Feasibility matrix after V1

| Dimension | Current state | V1 treatment |
| --- | --- | --- |
| Revenue acceleration | `READY_FOR_RESEARCH` | Exact factual observation only. |
| PAT acceleration | `READY_FOR_RESEARCH` | Exact factual observation only; sign/base transitions stay non-comparable. |
| Combined accounting confirmation | `POLICY_MISSING` | Not calculated. |
| Consensus surprise | `CANONICAL_DATA_MISSING` | Not calculated. |
| Revisions | `CANONICAL_DATA_MISSING` | Not calculated. |
| Guidance | `CANONICAL_DATA_MISSING` | Not calculated. |
| Event-time alignment | `EVENT_TIME_PARTIAL` | Exact filing date and adjacent calendar dates only. |
| Price reaction | `POLICY_MISSING` | Not calculated. |
| Volume reaction | `POLICY_MISSING` | Not calculated. |
| Bank/NBFC/insurer branches | `NOT_APPLICABLE` | Excluded rather than applying industrial Revenue/PAT semantics. |

## Explicit non-goals

No threshold, confirmation window pass/fail, materiality label, candidate,
ranking, score, price target, entry/stop/target, quantity, allocation,
BUY/SELL/HOLD/ADD/TRIM/EXIT/ROTATE instruction, Six-Gates authorization,
portfolio mutation, paper trade, broker/order operation, API/UI activation, or
production-performance claim is added.

## Next bounded continuation

The exact next bounded work is
`INFLECTION_EVENT_SESSION_AND_MARKET_REACTION_POLICY_PROPOSAL_V1`: a
documentation/research approval decision for canonical event-session timing,
adjustment treatment, benchmark selection, and reaction windows. It is not
authorized by this factual V1 implementation.
