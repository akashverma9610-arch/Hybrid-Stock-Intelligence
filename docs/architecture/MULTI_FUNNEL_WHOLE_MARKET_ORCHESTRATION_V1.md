# Whole-Market Multi-Funnel Orchestration V1

**Status: `ACTIVE_READ_ONLY / DISCOVERY_INFRASTRUCTURE_ONLY / NON_EXECUTABLE`.**

`WHOLE_MARKET_MULTI_FUNNEL_RUNNER = ACTIVE_READ_ONLY`

`MULTI_FUNNEL_DISCOVERY = OPERATIONAL`

`DISCOVERY_RECALL_AUDIT = NOT_ACTIVE`

`HSI_BRAIN_CANDIDATE_EVALUATION = NOT_INVOKED_BY_DISCOVERY`

These statuses describe discovery infrastructure, not operational intelligence
in all fourteen funnels or production scheduling. They confer no qualification,
recommendation, strategy activation, portfolio authority or execution authority.

## Reuse and dependency boundary

The pure `app.intelligence.multi_funnel_orchestration` boundary composes the
existing [registry and batch envelope](MULTI_FUNNEL_DISCOVERY_CONTRACT_AND_REGISTRY_V1.md),
[five source adapters](MULTI_FUNNEL_DISCOVERY_ADAPTERS_V1.md), and
[exact-security candidate union](MULTI_FUNNEL_CANDIDATE_UNION_AND_IDENTITY_V1.md).
These existing implementations are unchanged. No second universe, registry,
adapter engine, union, source of truth or Brain is introduced.

```text
explicit UTC cutoff + retained eligible NSE snapshot + canonical registry
  -> isolated reads of five supported canonical source types
  -> all fourteen funnel execution/coverage receipts
  -> raw immutable leads + explicit universe exclusions
  -> existing exact-security union
  -> BRAIN_INSPECTION_CANDIDATES (handoff only; stop)
```

`NseEquityInstrument`, `UniverseSnapshot` and the pure
`app.universe_analysis.service.build_universe_snapshot` are reused. Its existing
eligibility is NSE, EQUITY, main_board not explicitly false. Unknown main-board
metadata is not silently given a stricter/new investment interpretation. All
eligible IDs must already be exact `NSE:<ISIN>` and agree with their instrument
records. The snapshot checksum, counts and ordered membership must reproduce
exactly from the supplied retained records; duplicate identities and future
records fail the master input before any source read. Existing exclusion counts
and scope warnings are retained. No fuzzy/current-symbol resolver is added.

The old controlled `UniverseAnalysisService.run` path couples its universe job
to 61-rule diagnostics, Decision Score, Six Gates and stored analysis. It is
**not instantiated or called**. Only its pure snapshot builder is called.
Likewise, Top-3 source records are consumed, not `Top3OpportunityFinderService`.
Its stored `candidate_ids` are exact sector-constituent targets selected before
setup assessment, not its filtered `opportunity_ids` or qualifying outcomes.
Importing these existing modules also loads their existing type dependencies;
this is not a claim of a transitive-import-free module. No engine, repository,
provider or portfolio service is constructed or invoked by discovery.

## Input and read contract

`orchestrate_whole_market_discovery` requires an explicit aware `as_of`, the
retained `UniverseSnapshot`, its immutable instrument records, the exact
canonical registry/version/fingerprint, and an injected `read_sources(funnel,
as_of)` function. The caller supplies a read-only canonical-store reader; it
must honor storage-envelope availability at the supplied cutoff. The runner
contains no SQL, repository, provider, environment or clock access.

- `None`: source unavailable, not a successful empty evaluation.
- `()`: successful canonical read with no retained observations.
- Immutable tuple: the existing adapter evaluates those canonical records at
  the same master cutoff. It performs no source calculation or acquisition.
- Reader exception: stable `SOURCE_READ_FAILED`, no raw exception text/URL.
- Pre-adapter record validation failure: `SOURCE_VALIDATION_FAILED / DATA_BLOCKED`,
  not counted as an adapter invocation. No raw exception text is retained.
- Adapter exception or wrong funnel/cutoff result: stable `ADAPTER_FAILED /
  DATA_BLOCKED`, isolated before batch assembly, no raw text.
- Conflicting fingerprints for one supplied source ID: `SOURCE_CONFLICT /
  EVIDENCE_CONFLICTED`; no input-order winner is selected. Exact source replay
  remains in the reference receipt and reaches existing adapter deduplication.

Source identity/fingerprint pairs and supplied-record counts remain visible,
including non-emitting sources. Malformed identities cannot be echoed as raw
data; failure retains the count and any syntactically safe references already
obtained. Exceptions are isolated per funnel, without retry, logging arguments,
or catching process interrupts (`BaseException`). Master universe/registry
invariant failures stop the run rather than producing a misleading batch.

All fourteen canonical registry entries are enumerated in deterministic order.
An explicit binding table connects only the five implemented adapter functions
to their canonical source types; it is not another funnel registry. Canonical
registry engine-entry-point text is never dynamically invoked. The other nine
entries reuse `unavailable_adapter` exactly. Holding/watchlist contextual entries
are not converted into whole-market scans and do not trigger a reader call.

Registered, source-operational, adapter-available, executable and evaluated are
different facts. A Research Shadow adapter can read evidence without upgrading
the underlying funnel to an operational qualifying strategy. No independent
Earnings Acceleration leads are manufactured from Inflection observations.

## Batch, coverage and identity

`WholeMarketDiscoveryBatch` is immutable, with:

- explicit UTC cutoff; original universe identity/checksum/counts/warnings and
  reproducible instrument lineage; canonical registry ID/version/fingerprint;
- fourteen `DiscoveryFunnelExecution` records, original adapter results and
  coverage, source references/counts and stable execution states;
- requested funnels, executable/evaluated lists, blocked envelope partition,
  source-not-operational list, and actual per-funnel `executed` flags;
- original raw lead IDs and exact outside-universe lead IDs;
- the existing `MultiFunnelDiscoveryBatch` envelope and existing candidate union,
  retaining every surviving lead/origin and all candidate IDs/fingerprints;
- deterministic batch ID, content fingerprint and explicit JSON serialization.

The envelope's executed partition denotes **completed adapter evaluations**;
the execution receipts separately distinguish a failed attempted invocation.
`EVALUATED_NO_LEADS` means a successful source pass, not evaluation of every
eligible NSE security. Source-observation coverage remains distinct from
universe coverage. The compact envelope counts only emitted eligible securities
as proven identifiable per-security coverage; it does not manufacture per-stock
negative decisions from anonymous source-level counts.

Original adapter coverage remains authoritative and unmodified in execution
receipts. A separate scope-filtered adapter result is passed to the existing
union, with removed leads explicitly retained outside the pool. If every lead
is outside the universe, the scoped state is `IDENTITY_BLOCKED`, not a silent
successful no-lead claim. The exact excluded IDs and original result fingerprint
make this reversible as an audit, not as a mutation. Union duplicate/identity
exclusions and counts retain their existing meaning. Universe exclusions are
reported separately from union exclusions; there is no lossy flattening.

The compact envelope maps richer coverage states to its existing broad
`DATA_BLOCKED`/`NOT_EVALUATED` vocabulary; original `STALE`, `IDENTITY_BLOCKED`,
`EVIDENCE_CONFLICTED`, `SOURCE_NOT_OPERATIONAL` and reason codes remain intact.
No artificial TTL, expiry, freshness policy or present-day reinterpretation is
added. Retained historical Sector Rotation paths remain dated inspection
origins, not claims of a current executable setup.

Whole-market identity binds the contract version, existing envelope identity,
full universe snapshot and ordered execution/source provenance. The separate
content fingerprint additionally seals instrument metadata, raw/excluded
origins, coverage, envelope and candidate union. JSON has sorted keys and UTC
timestamps; input iteration order, locale and runtime time do not participate.
`verify()` reconstructs and compares without repairing the supplied receipt.
Identical inputs/replay yield identical bytes. Different source provenance may
change batch identity; candidate identity follows the unchanged union contract.

## Canonical read-only production audit

Audit uses one SQLite `mode=ro`, `query_only` read transaction, no source fetch
and no repository save. The latest relevant stored source availability gives
the explicit cutoff **`2026-09-04T19:30:59.533938+00:00`**. It is not runtime now.

Universe: `nse-universe:fundamental-probe:2d5692582f3f43fda4eb73aa3caf2d34`.
Universe as-of: `2026-08-25T15:00:38.602331+00:00`.
Eligible securities: **2,553**; existing exclusions: **0**.
Checksum: `7d9f4c332f95f4cb0b0107cbb75da9abee1e0e9b3c3d8b670a02d409bdcfceb7`.
Registry: `hsi-multi-funnel-discovery-registry / v1`.
Whole-market batch: `whole-market-discovery:5cf887c7bdfddb5698ebe4dba13239e1`.
Content fingerprint: `6367d9138b5002dfd267597f185dece951821b628e41ec8720cdd0e95037ddd4`.
Reverse-order replay is byte-identical; the SQLite connection reports zero writes.

The snapshot's exact member IDs select retained PIT instrument rows. The stored
NSE_UNIVERSE family also contains legacy identity records: flattening that whole
family would falsely yield 5,106 identities and fails the checksum. They are
not added to or substituted into the approved snapshot. No production rows are
changed to obtain a matching universe.

| Funnel | Registry state | Adapter state | Executed? | Coverage | Raw leads | Distinct securities | Blocker |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| COMPOUNDER | RESEARCH_SHADOW | ADAPTER_PARTIAL | Yes | EVALUATED_NO_LEADS | 0 | 0 | No retained prospective observation; successful empty read |
| EARNINGS_ACCELERATION | PARTIAL | ADAPTER_PARTIAL | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | EARNINGS_ACCELERATION_NOT_INDEPENDENT |
| EMERGING_COMPOUNDER | NOT_IMPLEMENTED | NOT_IMPLEMENTED | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | FUNNEL_NOT_IMPLEMENTED |
| FUNDAMENTAL_INFLECTION | RESEARCH_SHADOW | ADAPTER_PARTIAL | Yes | LEADS_EMITTED | 8 | 6 | No adapter blocker; research qualification remains inactive |
| HOLDING_STATE_CHANGE | PARTIAL | ADAPTER_PARTIAL | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | HOLDING_STATE_CHANGE_CONTRACT_UNAVAILABLE |
| MARKET_DISLOCATION | PARTIAL | ADAPTER_PARTIAL | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | MARKET_DISLOCATION_SECURITY_SCOPE_UNAVAILABLE |
| MOMENTUM | PARTIAL | ADAPTER_PARTIAL | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | MOMENTUM_TRIGGER_POLICY_UNAVAILABLE |
| NEWS_CATALYST | PARTIAL | ADAPTER_PARTIAL | No | POLICY_BLOCKED | 0 | 0 | NEWS_CATALYST_ADAPTER_POLICY_UNAVAILABLE |
| ORDERBOOK_CAPEX | PARTIAL | ADAPTER_PARTIAL | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | ORDERBOOK_CAPEX_TRIGGER_POLICY_UNAVAILABLE |
| POLICY_TRANSMISSION | RESEARCH_SHADOW | ADAPTER_PARTIAL | Yes | EVALUATED_NO_LEADS | 0 | 0 | No retained eligible source; successful empty read |
| PRE_BREAKOUT | OPERATIONAL | ADAPTER_ACTIVE | Yes | EVALUATED_NO_LEADS | 0 | 0 | No stored opportunity; successful empty read |
| SECTOR_ROTATION | OPERATIONAL | ADAPTER_ACTIVE | Yes | LEADS_EMITTED | 348 | 68 | None at adapter boundary; historical paths retain source dates |
| VALUATION_RECOVERY | POLICY_BLOCKED | SOURCE_BLOCKED | No | POLICY_BLOCKED | 0 | 0 | FUNNEL_POLICY_BLOCKED |
| WATCHLIST_STATE_CHANGE | NOT_IMPLEMENTED | NOT_IMPLEMENTED | No | SOURCE_NOT_OPERATIONAL | 0 | 0 | FUNNEL_NOT_IMPLEMENTED |

Five executable/evaluated adapters; nine blocked/not-evaluated (seven
source-not-operational and two policy-blocked). Raw leads **356**, distinct
origins **356**, exact duplicates **0**, outside-universe **0**, union
identity-blocked **0**. Candidate pool **73** exact securities: **72**
single-funnel, **1** multi-funnel. This does not describe opportunity quality.

| Audit target | Eligible membership | Pool presence | Origins | Funnel/posture |
| --- | --- | --- | ---: | --- |
| APARINDS — NSE:INE372A01015 | Yes | Yes | 2 | FUNDAMENTAL_INFLECTION / RESEARCH_INSPECTION |
| DEEPINDS — NSE:INE0FHS01024 | Yes | No | 0 | No eligible origin, not a negative investment judgment |
| GENUSPOWER — NSE:INE955D01029 | Yes | No | 0 | No eligible origin, not a negative investment judgment |
| GLAND — NSE:INE068V01023 | Yes | Yes | 2 | FUNDAMENTAL_INFLECTION / RESEARCH_INSPECTION |
| ICICIBANK — NSE:INE090A01021 | Yes | No | 0 | No eligible origin, not a negative investment judgment |

APARINDS source observations are
`inflection-accounting-prospective:b0d43a2ac94aef0fad48832c` and
`inflection-accounting-prospective:b4a23d09cd5f7fcb187262a9`;
GLAND observations are
`inflection-accounting-prospective:451038e44ba51de9bc85c078` and
`inflection-accounting-prospective:d85d50f8de1f31351ebb273b`.
Each original lead retains the associated revenue/PAT receipt IDs/fingerprints
and PIT company-type receipt. No portfolio was consulted for these symbol audits.

The only multi-funnel security is **`NSE:INE010B01027`**: eight Sector Rotation
origins and one Fundamental Inflection origin. Multiple funnels are not votes,
a score bonus, stronger conviction or qualification. No ranking is produced.

## Recall readiness, safety and next boundary

The handoff retains eligible membership, registry/readiness, actual execution,
source/adapter blockers, emitted raw IDs, excluded IDs, surviving origin lineage
and exact-security candidates. These support later questions about registration,
execution, emission and union retention. A security absent from a source that
only exposes aggregate no-lead/blocked counts has **no invented per-security
non-emission explanation**. Future Recall Audit must preserve that evidence gap.
No recall classifier, outcome, hit rate, alpha, return or performance metric is
implemented here. `BRAIN_INSPECTION_CANDIDATES` means only the union's existing
`CANDIDATE_FOR_SHARED_BRAIN_INSPECTION` posture.

There is no scheduling, provider acquisition, source scan/refresh, persistence,
SQL, migration, API/UI, runtime wiring, portfolio read/mutation, price/threshold,
score, confidence, setup/signal/gate creation or broker/order authority. FACT →
DATA → INTERPRETATION → INFERENCE and existing source research posture remain
unchanged. The runner never invokes the 61-point Brain evaluation.

Next separately authorized slice:
`DISCOVERY_RECALL_AUDIT_CONTRACT_AND_OUTCOME_CLASSIFICATION_V1`.
**Do not automatically start it.**

## Validation

Focused orchestration tests exercise all fourteen entries and five adapters,
explicit universe/as-of requirements, checksum/PIT/identity rejection, blocked
contextual funnels, source/adapter isolation without exception-text leakage,
source conflict/tampering, source counts, raw/excluded origin retention, existing
union handoff, research posture, five generic target identities, immutable
receipts, deterministic replay/UTC serialization and static call boundaries.
The production read-only audit is replayed with reversed input ordering. Relevant
discovery/union/universe/identity/source tests and the full backend suite are
required against the final implementation before committing this closure.

Completed validation on the final source:

- Focused orchestration: **34 passed / 0 failed**.
- Relevant discovery, adapters, union, universe, identity/PIT and source
  contracts: **145 passed / 0 failed / 2 warnings**.
- Full backend: **2706 passed / 0 failed / 6 skipped / 2 warnings**.
  Warnings are existing Starlette/httpx and AnyIO deprecations. Skips are
  opt-in provider/PostgreSQL integration tests, not discovery failures.
- Deterministic production replay: identical batch ID/fingerprint/serialization;
  **356 origins / 73 securities**, zero writes on the read-only connection.
- Markdown: **199 local links/anchors passed** across README and the four
  discovery architecture documents. Whitespace and `git diff --check` passed.
- Final defensive review corrected adapter result cutoff/funnel isolation and
  distinguished pre-adapter validation failure from actual invocation. Focused,
  relevant and full validation were rerun after these corrections. Existing
  adapters, registry, union and universe/Core application files are unchanged.
- No application DB-access or persistence/schema code changed; SQLite integrity
  and FK revalidation were not required by this code-only/read-only slice. This
  is not a new claim of database-wide integrity based on tests against fixtures.
