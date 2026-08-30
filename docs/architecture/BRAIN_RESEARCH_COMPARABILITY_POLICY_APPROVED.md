# Frozen Brain Research Comparability Policy

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

This records the first immutable factual-comparability policy. It is not a
research state, state delta, comparison engine, thesis/opportunity interpreter,
recommendation, alert, signal, or execution artifact.

## Identity and governance

| Field | Value |
| --- | --- |
| Policy ID | `brain-research-comparability-policy` |
| Frozen version | `v1-approved` |
| Proposal lineage | `brain-research-comparability-policy / v1-proposed` |
| Approval status | `APPROVED` |
| Approver | `human:Akash-Verma` |
| Selected for future comparator | `false` |
| Active | `false` |
| Comparison mode | `KNOWLEDGE_AT_THE_TIME` |
| Policy fingerprint | `361a2f7e8cd9a5acd7a2731d10a56c32ae52227c7fd412fbd2f1967b37ca1bc2` |
| Canonical artifact | `app/intelligence/brain_research_comparability_policy.py` |

`KNOWLEDGE_AT_THE_TIME` means each state may use only evidence visibly
eligible at that state’s `as_of`. A restated-history mode is not enabled or
included. Proposal history is retained; no proposal record is overwritten.

## Frozen core principles

- Comparability is dimension-local. One non-comparable dimension does not
  invalidate unrelated comparable dimensions.
- Whole-state failure is narrow: canonical-instrument mismatch, invalid
  timezone-aware temporal ordering, inconsistent source-state lineage, missing
  or tampered state-methodology identity, or comparison-mode mismatch.
- Required policy, schema, registry, benchmark, taxonomy, normalization,
  formula, or methodology drift is `NON_COMPARABLE` by default. No
  cross-version comparator is approved.
- Native typed lineage is required; generic Unified-State projections must not
  be reverse-engineered into lost native facts.
- Missing/unavailable evidence is never converted into zero, false, neutral, or
  unchanged.

## Frozen vocabulary

### Source eligibility

`PIT_REBUILDABLE`, `DURABLE_ARTIFACT_ONLY`, `CURRENT_ONLY`,
`REFERENCE_ONLY`, `UNSUPPORTED`.

### Factual comparability result

| Status | Meaning |
| --- | --- |
| `COMPARABLE` | Required identity, dependency, methodology, PIT, reliability, and integrity parity is proven. It has no direction. |
| `INSUFFICIENT` | Required evidence or dependency is absent/incomplete. |
| `NON_COMPARABLE` | Evidence may exist, but semantic parity is not established or policy forbids comparison. |
| `NOT_APPLICABLE` | The dimension/rule does not apply. |

## Frozen source eligibility

| Eligibility | Approved classifications |
| --- | --- |
| Conditional `PIT_REBUILDABLE` | Raw financial facts; eligible news/catalysts; official delivery; official corporate actions; provider-versioned OHLCV where integrity permits; PIT taxonomy/membership intervals. |
| `DURABLE_ARTIFACT_ONLY` | Stored market-regime result; governed Pre-Breakout assessment; candidate lineage; governed entry geometry; durable diagnostics; supplied/stored scorecards; stored reliability decision; first-observed derived macro state. |
| `CURRENT_ONLY` | Sector RS, breadth, rank, Top-3, and non-durable technical materialization. They must not be retrojected into historical comparisons. |
| `UNSUPPORTED` | Normalized historical ownership percentages and canonical valuation comparison facts. |
| `REFERENCE_ONLY` | Corporate-action normalization/reference facts where they establish identity or common price basis. |

## Frozen domain parity

### Financial and ownership

Financial comparison requires matching canonical instrument, metric, statement
scope, currency, value dimension, unit, scale, period type, value basis, fiscal
alignment, normalization, revision, PIT, and quality prerequisites.

Consolidated versus standalone, quarterly versus annual, incompatible basis,
and unsupported conversion are `NON_COMPARABLE`. Generic normalized ownership
percentage comparison remains unsupported; retained disclosures are lineage,
not synthetic historical percentages.

### Market, technical, sector, and setup

Price comparison requires instrument, exchange/series, session/timeframe, price
basis, provider identity/version, provenance, integrity, and corporate-action
treatment. Unproven price basis across a price-transforming action is
`NON_COMPARABLE`.

Technical facts require price basis, integrity, calendar/session, lookback,
minimum periods, formula/method version, action treatment, and selected policy
where applicable. Sector identity may be PIT-rebuildable only with eligible
taxonomy/membership lineage. Current RS/breadth/rank/Top-3 are current-only.

Governed Pre-Breakout assessment and entry geometry require exact policy ID,
version, fingerprint, selection, PIT evidence, price/delivery/tick/structural
lineage, integrity, and dependency fingerprints. Any setup policy fingerprint
mismatch is `NON_COMPARABLE`. Candidate existence remains factual only; fills
are excluded.

### Score, diagnostics, news, macro

Decision Score requires matching strategy/registry/configuration/components/
weights/normalization/missing-data treatment/completeness/confidence/evidence
lineage. A comparable score change is merely a factual score delta.

Diagnostics require matching registry, strategy, rule/input semantics,
completeness, evidence lineage, and version. Fingerprints preserve identity;
they do not express direction.

News/catalysts require stable event/article/filing identity, entity, type/schema,
source, PIT timestamps, confirmation, materiality where governed, and
correction/supersession lineage. Macro requires metric/family/component,
geography, period, release vintage, source, revision, and methodology parity.

## Reliability, integrity, dependency, and revision behavior

- Reliability `CONFLICTED` and native historical integrity `INVALID` are
  `NON_COMPARABLE`.
- Required `UNAVAILABLE` evidence is `INSUFFICIENT`.
- Stale evidence is not globally rejected, but needs a later domain-specific
  eligibility rule; no stale exception is approved here.
- Derived observations must preserve their immutable upstream dependency
  manifest and methodology/version. Dependency drift makes that dimension
  non-comparable.
- `KNOWLEDGE_AT_THE_TIME` is the only approved revision mode. Later restated
  history is neither implicit nor enabled.

## Explicit exclusions

The policy has no thesis strengthened/weakened, opportunity improved/degraded,
investment-risk, bullish/bearish, BUY/HOLD/SELL/TRIM/ROTATE, recommendation,
alert authorization, or execution semantics. It has no implementation wiring
to a research-state or comparison engine.

## Related proposal

The approved artifact freezes only the factual rules proposed in
[BRAIN_RESEARCH_COMPARABILITY_POLICY_PROPOSAL.md](BRAIN_RESEARCH_COMPARABILITY_POLICY_PROPOSAL.md).
The separate factual state contract remains described in
[BRAIN_RESEARCH_COMPARISON_STATE_PROPOSAL.md](BRAIN_RESEARCH_COMPARISON_STATE_PROPOSAL.md).
