# Technical Peer Cohort Policy V1

**Status:** `TECHNICAL_PEER_COHORT_POLICY_V1_CANDIDATE / POLICY_EVIDENCE_SEMANTICS_ONLY / NOT_ACTIVE`

## Scope and invariants

This is the evidence and policy-semantics candidate for the word “Peers” in
canonical diagnostic Rule 6. It neither changes the canonical 61-rule
registry nor activates a peer calculation, source acquisition, taxonomy
promotion, cohort persistence, readiness result, indicator, horizon policy,
or technical orchestration. It creates no portfolio, setup, rotation, trade,
broker, order, API, UI, alert, or provider behaviour.

The following remain frozen:

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
NO_INDICATOR_EXPANSION = TRUE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```

`SECTOR_CONTEXT != BUSINESS_PEER_COHORT`. A governed sector-index mapping and
its canonical price-return OHLC lineage remain valid sector-relative context;
neither an index nor its constituent set automatically defines a business-peer
cohort.

## A. Rule 6 archaeology: existing canonical behaviour

| Concern | Existing canonical fact |
| --- | --- |
| Rule | `6` — **Relative Strength Rank vs Nifty 50, Sector Index & Peers** |
| Intent represented by the evaluator | classify the security’s price-return excess versus `NIFTY_50` from the exact supplied technical snapshot; retain a sector return/excess where a governed sector series is supplied |
| Current runner | `Canonical61DiagnosticRunner._evaluate(6)` in `app/universe_analysis/service.py` |
| Benchmark | exact canonical `NIFTY_50`; every stock session supplied to the current-descriptive adapter must align to a stored benchmark session; no forward fill or newer endpoint is accepted |
| Equity timeframe | Daily only; the runner instantiates `RelativeStrengthRules(lookback=3, leader_minimum_excess_return=0.10, emerging_leader_minimum_excess_return=0.03, laggard_maximum_excess_return=-0.03)`, so valid stock and benchmark close series each require at least `4` aligned Daily observations |
| Formula | `stock_return = close[-1] / close[-1 - 3] - 1`; `benchmark_return` is the same formula on `NIFTY_50`; `excess_return = stock_return - benchmark_return` |
| Classification | `LEADER` at excess `>= 0.10`; `EMERGING_LEADER` at `>= 0.03`; `LAGGARD` at `<= -0.03`; otherwise `AVERAGE` |
| Sector dependency | optional explanatory context. If exact mapped sector-index sessions align, the engine records `sector_return` and `sector_excess_return`; their absence does not alter the current benchmark-relative classification |
| Peer dependency | the runner passes `peers=()`. `DeterministicDiagnosticEvaluators.relative_strength` records only `peers_available=False`; `RelativeStrengthEngine.calculate` does not consume the tuple numerically or construct peer comparisons |
| Implicit cohort construction | none. No same-sector, sector-index constituent, market-cap, valuation, correlation, name, text, or model-derived membership is constructed |
| Missing data | invalid/missing stock or benchmark series, fewer than four observations, or failed stock/benchmark session alignment yields the existing missing/insufficient-data path; no substitute series or fill is created |
| Applicability | Rule 6 is a canonical market/technical diagnostic and is applicable. The adapter-local `PeerCohortState.NOT_APPLICABLE` means “not consumed by this evaluator input adapter,” not “the rule has no possible peer leg.” |
| Current readiness | evaluator-only stock-versus-benchmark readiness can exist with certified aligned inputs. Full named Rule 6 readiness is `PARTIAL`: sector context is available for some securities, but authoritative business-peer membership and a governed peer comparison are not available. |

The existing source adapter in `app/universe_analysis/benchmark_sector_technical_input.py`
is deliberately unchanged. Its `PeerCohortState.NOT_APPLICABLE` is descriptive
of the current evaluator’s actual input use. Reinterpreting it as a new peer
gate, or changing the evaluator to use peers, would be a separate approved
Rule 6 implementation slice and is not authorized here.

## B. First-party classification evidence

The retained source receipt and reproducible primary pages are the [NSE India
Industry Classification page](https://www.nseindia.com/static/products-services/industry-classification),
[NSE Indices Industry Classification page](https://www.niftyindices.com/resources/industry-classification),
and the [July 2023 NSE Indices classification guideline](https://www.niftyindices.com/docs/default-source/default-document-library/nse-indices_industry-classification-guideline-2023-07.pdf?sfvrsn=76449434_2).
They describe a four-tier hierarchy:

| Level | Official meaning | Peer-policy implication |
| --- | --- | --- |
| Macro-Economic Sector | company business activity at macro level | too broad to be a business-peer cohort |
| Sector | specific company sector | valid broad sector context, not automatically peers |
| Industry | company industry classification | candidate broader business-context level only; no fallback is approved here |
| Basic Industry | micro-level core business activity | preferred candidate business-peer level if exact, authoritative membership becomes available |

NSE Indices states that each company is classified to the Basic Industry that
most closely describes the nature of its business. Revenue is used because it
more accurately describes core activity; for multi-business companies the
segment contributing more than 50% of revenue governs classification, with the
documented diversified outcomes where no segment dominates. That revenue-first
semantics supports **Basic Industry** as the most defensible candidate for a
business-peer cohort. It does not itself approve a cohort policy or a minimum
member count.

The retained `NSE_INDICES_TAXONOMY_SOURCE` lineage has exact ISIN/symbol
resolution and source hash/line provenance for its selected records, but its
constituent CSV label resolves only to the sector level. The stored
`InstrumentTaxonomyClassification` records therefore contain authoritative
macro-sector and sector values, with `industry`, `industry_code`,
`basic_industry`, and `basic_industry_code` deliberately null. The source
assessment is current-descriptive/first-observed, not an effective-dated
historical classification corpus.

## C. Candidate hierarchy and prohibited substitutes

No fallback is approved by this candidate. If a future peer policy is
approved, its possible evidence-backed order is:

| Candidate state | Exact meaning today | Full Rule 6 peer eligibility |
| --- | --- | --- |
| `AUTHORITATIVE_BASIC_INDUSTRY_COHORT` | exact membership from a first-party per-security Basic Industry assignment, with identity, source, known-at/effective semantics, and immutable membership lineage | candidate preferred level; still requires separately approved cohort-size and comparison policy |
| `AUTHORITATIVE_INDUSTRY_COHORT` | exact membership from a first-party per-security Industry assignment | broader secondary context candidate only; not approved as a full-readiness fallback |
| `SECTOR_CONTEXT_ONLY` | exact sector mapping and, where available, exact sector-index OHLC | sector-relative context only; never business-peer readiness |
| `NO_AUTHORITATIVE_PEER_COHORT` | no exact per-security Basic Industry or Industry membership available | peer leg not ready; do not construct a substitute |

The following are expressly prohibited as peer membership or fallback evidence:
market-cap, P/E, revenue, price/technical correlation, nearest-neighbour,
text/company-name similarity, LLM judgement, fuzzy taxonomy, and a common
sector index or its constituent set. They are not latent fallbacks. Any future
research on them requires its own methodology, shadow testing, and governance.

## D. Required authoritative membership lineage

An approved cohort membership would require every member to retain, at minimum:

```text
canonical security identity
classification level and exact label/code
classification source and source authority
effective/observed date and known-at semantics
cohort version and deterministic membership fingerprint
```

Membership is `CURRENT_DESCRIPTIVE` only until first-party effective-dated,
known-at historical classifications are proven. A current label must never be
back-projected into a historical Rule 6 evaluation. Target-self exclusion from
a comparison denominator is required only after the actual peer-comparison
mathematics and its denominator have been separately approved; no denominator
or minimum peer count is invented here.

```text
MINIMUM_PEER_COHORT_SIZE = UNSET
STRICT_HISTORICAL_PIT_PEER_COHORT = NOT_READY
```

## E. Current-descriptive readiness audit

This one read-only audit used the latest persisted 2,553-security technical
universe and the explicit current-descriptive cutoff
`2026-09-08T16:46:01.204825+00:00`. It did not fetch, write, promote, or
reclassify any data.

| Measure | Exact count | Interpretation |
| --- | ---: | --- |
| technical-scope securities | 2,553 | audit denominator |
| authoritative Macro-Economic Sector assignments | 711 | selected first-party current-descriptive records |
| authoritative Sector assignments | 711 | selected first-party current-descriptive records |
| authoritative Industry assignments | 0 | no stored per-security Industry assignment |
| authoritative Basic Industry assignments | 0 | no stored per-security Basic Industry assignment |
| exact governed sector-index mappings | 601 | existing mapping policy; unchanged |
| usable canonical sector-index OHLC | 354 | valid sector context; unchanged |
| exact source response available but full OHLC contract not satisfied | 247 | Capital Goods 112, Consumer Services 46, Chemicals 45, Construction 23, Power 21 |
| candidate authoritative business-peer cohorts | 0 | Basic Industry and Industry memberships are absent |
| securities with an authoritative business-peer cohort | 0 | no peer candidate can be assembled |
| securities with no authoritative business-peer cohort | 2,553 | no proxy promotion permitted |

The frozen external source receipt remains
`CURRENT_NSE_SECURITY_CLASSIFICATION_COVERAGE = EXTERNALLY_BLOCKED_PARTIAL`
with `1,827` all-listed-source classifications unavailable in its original
2,538-security source-audit population. The present 2,553-security technical
audit has `1,842` securities with no selected first-party macro/sector record
(`2,553 - 711`). This is a denominator/selection-scope reconciliation, not a
new taxonomy acquisition finding and not a reason to resume taxonomy
archaeology.

`SOURCE_RESPONSE_AVAILABLE` describes an exact official response. It does not
mean that `FULL_OHLC_CONTRACT_NOT_SATISFIED` has been repaired: the latter is
the required current blocker wording when that response lacks usable complete
Daily OHLC. The five exact source responses are therefore not source-absent.

## F. Cohort distribution

| Level assessed | Cohorts | Members | Singleton cohorts | Very small cohorts (2–4) | Securities without peers after self-exclusion | Ambiguous memberships |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Basic Industry | 0 | 0 | 0 | 0 | 0 | 0 |
| Industry | 0 | 0 | 0 | 0 | 0 | 0 |
| Sector — context only, not a peer cohort | 19 | 711 | 1 | 2 | 711 | 0 |

The sector-context size distribution is `{1: 1, 3: 1, 4: 1, 12: 1, 16: 1,
17: 1, 21: 1, 23: 1, 24: 1, 26: 1, 36: 1, 41: 1, 45: 2, 46: 1, 48: 1,
70: 1, 112: 1, 121: 1}`. It is reported solely to demonstrate that a broad
sector grouping is not a silently approved peer population. No minimum size,
aggregation, or exclusion outcome is inferred from it.

## G. Rule 6 dependency states and readiness

| Dependency / result | State | Exact evidence |
| --- | --- | --- |
| `BENCHMARK_CONTEXT` | `READY` | canonical `NIFTY_50` price-return OHLC lineage exists; an individual evaluation still needs its exact aligned Daily equity window |
| `SECTOR_CONTEXT` | `PARTIAL` | 354 securities have exact mapping plus usable canonical sector-index OHLC; 247 mapped securities have received source responses but fail the full OHLC contract |
| `BASIC_INDUSTRY_PEER_EVIDENCE` | `NOT_READY` | 0 authoritative stored Basic Industry assignments |
| `INDUSTRY_PEER_EVIDENCE` | `NOT_READY` | 0 authoritative stored Industry assignments |
| `PEER_COHORT_POLICY` | `NOT_READY` | this document is a candidate only; membership, minimum-size, denominator, and comparison policy are unapproved/unset |
| `PEER_COHORT_MEMBERSHIP` | `NOT_READY` | 0 members satisfy an authoritative business-peer cohort definition |
| `CURRENT_DESCRIPTIVE_PEER_READINESS` | `NOT_READY` | source has no Industry/Basic Industry per-security membership in the selected state |
| `HISTORICAL_PIT_PEER_READINESS` | `NOT_READY` | current/first-observed classifications have no proven historical effective/known-at lineage |
| Rule 6 evaluator-only benchmark-relative path | `PARTIAL` | current runner can calculate stock-versus-benchmark classification where its independently certified aligned Daily input is supplied; it does not implement peers |
| Rule 6 full named readiness | `PARTIAL` | 0 full peer-ready securities; 354 retain valid sector context, so absent peer policy is a missing applicable dependency, not `NOT_APPLICABLE` |

For any individual security, `READY` requires every actually approved full
Rule 6 dependency; `PARTIAL` means some applicable dependencies are present;
`NOT_READY` means an applicable required dependency is absent; and
`NOT_APPLICABLE` is reserved for a genuinely inapplicable domain, not the
absence of a peer policy. No individual currently qualifies as full Rule 6
peer-ready.

## H. Candidate policy decision and next boundary

`TECHNICAL_PEER_COHORT_POLICY_V1_CANDIDATE` is evidence-backed but not
activated. It establishes that Basic Industry is the preferred candidate
business-peer granularity, Industry may be considered only as broader
secondary context after separate approval, and sector/index evidence remains
context rather than a peer substitute. It deliberately leaves these parameters
unset:

```text
MINIMUM_PEER_COHORT_SIZE = UNSET
PEER_COMPARISON_DENOMINATOR = UNSET
INDUSTRY_FALLBACK_FOR_FULL_RULE_6 = UNSET
CURRENT_DESCRIPTIVE_PEER_POLICY = NOT_ACTIVE
STRICT_HISTORICAL_PIT_PEER_POLICY = NOT_READY
```

No narrow already-retained canonical source supplies authoritative Basic
Industry or Industry peer membership, so no bounded peer-membership
implementation is proposed. The separately recorded
[Rule Horizon / Timeframe Applicability Policy V1 candidate]
(RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1.md) does not change that
conclusion: the Rule 6 peer leg remains fail-closed/partial, while the external
taxonomy block stays parked.

## Validation and safety boundary

This documentation slice preserves exact canonical observations and performs
no SQLite mutation. Its intended validation is the focused Rule 6,
benchmark/sector-input, taxonomy-coverage, and sector-mapping coverage tests,
one full backend regression, a read-only SQLite integrity audit, Markdown-link
validation, and `git diff --check`. It adds no test-only classifier, no source
retrieval, and no synthetic cohort.
