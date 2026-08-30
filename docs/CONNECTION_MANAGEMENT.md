# Connection management (local/private V1)

`app.connections` provides a provider-neutral settings boundary for future UI
flows: **Settings → Connections → Kotak Neo → Save → Test Connection**. It is
configuration infrastructure only: it does not run analysis, scan markets,
create signals, change score/gate/strategy records, access an account, or place
or modify an order.

## Data split and credential source order

`ConnectionProfile` and its SQLite metadata/audit rows are secret-free: they
hold status, capability, timestamps, safe error code, and configured flags only.
`KeyringCredentialStore` writes actual values to the operating-system credential
manager; it is never a normal database, JSON read model, audit event,
provenance item, log, or API response. Tests use an explicit in-memory
substitute only. The resolver takes exactly one source: explicit test injection,
configured OS keyring values, or a developer environment fallback. It never
mixes a partial keyring record with environment values.

On Windows, the maintained `keyring` package uses Windows Credential Manager
(`WinVaultKeyring`) first. If that backend is unavailable or returns a known
Windows credential-runtime error (including `CredWrite` 1312), the local app
selects `WindowsDPAPICredentialStore`. It uses `pywin32`'s `win32crypt` with
current-user DPAPI protection and atomically writes encrypted blobs only under
`%LOCALAPPDATA%\NSEStockManager\credentials\`. Files contain just a schema
version, provider/connection metadata, and a DPAPI-protected blob; they never
contain plaintext credentials or session material. Best-effort restrictive file
permissions are applied on write. The selected backend is deterministic through
a non-secret local selector record: no existing keyring credential is copied,
deleted, or automatically migrated. A non-keyring programming error never
triggers fallback. If both secure backends are unavailable, the API fails closed
as `CREDENTIAL_STORE_UNAVAILABLE`; it never falls back to plaintext, SQLite, or
custom encryption. Safe profile metadata may report
`WINDOWS_CREDENTIAL_MANAGER` or `WINDOWS_DPAPI`, but never paths, blobs, or
values.

## Kotak Neo fields and modes

`tradeapi_access_token` is the only field required for `QUOTE_ONLY`. `SESSION_READ` also
requires `mobile_number`, `ucc`, and `mpin`; a **current six-digit authenticator
TOTP** is submitted transiently for that test and is not a stored credential.
TradeAPI Access Token and MPIN are `SECRET`; mobile number and UCC are sensitive identifiers.
The API exposes definitions and configured flags, never values. Partial saves
preserve omitted fields, placeholders such as `********` are rejected, and
clearing requires an explicit DELETE call.

The product does not retain a TOTP seed. The current authenticator code,
session token, session ID, and dynamic base URL are neither persisted nor
exposed. A saved profile is `CONFIGURED`, not `CONNECTED`; quote-only and
optional session capability results are independently validated.

## Local API boundary

`GET /api/v1/connections` and `GET /api/v1/connections/kotak-neo` return
secret-free profiles and field metadata. Local-only configuration writes are
`PUT /api/v1/connections/kotak-neo`, `POST
/api/v1/connections/kotak-neo/test`, `POST
/api/v1/connections/kotak-neo/session/test`, and `DELETE
/api/v1/connections/kotak-neo/credentials`. Test performs only the smallest
available market-data quote/session read; it never requests funds, holdings,
positions, orders, trades, or a WebSocket connection. These unauthenticated V1
routes are not publicly deployable before authentication/authorization exists.

Safe audit event types are `KOTAK_CONNECTION_CONFIGURED`,
`KOTAK_CONNECTION_TESTED`, `KOTAK_CONNECTION_TEST_FAILED`, and
`KOTAK_CONNECTION_CREDENTIALS_CLEARED`, plus the transient
`KOTAK_SESSION_TESTED` / `KOTAK_SESSION_TEST_FAILED` outcome events; they
retain no secret values.

## Connect Kotak Neo without PowerShell

1. Start the backend locally, bound to `127.0.0.1` (for example, `python -m
   uvicorn app.api.main:app --reload --host 127.0.0.1`).
2. Open `http://127.0.0.1:8000/setup/kotak-neo` for the simple password-field
   setup page. Swagger at `http://127.0.0.1:8000/docs` remains the equivalent
   local-only fallback.
3. Enter the TradeAPI Access Token under **Market Data** and select **Test
   Market Data**. This performs only token-only scrip-master resolution, one
   quote, and canonical normalization.
4. For the optional authenticated-session diagnostic, enter mobile number,
   UCC/client code, MPIN, and the current six-digit authenticator code. The
   code is cleared immediately and never stored.
5. Confirm the independent quote, instrument, normalization, TOTP, and MPIN
   statuses. A provider-reported IP restriction is shown as `IP_NOT_ALLOWED`;
   the application never guesses or configures localhost as an allowlisted IP.
6. Use **Clear Kotak Credentials** to remove the four saved values from the OS
   credential store.

The product Settings flow never requires a user to configure an instrument
token or the developer-only `KOTAK_NEO_TEST_*` variables. After authentication
it loads the documented Neo scrip-master path, intersects its NSE cash records
with the stored NSE universe, and selects the lexically first unambiguous
equity symbol. It makes one quote request. The `KOTAK_NEO_TEST_*` variables
remain isolated to the explicit developer smoke harness only.
