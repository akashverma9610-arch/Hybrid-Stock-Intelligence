# Post-V1 Product Phase P1 — Watch-only `HSISignal` Foundation

**Status: `IMPLEMENTED / INTERNAL_ON_DEMAND_PROJECTION / WATCH_ONLY / NON_EXECUTABLE / NOT_CONSUMER_ACTIVE`.**

## 1. Authority, purpose, and boundary

This document remains the canonical approval and acceptance record for the
first implementation slice of the [Post-V1 Product
Architecture](POST_V1_PRODUCT_ARCHITECTURE.md). P1 is now implemented only as
an internal, pure, on-demand projection. It does not activate a consumer
product or change frozen HSI Core V1. No schema, API, UI, runtime, provider,
credential, portfolio, order, or broker behavior is changed.

P1 implements a pure projection of one existing immutable
`MarketWideWatchRecord` into a normalized `HSISignal`.  It is not a new
detection, ranking, scoring, setup, gate, or execution engine.  Every P1
output is fixed to:

`actionability = WATCH_ONLY`
`execution_status = NON_EXECUTABLE`

## P1 implementation and acceptance record

The completed P1 boundary consists solely of three internal modules:

| Slice | Implemented artifact | Commit | Acceptance boundary |
| --- | --- | --- | --- |
| P1A | immutable `HSISignal` value contract | `9d2c46c` | deterministic, immutable, Watch-only/non-executable contract |
| P1B | read-only fail-closed strategy provenance registry | `24dbda2` | exact PIT-valid Pre-Breakout provenance or `STRATEGY_UNAVAILABLE` |
| P1C | pure Watch-to-signal projector | `1cf3b95` | one verified Watch × routed archetype to one deterministic signal |

P1 does not persist a signal, expose an API/UI, calculate a strategy, create a
setup/gate/score, access portfolio state, or enable execution. The source
Watch remains the single discovery artifact and `app.signals` remains
unchanged.

P1D closure validation at `1cf3b95` recorded `53 passed` for P1A/P1B/P1C
focused tests, `92 passed / 1 warning` for the relevant Watch and Pre-Breakout
governance tests, and `2152 passed / 0 failed / 6 skipped / 1 warning` for the
complete backend suite. These software results prove contract behavior only;
they do not establish strategy performance or activation.

The existing `app.signals` `SignalRecord` is not equivalent to P1.  It models
analytical setup/trade-plan lifecycle concepts, including entry, stop, target,
gate, and rotation references.  P1 must neither import nor reuse that contract
and must leave `app.signals` unchanged.  The existing `/signals` API must not
become a P1 consumer without a separately approved compatibility decision.

## 2. Established Core V1 inputs to reuse

| Core V1 contract | P1 reuse | Boundary retained |
| --- | --- | --- |
| `MarketWideWatchRecord` / `MarketWideWatchRun` | Immutable source record, `watch_id`, `watch_as_of`, canonical instrument, Watch fingerprint, blockers, router output | Watch remains the only discovery/read source. |
| `OpportunityArchetypeRouter` | Existing archetype and setup-policy-route classification | No new archetype or scoring rule. |
| Canonical instrument / historical universe | `canonical_instrument_id` and PIT membership already used by Watch | No symbol/name matching or product-local identity. |
| Canonical diagnostics / Watch evidence references | Diagnostic rule/result/artifact identifiers and fingerprints | No new evidence collection. |
| External evidence references | Existing canonical event/evidence-version fingerprints when present | Only Watch-PIT-filtered evidence is eligible. |
| Pre-Breakout governance | Selected approved policy view under `CURRENT_STORED_SCAN` | Registry lookup cannot activate, evaluate, or execute the policy. |
| `CoreApiSnapshot` convention | Existing immutable snapshot/audit model | No P1 persistence; the Watch remains the auditable source. |

`MarketWideWatchService.latest(as_of=...)` already excludes future-dated Watch
runs.  The Watch materialization path already reads canonical diagnostics and
external evidence at the Watch `as_of` time.  P1 must consume those retained
references, not query a newer "latest" diagnostic/evidence value.

## 3. Exact implemented `HSISignal` contract

The following contract is implemented only for internal P1 on-demand
projection; it is not a consumer-product runtime model or API contract.

| Field | P1 source / rule |
| --- | --- |
| `signal_id` | Deterministic identity described in section 5. |
| `canonical_instrument_id` | Exact `MarketWideWatchRecord.canonical_instrument_id`. |
| `watch_id`, `watch_fingerprint`, `watch_as_of` | Exact immutable Watch identity, fingerprint, and timezone-aware as-of. |
| `archetype`, `routing_policy_version` | One existing Watch archetype and `Watch.policy_identity`; no inferred archetype. |
| `strategy_resolution` | Read-only result from section 4, never an execution permission. |
| `horizon`, `direction` | Populate only when the Watch's existing canonical routing evidence explicitly supplies that exact value for the archetype. Otherwise `null` with `HORIZON_UNAVAILABLE` / `DIRECTION_UNAVAILABLE`; P1 must not infer a default. Current P1 defines no such routing-evidence mapping. |
| `strength`, `confidence`, `materiality` | Always `null` with explicit unavailable blockers in P1. P1 must not calculate, copy, aggregate, convert, or reinterpret values until separately governed calculation policies exist. |
| `actionability` | Literal `WATCH_ONLY`. |
| `execution_status` | Literal `NON_EXECUTABLE`. |
| `diagnostic_lineage` | Canonically ordered Watch diagnostic references: rule ID, diagnostic result, artifact ID, and artifact fingerprint. |
| `evidence_lineage` | Canonically ordered external evidence/event/version references and fingerprints already retained by Watch. |
| `detected_at`, `detection_time_status` | `detected_at` is populated only from a distinct canonical Watch detection timestamp, if one exists. The current Watch contract exposes `watch_as_of`, not a distinct detection timestamp: P1 therefore exposes `watch_as_of` and sets `detected_at` to `null` with `DETECTION_TIME_UNAVAILABLE`. Projection runtime/current wall-clock time must never affect this field, identity, or semantics. |
| `expires_at`, `staleness_policy` | `null` / `EXPIRY_POLICY_UNAVAILABLE` in P1. No artificial expiry duration is allowed. |
| `lifecycle_status`, `lifecycle_flags` | Exact source Watch `status` and `lifecycle_flags`; P1 creates no `WATCH_PROJECTED` or other synthetic signal lifecycle. The source Watch owns freshness/lifecycle semantics. |
| `portfolio_relevance` | Literal `NOT_EVALUATED`. The projector must not access, read, or mutate portfolio state. |
| `blocker_codes`, `unavailable_fields` | Canonically sorted union of Watch blockers, registry blockers, and unsupported-field blockers. |
| `projection_policy_version`, `fingerprint` | New P1 contract/policy version and a deterministic tamper-evident fingerprint. |

One `HSISignal` is projected per Watch record × archetype.  A Watch record with
no archetype creates no P1 signal.  The proposal intentionally does not map
Watch classifications without a routed archetype into synthetic signals.

## 4. Read-only versioned Strategy Registry

P1 implements a pure resolver, not a new generic strategy store. Its results
are either an exact policy reference or `STRATEGY_UNAVAILABLE`.

`PRE_BREAKOUT` may resolve only when all of the following hold at
`watch_as_of`:

1. the Watch's existing `setup_policy_routes` contains
   `PRE_BREAKOUT_POLICY` for that archetype;
2. `PreBreakoutPolicyGovernanceService.get_selected_prebreakout_policy()`
   returns the selected policy for `CURRENT_STORED_SCAN` as of that timestamp;
3. selection, approval, policy ID, policy version, and policy fingerprint all
   validate through the existing governance path; and
4. no ambiguity, approval rejection, inactivity, effective-time mismatch, or
   fingerprint/version mismatch is present.

Every other `OpportunityArchetype` resolves to `STRATEGY_UNAVAILABLE`.  The
same outcome applies to a missing, inactive, unapproved, ambiguous, temporally
invalid, or version-mismatched Pre-Breakout policy. A successful resolution is
provenance only: it does not create a setup, a Decision Score, Six-Gates
result, capital authorization, trade plan, or order authority.

## 5. Deterministic identity, PIT, and lineage rules

Implemented `signal_id` inputs, serialized canonically and hashed with the P1
projection contract version, are:

1. `canonical_instrument_id`;
2. `watch_id` and `watch_fingerprint`;
3. `watch_as_of` in timezone-aware canonical ISO-8601 form;
4. archetype;
5. `routing_policy_version` / Watch `policy_identity`;
6. complete strategy-resolution state and, when available, selected policy ID,
   version, approval ID, selection ID, and policy fingerprint;
7. ordered diagnostic artifact fingerprints;
8. ordered external evidence/event/version fingerprints; and
9. P1 projection-policy version.

Identical canonical inputs must produce the identical ID and fingerprint.
Any changed input produces a distinct immutable projection; no old projection
is overwritten.  Diagnostic or external evidence received after `watch_as_of`
is excluded.  The projection must reject a source Watch whose fingerprint fails
verification, whose as-of is naive, or whose retained lineage cannot be
verified.  This preserves reproducibility and makes tampering detectable.

Projection runtime, process time, current wall-clock time, and any current
portfolio state are forbidden identity inputs. `watch_as_of` remains the only
P1 time input unless a distinct canonical Watch detection timestamp is later
introduced; the absence of that timestamp is represented by
`DETECTION_TIME_UNAVAILABLE`, not by substituting projection time.

## 6. Forbidden P1 fields and behavior

P1 must not contain or create:

- entry, stop-loss, target, trigger, or execution prices;
- quantity, sizing, allocation, capital reservation, or cash mutation;
- a BUY, SELL, REDUCE, EXIT, or ROTATE instruction;
- a Six-Gates authorization, Decision Score, executable setup, or trade plan;
- broker, order, or provider-execution interface;
- holdings, portfolio, or trade lifecycle mutation; or
- fabricated default values for horizon, direction, strength, confidence,
  materiality, expiry, policy, or portfolio relevance.

## 7. Persistence decision

**Recommendation: begin P1 as a pure on-demand projection over a single
immutable Watch record.**

This follows Core V1's separation of immutable source snapshots from read-only
query projection.  A projected P1 signal has no independent state, lifecycle,
or new evidence in its first slice; persisting it would duplicate an already
fingerprinted Watch record without adding audit value.  Repeated projection is
deterministically idempotent by identity.

P1 is approved only as this pure deterministic on-demand projection. No P1
persistence, repository, database migration, snapshot family, or audit table
is authorized. A future product phase may separately propose immutable storage
only if it needs independent signal lifecycle, cross-Watch retention/query, or
an append-only product audit; that future work is outside P1.

## 8. Implemented code-change map

| Area | P1 role | Status |
| --- | --- | --- |
| `app/intelligence/market_wide_watch.py` | Read verified Watch record only | Reuse unchanged. |
| `app/intelligence/opportunity_archetypes.py` | Read existing archetype / policy route only | Reuse unchanged. |
| `app/historical/guard.py` | Canonical fingerprint helper/conventions | Reuse unchanged. |
| `app/strategies/pre_breakout/governance.py` | Read approved selected-policy view | Reuse unchanged. |
| `app/intelligence/hsi_signal.py` | Immutable P1A contract | Implemented; no projection/persistence behavior. |
| `app/intelligence/hsi_signal_projection.py` | Pure Watch-to-`HSISignal` projector | Implemented; on-demand only. |
| `app/intelligence/hsi_signal_strategy_registry.py` | Pure fail-closed resolver | Implemented; read-only provenance only. |
| `tests/unit/test_hsi_signal.py` | P1A contract tests | Implemented. |
| `tests/unit/test_hsi_signal_projection.py` | P1C projector tests | Implemented. |
| `tests/unit/test_hsi_signal_strategy_registry.py` | P1B registry tests | Implemented. |
| persistence, repositories, migrations, `app/api/**`, `frontend/**`, `app/signals/**` | No P1 change | Explicitly untouched; `app.signals` is not imported as the P1 contract. |

Dependency direction is one-way:

`immutable Watch + existing governance readers → pure P1 projection → future read-only product query`

P1 never writes to, alters, or calls back into Core V1.  It therefore preserves
Core V1 as the frozen implementation baseline and avoids parallel truth.

## 9. Focused acceptance tests

1. Identical verified Watch/registry inputs yield an identical signal ID and
   canonical serialization.
2. Repeated projection is idempotent and produces no write.
3. A future-dated Watch, diagnostic reference, external evidence reference, or
   policy selection is excluded or fails closed.
4. Every output preserves the exact Watch diagnostic and evidence lineage.
5. An approved, selected, effective Pre-Breakout policy resolves exactly.
6. Every non-Pre-Breakout archetype returns `STRATEGY_UNAVAILABLE`.
7. Missing, unapproved, inactive, ambiguous, temporally invalid, or
   version-mismatched policy inputs fail closed to `STRATEGY_UNAVAILABLE`.
8. Serialization has no forbidden execution fields and uses explicit null /
   unavailable values rather than fabricated defaults.
9. Projection has no order, broker, provider, portfolio, holdings, cash,
   gate, score, setup, or trade-plan side effect.
10. Stable serialization and fingerprint tests do not require persistence;
    persistence/reopen tests are outside P1.

## 10. Incorporated governance decisions and deferred future decisions

Established Core V1 facts are the immutable Watch/PIT/lineage mechanisms, the
existing Pre-Breakout governance lookup, and the evidence-only Six-Gates
boundary. The following P1 decisions are approved and are not implementation
blockers:

1. Detection time derives only from a distinct existing canonical Watch
   timestamp. In its absence, P1 exposes `watch_as_of` and
   `DETECTION_TIME_UNAVAILABLE`; projection time is forbidden.
2. Horizon and direction appear only when exact canonical routing evidence
   supports them; otherwise they remain unavailable.
3. Strength, confidence, and materiality remain unavailable: P1 calculates no
   new values and performs no conversion or aggregation.
4. P1 follows the source Watch's status and lifecycle flags. It creates no
   expiry duration or independent lifecycle; expiry policy remains unavailable.
5. Portfolio relevance is always `NOT_EVALUATED`; P1 does not access portfolio
   state.
6. P1 is pure deterministic on-demand projection with no persistence,
   repository, migration, or audit table.
7. Product API and consumer UI contracts are deferred, and `app.signals`
   remains unchanged and unimported.
8. Every P1 output is unconditionally `WATCH_ONLY` and `NON_EXECUTABLE`.
9. Missing, ambiguous, inactive, unapproved, temporally invalid, or
   version-mismatched strategy-policy resolution is
   `STRATEGY_UNAVAILABLE`.

The following are genuinely deferred future product decisions, not P1
implementation blockers: a future canonical routing taxonomy that supplies
horizon/direction; governed calculation policies for strength, confidence, or
materiality; a distinct canonical Watch detection timestamp; an expiry policy
or independent signal lifecycle; portfolio relevance semantics; product API/UI
contracts; and any separately approved persistence phase. P1 must not silently
choose any of them: the approved unavailable/not-evaluated values above are its
fail-closed behavior.

## 11. Completed independently testable implementation slices

| Slice | Scope | Acceptance criteria | Rollback boundary |
| --- | --- | --- | --- |
| P1.1 | Pure contract, deterministic serialization, and fingerprint | Accepted P1A tests pass; no repository/API dependency | Remove the isolated module/tests; Core V1 untouched. |
| P1.2 | Pure fail-closed Strategy Registry resolver | Accepted P1B tests pass using existing governance readers only | Remove resolver/module/tests; no policy records changed. |
| P1.3 | Pure Watch-to-`HSISignal` projector | Accepted P1C tests pass; repeated calls make no writes | Remove projector/module/tests; Watch remains authoritative. |

Product API/query, consumer UI, persistence, paper/shadow evaluation, and
controlled activation are outside P1 and require future approvals.
