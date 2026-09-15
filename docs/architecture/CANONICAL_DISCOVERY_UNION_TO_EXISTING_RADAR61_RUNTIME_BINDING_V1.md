# Canonical discovery union to existing Radar61 runtime binding V1

Slice status: `ACCEPTED/CLOSED` for the tested bounded binding, with remaining
origin coverage explicitly partial. Decision **B —
`RUNTIME_BINDING_PARTIAL_WITH_BOUNDED_BLOCKER`**.

Baseline: `2ad08c463928f76906c969654d811df274566057`, branch `main`.

This implementation record does not rewrite the historical
[handoff contract](CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1.md),
[14-funnel registry](MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md), or
[Radar bridge](RADAR_TO_HSI_DIAGNOSTIC_ORCHESTRATION_V1.md). Its accepted handoff
definition fingerprint remains
`sha256:731399dfbca758763dda0ad9ee1350aa50cd433ab183bb62fc710e4b5826b1e8`.

## Working entry and reuse

[UnionRadarRuntimeBinding.inspect](../../app/intelligence/discovery_union_radar_binding.py)
accepts the full verified `WholeMarketDiscoveryBatch`, an exact candidate ID,
explicit inspection cutoff/context, retained identity/membership references and
native cash-segment evidence. A naked union is not sufficient. Source reads use
only the existing snapshot `get_snapshot` interface through dependency injection.

The implemented ordinary path is:

`canonical14 runner -> existing candidate union -> security inspection ->
unchanged RadarToHsiDiagnosticOrchestrator.evaluate_one_lead -> unchanged
Canonical61DiagnosticRunner.run -> 61 rule references`.

The unique verified admitting lead is the Radar dispatch reference. It is **not**
the first funnel or highest-ranked origin. The complete immutable origin tuple
remains in the security handoff, alongside every native source envelope and
admission role. No synthetic union lead is created. Verified Fundamental
Inflection/Compounder research origins can accompany a sector-origin candidate;
they cannot independently admit it or supply diagnostic facts. Discovery
hit-counts never become weights, evidence values or scores.

`StoredCanonicalRadarEvidenceAssembler` concretely delegates to the existing
`StockDiagnosticInputAssembler.assemble`, retaining its stored-observation PIT
guard and optional native financial-input hook. The existing certified technical
input is supplied by a read-only native reader callback, verified and passed
unchanged. There is no provider fallback, second evidence store, setup/ranking
recalculation or hidden acquisition. Missing financial/research/benchmark evidence
remains missing; the callback is not authority to fabricate a technical input.

The exact typed canonical61 definition is authorized before dispatch and must
have been created/registered no later than the cutoff. The result correlates the
handoff fingerprint, complete assembled-input fingerprint, canonical strategy
semantic fingerprint and original Radar receipt. Its 61 references preserve
partial/insufficient/source-not-ready states, including existing limitations on
Rules 6, 14, 35 and 57. It creates no Rule 62 or execution-shaped output.

## Native provenance and clocks

- Exact `NSE:<ISIN>` identity, source envelopes, historical lifecycle selection
  and native inclusive membership boundaries are checked at each origin cutoff
  and the inspection cutoff. Duplicate/ambiguous identity inputs fail closed.
- Cash-segment evidence is a native official direct-source observation, checked
  together with the independent master EQUITY classification and historical
  identity. A tick/provider token alone is never ordinary-equity or CAS proof.
- For sector admission, the native Top3 run is reconstructed for comparison
  only. Its actual `CurrentSectorRankingArtifact` is independently verified; the
  run fingerprint is never substituted for a ranking-native fingerprint. Exact
  constituent ISIN and single-sector/top3 membership must agree.
- The supported source freshness case is an already-calculated ranking and
  discovery run at the **same explicit inspection cutoff**. Older observations
  return `SOURCE_FRESHNESS_NOT_PROVEN`; this is a conservative capability limit,
  not a new TTL or an assertion that all older evidence is intrinsically stale.
- Current-descriptive technical evidence remains `CURRENT_DESCRIPTIVE`.
  `STRICT_PIT` returns `HISTORICAL_PIT_NOT_PROVEN`, including unsupported
  CAS-dependent historical cases. There is no automatic mode fallback.
- The explicitly selected canonical horizon is checked against the native
  admitting lead and frozen registry's discovery-review horizons. Its authority
  reference is that registry identity/version/fingerprint, **not** a setup
  opportunity, strategy holding period or execution horizon. Rule applicability
  remains `POLICY_UNSET`. No rule/horizon/bootstrap policy activates here.
- Physical request/detection times, scalar confidence/materiality and context
  attachments are unavailable. No wall clock is used.

The [CAS primary-input blocker](NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1.md)
remains parked `EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED`. No CAS membership is
inferred or acquired. Supported current-descriptive diagnosis does not depend on
closing that external branch.

## Replay and remaining bounded gaps

The security request key follows the accepted contract: contract ID/version,
security, cutoff and explicit context only. Master/union/candidate IDs and origin
counts do not enter the logical key. Complete normalized handoff content has a
separate fingerprint.

One binding instance serializes submissions with a lock and retains up to 100
successful immutable results (or a smaller explicit limit). Exact replay returns
`IDEMPOTENT_REPLAY` without assembly/evaluation. Changed provenance at the same
key returns `DUPLICATE_REQUEST_AMBIGUOUS`, retaining the incoming snapshot and
prior fingerprint. Only a new explicit cutoff allows a successor. Capacity is
fail-closed; there is no eviction/retry loop. This is **session-local**, not a
durable cross-process idempotency claim. No scheduler or persistence was added.

Remaining partial coverage is intentional and visible:

1. The native Radar receipt is single-lead-shaped. More than one admitting
   origin returns `MULTI_ADMITTING_RADAR_RECEIPT_NOT_SUPPORTED`; no arbitrary
   winner or per-origin diagnosis is used. The verified multi-origin proof here
   is one admitting Sector origin plus one non-admitting Inflection origin.
2. Pre-Breakout and Policy Transmission native proof/envelope bindings are not
   installed by this bounded implementation. They return
   `NATIVE_ORIGIN_PROOF_BINDING_UNAVAILABLE`. In particular, real setup successor
   versions must not be relabelled `v1` to bypass the frozen Radar version guard,
   nor may `NOT_GOVERNED_FOR_SETUP_OPPORTUNITY` become horizon authority.
3. Unpromoted/partial/unimplemented funnels remain unavailable. Market
   Dislocation, Holding State Change and Watchlist State Change are rejected as
   market-wide origins even alongside a valid origin. Separate contextual
   attachment consumers are not implemented.
4. Native source readers must be supplied by a bounded stored-data caller.
   No production scheduler, API/UI, provider wiring, bulk live run, or durable
   receipt persistence is claimed. The proof uses fixture-backed native records
   and the **real** canonical runner, not mocked rule results.

These limits are why the decision is B, not full operational A. They do not
require rebuilding the Brain, diagnostic algorithms or evidence stores.

## Validation and authority boundary

[Focused integration/conformance tests](../../tests/unit/test_discovery_union_radar_binding.py)
cover exact1-61, native lineage tampering, future receipts, missing assembler,
all14 admission guards, source/ranking mismatch, multi-origin traceability,
deterministic keys/serialization, parallel replay, successor cutoffs, capacity,
missing evidence and no database/network/score/gate calls. Completed validation:
focused **51 passed**; relevant regressions **1,199 passed**; full backend
**8,486 passed / 0 failed / 6 skipped / 2 warnings** (782.24 seconds). The two
warnings concern existing Starlette/httpx and AnyIO deprecations. The first full
run exposed the pre-existing stale source pins described below; the complete
suite was rerun after their narrow test-only repair and final PIT hardening.

Changes are this record, the new binding module, its focused test file and two
predecessor tests' exact concrete-port allowlists. Those older tests correctly
proved that no concrete port existed during their documentation-only slices;
they now allow exactly the authorized additive module, retaining all external
caller prohibitions. No accepted predecessor application source or historical
governance artifact is edited. One additional pre-existing downstream test's
stale source pins are repaired: original historical hashes remain checked, and
the already-accepted NSE master/snapshot-repository extensions are independently
pinned to this slice's accepted baseline. Neither application source is changed.
V1 remains `ACTIVE`; V2 remains `NOT_ACTIVE`; research bootstrap remains
`UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE`. All outputs remain
`WATCH_ONLY / NON_EXECUTABLE`. No Decision Score, Setup, Six Gates, portfolio,
signals, broker/orders, API/UI or production activation is wired downstream.

Exactly one next frozen continuation:
**`CANONICAL_DISCOVERY_RADAR61_REMAINING_ORIGIN_PROVENANCE_BINDING_V1`**.

Bound it to native remaining-origin proof and multi-admitting receipt
compatibility, preserving this working sector/current path and every frozen
registry/version/authority guard. Do not add downstream judgement or CAS
acquisition. **Not started. No push.**
