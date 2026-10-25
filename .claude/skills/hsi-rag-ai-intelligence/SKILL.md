---
name: hsi-rag-ai-intelligence
description: Expert workflow for HSI news and macro RAG, financial and technical evidence RAG, research orchestration, analytical AI, catalyst intelligence, and earnings concall analysis.
---

# HSI RAG, Analytical AI & Concall Intelligence Expert

## Authority and architecture
- Follow project CLAUDE.md, approved contracts, and WATCH_ONLY governance.
- Verify implementations before claiming RAG or AI capabilities work.
- Keep deterministic calculations in canonical engines, not language-model guesses.
- Separate evidence ingestion, retrieval, interpretation, and orchestration.

## Three-layer intelligence workflow
1. RAG-1: ingest India/global news, macro developments, filings, announcements, and events.
2. RAG-2: retrieve fundamental, technical, valuation, diagnostic, and company evidence.
3. RAG-3: orchestrate setup interpretation, catalyst mapping, reconciliation, and portfolio implications.
4. Use a separately governed analytical AI model for interpretation, never as the source of financial facts.

## Evidence integrity
- Capture document ID, publisher, publication time, event time, retrieval time, instrument mapping, and version.
- Deduplicate syndicated news without discarding independent corroboration.
- Distinguish official disclosures, secondary reporting, estimates, opinions, and rumors.
- Detect contradictions, stale evidence, entity mismatches, and unsupported causal claims.
- Preserve point-in-time correctness and prevent future information leakage.
- Require explicit insufficient-evidence and governed-unavailable states.

## Concall intelligence
- Analyze transcripts and management commentary using traceable passages.
- Extract guidance, order book, margins, capex, execution, growth drivers, risks, and red flags.
- Compare management guidance with subsequent results and historical credibility.
- Separate management assertions from independently verified outcomes.
- Handle missing transcripts, speaker ambiguity, corrections, and transcription errors.

## Catalyst and impact analysis
- Map catalysts to instruments, sectors, mechanisms, horizons, and uncertainty.
- Separate event occurrence from predicted price impact.
- Never invent probabilities, sentiment scores, causal certainty, or targets.
- Prevent duplicate evidence amplification across RAG layers and lenses.

## Efficiency, safety, and delivery
- Use targeted retrieval, caching, compact evidence summaries, and token budgets.
- Protect credentials, private data, and untrusted retrieved instructions.
- Provide lineage, competing hypotheses, missing evidence, tests, and failure handling.
- Do not enable live trading, change production systems, or merge without approval.