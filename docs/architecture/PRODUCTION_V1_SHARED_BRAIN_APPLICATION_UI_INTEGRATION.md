# Production-v1 Shared Brain application/UI integration

## Read-only request flow

`GET /api/v1/stocks/{symbol}/shared-brain` resolves one exact stored NSE
symbol (or canonical instrument ID), fixes one timezone-aware `as_of` cutoff,
and passes that cutoff through every input.  It reads existing canonical
universe and financial-fact stores only; it does not scan, ingest, or make a
provider request.

The application service is
`SharedBrainApplicationService`.  Its stored adapter uses the existing
canonical fact-vintage selector, selected-vintage observation materializer,
financial observation-bundle builder, wrapper adapter, stored-only Unified
State builder, and U15 `SharedBrainProductionSnapshot` builder.  It then uses
the U15 context projector for the requested existing `BrainOutputContext`.

The endpoint returns a controlled application DTO, not a raw Unified State,
bundle, or persistence model.  Policies are explicit application dependencies:

- `financial-metric-trajectory-policy / v1-approved`
- `research-metric-directionality-policy / v1-approved`
- `research-semantic-materiality-policy / v1-approved`
- the existing v2-approved Brain comparability policy.

This explicit composition is not a fallback inside any pure semantic builder.

## UI use

Stock Detail (the existing Deep Analysis surface) requests the exact endpoint
and renders **Financial Intelligence**.  The frontend does not calculate YoY,
QoQ, directionality, materiality, thesis, score, or recommendation.  It only
formats values and displays backend-projected factual fields.

`factual_display_phrase` is presentation-only.  For example, negative prior
and current values with a positive absolute delta render `loss narrowed`.
That phrase is not persisted and has no effect on directionality, scores,
gates, thesis, opportunities, alerts, recommendations, or execution.

All seven existing contexts use the same snapshot, trajectory, directionality,
and materiality-policy fingerprints for the same instrument and cutoff.  Only
the context projection fingerprint differs.

## PIT and partial states

If omitted, `as_of` is resolved once at the application boundary using its
injected application clock and returned to the caller.  Pure builders never
resolve current time.  Stored facts must remain PIT eligible at that cutoff.

Missing or conflicted financial evidence remains a valid partial response with
typed blocker codes.  With no governed comparable pairs, the UI states that no
comparable financial trajectories are available; it never fabricates a neutral
or favorable result.  Materiality remains exactly `CALIBRATION_REQUIRED`; no
movement is classified as material or immaterial.

## Manual local check

1. Start the existing FastAPI and frontend services.
2. Open **NSE Equity Universe Intelligence** and choose a supported stored NSE
   symbol, or navigate to its Stock Detail page.
3. Review **Financial Intelligence**.
4. Confirm the returned as-of timestamp, evidence status, factual trajectory,
   directionality, materiality calibration status, and any blockers.
5. Request another supported context through the endpoint and verify that the
   snapshot, trajectory, directionality, and materiality-policy fingerprints
   match the Deep Analysis response.

## Current limits

Only already-stored canonical evidence is used.  There is no provider
read-through, cache, background work, persistence, score/gate modification,
thesis/opportunity interpretation, alert publication, recommendation, or
execution in this integration.
