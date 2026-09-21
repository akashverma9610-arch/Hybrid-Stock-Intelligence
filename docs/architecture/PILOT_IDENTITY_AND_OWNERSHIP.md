# Pilot identity and ownership boundary

Scope: `PILOT_IDENTITY_AND_OWNERSHIP`. Implementation is additive to frozen Core V1; public deployment and live managed-login verification are **NOT completed** by component tests. Core V1 ACTIVE; Execution Gate V2 NOT_ACTIVE. No broker/order authority.

## Engineering selection

Use **Auth0 Universal Login**, OAuth 2.0 Authorization Code with PKCE for the public SPA/PWA, and RS256 access tokens issued for a dedicated HSI API audience. Do not send ID tokens or Management API tokens to HSI. Apper is a client, never the authorization authority. Another SPA can use the same backend contract after its client ID/origin is explicitly allowed.

Auth0 was selected over Apper-native authentication because HSI needs independently verified human identity. Clerk is also a viable managed service with invite-only mode; Auth0's conventional API audience and public-client PKCE flow keep this Python resource server independent of frontend SDK/session semantics. Self-hosting an identity platform would add unnecessary pilot operations. No provider account was created or paid plan purchased.

Primary references inspected 2026-09-21:

- [Auth0 access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens): resource-server signature, claims, audience and permission checks.
- [Auth0 SPA PKCE SDK](https://auth0.com/docs/libraries/auth0-single-page-app-sdk): public clients do not require a client secret.
- [Auth0 disable signups](https://support.auth0.com/center/s/article/Disable-Signups-at-Connection-Level): database-connection self-registration can be disabled.
- [Auth0 pricing](https://auth0.com/pricing): a free tier is advertised; verify tenant feature/usage limits before provisioning. This design requires no paid organization RBAC, custom domain or billing integration. No promise about future vendor prices or production service-level guarantees is made.
- [Clerk restricted access](https://clerk.com/docs/guides/secure/restricting-access): reviewed alternative, not selected.
- [PyJWT validation API](https://pyjwt.readthedocs.io/en/stable/api.html): vetted signature implementation, not handwritten cryptography.

## Authentication and authorization

The [verifier](../../app/api/pilot_identity.py) pins an HTTPS issuer, API audience and allowed SPA `azp` client IDs. Only RS256 is accepted. It verifies signature, issuer, audience, subject, issued-at, expiration and any not-before claim; requires `hsi:access`; rejects M2M subjects/grants. Tokens have a maximum **600-second** lifetime in this pilot security profile. Set the provider's API/browser-flow access-token lifetime accordingly. This is an authentication-security bound, not an investment/PIT policy.

JWKS comes only from the configured issuer, never token-supplied URLs. TLS verification remains on. Key lookup uses a five-second timeout, five-minute cache and at most one attempted missing-key refresh per thirty seconds per process. Unknown, ambiguous, malformed or unverifiable keys fail closed. An already-issued token can remain valid until expiry; disabling the HSI tester record denies subsequent requests immediately. There is no live provider introspection claim. Infrastructure request-rate limiting remains a later ingress prerequisite.

After verification, the backend resolves `(issuer, subject)` in the HSI authorization store. The deterministic internal UUID identifies that binding. Email, client `user_id`, `owner_id`, role/admin fields, headers and JWT role metadata do not grant rights. Unknown subjects are denied even if successfully authenticated by Auth0. No automatic first-user owner, sign-up, email linking, or automatic provider migration exists.

Roles are OWNER, ADMIN and TESTER. The initial operator bootstrap creates one OWNER. The HTTP invitation operation creates TESTER only; no role-edit or privilege-escalation endpoint exists. ADMIN is recognized for explicitly authorized administration, not assignable by a tester or through JWT claims. OWNER/ADMIN is **not** a blanket permission to read tester private state.

## Runtime boundary

`app.api.main:create_app` installs the [pilot boundary](../../app/api/pilot_boundary.py) for `APP_ENV=pilot`, staging, production and unknown/non-local environment labels, or explicit `HSI_PILOT_AUTH_ENABLED=1`. It cannot be disabled by setting that flag to `0` in a non-local environment. Only development/local/test retain the existing local single-user mode. **Never expose that local profile to the Internet.** Existing loopback development services were not restarted or relabelled pilot during implementation.

Missing/malformed config or an absent/uninitialized identity database yields `503 PILOT_IDENTITY_UNAVAILABLE` for non-health requests. Minimal `/health` does not expose stored health/private payloads and distinguishes CONFIGURED from UNAVAILABLE; CONFIGURED is not proof of an Auth0 login. Anonymous/invalid credentials return 401; uninvited or route-forbidden users 403; inaccessible resource identifiers 404 where scoped detail is implemented. An unassigned portfolio remains unavailable, never another user's global latest snapshot.

Authorization uses an exact route/method allowlist. Unknown/future routes deny by default for every role. Mounted Agent tools cannot bypass it. CORS is explicit-origin only, permits the Authorization header/PATCH and remains separate from authorization. Responses are `no-store`; admitted responses vary by Authorization and Origin. No bearer token is accepted through query parameters or stored in authorization/audit tables.

## Resource and API matrix

| Resources/surface | Pilot behavior |
|---|---|
| News, filings, fundamentals, market regime/breadth/extremes/crisis, sectors | Authenticated shared canonical reads via existing services; no per-user evidence copy. |
| Portfolio, holdings, summary, sell-side; paper-trade list/detail/performance; performance/benchmark reports; legacy signals; capital rotation | Reuse existing query/serialization functions with a request-scoped, ownership-filtered canonical snapshot reader. Only exact bound IDs/fingerprints are eligible; paginate after isolation. No global-service fallback. |
| Portfolio-import draft cancellation | Existing operation permitted only for the authenticated draft owner. Cross-owner/unknown ID rejected before service invocation. No screenshot/CSV ingestion or confirmation capability added. |
| Unscoped import creation/confirmation, portfolio analysis jobs, live portfolio valuation, broker-linked state | Denied for all pilot roles pending separately proven user-scoped services. Existing local behavior is not silently activated for testers. |
| Stock decision-trust/shared-Brain projections, legacy Watch, P1 lifecycle and broad Agent routes | Conservatively denied on pilot ingress: existing surfaces can carry global holdings/portfolio-universe context. Shared data inside them is not itself private, but the full legacy response is not an audited tenant-safe consumer DTO. |
| Watchlists, preferences, alerts, feedback and personalized decisions | Typed ownership categories exist; no absent feature API, delivery worker or parallel financial store is invented. Unimplemented/unreviewed routes remain denied. |
| `/api/v1/pilot/me` | Verified internal user ID and server role only. |
| POST `/api/v1/pilot/admin/users` | OWNER/ADMIN authorizes an existing Auth0 human subject as TESTER; issuer and role are server-controlled. Does not create a provider account or send an email. |
| PATCH `/api/v1/pilot/admin/users/{user_id}` | OWNER/ADMIN enables/revokes TESTER access; no role change or owner takeover. |
| GET `/api/v1/pilot/admin/audit`, `/admin/status` | Explicit administrative authorization audit and minimal identity-system status, not a private financial dump. |
| Existing governance active-strategy/strategy-version GETs | Administrative read-only status; no activation permission. |
| Protected config/policy mutation, acquisition/ingest endpoints, other admin/health surfaces | Not exposed by this pilot allowlist, even to OWNER. Machine ingest must retain its separately controlled internal transport; never embed its credential in a frontend. |

Blocking an unscoped surface is a security closure, **not** a claim that its product functionality is operational. Do not mark the complete pilot ready solely because this boundary or its tests pass.

## Storage, ownership, and legacy migration

[PilotIdentityStore](../../app/storage/pilot_identity_store.py) is a separate HSI-controlled SQLite authorization sidecar, not a second Brain or portfolio ledger. Version 1 contains `pilot_identity_schema`, `pilot_users`, `pilot_ownership` and append-only `pilot_auth_audit`. Canonical SQLite/schema remains unchanged. Foreign keys bind ownership/audit actors to internal users; ownership changes and audit updates/deletions are rejected. The sidecar contains identity metadata, roles and immutable resource references, not passwords, access tokens, portfolio values or provider credentials. Secure it with service-account filesystem permissions and backups when provisioning.

Initialization is explicit, exclusive-create and refuses any existing file. Runtime does not create the sidecar. Ownership is `(resource kind, resource ID, canonical fingerprint, owner user ID)`; it cannot be silently reassigned. The request reader compares retained snapshot fingerprints before returning existing payloads, preserving their original PIT/as-of fields. This authorization check does not replace canonical source-integrity validation.

Legacy data is **unassigned by default**. The operator must verify the exact owner and records, then apply explicit bindings with an audit receipt; login never adopts historical data. Related private reports/sell-side/rotation snapshots each require their own reviewed bindings. New publisher integration must bind new private records explicitly before they are visible; no blanket inheritance from a shared global collection is authorized. Portfolio quantity/cash/cost calculations remain Core-owned and unchanged.

## Operator setup — not performed by this slice

1. Create an Auth0 tenant and SPA application through the owner's account. No secrets are to be pasted into ChatGPT or Apper source.
2. Use a database connection with public self-signup disabled; disable unused social/enterprise connections that could bypass the intended onboarding process. Create invited human accounts through the provider's administrative flow. Validate that an uninvited identity cannot reach HSI even if provider login succeeds.
3. Register the dedicated HSI API audience, RS256 and `hsi:access`; configure access-token lifetime at most 600 seconds. Use exact callback/logout/web origins and PKCE; no wildcard redirect, embedded client secret, implicit grant or browser-persisted privileged key. Keep tokens in SDK memory and exclude API/private content from PWA caches.
4. Configure server `HSI_IDENTITY_ISSUER` (HTTPS, trailing slash), `HSI_IDENTITY_AUDIENCE`, comma-separated `HSI_IDENTITY_CLIENT_IDS`, and absolute `HSI_IDENTITY_STORE`. Set `APP_ENV=pilot`. Keep canonical database/provider/runtime configuration separate and unchanged.
5. Bootstrap the exact verified owner subject offline with the existing backend Python environment. The commands below are templates, not executed operations; issuer/subject are provider identifiers, never tokens:

```powershell
python scripts/dev/pilot-identity-admin.py --store <separate-identity-db> --issuer https://<tenant>/ --owner-subject <verified-owner-subject> bootstrap-owner
```

6. After owner login, use the authenticated admin invitation API to authorize TESTER subjects. Requests accept only `subject` and `reason`; role/issuer overrides are rejected. Revocation accepts only `enabled` and `reason`. These HSI invitations do not provision Auth0 accounts.
7. Reconcile any approved legacy snapshot one by one, checking its private lineage and intended user. No wildcard/bulk adoption:

```powershell
python scripts/dev/pilot-identity-admin.py --store <separate-identity-db> --issuer https://<tenant>/ --owner-subject <verified-owner-subject> bind-snapshot --canonical-db <canonical-db> --snapshot-id <exact-id> --expected-fingerprint <exact-stored-fingerprint> --target-subject <verified-owner-or-tester-subject> --confirm-reviewed-ownership
```

The tool reads canonical SQLite in `mode=ro`, validates the exact stored fingerprint, and writes only the separate authorization binding/audit. It refuses ownership conflicts. No production binding was performed in this slice.

8. Before any public connection: real owner/two-tester login, bad issuer/audience/expiry tests, revocation, isolation, origin checks, TLS/ingress allowlist and deployment-mode checks must pass on private staging. This is a remaining operational canary, not a permission to deploy now.

## Validation and remaining work

Tests use temporary SQLite plus locally generated RSA keys and the real JWT verification path; only JWKS transport is fixture-fed. They prove server-side A/B reads, IDOR rejection, owned draft mutation, tester denial, explicit admin rights, no client role authority, paper/report isolation, immutable binding/audit, missing-config failure, no global legacy fallback, and token redaction. They do not prove vendor account configuration, live login, email delivery, Apper integration or hosting.

See the local [closure report](../reports/PILOT_IDENTITY_AND_OWNERSHIP_2026-09-21.md) for this run's exact validation outcomes. No later slice is started. Next continuation remains **`PILOT_IDENTITY_AND_OWNERSHIP`: private managed-login/owner-binding canary**, followed by closure review before a different pilot slice can begin.
