# Catalyst / Event Intelligence operational closure V1

Baseline: `779b186967dff726c635e967da28cdb9d9f11095`, `main`.

Decision B: `CATALYST_EVENT_INTELLIGENCE_OPERATIONAL_WITH_SOURCE_GAPS`.
Closure means the existing evidence path is wired and fixture-proven, not that
every event source is live or a directional catalyst strategy is calibrated.
V1 remains `ACTIVE`; Execution Gate V2 remains `NOT_ACTIVE`.
CAS remains `EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED`. Agent/Lyzr work is parked.

## Architecture and approved boundaries

Sources -> canonical evidence -> ONE deterministic HSI Brain -> Decision Score
-> Setup -> Six Gates -> Portfolio / Rotation / Sell / Signals.

`NEWS != CATALYST`. A producer's classification, headline, confidence or
materiality does not authorize a score, setup, gate or portfolio action.
Existing [economic/news architecture](economic_news_intelligence.md) and
[catalyst architecture](catalyst_intelligence.md) remain authoritative.
The [Batch 1 proposal](POST_V1_BATCH_1_EVENT_CATALYST_AND_RESILIENCE_POLICY_PROPOSAL.md)
approves EC-1 through EC-7 evidence boundaries only. Its exact operational
parameters remain unapproved: `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.
No new Event Policy V2, weight, TTL, direction classifier or lifecycle is added.

## Inventory and readiness

Paths below are repository-relative. OPERATIONAL means exercised with isolated
fixtures/current composition, not an assertion of live external source health.

| Family/boundary | Canonical owner and schema | Source / PIT / consumer | Runtime and policy readiness |
| --- | --- | --- | --- |
| Direct company disclosures | `app.filings.models.CorporateFiling`; existing filing store | Primary exchange/company; announced and received cutoff; `NewsCatalystEvidenceAdapter` -> Brain | OPERATIONAL for retained exact-company filings; coverage PARTIAL |
| Exchange announcements | `app.news.nse_official.NseCorporateAnnouncement`; `app.data_operations.nse_news` | Official sequence ID plus source fingerprint, publication and host receipt; existing source acquisition | Implemented bounded source; live reachability NOT_TESTED here |
| Earnings | `NewsEventCategory.EARNINGS_RESULTS`, `EventType.EARNINGS`; canonical earnings calendar separately | News is descriptive; verified future schedule belongs to Gate 6 | PARTIAL event coverage; calendar/blackout authority unchanged |
| Filings / corporate actions | `CorporateFiling`, `FilingType`; corporate-action evidence has its own owner | Source reference, revisions, announced/received boundaries | OPERATIONAL evidence path; no generic article-to-corporate-action conversion |
| Orders / capex | `ORDER_CONTRACT`, `CAPACITY_EXPANSION`; `CatalystType.ORDER_WIN/CAPEX`; external `ORDER_WIN/CAPEX` | Exact company evidence, existing category mappings | PARTIAL: no guessed capex mapping when V1D returns UNCLASSIFIED; no impact inference |
| Management / governance | News MANAGEMENT_CHANGE; external GOVERNANCE; research governance claims | Primary facts and counterevidence retained; explicit canonical conflicts visible | PARTIAL; external GOVERNANCE is not automatically typed adverse evidence |
| Regulatory / legal | `REGULATORY_LEGAL`; research primary regulatory claims; Sell/Risk review input | Primary authority is distinct from producer source labels | PARTIAL; no liability, fraud or adverse-polarity inference |
| Policy transmission | `PolicyStage`, `CompanyExposure`; `long_term_policy_transmission_research_shadow.py` | Exact verified target, stage, publication/discovery/receipt/effective boundaries | Research only; economic direction/lag/benefit POLICY_DEFINITION_MISSING |
| Sector sensitivity | `sector_economics`, `company_sensitivity` profiles and transmission services | Versioned evidence/profiles; company override required | PARTIAL; no sector-positive -> all-companies-positive assumption |
| News-only items | `NewsArticleEvidence`, `NewsEvidenceStore`, `NewsResearchInputBuilder` | Primary exchange/issuer versus reputable/secondary/unknown; publication and receipt cutoff | OPERATIONAL secondary context, not catalyst eligibility |
| Materiality | External `Materiality`: CRITICAL/HIGH/MEDIUM/LOW/NOISE; `CatalystMateriality` | Producer metadata retained; observed order-value / TTM-revenue only when both exist and revenue > 0 | PARTIAL: no canonical threshold, promotion or numerical news score |
| Direction | No direction field in `ExternalEvent`; typed crowd `NewsEvent.polarity` is separate | Narrative and interpretation cannot populate canonical direction | UNAVAILABLE for this projected path; explicit conflicts retained, never forced binary |
| Freshness | Brain `FreshnessStatus` and policy reference | Existing News/catalyst adapter returns UNKNOWN and no freshness policy | PARTIAL; no new TTL, expiry, cancellation/resolution inference |
| Deduplication | Producer event identity, immutable evidence versions, V1D projection ID; News URL key | Exact replay is one event/evidence/News row; revised evidence is another version of the same event | OPERATIONAL exact identity; cross-producer real-world reconciliation PARTIAL |
| PIT | Repository/application as-of readers; `eligible_as_of`; Brain builder | Publication and receipt <= decision cutoff; original received-at survives retry | OPERATIONAL tested boundaries; source metadata is not proof of strict historical reaction coverage |
| Brain assembly | `StoredSharedBrainEvidenceAssembler` -> `MacroNewsEvidenceStoredSource` -> `UnifiedIntelligenceState` | Existing News and filing stores; source/dependency fingerprints and warnings | OPERATIONAL: native NEWS_CATALYSTS reference, not a second Brain |
| Decision Score | `app.scoring.engine`; canonical score evidence adapter | Existing diagnostic inputs/weights, not news count | Descriptive path only; no new catalyst contribution; Rule 57 remains a supporting diagnostic where already configured |
| Setup | `canonical_setup`, governed Pre-Breakout assessment; universe `catalyst_context` | Native technical/structural setup and eligible diagnostic context | PARTIAL contextual linkage; no target, date or invalidation invented from prose |
| Six Gates event risk | `app.gates.engine`, V1 Gate 6 and approved policy selection | Verified earnings schedule and configured trading-session blackout; surveillance remains separate | OPERATIONAL existing policy; generic legal/news veto not newly wired or authorized |

## Minimal binding and runtime edges

The missing edge was accepted External Intelligence intake -> durable V1D News
projection. The projector and downstream Brain reader already existed; no
additional database, event schema or intelligence engine was necessary.

`ExternalIntelligenceApplicationService` now accepts an optional existing
`ExternalIntelligenceNewsProjector`. Default authenticated SQLite API composition
injects it using the same database path. The existing lifetime closes this
owned News connection. Explicit callers that omit it retain their prior behavior.

| Edge | Result |
| --- | --- |
| Source/Desk -> authenticated V1C payload | PARTIAL source coverage; existing transport/schema/auth unchanged |
| Payload -> immutable event/evidence/request transaction | OPERATIONAL; source references are not fetched and receipt time is backend-owned |
| Committed canonical evidence -> existing News projection | OPERATIONAL after this binding; SECONDARY_RESEARCH authority retained |
| News store -> canonical Brain evidence assembly | OPERATIONAL; already wired in production application composition |
| Reevaluation request -> read-only consumer | IMPLEMENTED_NOT_WIRED to an automatic dispatcher; explicit existing consumer is tested |
| Brain News references -> descriptive downstream reads | OPERATIONAL; no automatic recalculation, score/gate pass or trade |
| News -> typed Rule 30/57 inputs | PARTIAL / SOURCE_NOT_READY when canonical typed research/reaction evidence is absent |

Projection occurs after canonical transaction commit and before an accepted
receipt is returned. If projection fails, intake does not return success;
canonical evidence remains durable. The caller's exact retry repairs projection
without changing first receipt time or duplicating records. A canonical conflict
returns before projection. This is explicitly two stores' existing transactions,
not a claimed atomic cross-store transaction. There is no retry loop, scheduler,
historic backfill, source acquisition or direct Brain/score/gate invocation.
Existing backlog can remain unprojected until a separately controlled replay.

## Identity, source authority, conflict and lifecycle limits

An `ExternalEvent` key is producer ID/event ID plus its stable identity
fingerprint. Each `EvidenceVersion` has a content-derived identity. V1D references
both IDs and fingerprints in News provenance and uses event + evidence +
projection version for the derived identity. FACT, DATA, INTERPRETATION and
INFERENCE remain separate in canonical storage. The Brain references their
derivative's fingerprint; it does not copy AI text as a fact.

Supporting reports are not independent confirmation votes. Same-ID replay is
deduplicated; later evidence versions remain separate references to the same
canonical event. Independent producer IDs cannot yet be guaranteed to identify
one real-world event. `NewsEventClusteringService` groups by linked filing or
category, instrument set and publication date; it is a bounded heuristic, not
proof that same-day events are identical or later republications are reconciled.
It is not introduced into this binding. No count-based weighting is added.

Primary filing provenance remains primary. V1D intentionally labels every
external projection SECONDARY_RESEARCH even if the producer claims an official
source. Exact VERIFIED company IDs are retained; unverified exposures do not
attach to a company. V1C identity-shape validation does not independently verify
the source document or company economic exposure. This is a coverage/authority
limit, not permission to upgrade producer claims.

Canonical `CONFLICTED` warnings reach Brain availability unchanged. Rejected
event-identity conflicts do not overwrite previous evidence. Counterevidence and
risks remain in immutable evidence; free-text contradiction is not automatically
classified CONFLICTED. The positive/adverse/mixed fixture descriptions test
retention, not a newly approved polarity inference.

Publication, receipt and effective/event time remain distinct. New versions do
not affect earlier cutoffs. A disclosed future earnings schedule may be known
now but is not a completed event; Gate 6 handles it separately. Stored catalyst
artifacts require their event/publication/retrieval/first-observed boundaries.
Current News freshness remains UNKNOWN. Research Catalyst `occurred/cancelled`
and claim-resolution vocabulary exist but do not establish a general
NEW/VALIDATED/MATERIAL/ACTIVE/STALE lifecycle. Old facts, unresolved freshness
and missing data cannot be advertised as active material catalysts.

## Diagnostic, score and gate findings

Rule 30 uses eligible typed `ResearchSnapshot.catalysts`. Secondary News
research documents are validation-ineligible and remain context after the
canonical research as-of filter. `app.universe_analysis.service._research_evidence`
accepts typed research/crowd payloads only; generic News rows are not grafted into
diagnostics.

Rule 57 is `post_news_reaction`: `app.crowd.engine.post_news` requires a typed
event (including supplied polarity), valid market bars and post-publication
bars. It uses existing first/last post-event closes. Missing inputs yield
INSUFFICIENT_DATA; current-descriptive data is not upgraded to strict PIT.
This slice does not infer polarity or implement the separately unresolved
session/reaction policy. Existing result labels are diagnostic states, not
instructions to trade. Thresholds and rule meaning remain unchanged.

Score components retain their exact existing weights. Rule 57 is a supporting
input of the existing liquidity/SMC component; Rule 30/news count is not a new
weighted component. Brain NEWS_CATALYSTS availability does not imply a score.
Setup remains technically governed; stored catalyst context does not create
entry/stop/targets or define invalidation. Gate 6 keeps verified-schedule and
blackout policy, including existing-position context exceptions. Generic news
cannot grant, veto or bypass a gate unless an existing gate input/policy does so.
Sell/Risk's isolated review policy still requires typed adverse classification,
freshness and provenance; this bridge does not manufacture those inputs.

## Fixture proof and remaining source gaps

The focused closure suite proves the default authenticated route feeds the
native Brain, direct positive/adverse/mixed descriptions remain referenced,
primary filings retain authority, explicit source conflict reaches Brain,
replay/new-version dedup and PIT exclusion, projection-outage recovery, no
unverified-company attachment, and owned-resource shutdown.
The existing worker parser accepts `NO_NEW_MATERIAL_INTELLIGENCE` with a null
event; this creates no synthetic event. An empty/unavailable News store is not
itself proof that the world contains no material news.

Live provider/Desk health and current coverage were not exercised. Production
DB data, credentials, portfolio, paper trades and broker/order operations were
not accessed by this slice. Runtime changes are limited to optional projector
composition and connection cleanup; all integration writes use temporary DBs.

Remaining: source coverage; cross-producer reconciliation; independently verified
exposure; event-family materiality/direction/freshness/resolution policy;
canonical reaction inputs; historical backlog projection and automatic request
dispatch; research-only macro/policy transmission. These do not prevent the
bounded descriptive evidence path from functioning safely.

## Validation and defensive review

- New isolated closure cases: 11; focused catalyst/event group: 37 passed,
  0 failed, 2 warnings.
- Combined focused and historical source-pin conformance group: 1,069 passed,
  0 failed, 2 warnings.
- Relevant Brain, diagnostics, score, setup, gates and research regressions:
  169 passed, 0 failed, 2 warnings.
- Final complete backend suite: 8,609 passed, 0 failed, 6 skipped, 2 warnings.
  The warnings concern deprecated FastAPI/Starlette test-client dependencies.
  Live-provider and optional PostgreSQL tests retain their existing opt-in skips.
- Local Markdown links and trailing-whitespace checks passed.

The first full run found five source-pin failures (8,604 passed), not behavioral
failures. Three conformance test files now verify historical fingerprints against
their original committed bytes, then require exactly the reviewed additive
successor edits. All remaining bytes stay pinned; missing or repeated replacement
anchors fail. Historical governance artifacts/fingerprints were not rewritten.
The subsequent full run above includes these compatibility corrections.

Application changes are limited to `external_intelligence_application.py`,
`app/api/dependencies.py` and `app/api/main.py`. The existing projector, News
schema/store, Brain assembler, diagnostics, score weights, setup policies,
Six Gates, portfolio, providers and Agent integrations remain unchanged.
No source fetch, database migration, production replay, portfolio mutation,
broker/order call or automatic trading was performed. Both API fixture clocks
are fixed; the tests do not use live external evidence.

Exactly one next frozen continuation:
`OPENING_GAP_OVERNIGHT_INTELLIGENCE_OPERATIONAL_CLOSURE_V1`.
It is not started. No Agent/Lyzr, CAS, Gate-1 or horizon work is resumed.
