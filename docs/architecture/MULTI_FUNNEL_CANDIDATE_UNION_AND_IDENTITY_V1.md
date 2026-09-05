# Multi-Funnel Candidate Union and Identity V1

**Status: `ACTIVE_READ_ONLY / CANDIDATE_POOL_FOR_SHARED_BRAIN_INSPECTION / NON_EXECUTABLE / NO_RECALL_AUDIT`.**

## Purpose and strict boundary

This slice deterministically groups already-produced
`CanonicalDiscoveryLead` records into one immutable pool item for each exact
canonical NSE security at one explicit PIT cutoff.  A pool item means only
`CANDIDATE_FOR_SHARED_BRAIN_INSPECTION`.  It is not a qualified investment
candidate, a signal, a ranking, a setup, a Decision Score, a Six-Gates
result, a portfolio instruction, or an action.

The implementation is pure and read-only.  It accepts existing adapter
results, retains their coverage and all source origins, and writes nothing.
It does not invoke a funnel, bind a universe, fetch a provider, run a shared
Brain/61-point diagnostic, resolve a final horizon, compute a score or
confidence, call Six Gates, access a portfolio, create a trade plan, or
access broker/order/API/UI/runtime state.

The separately implemented [whole-market orchestration](MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md)
binds the eligible universe and invokes this unchanged union read-only.
`DISCOVERY_RECALL_AUDIT` is **not active**; Brain inspection is not invoked.

## Authoritative identity

The union key is the existing `CanonicalDiscoveryLead.canonical_instrument_id`
only when it is the canonical NSE-security form `NSE:<exact ISIN>`.  The ISIN
is parsed from that pre-existing canonical security identity; it is not a
new resolver, continuity rule, or lookup.  That prevents a name, symbol, CIN,
or issuer relationship from becoming a competing identity system.

- Symbol/name are not inputs to matching and are not stored on the pool item.
- Issuer IDs are descriptive origin metadata.  Multiple listed securities for
  one issuer remain separate pool items.
- Existing approved NSE session identity/ISIN continuity infrastructure
  remains authoritative.  This union neither infers a symbol change nor uses
  a current symbol backwards in time.
- A lead without an exact canonical NSE security identity is excluded with
  `IDENTITY_BLOCKED / CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED`; it is never
  fuzzy-matched.
- Separate canonical instrument identities are never merged.  The lead
  contract has no symbol/name matching field, so a visual symbol/name conflict
  cannot be silently collapsed by this layer.  Conflicting adapter input for
  the same funnel fails closed; conflicting lead identity is represented as
  `IDENTITY_CONFLICTED` when such an origin is retained as an exclusion.

## Immutable contract

`app.intelligence.multi_funnel_candidate_union` provides:

| Contract | Required preserved facts | Boundary |
| --- | --- | --- |
| `DiscoveryCandidateOrigin` | Original immutable lead, lead ID/fingerprint, funnel/version, trigger, horizons, source layer, readiness/posture, quality, lineage, receipt IDs, source known time, and source reporting dimensions carried by the lead lineage | Origin is not flattened into display strings and is never upgraded. |
| `CanonicalDiscoveryPoolItem` | Exact security/ISIN, explicit batch as-of, all origins, known issuer IDs, factual funnel set, factual horizon lineage, earliest/latest lineage known time, identity and content fingerprint | Status is fixed to `CANDIDATE_FOR_SHARED_BRAIN_INSPECTION`; no primary horizon, winner, score, or vote exists. |
| `CandidateUnionFunnelCoverage` | Original `DiscoveryAdapterCoverage`, adapter-result fingerprint, and raw/distinct/duplicate/security accounting per funnel | A blocked or not-operational adapter remains distinguishable from `EVALUATED_NO_LEADS`. |
| `MultiFunnelCandidateUnionBatch` | Explicit as-of, per-funnel coverage, pool items, explicit future/identity exclusions, deterministic identity/fingerprint and descriptive counts | No persistence or runner is introduced. |

The pool-item identity is the contract version, exact canonical instrument,
and UTC batch as-of.  Its separate content fingerprint covers its factual
origin/provenance payload.  Thus new legitimate origins alter content
lineage without changing the conceptual security-at-cutoff identity.  Batch
identity uses the cutoff and source adapter-result fingerprints; the batch
fingerprint covers all coverage, candidates, exclusions and counts.

Every timestamp is explicit, timezone-aware and normalized to UTC.  An input
adapter result must have the same as-of as the union batch.  A lead whose
discovery time or any lineage `known_at` is after the batch cutoff is excluded
as `FUTURE_LEAD_EXCLUDED / LEAD_AFTER_BATCH_AS_OF`.  The union does not relax
adapter PIT checks.

## Origin and duplicate semantics

An exact replay—same canonical lead ID and fingerprint—retains one origin and
increments only the descriptive exact-duplicate count.  It cannot multiply
funnel provenance.  The same security may retain several origins from the
same funnel if they have distinct legitimate lead/source identities: for
example, distinct Consolidated and Standalone Fundamental Inflection
observations remain two origins on one security pool item.  The union never
chooses a reporting basis.

Origins from different funnels are likewise retained independently.  A
security found by Pre-Breakout, Sector Rotation, Fundamental Inflection and
Policy Transmission would have one pool item with four factual origins.  No
funnel wins, no counts are summed into quality, and `distinct_funnel_count`
is descriptive metadata only—not confidence, conviction, ranking, or an
investment judgement.  Research-shadow and operational readiness stay on the
individual origin; an operational origin never upgrades a research origin.

The union exposes originating horizon values as factual lineage only.  It has
no `PRIMARY_HORIZON`, final horizon, trigger transformation, quality aggregate
or discovery score.

## Current read-only audit

The following audit read existing immutable source snapshots only at the
explicit cutoff `2026-09-04T19:30:59.533938+00:00`; it did not write source
or union data.

| Measure | Result |
| --- | ---: |
| Raw adapter leads | 356 |
| Exact duplicate leads removed | 0 |
| Distinct retained origins | 356 |
| Identity-blocked leads | 0 |
| Final exact-security pool items | 73 |
| Single-funnel securities | 72 |
| Multi-funnel securities | 1 |
| Origins per security | 1: 3; 2: 27; 6: 23; 8: 19; 9: 1 |
| Distinct funnels per security | 1: 72; 2: 1 |

### Per-funnel accounting

| Funnel | Adapter coverage | Raw leads | Distinct origins | Exact securities | Exact duplicates |
| --- | --- | ---: | ---: | ---: | ---: |
| `SECTOR_ROTATION` | `LEADS_EMITTED` | 348 | 348 | 68 | 0 |
| `FUNDAMENTAL_INFLECTION` | `LEADS_EMITTED` | 8 | 8 | 6 | 0 |
| `PRE_BREAKOUT` | `EVALUATED_NO_LEADS` | 0 | 0 | 0 | 0 |
| `COMPOUNDER` | `EVALUATED_NO_LEADS` | 0 | 0 | 0 | 0 |
| `POLICY_TRANSMISSION` | `EVALUATED_NO_LEADS` | 0 | 0 | 0 | 0 |

The remaining registered adapters preserve their explicit
`SOURCE_NOT_OPERATIONAL` or `POLICY_BLOCKED` coverage in the batch; zero
leads do not convert those states into a successful no-leads result.

Sector Rotation’s 348 leads are not an adapter replay defect in this audit:
they come from eight distinct stored `Top3OpportunityFinderRun` receipts,
with candidate counts `45, 45, 43, 43, 43, 43, 43, 43`.  All 348
`(run_id, canonical_security)` pairs are distinct, across 68 securities.  A
security therefore retains its distinct historical/run origin receipts rather
than arbitrarily discarding them.  The union removes no exact sector replay.

One factual `MULTI_ORIGIN_DISCOVERY_SECURITY` exists at this cutoff:
`NSE:INE010B01027`, with eight Sector Rotation origins and one Fundamental
Inflection origin.  This is an audit fact only, not a top pick or a claim of
greater conviction.

### Five-target audit

| Security | In pool | Origins / funnels | Horizon lineage | Posture / source receipts |
| --- | --- | --- | --- | --- |
| `APARINDS` / `NSE:INE372A01015` | Yes | 2 / Fundamental Inflection | Long-term, positional | Both `RESEARCH_INSPECTION`; `inflection-accounting-prospective:b0d43a2ac94aef0fad48832c`, `inflection-accounting-prospective:b4a23d09cd5f7fcb187262a9` plus their retained Revenue/PAT/company-type lineage. |
| `DEEPINDS` / `NSE:INE0FHS01024` | No | 0 | — | No eligible stored source origin at this cutoff. |
| `GENUSPOWER` / `NSE:INE955D01029` | No | 0 | — | No eligible stored source origin at this cutoff. |
| `GLAND` / `NSE:INE068V01023` | Yes | 2 / Fundamental Inflection | Long-term, positional | Both `RESEARCH_INSPECTION`; `inflection-accounting-prospective:451038e44ba51de9bc85c078`, `inflection-accounting-prospective:d85d50f8de1f31351ebb273b` plus their retained Revenue/PAT/company-type lineage. |
| `ICICIBANK` / `NSE:INE090A01021` | No | 0 | — | No eligible stored source origin at this cutoff. |

APARINDS and GLAND demonstrate the intended behavior: two legitimate
Fundamental Inflection source observations collapse to one exact-security
pool item while every separate origin remains inspectable.  Nothing in this
audit is investment advice or a portfolio conclusion.

## Invariants and validation

- Exact canonical NSE security identity is mandatory; issuer/CIN and symbol
  are never union keys.
- Same inputs in any order produce identical pool items, IDs, fingerprints,
  coverage and serialization.  Replays are idempotent and read-only.
- All origins and adapter coverage remain immutable, typed and
  tamper-verifiable.  Duplicate/conflicting lineage is rejected by the lead
  contract; adapter-result ambiguity fails closed.
- There is no current-time fallback and no provider, persistence, API/UI,
  portfolio, broker/order, score, Decision Score, Six Gates, Brain or runner
  dependency.
- No discovery score, funnel vote, consensus strength, origin weighting,
  synthetic confidence, primary horizon, rank, BUY/SELL/HOLD, allocation,
  target, stop, quantity or portfolio action is present.

Focused tests cover exact security grouping, symbol/issuer non-authority,
replay de-duplication, same-funnel distinct receipt preservation,
Consolidated/Standalone-style origin retention, cross-funnel union, future
exclusion, invalid identity exclusion, coverage preservation, deterministic
serialization, identity/fingerprint separation, and static non-execution
boundaries.
