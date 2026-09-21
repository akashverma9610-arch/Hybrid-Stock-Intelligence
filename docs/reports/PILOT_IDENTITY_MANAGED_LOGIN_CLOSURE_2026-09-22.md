# PILOT_IDENTITY_AND_OWNERSHIP private closure receipt

Baseline: `0be803a535c8b326b7d71d776b8fd722977433f0`, branch `main`.
Decision: **CLOSED — managed identity and real-user isolation proven**, within
the private, owner-controlled distinct-subject canary scope documented below.
Scope: [identity boundary](../architecture/PILOT_IDENTITY_AND_OWNERSHIP.md) and
[local canary](../architecture/PILOT_IDENTITY_PRIVATE_CANARY.md) only.
This supplements, rather than rewrites, the historical
[implementation receipt](PILOT_IDENTITY_AND_OWNERSHIP_2026-09-21.md).

## Proof and limits

Real Auth0 Universal Login issued tokens to three distinct owner-controlled
subjects: OWNER, Tester A and Tester B. These are not three independent people.
The unchanged HSI backend verified signature, issuer, audience, permitted SPA,
scope and token times; role and ownership came from the HSI sidecar.
The local canary used synthetic empty financial fixtures, not production balances.

| Check | Result and evidence class |
|---|---|
| OWNER login | Backend identity 200 / OWNER; directly observed in local browser earlier in this continuation. |
| OWNER isolation | 4/4 checks: no automatic tester-portfolio access; cross-owner draft mutation 404; admin status 200. |
| Tester A | Backend identity 200 / TESTER; 5/5 isolation checks observed. |
| Tester B | Backend identity 200 / TESTER; 5/5 checks observed earlier and confirmed by owner in external browser. |
| Tester isolation | Own synthetic portfolio only, hostile owner/role hints do not select another portfolio, cross-owner draft cancellation 404, admin reads/mutations 403. |
| Live authorization revocation | Owner reported `TESTER_B_REVOKED / 200`, then the still-open B session returned `403 / PILOT_INVITATION_REQUIRED`, without refresh or new login. |
| Live restoration | Owner reported `TESTER_B_ENABLED / 200`, then the same B session returned `200 / B / TESTER`, error null. |
| Independent audit corroboration | Isolated sidecar contains OWNER_BOOTSTRAP, two TESTER_INVITED, four OWNERSHIP_BOUND, TESTER_REVOKED and TESTER_ENABLED entries. One additional idempotent enable request was audited. Both testers ended enabled. |
| Invalid issuer/audience/client/expiry and uninvited subject | Offline real-RSA verification and boundary tests; not independently issued live invalid provider tokens. |

Revocation above means **HSI authorization revocation**, not Auth0 token/session
revocation. Browser outcome reports after switching browsers are owner-attested;
the sidecar independently corroborates mutations, not every HTTP read. No token,
password, OTP, authorization code or private financial payload is in this receipt.

The embedded browser crashed during proof. Completing the same local flow in an
external browser avoided that UI failure. Intermittent `TOKEN_NOT_YET_VALID`
rejections were also observed; their underlying clock/provider cause is not
conclusively established. The verifier was not relaxed. A manual cached-token
recheck was added only to the canary, without refresh, leeway or automatic retries.
Valid sessions subsequently passed. Deployment clock synchronization and negative
token checks remain deployment-environment requirements.

## Verified provider configuration and frontend handoff

- Auth0 US development tenant; no paid upgrade or hosting provisioned.
- Issuer: `https://dev-shree1008.us.auth0.com/`.
- API audience: `urn:hsi:senseedge:pilot`.
- Public SPA client: `23z3dN1IKSKJpKi8hKjbjJFL8fVZHfjl` (not a secret).
- Authorization Code + S256 PKCE through the official pinned SPA SDK; API RS256.
- API maximum access-token lifetime 600 seconds; offline access/refresh disabled.
- API user access restricted per application to this SPA and `hsi:access`;
  M2M access denied. HSI, not provider role metadata, owns authorization.
- Database-connection self-signup disabled. Social login disabled for this SPA.
- Only exact temporary loopback callback/logout/origins used by this canary.
  Remove them before production deployment; this is not approval for HTTP online.

The later frontend bridge must use the verified issuer/audience/client with PKCE,
memory-only tokens, and `Authorization: Bearer` to HSI. Resolve the displayed user
and role through `/api/v1/pilot/me`; never send a client-supplied authority override.
401 requires reauthentication; 403 means no authorization, not a reason to fall
back to legacy/global endpoints. Keep private responses out of PWA/offline caches.
No client secret belongs in Apper or any other frontend. No production frontend,
public ingress, runtime identity configuration or hosting was activated here.

## Explicit legacy ownership reconciliation

The owner explicitly confirmed that the existing five-holdings legacy portfolio
belongs exclusively to their verified OWNER identity. Read-only inspection found
one portfolio and one PORTFOLIO snapshot, and verified matching portfolio identity,
five holdings, exact record ID and retained fingerprint before binding.

- Canonical database: `data/nse_stock_manager.db`, opened read-only.
- Separate Git-ignored authorization store: `data/pilot_identity.sqlite`.
- The existing operator CLI exclusively initialized the new sidecar, bootstrapped
  the verified OWNER subject, and applied one `CORE_SNAPSHOT` binding.
- Record: `portfolio-api-481f4e1375d2e63c4e9f443b`.
- Retained fingerprint: `481f4e1375d2e63c4e9f443b4f356604116efdaef6a8b1d7bccb2c0e347441a3`.
- Audit reasons: `EXPLICIT_OPERATOR_OWNER_BOOTSTRAP` and
  `EXPLICIT_OPERATOR_REVIEWED_LEGACY_BINDING`.
- Reopened binding matches the canonical record and fingerprint. No first-login
  adoption, ownership inheritance or portfolio payload rewrite occurred.
- This real-data sidecar has only the OWNER. Synthetic test users/bindings remain
  isolated in the canary sidecar and are not copied to production authorization.
- Related sell-side/setup/rotation reports and future records are **not** broadly
  adopted: exact independently reviewed ownership remains necessary. Unbound
  private records remain unavailable. Query completion belongs to the next slice.

Both authorization sidecars passed integrity_check and have zero FK violations.
The synthetic financial fixture database also passed both checks. Canary stdout
and stderr were checked after shutdown: only fixed safe labels, no token or
callback data. Production cash remains UNKNOWN; paper trades and trade plans 0.
Canonical file size/mtime remained unchanged during binding; no pilot tables were
created in canonical SQLite. The canary process was stopped after checking its
exact executable and command line; no other backend or port owner was stopped.

## Validation and defensive review

- Final affected suite: **92 passed / 0 failed / 0 skipped / 2 warnings** (14.97s).
  Includes 15 canary tests, 62 identity tests and affected portfolio/signal/API tests.
- Separate final harness run: **15 passed / 0 failed / 0 skipped / 2 warnings** (4.08s).
- Same-token revoke/deny/re-enable/allow is explicitly exercised in the final test.
- Earlier focused run: 77 passed / 0 failed / 0 skipped / 2 warnings.
- Initial attempted affected-test command named a nonexistent test file; no tests
  ran. Corrected selection and final run passed; no application fix was needed.
- Full backend retained baseline: **8,820 passed / 0 failed / 6 skipped / 2 warnings**.
  Not rerun: no backend application source changed; closure instructions explicitly
  permit retaining this baseline for configuration/isolated-canary-only work.
- Production frontend untouched; retained 53-test result is not a new execution.
- JavaScript syntax, Markdown local links, whitespace and secret-pattern checks
  passed. Staged diff contains only eight intended text source/test/documentation
  files; `git diff --check` and `git diff --cached --check` passed.
- Final canonical read-only full integrity_check: **ok**, FK violations **0**,
  completed in **412.61 seconds**. File size and mtime unchanged throughout.

The harness mounts the real backend without bypassing identity verification. Its
only financial fixtures are synthetic; its admin mutations affect only the canary
sidecar. Fixed-label diagnostic logging cannot echo exceptions or token values.
No application source, Brain, policy, provider, production UI, gate or order code
changed. SDK install scripts were disabled, dependencies pinned, and node_modules,
authorization DBs, canary receipts and logs remain ignored/uncommitted.

## Closure boundary

This receipt proves private managed login, distinct-subject isolation, backend
admin boundaries, revocation and reviewed legacy ownership. It does not prove
public hosting, independent-user onboarding, all product features, Auth0 provider
token revocation or production financial analysis. Local authorization state must
be securely migrated/backed up under the later deployment procedure; this run
does not install an always-on pilot runtime.

Core V1 **ACTIVE**; Execution Gate V2 **NOT_ACTIVE**. No public deployment, push,
broker authority, financial mutation, billing or later closure implementation.
Next exact audited slice: **PILOT_CANONICAL_QUERY_CLOSURE**; not started.
