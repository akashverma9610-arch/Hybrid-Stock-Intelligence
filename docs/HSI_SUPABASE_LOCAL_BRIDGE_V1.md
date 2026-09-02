# HSI Supabase Inbox → Local Bridge V1

The bridge is a local, bounded transport only:

`Supabase external_intelligence_inbox` → loopback HSI intake → canonical HSI chain.

HSI remains private. The bridge permits only the approved Supabase project, the
`claim_external_intelligence_inbox` RPC, the `external_intelligence_inbox`
table, and `http://127.0.0.1:8000/api/v1/intelligence/events`.

## Runtime configuration

Configure these only in the trusted local worker environment, never in browser
code or source control:

- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL=https://mfvxjkgdmrprfzylnhbe.supabase.co`
- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_SECRET_KEY` — server-side `sb_secret_…`
- `HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN` — the existing local HSI intake secret

Optional bounded controls:

- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_ENABLED=false` (default)
- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_BATCH_SIZE=10` (maximum 10)
- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_CLAIM_TTL_SECONDS=600`
- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_POLL_INTERVAL_SECONDS=60`
- `HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_MAX_ATTEMPTS=10`

The Supabase secret is sent only in the `apikey` header. It is never placed in
an Authorization header, URL, response, receipt, or log.

## Operation

Run one explicit bounded cycle:

```powershell
python -m app.runtime bridge-external-intelligence-inbox --once
```

Continuous foreground operation is disabled by default. Set the enabled flag
only in the trusted local worker environment, then run the same command without
`--once`; it polls no faster than every 60 seconds. There is no startup hook or
hidden daemon.

The claim RPC is the sole claim mechanism. A valid event is revalidated against
the existing V1C request model before local delivery. Accepted HSI receipts are
marked `DELIVERED`; transient failures use 1/2/4/8/15/30/60-minute bounded
backoff; malformed payloads and permanent HSI 4xx/conflicts are retained as
`DEAD_LETTER`.

If HSI accepted a payload but Supabase could not be updated, the row remains
claimable after its TTL and is resent unchanged. HSI's existing idempotency
then returns `ACCEPTED_EXISTING` and the bridge can mark it delivered.
