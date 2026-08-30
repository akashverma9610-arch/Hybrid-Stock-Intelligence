# Production-v1 Data Operations Runbook

## First deployment

1. Configure the existing credential/source integrations; never put tokens in
   staging files or `.env.example`.
2. Initialize the persistent database and import the approved canonical
   universe/reference evidence.
3. Create `data/incoming/<family>`, `data/archive/<family>`, and
   `data/quarantine/<family>` by running the relevant U17 job once.
4. Run an explicit backfill only for registered approved family adapters.
5. Inspect `python -m app.runtime data-operations-status` and resolve all
   typed failures/gaps before enabling a worker.
6. Set `DATA_OPERATIONS_ENABLED=true` only in the operator process that owns
   the intended local scheduler; FastAPI remains passive.
7. Verify `GET /api/v1/data-operations/health`, then open Deep Analysis and
   confirm evidence freshness/blockers are factual.

## Daily delivery failure

1. Read `data-operations-status` and identify the family/run receipt.
2. Inspect the safe error/finding and the corresponding archive/quarantine
   directory.
3. Correct the source/configuration issue. Do not delete canonical evidence or
   the database.
4. Put a corrected official source file in `data/incoming/delivery/`.
5. Run `python -m app.runtime data-operations-run --family delivery --mode incremental`.
6. Confirm archive/quarantine disposition, counts, watermark, and operational
   health. Reconciliation findings must be handled, not discarded.

## Recovery principles

- Re-run safely: identical evidence is idempotent.
- Do not delete old evidence to make a refresh succeed.
- A source outage preserves last-known-good evidence but does not make it
  fresh.
- Escalate unresolved conflicts or invalid official data; do not silently
  choose a convenient historical value.
