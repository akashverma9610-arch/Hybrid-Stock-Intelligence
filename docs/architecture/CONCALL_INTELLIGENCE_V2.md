# HSI V2 — Concall Intelligence Engine (PRD + TRD addendum)

Status: APPROVED FOR IMPLEMENTATION; not yet coded. Scope: existing Hybrid Stock Intelligence repository, no separate application.

## Product requirements
- Collect available earnings-call transcripts, exchange disclosures, investor presentations and optionally authorized audio for NSE-listed companies. Preserve original files, source URLs, publication times, company identifiers, financial quarter, transcript version, and licensing/availability status.
- Prefer 12–20 historical quarters when available; absence is explicit, never hallucinated.
- Extract management forward guidance on revenue, margins, EBITDA, order book, execution, capex, working capital, debt, exports, capacity and risks. Distinguish management assertions, analyst questions, and verified facts.
- Link each extracted assertion to verbatim evidence spans, speaker, timestamp/page, confidence, and version.
- Compare numeric guidance to subsequently reported actuals with comparable fiscal period, metric definition, consolidated/standalone basis, units and accounting scope. Report absolute/relative errors, revisions, misses and management credibility over time.
- Detect changes in tone, hedging, evasive answers, contradictions, catalysts and red flags as hypotheses, not verified facts. Include peer comparisons only after metric normalization.
- Present company-level Concall Timeline, Guidance vs Actual, Q&A Highlights, Management Credibility, Catalysts, Risks, Evidence and Data Freshness.
- Trigger alerts on material guidance changes, verified thesis impacts and newly published transcripts; deduplicate notifications.

## Technical requirements
Pipeline: discover -> source validation/licensing -> fetch -> checksum/version -> parse/transcribe (if permitted) -> speaker attribution -> structured extraction -> evidence validation -> metric normalization -> actuals reconciliation -> intelligence materialization -> HSI RAG/lenses -> dashboard/alerts.
- Store immutable raw artifacts and provenance; idempotent jobs keyed by company, fiscal quarter, source checksum and extraction model version.
- Reuse existing stock master, financial facts, evidence store, fundamental calculations, orchestration and RAG. Do not create another independent financial calculation or NSE funnel.
- Suggested entities: concall_sources, concall_documents, concall_segments, concall_claims, concall_guidance, concall_actual_matches, concall_management_scores, concall_events, concall_job_runs. Use migrations aligned to actual repository schema after audit.
- Every output carries source lineage, as-of time, extraction model/prompt version and verified/unverified/conflicted status. Retrieval must respect document access restrictions.
- Scoring: Concall evidence informs existing Fundamental/Earnings/Management dimensions; no additional additive points in the 10-point score unless explicitly approved after overlap testing.
- No transcript -> DATA_UNAVAILABLE. Conflicting sources -> REVIEW_REQUIRED. Audio transcription low confidence -> UNVERIFIED. Never infer missing numerical guidance.
- Security: validate downloaded formats, limit document sizes, sanitize prompt-injection content, use least-privilege storage, log changes and avoid storing provider secrets.
- Backfill by bounded batches; incremental polling and retry with exponential backoff. Reprocess only on new source version, parser change or approved model upgrade.

## Acceptance tests
1. Same transcript reingestion produces no duplicate claims.
2. Each displayed guidance value traces to source page/segment and period.
3. FY vs quarterly and standalone vs consolidated mismatches are rejected.
4. Revised guidance remains versioned and historical snapshots reproducible.
5. Missing/ambiguous transcript cannot yield invented conclusions.
6. Scoring unchanged when concall duplicates evidence already counted elsewhere.
7. Thesis and catalyst alerts include materiality, confidence and evidence.
8. Integration tests cover existing HSI query contracts, 35 lenses, RAG and dashboard without regressions.

## Delivery sequence
1. Audit existing repo and map real schemas/services.
2. Update canonical master PRD/TRD/schema and migration plan.
3. Implement source ingestion + provenance.
4. Implement claim extraction + guidance reconciliation.
5. Integrate shared intelligence, existing lenses, scoring and RAG.
6. Implement dashboard and alerts.
7. Backfill, test, benchmark, stage, and release only after approval.

This addendum is a specification, not evidence that the engine is implemented or operational.
