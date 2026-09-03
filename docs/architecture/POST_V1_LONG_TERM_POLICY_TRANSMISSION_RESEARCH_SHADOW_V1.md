# Long-Term Policy Transmission — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

## Purpose

This isolated receipt answers only whether a canonical, primary-source policy
fact has a PIT-valid, exact canonical company-exposure path. It does not state
that the policy is favourable or unfavourable, that a company benefits, or that
any economic, financial, price, portfolio, or execution outcome follows.

`FACT → DATA → INTERPRETATION → INFERENCE` remains mandatory. A primary policy
fact and an exact industry/company association are facts and lineage; economic
transmission remains an unapproved interpretation until a separately governed
policy defines it.

## Canonical inputs and PIT boundary

The evaluator consumes only the existing immutable Long-Term Thesis Research
Shadow receipt and `EvidenceVersion`. It verifies the receipt, requires the
`LONG_TERM_POLICY_TRANSMISSION` family, and retains the event/evidence IDs and
fingerprints. Canonical policy evidence must have all of the following at the
thesis as-of time:

1. a government, regulator, exchange, or other existing authoritative source
   type (`OFFICIAL`, `OFFICIAL_PRIMARY`, `GOVERNMENT`, `REGULATOR`, or
   `EXCHANGE`) with a non-empty source reference;
2. a `GOVERNMENT_POLICY`, `REGULATORY`, or `MONETARY_POLICY` event with a
   staged policy record other than `RUMOUR` or `STATEMENT`;
3. `published_at`, `discovered_at`, and `received_at` no later than the
   thesis as-of, plus an explicitly retained effective time no later than it;
4. retained affected-sector or affected-industry scope; and
5. an exact, `VERIFIED`, canonical-instrument company exposure. No keyword,
   free-text, product, geographic, customer, revenue, or value-chain inference
   is added.

The source receipt’s existing coverage already retains the legal/rule,
funding, tender/order, capacity, execution, revenue, cash-flow, cancellation/
supersession, and review-lineage domains. This evaluator neither fills a
missing stage nor treats a later stage as evidence for an earlier as-of.

## Exact result semantics

| State | Condition | Meaning |
| --- | --- | --- |
| `DATA_INSUFFICIENT` | Missing/unverifiable source receipt, primary provenance, supported policy event/stage, effective time, policy scope, exact verified exposure, or PIT validity. | No transmission conclusion. |
| `EVIDENCE_CONFLICTED` | The canonical source Research Shadow reports required coverage conflicted. | Conflict wins; the evaluator selects no source. |
| `NOT_APPLICABLE` | The company is unknown/structurally non-comparable, or the policy has exact verified exposures only for other instruments. | Not a policy-benefit conclusion. |
| `POLICY_DEFINITION_MISSING` | Primary, timed, scoped policy evidence and exact company exposure are retained. | Lineage exists, but no transmission conclusion is permitted. |

Even the last state carries blockers for policy direction, exposure-type
semantics, materiality, implementation effectiveness, lag, economic
sensitivity, and persistence. Financial companies may retain policy/exposure
lineage, but the evaluator applies no industrial-company formula to banks,
NBFCs, or insurers.

## Explicitly unavailable

The following are intentionally absent: positive/negative transmission;
direct/indirect benefit; exposure magnitude; implementation probability;
enforcement strength; transmission lag; substitution/competitive response;
revenue, margin, EBITDA, EPS, cash-flow, market-share, valuation, or price
effect; ranking; materiality scoring; lifecycle/expiry; milestones; outcome
measurement; and policy-reversal risk. None is silently inferred from policy
stage, sector membership, news, or exposure type.

Every result is fixed to `WATCH_ONLY / NON_EXECUTABLE / RESEARCH_SHADOW_V1`.
The module has no persistence, provider, API/UI, portfolio, broker, order,
score, setup, Six-Gates, market-scan, paper-trading, or runtime-clock
dependency. It is removed by deleting its one module/test pair.
