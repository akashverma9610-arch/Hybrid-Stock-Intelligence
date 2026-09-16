# P1 Signal Lifecycle compatibility policy V1

Slice: `SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_DEFINITION_V1`.
Baseline: `cdb06f9d374c960c8924568ce3d5abe1da25291b`, `main`, clean.
Status: **APPROVED_FOR_IMPLEMENTATION / DOCUMENTATION_ONLY / NOT_RUNTIME_ACTIVE**.
Decision B: `SIGNAL_LIFECYCLE_P1_POLICY_APPROVED_WITH_DEFERRED_OPTIONAL_SEMANTICS`.
The user's bounded policy-definition instruction authorizes the compatible
choices below; it does not activate a strategy or alter a predecessor approval.

This resolves the [lifecycle audit](SIGNAL_LIFECYCLE_OPERATIONAL_CLOSURE_V1.md).
The [P1 acceptance record](POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md) continues
to govern immutable observations. This additive lifetime policy does not modify
P1A/P1B/P1C, Watch, setup calculations or legacy `app.signals`.
V1 ACTIVE; Execution Gate V2 NOT_ACTIVE; CAS and Agent/Lyzr parked.
ONE Brain; WATCH_ONLY / NON_EXECUTABLE; no broker/order authority.

## LC-01 — Observation versus lifetime

**DIRECTLY_DERIVED_FROM_P1:** an HSISignal is one verified immutable Watch-derived
observation. Its ID/fingerprint and unavailable fields remain unchanged.
**COMPATIBLE_EXTENSION:** a lifetime relates admitted observations; it is not a
second signal model, strategy, Watch, setup or Brain. Only the PRE_BREAKOUT
path with RESOLVED P1 registry provenance can start/continue a lifetime.
An unsupported-archetype P1 projection remains descriptive and cannot do so.

## LC-02 — Exact structural instance and provenance linkage

**COMPATIBLE_EXTENSION:** require the original canonical setup assessment and
its [candidate](../../app/strategies/pre_breakout/candidate_assembly.py) and
[opportunity](../../app/production_v1/canonical_setup_activation.py), not only
Watch.setup_state. All three must verify against retained fingerprints, with
exact canonical instrument and assessment/candidate/opportunity linkage.
For an admitted positive observation:

- Watch.watch_as_of = HSISignal.watch_as_of = assessment.evaluation_as_of =
  candidate.evaluation_as_of = opportunity.decision_as_of = evaluation cutoff T.
- P1 must reproduce byte-for-byte through the existing projector for the exact
  Watch, archetype and as-of registry result. Watch must route PRE_BREAKOUT /
  PRE_BREAKOUT_POLICY and report CURRENT_VALID_SETUP.
- Assessment status must be ELIGIBLE_TO_FORM_CANDIDATE, eligibility true and
  blockers empty. Native candidate assembly and opportunity verification must
  succeed. No new indicator/price/setup calculation is permitted.
- Policy ID/version/fingerprint and selection ID must match across assessment,
  candidate, opportunity and P1 resolution. Selection fingerprint must match
  the canonical selection; approval ID/fingerprint must match its canonical
  approved record. P1B must resolve at T; all source known-at checks apply.
- Link retained Watch, P1, assessment, candidate, opportunity, registry result,
  selection and approval IDs/fingerprints in the lifecycle evidence bundle.
  These extra references belong outside P1. Missing linkage is SOURCE_BLOCKED;
  contradictory linkage is CONFLICTED; neither is a false strategy result.

`setup_instance_key` is a digest over canonical instrument, PRE_BREAKOUT and
the exact candidate structural fields listed in the machine vocabulary below.
It groups repeated evaluations of identical governed geometry; it does NOT
replace assessment/candidate/opportunity identities. Exact Decimal values and
base timestamps are compared; there is no tolerance or fuzzy similarity.
Changing any key field is a replacement setup by definition of this policy,
not a claim of statistically material market change. Daily tick-record ID,
evaluation time, entry-reference price, diagnostic values and source record
fingerprints remain provenance, not geometry-key inputs. Tick-size VALUE is
included. Thus an irrelevant source-ID revision does not manufacture a setup.
Prices are read only to fingerprint native geometry; no lifecycle/P1 price,
entry/stop/target/quantity fields or executable plan are introduced.

## LC-03 — Slot and deterministic lifetime identity

**COMPATIBLE_EXTENSION:** one CURRENT lifetime at most per slot:
`(canonical_instrument_id, PRE_BREAKOUT, HORIZON_UNAVAILABLE)`.
The horizon marker is a partition token, not an assumed time horizon. P1
horizon must remain null/UNAVAILABLE for this policy. Other horizon values
fail closed; a future horizon-bearing policy requires its own compatibility.
The slot excludes policy version so two versions cannot be current together.

Use the canonical JSON/hash rules in LC-11 for:

- `provenance_key`: registry ID/version, policy ID/version/fingerprint,
  approval ID/fingerprint, selection ID/fingerprint.
- `lifetime_id`: policy contract, slot, setup_instance_key, provenance_key,
  originating P1 signal ID/fingerprint, initial T and predecessor terminal
  transition ID (null on first admission).

Full SHA-256 digests with `hsi-signal-lifetime:` / `hsi-setup-instance:` prefixes
are required. Prefix slot, provenance and input digests with
`hsi-signal-slot:`, `hsi-signal-provenance:` and `hsi-signal-lifecycle-input:`
respectively; each hashes the named LC-03/LC-11 fields plus the contract.
Identity inputs never include their own hash. Same complete
input/history produces the same identity. A later positive observation joins
the existing CURRENT lifetime only if slot, setup key and provenance key match.
Changes to Watch ID, non-key diagnostics or assessment ID alone do not create
a lifetime. A terminal lifetime never joins later observations.

## LC-04 — States and initial admission

**COMPATIBLE_EXTENSION:** exactly CURRENT, INVALIDATED and SUPERSEDED.
CURRENT means last admitted positive qualification, not continuously verified
present-day validity or execution permission. INVALIDATED and SUPERSEDED are
terminal for that lifetime. No DRAFT/triggered/trade/expired state is borrowed.

With no CURRENT lifetime and all LC-02/LC-10 requirements satisfied, start
CURRENT with INITIAL_QUALIFICATION. Candidate discovery, high score, news, gap,
Watch membership or a policy record alone is insufficient. If a terminal
lifetime exists, link its terminal event as predecessor; never reactivate it.

## LC-05 — Continuation and non-decisive evidence

**COMPATIBLE_EXTENSION:** a later positive Watch/assessment satisfying LC-02,
with the same slot/setup/provenance keys, appends CURRENT -> CURRENT using
SETUP_CONTINUED. It retains the new observation/evidence references and last
confirmed cutoff, not a new lifetime. Repeated identical canonical evaluation
is NO_CHANGE and creates no second transition, even on another invocation.
Invocation time is never a substitute for a new canonical evaluation cutoff.

Missing, stale, incomplete, unapproved or conflicting inputs append no
state-changing event. Return SOURCE_BLOCKED, POLICY_BLOCKED or CONFLICTED with
finite reason codes; retain last confirmed state/as-of. This is not continuing
confirmation. At a later query cutoff without a successful evaluation at that
cutoff, return SOURCE_BLOCKED / REEVALUATION_REQUIRED for a CURRENT lifetime.
No freshness TTL is invented. Terminal states need no ongoing confirmation.

## LC-06 — Narrow existing-predicate invalidation

**COMPATIBLE_EXTENSION over existing predicates, not new thresholds:** a later
complete canonical assessment for the CURRENT slot, evaluated under the exact
originating policy/selection provenance, may invalidate when at least one of
the explicit failure codes below is present with the corresponding native
category/status. These codes are produced by the existing
[setup assessment](../../app/strategies/pre_breakout/setup_assessment.py).

- Technical: BBW_NOT_COMPRESSED, ATR_NOT_CONTRACTING, VOLUME_NOT_DRY,
  DELIVERY_NOT_ABOVE_THRESHOLD, HIGH_DISTANCE_OUTSIDE_RANGE, RSI_OUTSIDE_RANGE;
  require TECHNICAL_SETUP_FAIL and BLOCKED_TECHNICAL_SETUP, with the respective
  existing resolved boolean false, never null.
- Structural: BASE_STRUCTURE_BROKEN or NO_VALID_WINDOW; require
  STRUCTURAL_SETUP_FAIL and BLOCKED_STRUCTURAL_SETUP and corresponding native
  structural status BASE_STRUCTURE_BROKEN or NO_VALID_BASE_WINDOW.

The complete bundle must have no DATA_BLOCKER or GOVERNANCE_BLOCKER, no
unresolved policy fields, reference-data conflict or future evidence. A retained
assessment fingerprint and exact source lineage are mandatory; naked booleans,
free-text reasons, Watch absence or NO_CURRENT_SETUP alone are inadmissible.
Negative evaluations cannot create a candidate/opportunity; they instead link
the existing CURRENT lifetime and its originating setup with the new assessment.
Their assessment as-of defines T. The current selected policy must still match
the lifetime provenance; do not evaluate old signals under a new policy.

The transition is CURRENT -> INVALIDATED / SETUP_PREDICATE_FAILED at T.
It means pre-breakout qualification is no longer confirmed under these allowed
predicates, NOT that the investment thesis failed, a loss occurred or a sale
is required. The new assessment tests current qualification; it does not claim
to re-run a historical base window. Other sector/entry-economics failures remain
contextual SOURCE_BLOCKED / PREDICATE_NOT_LIFECYCLE_MAPPED in V1. No lifecycle
conclusion is inferred from the mere existence of a BLOCKED status.

## LC-07 — Supersession, re-entry and policy versions

**COMPATIBLE_EXTENSION:** if a later fully qualified observation has a different
setup key OR provenance key in the same slot, atomically append CURRENT ->
SUPERSEDED / REPLACED_BY_QUALIFYING_SETUP and admit the new CURRENT lifetime.
Link the old transition to the replacement lifetime and its evidence bundle;
link the new admission to that terminal transition. Compute old transition ID
from old lifetime/prior head/replacement observation (not the new lifetime ID),
then the new lifetime ID, avoiding a circular identity dependency. Replacement
links participate in the full batch content fingerprint.

No interval with two CURRENT lifetimes is permitted. Failure to admit the new
one rolls back both events. Merely observing a different setup or version
without complete qualification does not supersede anything.
After INVALIDATED or SUPERSEDED, later qualification always creates a NEW
lifetime, even if geometry/provenance returns to prior values. No cooldown or
reactivation is invented. Version Y cannot continue or invalidate version X
using Y's rules; it can supersede X only through a new fully qualified admission.
Historical source versions/approvals remain immutable and replayable.

## LC-08 — Retirement, disablement and security lifecycle

**COMPATIBLE_EXTENSION:** new-emission/continuation authority always requires
current PIT-valid P1B RESOLVED provenance. Missing/rejected/disabled/unavailable
resolution blocks new admission and strategy reevaluation: POLICY_BLOCKED /
STRATEGY_AUTHORITY_UNAVAILABLE, with exact registry reason retained. Existing
lifetime remains last-confirmed, not certified current authority. Do not infer
permanent retirement from an outage or missing record.
The registry has no separate retirement-event contract; no such event producer
is fabricated. A future explicit retirement source can enforce the same
new-emission block but cannot silently add terminal semantics under this V1.
Historical replay needs original retained provenance, not today's permission.

Exact canonical security source evidence is independent cessation authority:
an eligible HistoricalSecurityIdentity with status DELISTED or MERGED, or an
eligible canonical action DELISTING or MERGER identifying that exact security,
can append CURRENT -> INVALIDATED / SECURITY_LIFECYCLE_ENDED at T. Require
retained source identity/fingerprint, unambiguous canonical linkage, source
known-at and effective time <= T, and native eligibility checks. This closure
remains allowed when strategy reevaluation authority is absent.
Cessation action evidence must be effective at or after that lifetime's initial
cutoff; an older action cannot repeatedly close a later legitimately relisted
lifetime. Admission requires a unique eligible ACTIVE or RELISTED canonical
identity at T, with no unresolved contradictory terminal identity. Relisting
requires its native evidence and new qualification, not an inferred reversal
of a prior action or resurrection of an old lifetime.
SUSPENDED, INACTIVE, missing identity or ambiguous continuity instead returns
SOURCE_BLOCKED / SECURITY_NOT_ELIGIBLE, with no invented terminal event.

Same canonical ID + verified symbol change is label-only. A different ISIN or
canonical ID never rebinds history; it uses another slot only after native
identity/qualification checks. Do not infer old-security cessation without its
own evidence. Split/bonus/other action basis must pass existing setup/identity
integrity; no automatic geometry conversion or resurrection is performed.

## LC-09 — Expiry and explicit exclusions

**DEFERRED:** EXPIRY_NOT_GOVERNED_FOR_THIS_PATH. No EXPIRED state/transition,
TTL, days, sessions, predicted horizon, or wall-clock expiry. P1 expires_at and
horizon remain unavailable. This does not block invalidation/replacement.
Empirical severity, new negative predicates, outcome calibration and return
claims are deferred. Other archetypes/funnels remain unsupported. No generic
positive-news activation, gap-sign invalidation, score bonus, sector override,
TradePlan entry/stop/target rule or gate authorization is introduced.

## LC-10 — Evidence timing, priority and out-of-order policy

**DIRECTLY_DERIVED_FROM_P1** PIT; **COMPATIBLE_EXTENSION** append discipline.
Every source reference carries kind, ID, retained fingerprint, canonical
instrument, evidence_as_of, evidence_known_at and effective_at where applicable.
All required timestamps are timezone-aware and <= T; effective_at <= T too.
Known-at must be verified from the owning canonical source/retained ledger,
never filled from processing time, Watch as-of, a file date or a later revision.
Assessment timestamps are evaluation times, not proof of source availability.
If the full source envelope cannot establish known-at, return SOURCE_BLOCKED /
EVIDENCE_KNOWN_AT_UNAVAILABLE. Existing source-specific freshness, price-basis
and identity eligibility rules continue to apply; no strict-PIT downgrade.

Validate/deduplicate the entire explicit evaluation bundle before choosing an
event. Identical same-ID/fingerprint references coalesce; contradictory versions
at the same governing cutoff yield CONFLICTED / EVIDENCE_CONFLICT. No hash-order
tie-break selects a policy, setup or truth. Sort references by (kind, ID,
fingerprint) only for serialization. Priority after input validation:
verified security cessation; otherwise positive admission/continuation/
replacement; otherwise allowed negative assessment; otherwise blocked/no event.
Conflicting positive/negative assessments at one cutoff block instead of using
this priority to hide the conflict. Security cessation cannot admit a replacement.

Each slot has a monotonic accepted cutoff. Exact input-key retry is handled
first. A distinct bundle at or before the committed slot cutoff is rejected
with OUT_OF_ORDER_REQUIRES_REEVALUATION (older) or CUTOFF_CONFLICT (equal).
Never insert a backdated transition, rewrite a terminal fact or silently rebuild
accepted history with newly discovered evidence. Caller may evaluate a new
explicit later canonical cutoff under this same policy, retaining the late
source's real known-at and all then-applicable source rules. A blocked receipt
does not certify historical completeness; existing committed facts describe
the admitted evidence set only. This is intentional fail-closed rejection,
not arbitrary processing-order lifecycle reconciliation.

## LC-11 — Transition fields, hashing and idempotency

**COMPATIBLE_EXTENSION:** each accepted step retains policy contract, slot,
input_key, prior_batch_id/fingerprint (null at genesis), T, canonical source
references, P1 serialization/reference when applicable, and one or two ordered
transitions. Each transition retains lifetime_id, prior_state (null only on
admission), next_state, reason_code, transition_as_of=T, known_at=max admitted
source known-at, original provenance_key and origin setup/opportunity reference,
new assessment/Watch/observation references where present, previous transition
ID/fingerprint and replacement linkage where applicable. Negative/security
steps need no newly fabricated P1 observation. Unknown fields are rejected;
opaque prose may annotate outside semantic facts but cannot be a reason code.

Evaluation outcomes are ACCEPTED, NO_CHANGE, SOURCE_BLOCKED, POLICY_BLOCKED
or CONFLICTED, separate from the three lifetime states. Blocked/rejected attempts
are returned to the caller, never saved as accepted transitions or used to
advance a head. Preserve original reason detail but restrict the primary code
to LC-15. When several blockers coexist use CONFLICTED before POLICY_BLOCKED
before SOURCE_BLOCKED. No new rejection-event platform is required.

Canonical encoding: UTF-8 JSON, sorted object keys, compact separators,
ensure_ascii=True; enums use their exact value; aware timestamps normalize to
UTC ISO8601 with microseconds; finite Decimals use fixed-point text with
insignificant fractional zeros removed and negative zero normalized to 0.
Never float-convert or use context-dependent Decimal normalization. Preserve
native retained fingerprints as supplied; do not repair/re-hash tampered source
objects. Recompute only the new contract's hashes for verification.

`input_key` hashes contract + slot + T + sorted complete source-reference
envelopes + exact P1/assessment/opportunity/provenance fingerprints + normalized
request kind (POSITIVE_ASSESSMENT, NEGATIVE_ASSESSMENT or SECURITY_CESSATION).
Identical bundle retries reuse this key independent of a worker/current head.
Transition ID hashes contract, slot, lifetime ID, prior transition ID, T,
prior/next states, finite reason and input_key; exclude its own ID/fingerprint
and replacement lifetime ID. Batch fingerprint covers every retained semantic
field and both replacement links, excluding only its own ID/fingerprint.
`batch_id = hsi-signal-lifecycle-batch:<full SHA-256>`.
Prefix transition IDs with `hsi-signal-lifecycle-transition:`. Their content
fingerprint includes the transition ID and complete final replacement linkage,
excluding only their own fingerprint. For admission, within-lifetime previous
transition ID/fingerprint are null; the separate predecessor terminal reference
links any earlier lifetime. IDs are calculated before linkage fingerprints;
no source, lifetime or transition identity depends on its own content hash.

## LC-12 — Durable ownership and concurrency (next slice only)

**COMPATIBLE_EXTENSION:** reuse the existing SQLiteCoreApiSnapshotRepository
database and immutable CoreApiSnapshot encoding infrastructure. Add one typed
P1_SIGNAL_LIFECYCLE_BATCH family for accepted immutable batches; never reuse
legacy SIGNAL, signals or signal_lifecycle_events tables for P1 payloads.
Store the native serialized P1 observation and its source references in the
batch (or reference an already immutable retained identical observation); no
mutable observation fields. Store enough exact source/provenance payloads or
immutable references to reconstruct without a current/latest source lookup.
Loading must verify IDs/fingerprints and reproduce native P1 through its public
construction/verification path, not pass derived init=False fields to a generic
constructor or modify P1 deserialization semantics.

A small additive `p1_signal_lifecycle_heads` table in that SAME database owns
slot_key primary key, latest batch ID/fingerprint, accepted cutoff and current
lifetime ID (nullable); it is a replaceable concurrency index, not history.
The future repository method must transactionally insert the immutable batch
and compare/update the expected slot head under SQLite BEGIN IMMEDIATE.
Use the existing [bounded transaction pattern](../../app/filings/earnings_schedule_store.py)
as infrastructure reference only; do not reuse earnings schema/semantics.
Enforce UNIQUE(slot_key, input_key) and UNIQUE(slot_key, accepted_cutoff) through
an additive batch index in the same transaction. IDs/fingerprints are immutable.
New family/index/head migration is required in runtime implementation; none is
created or applied here. No new database, queue or event-sourcing platform.

On retry, identical input_key AND identical canonical input payload return the
already accepted result without writes. Same key/different payload is conflict.
On concurrent head mismatch: rollback, reload; identical accepted input returns
that result; otherwise recompute against new head and obey LC-10. Never blindly
retry a stale proposed transition. Replacement closure/admission is one atomic
batch. Failure before commit leaves neither event; failure after commit is
recovered by idempotent read. A uniqueness exception alone is not a successful
semantic duplicate unless retained content matches.

## LC-13 — Current-state projection/replay and query boundary

**COMPATIBLE_EXTENSION:** the future isolated lifecycle module reduces only
verified committed batch chains. The existing Watch-to-HSISignal projector stays
unchanged and supplies observations; it is not repurposed as a lifetime reducer.
No alternative implementation of either projection is authorized.
Replay follows prior-batch links and increasing canonical T, not insertion order;
validate one chain, hashes, reasons/edges, original provenance and atomic
replacement links. Branch/missing predecessor/tampering is CONFLICTED, not
best-effort latest. Rebuild the head index from that immutable chain only.
At query cutoff Q, use batches with T <= Q and all retained known-at <= Q.
Do not consult newer Watch/setup/policy versions. Return slot/lifetime ID,
original provenance/setup key, state, last confirmed/effective cutoff, observation
references, transition history IDs, readiness/reason and authority constants.
CURRENT at an unconfirmed later Q follows LC-05; no false freshness claim.
This read-only replay consults no live registry: a blocked reevaluation response
may report POLICY_BLOCKED, while a later chain-only query reports
SOURCE_BLOCKED / REEVALUATION_REQUIRED because no accepted confirmation exists
at Q. Neither manufactures an accepted retirement or continuation event.

## LC-14 — Brain, portfolio, Alerts and legacy compatibility

**DIRECTLY_DERIVED_FROM_P1:** lifecycle is downstream evidence, not analytical
authority. No Decision Score threshold/bonus, setup recalculation, gate PASS or
portfolio access/mutation. Signal current != executable != Six Gates PASS.
Invalidation != automatic sale; expiry-unavailable != prediction of correctness.
Catalyst/Event, Opening/Overnight, regime and sector remain contextual unless
the existing exact setup predicate already consumed them upstream.
Later Alerts may read committed batch IDs/reasons/state/cutoff/provenance and
deduplicate by transition ID. Channels, throttling, subscriptions and delivery
remain outside this policy and are not implemented.

| Legacy semantic | P1-compatible? | Decision/classification |
| --- | --- | --- |
| Immutable facts and retained evidence references | Conceptual reuse | DIRECTLY_DERIVED_FROM_P1; reuse immutability principle, not legacy payload |
| SQLite immutable insert and duplicate detection | Adapt infrastructure | COMPATIBLE_EXTENSION; atomic P1 batch/head method, not duplicate exception as success |
| Legacy SignalRecord / TradePlan identity | No | REJECTED_AS_LEGACY_CONFLICT; P1 observation unchanged, separate lifetime linkage |
| Legacy status/trigger/score/gate/rotation rules | No automatic mapping | REJECTED_AS_LEGACY_CONFLICT; three states and five reasons defined here only |
| Configured expiry/cooldown and confidence calculation | No | REJECTED_AS_LEGACY_CONFLICT; no numeric defaults |
| Legacy revalidate prior_events behavior | No | REJECTED_AS_LEGACY_CONFLICT; terminal absorption and linked replay required |
| Paper replay, signal API/UI, alert delivery | Not reused | DEFERRED; no paper/order/portfolio/API call |

## LC-15 — Finite machine vocabulary and completeness cases

This block is normative documentation, NOT a runtime schema/registration.
All key fields refer to the existing candidate contract; failure mappings refer
to existing setup categories. Cases require LC-02/LC-10 validation first.

```json
{
  "contract": "hsi-signal-lifecycle-p1/v1",
  "states": ["CURRENT", "INVALIDATED", "SUPERSEDED"],
  "terminal_states": ["INVALIDATED", "SUPERSEDED"],
  "actionability": "WATCH_ONLY",
  "execution_status": "NON_EXECUTABLE",
  "expiry": "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH",
  "strategy": "PRE_BREAKOUT",
  "geometry_fields": ["base_start", "base_end", "base_duration", "base_top", "resistance", "breakout_confirmation_trigger", "structural_support", "final_structural_stop", "measured_move_target", "tick_size"],
  "edges": [
    [null, "CURRENT", "INITIAL_QUALIFICATION"],
    ["CURRENT", "CURRENT", "SETUP_CONTINUED"],
    ["CURRENT", "INVALIDATED", "SETUP_PREDICATE_FAILED"],
    ["CURRENT", "SUPERSEDED", "REPLACED_BY_QUALIFYING_SETUP"],
    ["CURRENT", "INVALIDATED", "SECURITY_LIFECYCLE_ENDED"]
  ],
  "negative_codes": {
    "TECHNICAL_SETUP_FAIL": ["BBW_NOT_COMPRESSED", "ATR_NOT_CONTRACTING", "VOLUME_NOT_DRY", "DELIVERY_NOT_ABOVE_THRESHOLD", "HIGH_DISTANCE_OUTSIDE_RANGE", "RSI_OUTSIDE_RANGE"],
    "STRUCTURAL_SETUP_FAIL": ["BASE_STRUCTURE_BROKEN", "NO_VALID_WINDOW"]
  },
  "blocked_reasons": ["EVIDENCE_KNOWN_AT_UNAVAILABLE", "EVIDENCE_CONFLICT", "SOURCE_LINEAGE_UNAVAILABLE", "SOURCE_NOT_ELIGIBLE", "STRATEGY_AUTHORITY_UNAVAILABLE", "SECURITY_NOT_ELIGIBLE", "PREDICATE_NOT_LIFECYCLE_MAPPED", "REEVALUATION_REQUIRED", "OUT_OF_ORDER_REQUIRES_REEVALUATION", "CUTOFF_CONFLICT", "INPUT_CONFLICT", "CHAIN_CONFLICT"],
  "cases": {
    "A": "FIRST_QUALIFICATION_NEW_CURRENT",
    "B": "IDENTICAL_INPUT_NO_CHANGE",
    "C": "MATCHING_KEYS_CURRENT_TO_CURRENT",
    "D": "ALLOWED_COMPLETE_NEGATIVE_TERMINAL_INVALIDATION",
    "E": "RECOVERY_NEW_LIFETIME_NEVER_RESURRECTION",
    "F": "CHANGED_GEOMETRY_ATOMIC_SUPERSESSION_AND_ADMISSION",
    "G": "FUTURE_INPUT_REJECTED_NO_TRANSITION",
    "H": "NEW_PROVENANCE_NEW_LIFETIME_ONLY_IF_QUALIFIED",
    "I": "AUTHORITY_UNAVAILABLE_BLOCK_NEW_EMISSION_PRESERVE_HISTORY",
    "J": "DUPLICATE_NO_OP_OR_CAS_RELOAD_WITHOUT_DOUBLE_TRANSITION"
  }
}
```

## LC-16 — Acceptance and next work

Every semantic above is labeled DIRECTLY_DERIVED_FROM_P1, COMPATIBLE_EXTENSION,
REJECTED_AS_LEGACY_CONFLICT or DEFERRED. Core lifetime identity, exact setup
linkage, admission/continuation/invalidation/re-entry/supersession, version and
retirement handling, source ordering and durable ownership are settled here.
Runtime source absence remains a fail-closed data condition, not another policy
approval loop. Expiry, explicit retirement-event ingestion, unmapped negative
categories and additional strategies are optional/deferred, not secretly enabled.

This slice creates only this principal document and conformance tests. There is
no transition writer, projector runtime, schema migration, activation or new
application module. Existing/frozen documents and source pins remain unchanged.
Focused/relevant tests, local Markdown links and diff checks must pass before
the local commit. Full regression is conditional on shared/runtime changes;
there are none in this documentation/test-only slice.

Validation recorded: 14 focused conformance tests passed; 121 relevant P1,
Watch/projector, Pre-Breakout governance/setup/provenance, legacy lifecycle and
persistence regressions passed with 2 existing TestClient/httpx/anyio warnings.
These are policy/source-compatibility proofs, not implementation or live
lifecycle durability tests. Full backend suite was not rerun because no shared
application/runtime behavior changed. Seven normalized-text predecessor hashes
are checked by the focused tests; no source-pin expectation was modified.

Exactly one next frozen continuation: `SIGNAL_LIFECYCLE_P1_RUNTIME_BINDING_V1`.
Not started. Implement this policy and its persistence/replay fixtures, not
another policy/proposal/audit layer. Do not push.
