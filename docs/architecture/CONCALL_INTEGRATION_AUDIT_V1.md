# Concall integration — repository audit and implementation map (2026-10-23)

## Verified repository findings
- `app/filings` and `docs/CORPORATE_FILINGS.md` store immutable exchange filing metadata, revision lineage, and point-in-time visibility. NSE/BSE adapters currently normalize supplied records, without direct HTTP collection or PDF parsing. Do not change this source boundary.
- `app/fundamentals` and `docs/FUNDAMENTAL_DATA.md` preserve reported metric identity, period, scope, publication/receipt timestamps, revision history and official local export lineage. `app/fundamentals/financial_metric_observation_schema.py` is an approved passive schema, not an active materializer.
- `app/evidence_coverage.py` models evidence completeness separately from confidence and actionability. Extend only with compatibility review; do not globally require concalls for all stock analyses.
- `docs/SCORING_POLICY.md` defines a 10-component score, with no silent missing-weight renormalization. No additional concall component; claims are research evidence, not points.
- `docs/ARCHITECTURE.md` defines read-only FastAPI projections and immutable stored-data boundaries. Never make HTTP reads trigger parsing, scans or model inference.

## Safe implementation seams
1. Add a bounded `app/concall` package for passive source models, transcript segment and claim schemas, versioned fingerprints and point-in-time guards; no network side effects at import.
2. Implement an opt-in, explicit offline/local-file import first. Only later add approved document fetching behind a source policy, never bypass NSE/BSE restrictions.
3. Map filing/document identity to `app/filings` immutable records. Concall is a distinct document subtype, not a replacement for a financial-result filing.
4. Build a separate reconciliation service: management guidance claims versus selected, verified financial actuals. Require metric, fiscal period, scope, currency, units, basis and visibility alignment; reject ambiguous matches.
5. Persist raw source lineage, claims, evidence spans, reconciliation versions and as-of snapshots. Maintain `UNAVAILABLE`, `UNVERIFIED`, `CONFLICTED` and `VERIFIED` states.
6. Expose only read-only stored projections through a new API route after schema review; add UI timeline and evidence drilldown without leaking internal diagnostic or scoring internals.
7. RAG/lens consumers receive evidence IDs and explicit confidence, not a duplicate fundamental score. Alerts require human-approved materiality policy.

## Implementation gates
- G0: inspect actual `app/filings`, `app/fundamentals`, `app/api`, database and test conventions before editing code.
- G1: passive schema + deterministic unit tests, idempotency and PIT tests.
- G2: approved local-source import and evidence extraction tests.
- G3: reconciliation + negative mismatch tests.
- G4: read projection, UI, alerts, regression suite, release approval.

## Exclusions and cautions
No live-source availability claim; no auto-download/scraping; no trade/order automation; no artificial data; no unapproved scoring-policy modification. Documentation-only audit, not runtime proof or successful integration test.
