# BSE Official Financial Evidence Collector V1

The collector is a deliberately bounded acquisition path for only these canonical holdings:

- `NSE:INE372A01015` / APARINDS
- `NSE:INE0FHS01024` / DEEPINDS
- `NSE:INE955D01029` / GENUSPOWER
- `NSE:INE068V01023` / GLAND
- `NSE:INE090A01021` / ICICIBANK

Run one bounded collection locally with:

```powershell
python -m app.runtime collect-real-portfolio-bse-financials
```

There are no command arguments for a security, URL, token, or document. The collector resolves each canonical ISIN through BSE's allowlisted public exact-security lookup, requiring one result whose returned ISIN equals the requested ISIN and whose BSE code, security ID, and issuer name occur in the same BSE result item. It then discovers XBRL only through BSE's structured per-security Financial Results archive (`Result_Arch_Download`) and accepts only an official BSE XBRL URL. The historical `/downloads1/SCRIP.ZIP` route is not used: BSE currently returns HTTP 404 from that guessed path. A missing, ambiguous, mismatched, malformed, oversized, or unsupported-content-type response fails that target closed.

Downloaded XBRL is stored as a hash-addressed XML file plus JSON receipt beneath `data/official_sources/bse_financial_results/collector`. The receipt records the canonical ID, ISIN, BSE code, source URL, SHA-256, byte length, filing publication time, and HSI receipt time. Existing identical content is reused. A different hash for the same official XBRL document is retained as a new immutable staged version; canonical fact conflicts remain visible through the existing financial-fact conflict behavior and are never overwritten.

The collector delegates parsing, canonical filing writes, fact normalization, revision links, and fact conflict handling to `BSEOfficialLocalXbrlIngestionService`. It does not create a second facts store or a second Shared Brain financial artifact. BSE publication time remains the source `published_at`; the time HSI acquired the evidence is recorded separately as `received_at`, so a later acquisition cannot appear in a historical as-of view before HSI received it.

The optional background worker is disabled by default. Enable it explicitly only for a local process with:

```powershell
$env:BSE_OFFICIAL_FINANCIAL_COLLECTOR_ENABLED = 'true'
$env:BSE_OFFICIAL_FINANCIAL_COLLECTOR_INTERVAL_SECONDS = '3600'
```

The collector is read-only against public BSE endpoints. It accepts no credentials, performs no broker activity, and cannot place orders. After a collection produces canonical facts, the existing stored-evidence Shared Brain and sell-side flows may be refreshed separately; no downstream result is fabricated when source evidence is absent.
