# Post-V1 Fast-Rotation Comparison Foundation

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW / WATCH_ONLY / NON_EXECUTABLE / NOT_ACTIVE`.**

## Scope and decision

This is the bounded Post-V1 foundation for **Fast Rotation**.  It does not
select an investment, authorise replacement, calculate a score, inspect a
portfolio, or create an order.  Its initial useful output is a deterministic,
PIT-safe observation of an already-completed Core comparison, with the exact
facts needed to tell whether that observation is suitable for later research
and calibration.

`ROTATION_COMPARISON` is not `ROTATION_AUTHORIZATION`.

The frozen Core `CapitalRotationEngine` remains the sole owner of its existing
portfolio-bound candidate/holding comparison, gate, score, friction and
cash-unknown semantics.  In particular, Core labels such as
`ROTATE_CANDIDATE_PREFERRED` are neither imported into this consumer contract
nor reinterpreted as a Post-V1 action.  The foundation receives immutable,
already-derived facts from a caller; it has no repository, portfolio, broker,
order, API, UI, provider, clock, or persistence dependency.

## Reused facts and policy gaps

| Existing canonical boundary | Foundation use | Deliberately not inherited |
| --- | --- | --- |
| `PortfolioRotationEvaluation` and immutable Core comparison lineage | Caller may supply its exact evaluation/comparison identity, configuration version, content fingerprint and canonical as-of facts. | Core action/stance labels, execution eligibility and portfolio mutation semantics. |
| Canonical instrument identity and evidence fingerprints | Challenger and incumbent (or cash) must be exact and lineaged. | Fuzzy mapping, inferred peer/bucket membership. |
| Core cash-unknown handling | `CASH` can be an injected alternative identity only. | A cash amount, deployment, sizing, or instruction. |
| Core score/gate/risk-reward/friction fields | Caller may attest that their exact method/version and evidence parity are available. | A universal score hurdle, a new risk/reward calculation, or a friction estimate. |
| Rule 46 and risk/thesis state | Descriptive invalidation context may be retained in source lineage. | A rotation approval or automatic exit. |

The foundation must never query the source portfolio.  A caller that needs
portfolio data must first create a separate immutable, read-only input under a
future approved contract.

## Research and regulatory traceability

| Source (accessed 2026-09-03) | Supported fact | Limitation retained by this policy |
| --- | --- | --- |
| [Nifty 500 Index Methodology, October 2025](https://www.niftyindices.com/docs/default-source/indices/nifty-500/nifty-500-whitepaper_2025.pdf?sfvrsn=7b2c6635_4) | Broad-index eligibility uses, among other criteria, six-month trading frequency and average impact cost. | Index eligibility is not an order-size, slippage, tax, or individual rotation-cost approval. |
| [Nifty equity-index methodology](https://www.niftyindices.com/Methodology/Method_Nifty_50.pdf) | Index liquidity methodology uses an impact-cost and turnover/trading-history framework. | It cannot supply an HSI execution-cost model without an approved PIT, instrument- and order-size-specific contract. |
| [SEBI trading master circular](https://www.sebi.gov.in/sebi_data/commondocs/jul-2021/Chapter%201%20-%20Trading_p.pdf) | Exchanges levy transaction charges and must apply them fairly and transparently to comparable trades. | It does not define a single end-user friction value. |
| [Income Tax Department individual tax guidance](https://www.incometaxindia.gov.in/w/computation-of-tax-for-individual-1) | Tax treatment can depend on statutory timing and taxpayer facts. | No tax rate, holding-period assumption, or net-return calculation is selected here. |

Therefore every numerical candidate in the research pack remains either
`REGULATORY_BOUNDARY`, `RESEARCH_SHADOW_V1_CANDIDATE`, or
`PARAMETER_RESEARCH_REQUIRED`; none becomes a runtime threshold.

## Immutable injected comparison observation

The initial pure module may accept only an immutable, caller-supplied
comparison observation with these required facts:

1. a canonical challenger identity and either a canonical incumbent identity
   or the literal alternative `CASH`;
2. a source Core comparison/evaluation identity, source configuration version,
   and tamper-evident source content fingerprint;
3. an explicit `as_of`, challenger availability time, alternative availability
   time, and source-evaluation availability time, all timezone-aware and no
   later than `as_of`;
4. non-empty challenger and alternative evidence/diagnostic lineage
   fingerprints; and
5. descriptive availability/provenance states for common score scale,
   comparable risk/reward method, friction/liquidity/tradability evidence,
   correlation/concentration evidence, bucket assignment, persistence/churn,
   and invalidation context.

The implementation may normalize collection ordering but must reject duplicate
or conflicting lineage references.  It must not calculate, repair, infer, or
substitute any source fact.  A content fingerprint covers every serialized
field; a deterministic observation identity uses only the contract version,
canonical identities, source comparison identity/version/fingerprint, and
canonical as-of time.  Neither uses wall-clock time, locale, input order, or
environment state.

### Permitted descriptive outcomes

| Status | Meaning | Never means |
| --- | --- | --- |
| `CORE_COMPARISON_OBSERVED` | A source comparison is exact, PIT-valid, lineaged, and internally usable as a calibration/research observation. | A challenger is better, a holding should be replaced, or cash should be deployed. |
| `POLICY_PARAMETER_UNAVAILABLE` | A source observation exists, but bucket/cross-bucket, comparable-economics, cost/tax, correlation/concentration, or persistence policy is not approved. | Neutral evidence or an implicit exemption. |
| `DATA_INSUFFICIENT` | Required canonical evidence/status is absent, stale, non-comparable, or unavailable. | A lower-quality comparison. |
| `CONFLICTED` | Relevant exact source facts disagree. | Selection by input order or most favorable input. |
| `TEMPORALLY_INVALID` | Any source fact is later than `as_of`. | Use of a future correction or current view. |
| `UNVERIFIABLE` | Identity, version, fingerprint, or lineage cannot be verified. | Recalculation or repair of a tampered input. |

All outputs are unconditionally `WATCH_ONLY / NON_EXECUTABLE`.  They contain
no `ROTATE`, `BUY`, `SELL`, `ADD`, `TRIM`, `EXIT`, price, quantity, allocation,
capital authorisation, broker, order, or portfolio object.

## Exact policy/data gates retained as unavailable

| Required future Fast-Rotation decision | Current treatment |
| --- | --- |
| Immutable bucket taxonomy (`CORE_COMPOUNDER`, `EMERGING_SATELLITE`, `THEMATIC`, `TACTICAL`) and assignment lineage | `POLICY_PARAMETER_UNAVAILABLE`; no assignment source is approved. |
| Same-bucket comparison | May only be described when an exact approved assignment is injected; it creates no preference. |
| Cross-bucket comparison/higher hurdle | `POLICY_PARAMETER_UNAVAILABLE`; cross-bucket substitution is forbidden. |
| Normalized improvement delta | Candidate grid `{0.70, 0.85, 1.00}` remains `RESEARCH_SHADOW_V1_CANDIDATE` pending common-scale/PIT calibration. |
| Comparable risk/reward | `POLICY_PARAMETER_UNAVAILABLE` without identical horizon, method, scope and non-zero denominators. |
| Slippage, tax, friction, liquidity and tradability | `DATA_INSUFFICIENT` without approved PIT order-size/cost/tax evidence; Nifty eligibility is insufficient. |
| Correlation/concentration | `POLICY_PARAMETER_UNAVAILABLE` without approved return-window and immutable read-only portfolio exposure contracts. |
| Persistence/cooldown | Candidate grids `{1,3,5}` sessions and `{5,10,20}` sessions remain calibration-only. |
| Invalidation | Core Rule 46/risk state may be lineaged context only; it cannot authorise a replacement. |

## PIT, freshness and conflict rules

The source observation, both alternative evidence sets, and all declared
availability timestamps must be `<= as_of`.  No current/latest lookup is
allowed.  The initial layer has no synthetic freshness duration: it records
the supplied canonical freshness/persistence state and returns
`DATA_INSUFFICIENT` when the future policy-required state is absent or stale.
Exact duplicates are retained in audit references and do not multiply an
observation; conflicting same-key content returns `CONFLICTED`.  Newer source
facts win only when their effective/availability time is earlier than the
requested `as_of` and their content is not conflicted.

## Acceptance and rollback boundary

The initial implementation is accepted only if focused tests prove immutable
input/output, deterministic identity and serialization, PIT exclusion,
tamper rejection, exact cash/identity handling, duplicate/conflict handling,
and absence of forbidden dependencies and side effects.  It must also prove
that a verified Core observation does not become a Fast-Rotation preference.

Rollback is deletion of this standalone Post-V1 module and its tests.  It does
not alter Core rotation, any database schema, a persisted evaluation, API/UI,
provider, runtime, portfolio, or policy configuration.

## Activation prerequisites

Before a Fast-Rotation evaluator can emit even a positive Watch review,
separate approval must select versioned bucket, cross-bucket, common-score,
risk/reward, cost/tax/slippage, liquidity, correlation/concentration,
persistence, staleness, conflict, and shadow-calibration contracts.  It must
then demonstrate PIT-safe coverage and human review.  It still may not grant
trade or portfolio authority.
