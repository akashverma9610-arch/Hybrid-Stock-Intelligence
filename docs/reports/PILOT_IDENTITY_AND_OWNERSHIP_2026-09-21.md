# PILOT_IDENTITY_AND_OWNERSHIP RESULT

Date: 2026-09-21. Branch: main.
Baseline: `cc639c2d700b1f18eb0873c118d9b042c7d32d2b`.

Decision: **SERVER_ISOLATION_IMPLEMENTED_AND_VALIDATED / LIVE_IDENTITY_SETUP_PENDING**.
This supersedes the earlier provider-choice blocker: the owner approved independent managed identity and engineering provider selection. It does not authorize public deployment or declare the whole pilot operational.

## Identity provider and server verification

Selected **Auth0**, using standard OAuth/OIDC public-client Authorization Code with PKCE and RS256 API access tokens. HSI verifies the configured HTTPS issuer, API audience, signature, expiration/issued-at/not-before, allowed SPA client and `hsi:access` scope. ID tokens, M2M credentials and arbitrary JWT role metadata cannot grant access. Key refresh is bounded; TLS verification remains enabled. Tokens are neither persisted nor logged.

HSI resolves the verified issuer/subject to its internal stable UUID and server-maintained role. Client-supplied user/owner IDs, role/admin flags and spoofed identity headers do not control authorization. Backend ownership remains independent of Apper and of frontend implementation.

[Architecture, evidence and operator instructions](../architecture/PILOT_IDENTITY_AND_OWNERSHIP.md) record the Auth0/Clerk comparison, primary-source references, free-tier caveats, exact token security profile, configuration keys and manual onboarding steps. No account, paid plan, public endpoint or provider credential was created.

## Role model and integration contract

- OWNER/ADMIN: explicitly allowlisted user invitation/revocation, authorization audit, identity-system status and existing strategy-version/active-strategy read views.
- TESTER: authorized shared research plus explicitly owned private records.
- No role has an implicit right to another user's financial state. No HTTP role-promotion endpoint exists; invitations always register TESTER.
- Protected configuration/policy mutations, acquisition and broker/order paths are not admitted by pilot ingress.
- Apper or another frontend sends a short-lived API bearer token, never a privileged shared key. The backend returns its own verified user ID/role through `/api/v1/pilot/me`.
- Provider account creation and the HSI allowlist invitation are separate: successful provider login alone never enrolls a user.

## Shared/private resource matrix

| Resource | Implemented boundary / truthful state |
|---|---|
| News, filings, fundamentals, common market/sector research | Authenticated shared reads from existing services; no tenant copy of canonical evidence/Brain. |
| Portfolio, holdings, cash, cost basis and sell-side snapshot reads | Exact owner-bound canonical record/fingerprint selection; no global-latest fallback or admin bypass. Existing serialization and PIT/as-of fields retained. |
| Paper trades, their performance, reports/benchmarks, legacy signals and capital rotation | Existing query adapters consume request-scoped owned snapshots. Lists/detail/pagination cannot fall back to another user's records. |
| Existing import-draft cancellation | Owner check precedes mutation; cross-user/unknown draft IDs rejected. |
| Import creation/confirmation, analysis-job execution, live portfolio valuation, broker-linked data | Denied for every pilot role until a separately audited owner-scoped service exists. No screenshot/CSV feature or broker integration implemented here. |
| Watch, stock trust-envelope/shared-Brain, P1 lifecycle and broad Agent surfaces | Denied at pilot ingress because current routes may expose global portfolio-derived context. This does not label canonical intelligence unavailable or duplicate it; later query closure must provide appropriate tenant-safe projections. |
| Watchlists, preferences, alerts, feedback, personal decisions and broker accounts | Typed ownership categories provided. Missing product APIs/workers remain unimplemented and denied; no generic payload store or second financial model created. |
| New/unknown endpoints and non-allowlisted methods | Denied by default. Client button hiding and CORS are not authorization. |

Blocking unsafe legacy routes closes an exposure path; it is **not** completion of those product features. The original global local-development facade remains local-only. Pilot/staging/production and unknown non-local environments always enforce the new boundary; missing configuration returns 503, not legacy access. Actual loopback development services were not restarted or exposed.

## Schema and legacy-data handling

A separate, explicit-initialization HSI authorization sidecar contains four versioned tables: schema marker, users, ownership bindings and append-only authorization audit. Canonical SQLite/schema was not changed. Ownership/audit rows have foreign keys; ownership reassignment and audit update/delete are rejected.

Existing single-user records remain **unassigned**. There is no first-login adoption, email matching, guessed owner or silent reassignment. The offline operator tool exclusively creates a new authorization DB for bootstrap, refusing existing files. Legacy binding requires exact snapshot ID, expected stored fingerprint, verified target subject and explicit ownership-review confirmation. Canonical SQLite is opened read-only; only the separate binding/audit is written. Repeated identical bindings are idempotent; conflicts fail closed.

No production authorization store, owner, tester or legacy binding was provisioned in this run. New private publisher records require explicit ownership before visibility; an unbound record is unavailable.

## Security review and corrections

1. Verified real RSA signatures in tests; only JWKS transport is replaced with synthetic keys. Tests do not use a mocked logged-in-user switch.
2. Both users can read their own stored portfolio. Neither can read the other's paper-trade detail or mutate the other's draft.
3. Spoofed user/owner headers, query parameters and JWT role/admin claims do not change the principal.
4. An Owner token does not grant access to either tester portfolio.
5. Store authorization rechecks the persisted admin role; constructing a forged principal object cannot invoke administrative writes.
6. Identity/ownership DB reopen, SQLite integrity, FK enforcement, immutable audit/bindings and explicit legacy reconciliation are tested.
7. Raw caller paths/request IDs are not logged in pilot mode; server request IDs and route templates replace them. Error bodies do not echo token or provider exception details.
8. Mounted Agent paths, private compound projections, unscoped financial mutations and unknown future routes cannot bypass the allowlist.
9. PostgreSQL configuration URLs are not interpreted as filesystem paths by the sidecar-separation check.
10. Frozen governance receipt hashes were preserved. The existing exact-successor source checker now permits only the explicitly authorized main.py auth wiring; every other byte remains pinned. Production connection tests now expect the earlier identity-unavailable rejection instead of the old downstream connection-management rejection.

## Validation

| Check | Result |
|---|---|
| New focused identity/ownership suite | **62 passed / 0 failed / 0 skipped / 2 warnings** |
| Relevant security/governance/source-pin regression | **1,123 passed / 0 failed / 0 skipped / 2 warnings** |
| Earlier affected API/query regression | **94 passed / 0 failed / 0 skipped / 2 warnings** before the final two added defensive tests |
| Initial full backend run | **8,814 passed / 4 failed / 6 skipped / 2 warnings**, 608.33 seconds; failures understood and corrected as below |
| Final full backend rerun | **8,820 passed / 0 failed / 6 skipped / 2 warnings**, 453.15 seconds; exit code 0 |
| Frontend retained contract/PWA tests | **53 passed / 0 failed / 0 skipped**; first sandbox attempt failed before test execution at Node Windows user-info lookup, same tests passed in approved host context |
| Production SQLite full integrity_check | **ok**, completed in 612.2 seconds using read-only connection |
| Production foreign_key_check | **0 violations** |
| Canonical DB size/modification metadata | Unchanged; 18,529,284,096 bytes, mtime_ns 1789316418469731900 |
| Fresh canonical counts | FinancialFacts 6,118; CorporateFilings 455; portfolios 1; snapshots 1; generic strategy_versions 0; generic diagnostic_results 0; paper_trades 0; trade_plans 0 |
| Pilot tables in canonical DB | **None** |
| Live Auth0/Apper two-user E2E | **NOT RUN / NOT CONFIGURED**; not represented by synthetic signature tests |
| Public deployment / push | **Not performed** |
| Edited Markdown local links and whitespace | **Passed** |
| `git diff --check` | **Passed** |

Initial full-suite failures:
- `test_canonical_discovery_union_to_brain_handoff_contract.py::test_frozen_source_matches_baseline_and_worktree` (main.py parameter).
- `test_fundamental_v2_downstream.py::test_active_registry_weights_and_forbidden_boundaries_unchanged`.
- `test_hsi_brain_funnel_runtime_reconciliation_audit.py::test_source_pin_matches_current_and_accepted_baseline` (main.py parameter).
- `test_connection_api.py::test_connection_mutation_routes_are_disabled_outside_local_private_boundary`.

The first three were missing exact successor allowances for this authorized security composition; the fourth expected the older 403 rather than the new fail-closed 503 before connection management. No frozen artifact fingerprint or investment rule was edited. Targeted corrections passed the relevant suite and the completed final full run is green.

## Files in this slice

- [API composition](../../app/api/main.py)
- [Token verification and identity types](../../app/api/pilot_identity.py)
- [Pilot authorization/query boundary](../../app/api/pilot_boundary.py)
- [Authorization sidecar](../../app/storage/pilot_identity_store.py)
- [Explicit operator bootstrap/binding tool](../../scripts/dev/pilot-identity-admin.py)
- [Dependencies](../../pyproject.toml)
- [Security/isolation tests](../../tests/unit/test_pilot_identity_and_ownership.py)
- [Exact successor compatibility helper](../../tests/unit/test_catalyst_event_operational_closure.py)
- [Production connection rejection test](../../tests/unit/test_connection_api.py)
- [Architecture/operator document](../architecture/PILOT_IDENTITY_AND_OWNERSHIP.md)
- This closure report.

## Remaining blockers and next exact slice

- Auth0 tenant/application/API, exact callback/origin settings and invited human accounts have not been provisioned.
- Real provider-signed login/revocation and owner/two-tester canary must still be demonstrated privately.
- Production sidecar initialization and explicit reviewed legacy owner bindings remain unapplied.
- Pilot exposure, Apper integration and currently unscoped product surfaces remain blocked; no claim of overall pilot completion is made.

Immediate continuation remains **PILOT_IDENTITY_AND_OWNERSHIP — private managed-login and reviewed legacy-binding canary**. Do not start a later slice in this run. The already-audited next roadmap slice after DC02 acceptance is `PILOT_CANONICAL_QUERY_CLOSURE`; it has not been started.

Core V1: **ACTIVE**. Execution Gate V2: **NOT_ACTIVE**. No Brain/policy/strategy changes, portfolio mutation, provider acquisition, broker/order action, billing or public deployment.
