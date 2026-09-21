# Private managed-identity canary

Scope: continuation of [PILOT_IDENTITY_AND_OWNERSHIP](PILOT_IDENTITY_AND_OWNERSHIP.md).
Status: **private managed-login/isolation canary proven**; not public deployment.
The [closure receipt](../reports/PILOT_IDENTITY_MANAGED_LOGIN_CLOSURE_2026-09-22.md)
distinguishes direct observations, owner-reported browser outcomes, offline tests,
and reviewed legacy ownership binding.
Core V1 ACTIVE; Execution Gate V2 NOT_ACTIVE. No deployment or next closure slice.

## What this proves, and what it does not

The [operator harness](../../scripts/dev/pilot_identity_canary.py) mounts the
unchanged HSI FastAPI application and its real `ManagedTokenVerifier`. Live use
retrieves signing keys from the configured Auth0 HTTPS issuer; no test JWKS,
identity substitution, or authentication override exists in the harness.
Owner, Tester A and Tester B are explicitly supplied Auth0 database subjects,
not identities derived from email, client roles, or first login.

The operator may control all three test identities, including a Gmail plus
alias. This proves distinct authenticated-subject isolation, not three separate
people, deliverability to independent testers, or production onboarding.

All financial fixtures are **synthetic empty portfolios** with unknown cash,
and synthetic import-draft identifiers. They live in a newly created ignored
`.tmp/pilot-identity-canary-*` directory, separate from the authorization SQLite
sidecar in that directory. The production canonical database is never opened.
No historical production portfolio is adopted or rewritten. Fixture timestamps
are labelled synthetic and are not canonical historical market evidence.

The actual `/api/v1/portfolio`, identity, admin, and draft-cancellation routes
are used. A tester's hostile owner/role query cannot select another tester's
portfolio; cross-owner draft cancellation is denied before mutation. Owner is
not implicitly an owner of either test portfolio. Explicit owner revocation
and re-enable affect only this canary sidecar. No provider/market-data call,
trading job, order, public route, or production feature activation is added.

## Local setup and controls

Install the exact official Auth0 SDK dependency using `npm ci --ignore-scripts`
inside `scripts/dev/pilot_identity_canary`. Package-lock integrity pins its
dependencies. The SDK is served locally, not loaded from a floating CDN URL.
This package is independent of the production frontend.

Register these exact **temporary development-canary** SPA settings:

| Setting | Value |
|---|---|
| Allowed Callback URLs | `http://127.0.0.1:8766/callback` |
| Allowed Logout URLs | `http://127.0.0.1:8766` |
| Allowed Web Origins | `http://127.0.0.1:8766` |
| Allowed Origins (CORS) | `http://127.0.0.1:8766` |

No wildcard or Internet HTTP origin is authorized. Remove these local entries
before production deployment; public pilot callbacks require the separately
approved HTTPS ingress. Host and Origin checks reject DNS rebinding and
cross-origin API requests. Binding is fixed to `127.0.0.1:8766`; forwarded headers
are not trusted. The canary shuts down after at most two hours or Ctrl+C.

Use the existing HSI Python environment from the repository root:

```powershell
python scripts/dev/pilot_identity_canary.py --issuer <verified-https-issuer> --audience <verified-api-audience> --client-id <verified-spa-id> --owner-subject <verified-owner-subject> --tester-a-subject <verified-a-subject> --tester-b-subject <verified-b-subject>
```

Arguments are non-secret provider identifiers, never passwords or tokens. The
operator must verify the intended three subjects before starting: initialization
is an explicit isolated-canary authorization, not automatic enrollment. Each
launch creates fresh synthetic state and leaves prior audit sidecars intact.

Auth0's maintained SPA SDK performs authorization-code + S256 PKCE, OAuth state,
and ID-token nonce validation. No handwritten OAuth cryptography. Tokens remain
in SDK memory; refresh tokens are disabled. Temporary SDK redirect transaction
state is not an access-token cache. There is no token logging or response dump.
The callback URL is cleared before processing; server access/error logs are
disabled so authorization codes cannot enter logs. Browser checks emit only
fixed test labels, HTTP statuses and pass/fail, not raw private API payloads.
After callback, an explicit **Recheck current login** button can resubmit the
same SDK-memory-cached token to the unchanged verifier. This does not refresh
tokens, change any timestamp check, or introduce an automatic retry loop. A
future-token rejection is not automatically treated as clock drift; diagnose
the host/provider timing and retain the rejection until validation succeeds.
All responses are no-store, no-referrer and unframeable; no service worker or
PWA cache is involved. Tokens with a lifetime over 600 seconds remain rejected
by the unchanged backend verifier, regardless of SDK behavior.

## Human canary sequence

1. Sign in as Owner through Universal Login. Enter credentials only on Auth0.
   Verify backend-derived OWNER, admin status allowed, no tester portfolio access.
2. Sign out, sign in as Tester A, and run the read-only isolation checks.
3. Sign out, sign in as Tester B, and run the same checks. Both must retrieve
   only their own synthetic portfolio and be denied cross-user mutations/admin.
4. Keep Tester B signed in in a separate browser tab. Sign in as Owner in
   another tab and explicitly disable B using the owner-only button. B's
   already-issued valid token must then be rejected by HSI. Re-enable only by
   an explicit owner action. Provider-token revocation is not claimed.
5. Record only non-secret outcomes. Wrong issuer/client/audience, malformed and
   expired credentials are also covered by offline real-RSA verifier tests;
   these must not be mislabeled as independently issued live invalid tokens.
6. Stop the harness. Real production owner binding, canonical DB integrity and
   the complete closure report remain separate completion requirements inside
   the same identity slice. Do not declare closure from harness tests alone.

## Primary references

- [Auth0 SPA SDK](https://auth0.com/docs/libraries/auth0-single-page-app-sdk)
- [Auth0 PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce/add-login-using-the-authorization-code-flow-with-pkce)
- [Localhost callback risks](https://support.auth0.com/center/s/article/Security-Risks-of-Using-Localhost-for-Callback-URL)
- [Gmail aliases](https://support.google.com/mail/answer/22370)
