# Canonical Discovery Union to Brain Handoff Contract V1

Status: `CONTRACT_DEFINED / CONSUMER_BINDING_NOT_READY / NOT_ACTIVE`

Contract: `canonical-discovery-union-to-brain-handoff / v1`

Baseline: `89660090782a30b0eec8cc72dbe6a912f2087d17`, `main`, initially clean.

Decision **B — `HANDOFF_CONTRACT_READY_WITH_CONSUMER_BINDING_BLOCKER`**. This **contract/governance slice is ACCEPTED/CLOSED**, not a live handoff implementation or registration.

[Machine-readable contract, field matrix and invariants](CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1.json).
[Accepted reconciliation audit](HSI_BRAIN_FUNNEL_RUNTIME_RECONCILIATION_AUDIT_V1.md).
[Source union](MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md).
[Source runner](MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md).
[Existing Radar bridge](RADAR_TO_HSI_DIAGNOSTIC_ORCHESTRATION_V1.md).

## 1. Scope and frozen authority

This document defines the next immutable reference contract; it adds no application model, serializer, reader, repository, queue, scheduler, API, UI or runtime invocation. Tests below are **synthetic conformance witnesses**, not production evidence or a registered consumer.

`DISCOVERY_AUTHORITY != BRAIN_DECISION_AUTHORITY`

`BRAIN_INSPECTION_REQUEST != EXECUTION_AUTHORIZATION`

Every future conforming output is `WATCH_ONLY / NON_EXECUTABLE`. No price, entry, stop, target, quantity, sizing, allocation, trade instruction, portfolio interface, confidence/score authority or gate bypass is allowed.

Preserve V1 `six-gates-production-v1 / v1 = ACTIVE`; Execution Gate V2 `NOT_ACTIVE`; research bootstrap `UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE`; bootstrap seed `UNSET`. None of the accepted Gate-1 artifacts or source policies is altered.

The intended flow remains one eligible-NSE discovery platform, exact-security union, one shared Brain inspection, same canonical61, Score, appropriate setup/thesis/invalidation, Six Gates, then governed projections. This contract stops **before** invocation or any downstream success claim.

## 2. Reused source contracts and immutable identity

Use existing:

- [CanonicalDiscoveryLead / registry](../../app/intelligence/multi_funnel_discovery.py), contract `multi-funnel-discovery/v1`;
- [CanonicalDiscoveryPoolItem / MultiFunnelCandidateUnionBatch](../../app/intelligence/multi_funnel_candidate_union.py), contract `multi-funnel-candidate-union/v1`;
- [WholeMarketDiscoveryBatch](../../app/intelligence/multi_funnel_orchestration.py), contract `multi-funnel-whole-market-orchestration/v1`;
- [NseEquityInstrument / UniverseSnapshot](../../app/universe_analysis/models.py);
- [HistoricalSecurityIdentity](../../app/historical/security_master.py), [UniverseMembership](../../app/historical/models.py) and [native PIT guards](../../app/historical/guard.py);
- source adapter contract `hsi-multi-funnel-discovery-adapters/v1`, native source records, policy selection and fingerprint verifiers.

A naked pool item or union cannot prove universe membership, source producer version, native knownness or trigger freshness. A conforming handoff requires the **verified full master → union → candidate chain**, plus existing source-native reference enrichment. Keep original payloads/fingerprints; do not recompute a replacement to make tampered input valid.

Canonical identity is exact `NSE:<ISIN>`, agreeing with the separate ISIN and source identity. The existing ISIN shape is `[A-Z]{2}[A-Z0-9]{9}[0-9]`; shape alone is not proof of identity. Require exchange NSE, canonical security type EQUITY and source-proven `NSE_CASH_EQUITY` segment, using existing vocabulary. The [CM master importer](../../app/market_data/reference_data/nse_master.py) is evidence of a native source path, **not** something invoked here; its EQ series or a tick/provider record alone cannot establish ordinary-equity eligibility or CAS applicability.

Retain identity ID/version, native source fingerprint/envelope, descriptive symbol and exact lifecycle status. No fuzzy/symbol fallback. Native source ambiguity, absent segment proof or unresolved lifecycle fails closed. Existing universe eligibility remains NSE/EQUITY/`main_board is not False`; unknown main-board metadata is not silently reclassified.

Lifecycle is descriptive. A known suspension or non-tradable state does not become execution permission, nor does this contract invent a new universe policy. Admission still requires the existing governed membership/applicability at the relevant cutoffs. Missing identity provenance never gets filled from current records.

## 3. Exact clocks and historical truth

| Symbol / field | Normative meaning | Invariant |
| --- | --- | --- |
| `D_i = origins[i].discovery_as_of` | Existing source observation/discovery cutoff | Not a newly asserted physical event or detection time |
| `U = source_union.as_of = source_candidate.batch_as_of` | Effective union cutoff | Not physical formation time |
| `I = inspection_as_of` | Explicit intended canonical inspection cutoff | Neither trade-decision, execution nor setup-entry time |
| `union_formed_at`, `request_created_at` | No independent canonical physical timestamp exists | Fixed null / UNAVAILABLE; never `now()` |
| distinct `origins.detected_at` | Not present in current lead | Null / unavailable; show `discovery_as_of` honestly |

Require source-native observed/publication/receipt/known/effective timestamps, where applicable, **no later than D_i**, with **D_i ≤ U ≤ I**. Evidence validity/freshness must also satisfy its native requirements at I. UTC-normalize all aware times; reject naive values. No default cutoff, arbitrary window, duration, expiry or scheduler time.

Identity and membership must be known/effective at **each D_i and I**. A snapshot known only at U does not prove membership at an earlier D_i. Use a retained snapshot demonstrably valid at those boundaries or existing historical membership/identity records. Native `eligible_as_of` and membership guards preserve **inclusive** end boundaries where present; do not replace other sources' interval rules with a generic convention.

Current technical observations cannot masquerade as historical proof. `inspection_context.temporal_requirement` is explicit **STRICT_PIT** or **CURRENT_DESCRIPTIVE**, never a fallback. Current-descriptive results retain limitations and cannot become historical/scenario authority. A strict request facing only current-descriptive technical evidence fails with `PIT_INVALID / HISTORICAL_PIT_NOT_PROVEN`.

## 4. One logical request, complete immutable content

The exact identity preimage is:

```text
K = content_fingerprint({
  contract_id,
  contract_version,
  canonical_security_id,
  inspection_as_of,
  inspection_context: {
    purpose,
    temporal_requirement,
    canonical_horizon,
    horizon_authority_reference
  }
})
inspection_request_id = "brain-inspection-request:" + K without "sha256:"
```

Purpose is fixed to `MARKET_WIDE_DISCOVERY_REVIEW`. Horizon is null with null authority when unavailable; otherwise use the existing `CanonicalDiagnosticHorizon` vocabulary (SHORT_TERM / POSITIONAL / LONG_TERM) **only with exact governed authority at I**. A populated horizon without authority, or authority without horizon, is invalid. Union `horizon_lineage` is not a selected horizon; first-origin/input-order choice is forbidden.

The key deliberately excludes union/candidate IDs, origins/counts, symbol, rank, current time, consumer binding and result states. Three funnels discovering one security at the same explicit context/cutoff produce one logical request. Different securities of one issuer remain different requests.

`handoff_fingerprint = content_fingerprint(entire normalized handoff payload excluding only handoff_fingerprint)`.

Include the derived request ID, definition fingerprint, original master/union/candidate references, complete origin snapshot and native fingerprints, identity/membership proofs, context references, all null/unavailable states, readiness/reasons and consumer state. Identity and fingerprint have separate purposes and no circular inputs. The contract artifact's fingerprint covers its definition, not a runtime request; each request references that immutable definition fingerprint.

Use [existing canonical_json / content_fingerprint](../../app/fundamentals/diagnostic_comparability.py): UTF-8, sorted keys, compact separators, UTC aware timestamps, Decimal strings, no NaN. Sort origins by funnel ID/lead ID/native fingerprint; lineage by kind/reference ID/native fingerprint/known-at; reason and proof-reference collections deterministically. Verify native payloads before normalization. Bare native manifest hashes and prefixed content hashes retain their **native** encoding.

Exact duplicate references follow native replay semantics; conflicting references are rejected, not silently collapsed. The listed schema is closed: unlisted execution-shaped values are invalid, not ignored.

## 5. Replay and late origins

| Situation | Required behavior |
| --- | --- |
| Same key, same complete content fingerprint | IDEMPOTENT_REPLAY; reuse the logical request, no second61 run |
| Same key, different content fingerprint | BLOCKED / DUPLICATE_REQUEST_AMBIGUOUS; retain both immutable snapshots and fingerprints; no first/last winner |
| Extra origin in another union at the same I/context | Same logical key; changed content is the conflict above, not permission for another diagnosis |
| Origin/evidence genuinely after the original cutoff | Cannot enter the old request; PIT_INVALID |
| Later explicit inspection cutoff I' > I | A new immutable request may be formed from its valid canonical batch, with optional prior-request reference; old request remains unchanged |

Chosen policy: **NEXT_EXPLICIT_INSPECTION_CUTOFF_ONLY**, not mutable append or automatic reinspection. A scheduler or future approved caller supplies the new cutoff independently; this contract invents neither cadence nor a retry/expiry window. Extra funnel hits alone do not increase the number of evaluations at a given key.

Rejected/ambiguous submissions retain every original source reference and safe reason. No silent origin loss. Malformed unsafe identity may prevent creating any request ID; report a stable rejection rather than manufacture one. This defines receipt obligations but implements no receipt store.

## 6. Origin admission and scope protection

For every origin preserve the entire original lead, funnel/version, trigger codes, canonical discovery-as-of, source layer (FACT / DATA / INTERPRETATION / INFERENCE), reference ID/fingerprint/kind/known-at lineage, quality/readiness/blockers, source producer/contract version, and applicable policy/freshness provenance.

A funnel version is **not automatically** a source-producer version or independent trigger-policy version. Do not invent a standalone trigger ID: use the canonical tuple of funnel/version/trigger codes plus pinned source/adapter/policy references.

Current leads have no authoritative scalar materiality/confidence: keep null/unavailable, not zero or hit-count-derived. Strategy/archetype may be copied only from an independently verified governed source; funnel names are not strategy approval. No new score or weights.

Roles are derived by verification, not accepted from caller assertions:

- **ADMITTING:** integrity/PIT/scope/native-source/freshness valid, exact operational source and approved trigger provenance.
- **NON_ADMITTING_RESEARCH:** preserve the three research families as context with explicit blockers; never sufficient by themselves and never promoted by this contract.
- **NON_ADMITTING_UNAVAILABLE:** partial/missing-policy families remain visible, cannot establish admission without separately approved source policy/adapter.
- A contextual-only funnel inside ordinary market-wide union origins is **UNSUPPORTED_SCOPE**, even if another origin is valid. Do not prune or relabel it to obtain READY.

At least one valid admitting ordinary origin is required. All origins retain integrity/PIT verification; malformed, future or conflicting origin evidence cannot hide behind a good origin. Non-admitting research preserves unknown/stale freshness but cannot contribute facts or admission. Stale **admitting required triggers** block; missing required producer/freshness provenance blocks.

| Canonical funnel | Current registry status | Contract admission position |
| --- | --- | --- |
| `COMPOUNDER` | RESEARCH_SHADOW | NON_ADMITTING_RESEARCH |
| `EARNINGS_ACCELERATION` | PARTIAL | NON_ADMITTING_UNAVAILABLE |
| `EMERGING_COMPOUNDER` | NOT_IMPLEMENTED | NON_ADMITTING_UNAVAILABLE |
| `FUNDAMENTAL_INFLECTION` | RESEARCH_SHADOW | NON_ADMITTING_RESEARCH |
| `HOLDING_STATE_CHANGE` | PARTIAL | UNSUPPORTED_AS_MARKETWIDE_ORIGIN |
| `MARKET_DISLOCATION` | PARTIAL | UNSUPPORTED_AS_MARKETWIDE_ORIGIN |
| `MOMENTUM` | PARTIAL | NON_ADMITTING_UNAVAILABLE |
| `NEWS_CATALYST` | PARTIAL | NON_ADMITTING_UNAVAILABLE |
| `ORDERBOOK_CAPEX` | PARTIAL | NON_ADMITTING_UNAVAILABLE |
| `POLICY_TRANSMISSION` | RESEARCH_SHADOW | NON_ADMITTING_RESEARCH |
| `PRE_BREAKOUT` | OPERATIONAL | CONDITIONAL_SOURCE_PROOF_REQUIRED |
| `SECTOR_ROTATION` | OPERATIONAL | CONDITIONAL_SOURCE_PROOF_REQUIRED |
| `VALUATION_RECOVERY` | POLICY_BLOCKED | NON_ADMITTING_UNAVAILABLE |
| `WATCHLIST_STATE_CHANGE` | NOT_IMPLEMENTED | UNSUPPORTED_AS_MARKETWIDE_ORIGIN |

This represents exactly fourteen canonical entries and only one request type. Conditional Pre-Breakout/Sector eligibility is not a blanket status-based approval. Momentum/Earnings/Orderbook/News can use the same contract only after their missing governed emitter/source requirements exist. Research families require their own promotion. Emerging Compounder and Valuation Recovery gain no discovery logic or placeholder executable policy.

Separate context attachments cannot satisfy origin eligibility. Market Dislocation may accompany an independently valid candidate as source-proven regime context. Holding/watchlist attachments require a separately approved contextual consumer and are **unsupported in this market-wide scope**. No portfolio lookup is introduced. A malformed contextual union origin is not automatically converted into an attachment.

## 7. Candidate readiness versus consumer readiness

Candidate states:

`READY_FOR_BRAIN_INSPECTION`, `INSUFFICIENT_PROVENANCE`, `IDENTITY_UNRESOLVED`, `STALE_TRIGGER`, `PIT_INVALID`, `UNSUPPORTED_SCOPE`, `BLOCKED`.

Native discovery enums remain unchanged; these are contract-governance vocabulary, not new application enums. Collect all safe applicable reason codes, sorted. Primary-state precedence: BLOCKED → IDENTITY_UNRESOLVED → UNSUPPORTED_SCOPE → PIT_INVALID → INSUFFICIENT_PROVENANCE → STALE_TRIGGER → READY_FOR_BRAIN_INSPECTION.

| Failure / exclusion | State | Exact condition |
| --- | --- | --- |
| `SCHEMA_INVALID` | BLOCKED | Unknown/malformed structure, forbidden execution fields, unsafe ID or non-finite value |
| `SOURCE_FINGERPRINT_INVALID` | BLOCKED | Native union/candidate/lead/source fingerprint fails; no recompute/repair |
| `DUPLICATE_REQUEST_AMBIGUOUS` | BLOCKED | Same logical inspection key with different immutable content |
| `IDENTITY_INVALID` | IDENTITY_UNRESOLVED | Missing/ambiguous exact NSE ISIN identity or conflicting identity/lifecycle records |
| `UNIVERSE_MEMBERSHIP_MISSING` | IDENTITY_UNRESOLVED | No exact source-proven membership at each D_i and I |
| `UNSUPPORTED_CONTEXTUAL_ORIGIN` | UNSUPPORTED_SCOPE | Context-only funnel emitted as ordinary whole-market origin, even alongside valid origins |
| `UNIVERSE_SCOPE_UNSUPPORTED` | UNSUPPORTED_SCOPE | Wrong exchange/segment/security type or native universe ineligible; no new classifier |
| `FUTURE_EVIDENCE` | PIT_INVALID | Any retained origin or required source metadata after its cutoff; no hiding among valid origins |
| `HISTORICAL_PIT_NOT_PROVEN` | PIT_INVALID | Strict request paired with current-descriptive-only deep evidence; no mode conversion |
| `PROVENANCE_MISSING` | INSUFFICIENT_PROVENANCE | Missing source ID/fingerprint/version/knownness or source-native verification |
| `PRODUCER_VERSION_MISSING` | INSUFFICIENT_PROVENANCE | Module/funnel version alone does not establish actual source producer contract version |
| `FRESHNESS_UNAVAILABLE` | INSUFFICIENT_PROVENANCE | Required admitting trigger has no governed freshness/applicability proof at I |
| `NO_VALID_ORIGIN` | INSUFFICIENT_PROVENANCE | No integrity-valid, temporally valid, policy-eligible ordinary origin |
| `STALE_REQUIRED_TRIGGER` | STALE_TRIGGER | An otherwise admitting required trigger is stale under its own source policy |
| `CONSUMER_BINDING_NOT_READY` | CONSUMER_BINDING_NOT_READY | Separate consumer state, never changes candidate proof into actual delivery |
| `FUNNEL_POLICY_NOT_READY` | NON_ADMITTING_UNAVAILABLE | Partial/unavailable source family cannot admit solely from registry existence |
| `RESEARCH_NOT_PROMOTED` | NON_ADMITTING_RESEARCH | Research origin retained, cannot establish admission or change qualification |

Consumer state is independent. Candidate READY means its evidence permits an inspection request, **not that it was delivered**. Current consumer binding reference is null and state is **CONSUMER_BINDING_NOT_READY**; effective dispatch remains blocked and `submission_state = NOT_SUBMITTED`.

Any future delivery acknowledgement means only submission for canonical inspection. It does not mean diagnosis passed, Score available, setup exists, gate PASS, portfolio action or execution authorization.

## 8. Source-reference and freshness boundary

Travel with the request: full immutable discovery provenance, master/union/candidate and universe references, native producer/policy/source fingerprints, identity/membership proof references and per-origin eligibility/freshness findings. Do not copy entire OHLCV/news/financial stores into it.

The Brain assembler independently resolves native canonical evidence and governance at I. A reference string, SHA shape, verified wrapper, module name or funnel emission alone is not proof of underlying truth. Verify source fingerprints and original source-envelope knownness; never repair them. In particular, a Top3-run fingerprint attached to a ranking reference is not an independent ranking-native fingerprint.

Freshness is source-specific. Preserve native token, policy reference/version and applicability result at I; descriptive wrapper vocabulary is SOURCE_VALID / STALE / UNAVAILABLE / CONFLICTED. `SOURCE_DEFINED` alone is not proof of freshness. No common TTL, stale-age threshold or invented exemption. If a source has an approved no-age criterion, carry its reference; do not treat absence of policy as such a criterion.

## 9. Field-level mapping

Existing availability vocabulary is DIRECTLY_AVAILABLE / DERIVABLE_FROM_CANONICAL_SOURCE / MISSING / REQUIRES_POLICY / REQUIRES_IMPLEMENTATION. “Derivable” requires actual native proof, not guessed values. Missing optional metadata stays unavailable; missing required proof blocks the instance.

| Field / group | Requirement | Existing availability | Source and gap | Identity/content role |
| --- | --- | --- | --- | --- |
| `contract_id` | REQUIRED | DIRECTLY_AVAILABLE | literal canonical-discovery-union-to-brain-handoff; none | IDENTITY_AND_CONTENT |
| `contract_version` | REQUIRED | DIRECTLY_AVAILABLE | literal v1; none | IDENTITY_AND_CONTENT |
| `contract_fingerprint` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | native fingerprint of this governance artifact; contract implementation | CONTENT |
| `inspection_request_id` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | K formula in identity section; pure handoff implementation | DERIVED_IDENTITY |
| `handoff_fingerprint` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | F formula; entire normalized request payload except this field; pure handoff implementation | DERIVED_CONTENT |
| `canonical_security_id` | REQUIRED | DIRECTLY_AVAILABLE | CanonicalDiscoveryPoolItem.canonical_instrument_id; verify native identity reference | IDENTITY_AND_CONTENT |
| `isin` | REQUIRED | DIRECTLY_AVAILABLE | CanonicalDiscoveryPoolItem.isin + identity record; none | CONTENT |
| `exchange` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | NseEquityInstrument.exchange and HistoricalSecurityIdentity.exchange; native identity enrichment | CONTENT |
| `security_type` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | NseEquityInstrument.security_type; native identity enrichment | CONTENT |
| `segment` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | canonical source-proven NSE_CASH_EQUITY classification/reference; CM source provenance; never infer solely from EQ series, provider token or ISIN | CONTENT |
| `symbol` | OPTIONAL_NULLABLE | DERIVABLE_FROM_CANONICAL_SOURCE | retained NseEquityInstrument.symbol; absent -> null; no fuzzy resolution | CONTENT_NOT_IDENTITY |
| `identity_reference` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | HistoricalSecurityIdentity identity_id/version/source fingerprint + retained source envelope; source_fingerprint/reference may be absent in legacy records; fail closed | CONTENT |
| `lifecycle_state` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | HistoricalSecurityStatus exact source enum; preserve listing_status/tradable metadata separately; unresolved/conflicting lifecycle -> IDENTITY_UNRESOLVED | CONTENT |
| `source_master` | REQUIRED | DIRECTLY_AVAILABLE | WholeMarketDiscoveryBatch batch_id/fingerprint and contract multi-funnel-whole-market-orchestration/v1; standalone union is insufficient | CONTENT_NOT_IDENTITY |
| `source_union` | REQUIRED | DIRECTLY_AVAILABLE | MultiFunnelCandidateUnionBatch batch_id/fingerprint/as_of + constant multi-funnel-candidate-union/v1; none | CONTENT_NOT_IDENTITY |
| `source_candidate` | REQUIRED | DIRECTLY_AVAILABLE | CanonicalDiscoveryPoolItem candidate_id/fingerprint/status; none | CONTENT_NOT_IDENTITY |
| `universe_reference` | REQUIRED | DIRECTLY_AVAILABLE | WholeMarketDiscoveryBatch.universe snapshot_id/version/checksum/membership and instrument records; membership proof at each origin cutoff and I | CONTENT |
| `membership_references` | REQUIRED_NONEMPTY | DERIVABLE_FROM_CANONICAL_SOURCE | UniverseMembership + native source envelope OR retained snapshot demonstrably valid at each D_i and I; read-only historical membership/lifecycle enrichment | CONTENT |
| `union_as_of` | REQUIRED | DIRECTLY_AVAILABLE | candidate.batch_as_of and union.as_of; none | CONTENT_NOT_IDENTITY |
| `union_formed_at` | OPTIONAL_FIXED_NULL | MISSING | no distinct creation timestamp on current union; not a blocker; no fabricated clock | CONTENT |
| `inspection_as_of` | REQUIRED_EXPLICIT | REQUIRES_IMPLEMENTATION | future caller's explicit canonical inspection boundary; caller binding; no duration/window chosen here | IDENTITY_AND_CONTENT |
| `request_created_at` | OPTIONAL_FIXED_NULL | MISSING | no canonical physical request creation timestamp; not a blocker | CONTENT |
| `inspection_context` | REQUIRED | REQUIRES_IMPLEMENTATION | purpose MARKET_WIDE_DISCOVERY_REVIEW; temporal_requirement STRICT_PIT or CURRENT_DESCRIPTIVE; optional canonical_horizon + authority_ref; Radar horizon unresolved if absent; no consumer default | IDENTITY_AND_CONTENT |
| `origins` | REQUIRED_NONEMPTY | DIRECTLY_AVAILABLE | entire source_candidate.origins including original lead payload/id/fingerprint; native source proof enrichment | CONTENT_NOT_IDENTITY |
| `origins.discovery_as_of` | REQUIRED_PER_ORIGIN | DIRECTLY_AVAILABLE | CanonicalDiscoveryLead.discovery_as_of; distinct detected_at stays null if not present | CONTENT |
| `origins.trigger_identity` | REQUIRED_PER_ORIGIN | DERIVABLE_FROM_CANONICAL_SOURCE | DiscoveryFunnelId/funnel_version/DiscoveryTriggerCode values + verified source/adapter policy reference; no independent trigger-policy version guessed from funnel_version | CONTENT |
| `origins.producer_reference` | REQUIRED_PER_ORIGIN | DERIVABLE_FROM_CANONICAL_SOURCE | source contract/producer ID/version/native fingerprint and adapter contract hsi-multi-funnel-discovery-adapters/v1; five adapters carry source references; no universal proof resolver yet | CONTENT |
| `origins.lineage` | REQUIRED_NONEMPTY_PER_ORIGIN | DIRECTLY_AVAILABLE | DiscoveryLineageReference ID/fingerprint/kind/known_at + source envelope verification; native readers/knownness verification | CONTENT |
| `origins.freshness` | REQUIRED_PER_ORIGIN | REQUIRES_POLICY | native trigger state/freshness policy reference and applicability result at I; common lead only says SOURCE_DEFINED; missing proof -> INSUFFICIENT_PROVENANCE | CONTENT |
| `origins.role_and_admission` | REQUIRED_PER_ORIGIN | REQUIRES_IMPLEMENTATION | derived from exact registry/source/role rules, not caller override; pure verifier; no policy activation | CONTENT |
| `origins.strategy_archetype` | OPTIONAL_NULLABLE | REQUIRES_POLICY | only verified original governed source reference; absence not a new strategy | CONTENT |
| `origins.materiality_confidence` | OPTIONAL_FIXED_NULL_FOR_CURRENT_LEADS | MISSING | current lead carries no authoritative scalar; not a blocker or zero/default | CONTENT |
| `context_references` | OPTIONAL_EMPTY_TUPLE | REQUIRES_IMPLEMENTATION | separately supplied native references, not transformed union origins; no portfolio lookup here; contexts never satisfy at-least-one origin | CONTENT_NOT_IDENTITY |
| `admission_state_and_reasons` | REQUIRED | DERIVABLE_FROM_CANONICAL_SOURCE | ordered failure rules in this contract; pure validator only; stable sorted reasons | CONTENT |
| `consumer_binding_reference` | OPTIONAL_NULLABLE | MISSING | future registered read-only assembler/runner governance binding; CONSUMER_BINDING_NOT_READY | CONTENT_NOT_IDENTITY |
| `consumer_binding_state` | REQUIRED | MISSING | CONSUMER_BINDING_NOT_READY currently; future verified binding only; concrete production assembler and typed governance binding absent | CONTENT |
| `submission_state` | REQUIRED_FIXED_NOT_SUBMITTED | DIRECTLY_AVAILABLE | this definition/synthetic conformance is not runtime delivery; runtime integration not authorized | CONTENT |
| `prior_request_reference` | OPTIONAL_NULLABLE | REQUIRES_IMPLEMENTATION | previous immutable request ID/fingerprint for an explicitly new inspection cutoff; no successor store implemented | CONTENT_NOT_IDENTITY |
| `authority_boundary` | REQUIRED_FIXED | DIRECTLY_AVAILABLE | DISCOVERY_AUTHORITY != BRAIN_DECISION_AUTHORITY; BRAIN_INSPECTION_REQUEST != EXECUTION_AUTHORIZATION; none | CONTENT |

The JSON matrix additionally gives exact PIT, freshness, consumer use and readiness for **all 39 groups**, including nested origin/reference semantics. It is a governance contract, not an application JSON-schema migration.

**Lossless mapping conclusion:** original master/union/candidate/lead data can be retained unchanged. Identity/membership/source-producer/freshness proof and consumer context require enrichment through existing canonical records. A naked union or missing/legacy proof is rejected. This is **B**, not A: a defined reference boundary does not make the missing production assembler ready. It is not a requirement to rebuild the union schema or a second Brain (C/D).

## 10. Radar reconciliation and intended consumer

[Existing RadarToHsiDiagnosticOrchestrator](../../app/intelligence/radar_diagnostic_orchestration.py) accepts one CanonicalDiscoveryLead, explicit evaluation-as-of, explicit CanonicalDiagnosticHorizon and an injected assembler/Canonical61 runner. It gates exact OPERATIONAL registry family/version and requires a horizon supported by the lead.

Hazards that prevent direct reuse as a union consumer:

1. `evaluate_leads` deduplicates **lead_id**, not security. Distinct origins can cause repeated diagnoses.
2. Its technical guard explicitly requires current-descriptive READY **and strict-historical-PIT NOT_READY**.
3. It invokes `runner.run(evidence)` without the optional governance parameter.
4. `CanonicalRadarEvidenceAssembler.assemble_for_radar` is still a protocol, not an installed production implementation.
5. Union horizons do not select a canonical horizon; research source availability does not imply promotion.

A future security-level wrapper/consumer binding is required. **Do not loop all origins, select an arbitrary first lead, synthesize a fake “union lead,” or label Radar as strict historical.** Reuse the existing canonical runner and evidence/result validation concepts. Radar is unchanged in this slice.

Intended deterministic entry: [Canonical61DiagnosticRunner.run](../../app/universe_analysis/service.py), fed by `StockDiagnosticInputAssembler.assemble` and native financial/technical/benchmark/research wrappers at I, with exact typed strategy/governance verification. The canonical strategy remains `canonical-universe-analysis / v1`; the handoff contract is not a strategy.

Same Brain/comparability path: [SharedBrainApplicationService](../../app/intelligence/shared_brain_application.py) and existing production snapshot composition consume compatible canonical artifacts. They do not automatically invoke diagnosis or Score. Do not create a second dossier or universal scoring authority.

Before any future binding can dispatch it must prove read-only exact source lookup, security-level idempotency, native knownness, temporal/horizon compatibility, canonical approval/selection validity, one runner call, all61 correlation and no production writes/portfolio/broker authority from this request. Actual dispatch, persistence and scheduler remain absent.

## 11. Result correlation, downstream and presentation

A future result references **both request ID and exact handoff content fingerprint**, canonical security, I/context, source union/candidate IDs/fingerprints, all origin IDs/native fingerprints, independently assembled deep-input fingerprint, canonical diagnostic registry/strategy fingerprint and the actual result ID/fingerprint/temporal readiness.

This preserves the conceptual chain:

```text
original trigger -> source union candidate -> one inspection request
  -> independently verified deep evidence -> same canonical61 result
  -> existing Score -> appropriate setup/thesis -> Six Gates
  -> governed Watch/signal/portfolio projection -> API/UI
```

No result object, persistence table or “successful” downstream lifecycle is fabricated by the handoff. Existing insufficiency and score/gate rules remain unchanged; hits/rank/trigger count are never evidence weights.

Future public projection may expose security, discovered-by funnels, honest source discovery timestamps, safe trigger references, inspection ID/fingerprint, evaluation-as-of/freshness and blockers. It must **not expose the private61-rule inventory** or execution authority. Current API/UI is unchanged.

The contract supports batch/event/future scheduled callers but defines no cadence, retry policy, queue or equal funnel frequency. Explicit new cutoffs govern new requests.

## 12. Readiness, preservation and next item

Closed here: deterministic security-level logical identity; all-origin immutable content and replay conflicts; exact clock separation; contextual/research guards; source-reference mapping; candidate/consumer separation; result provenance contract.

Remaining: concrete native proof enrichment, per-source policy/freshness availability, context/horizon resolution, typed read-only assembler/consumer binding, strict-historical technical capability where requested, future runtime idempotency/correlation. Source insufficiency remains truthful and request-specific; the contract does not claim production data completeness.

Pending Gate-1 `NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1` remains PENDING_NOT_STARTED with accepted `SESSION_PRICE_SOURCE_APPLICABILITY_SOURCE_GAPS`. Recommend it **immediately after this contract**, restoring the predecessor's one-contract deferral. Consumer binding is a bounded future prerequisite, not silently completed and not a reason to indefinitely displace independent accepted source recovery.

The artifact preserves 200 LF-normalized source pins, predecessor native fingerprints and unchanged authority/parameter fields. Only this Markdown, its JSON, focused conformance test and README index link may change. Full backend is not required because shared/runtime behavior is unchanged; focused/relevant tests, edited Markdown links, whitespace and `git diff --check` must pass before local commit.

### Validation receipt

- Focused contract conformance: **334 passed / 0 failed / 0 skipped / 0 warnings**.
- Relevant discovery, union, Radar, Watch/P1, historical identity/PIT, technical input, canonical diagnosis, Shared Brain, Score, setup, gates, predecessor and source-governance regression: **1,072 passed / 0 failed / 0 skipped / 2 warnings**. The warnings are dependency deprecations in Starlette's httpx/AnyIO test-client interfaces.
- Native predecessor fingerprints and all 200 source pins match the accepted baseline. Edited Markdown links, table columns and whitespace are checked by the focused tests; staged `git diff --check` is required before commit.
- Full backend suite: **not run**, as authorized for this contract-only slice; no shared/application/runtime behavior changed. These tests prove offline contract conformance and preserved existing behavior, not a live Brain request or production-source readiness.

Exactly one next frozen continuation:

**`NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1`**

Resume only the previously frozen official CAS security-membership and close-source recovery scope, preserving the accepted session/price audit, all authority/parameter states and this handoff contract. Do not combine it with consumer wiring, live diagnosis or funnel promotion.

**Not started. No push.**
