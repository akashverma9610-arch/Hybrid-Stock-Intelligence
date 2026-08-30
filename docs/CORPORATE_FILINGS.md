# Corporate filings and announcements

`app.filings` stores immutable primary-source corporate disclosures as facts.
The source priority for a future interpretation layer is NSE, then BSE, then an
explicitly configured issuer-primary source. Records from NSE and BSE are never
blindly collapsed: cross-exchange equivalents remain distinct evidence records.

## Boundaries

The NSE and BSE adapters normalize records supplied by a documented/exported or
otherwise approved future integration. They make no HTTP request, scraping,
browser automation, anti-bot workaround, session bypass, or undocumented API
assumption. Both source boundaries are implemented but remain
`CONFIGURED_NOT_VALIDATED` until external contract validation is separately
approved.

The controlled taxonomy covers announcements, results, board meetings,
presentations/investor meets, actions, ownership, fund raising, acquisitions,
orders, management/regulatory matters, dividend, bonus, split, rights, buyback,
and `OTHER`. Raw exchange categories remain alongside the conservative taxonomy.
Ingestion makes no sentiment, catalyst, financial-quality, Decision Score, gate,
crisis, or euphoria judgment.

## Identity, revisions, and point in time

Source/exchange filing identifiers are preferred. Without one, an immutable hash
uses source, exchange, instrument, subject, announcement time, and document
reference. Re-fetching an identical filing is idempotent; conflicting reuse of
an ID is rejected. A revision names its original filing and is stored alongside
it rather than overwriting history.

As-of queries require both `announced_at` and `received_at` to be on or before
the requested time. A later received filing or amendment cannot appear in an
earlier replay. Exact announcement, effective, period-end, record/ex dates, and
reporting-as-of dates are retained for future catalyst, crisis, and euphoria
consumers.

## Documents and future extraction

Attachment metadata includes type, title/filename, source reference, MIME type,
publication time, optional checksum, parse status, and XBRL marker. This task
does not download attachments or proxy arbitrary URLs. PDF/XBRL/HTML/CSV
retrieval and parsing remain future internal work. Financial-result metadata
preserves period, scope, result type, and revised state; no statement extraction
or financial scoring happens here. Shareholding records preserve filing metadata
only.

`GET /api/v1/filings` and `GET /api/v1/filings/{filing_id}` are read-only,
bounded views of injected stored filings. They do not ingest, fetch documents,
or mutate credentials/accounts/portfolios.
## Financial-fact linkage

Structured result values are normalized separately by `app.fundamentals`; this filings layer does not parse PDF/XBRL content. Every reported canonical fact must reference an immutable `FINANCIAL_RESULTS` filing and match its announced and received timestamps. Revisions remain separate filings/facts; they never overwrite the original reported history.

When the existing stock-analysis pipeline is supplied the canonical adapter, filing context is passed through as factual IDs for latest results, revisions, investor presentations, board meetings, actions, and shareholding records. It assigns no sentiment or catalyst strength.

Official NSE local-export ingestion may populate these records with `source=NSE`, `PRIMARY_EXCHANGE`, an official-export warning, source filename checksum in its immutable import run, broadcast time, and local receipt time. It never represents an application download from NSE.
