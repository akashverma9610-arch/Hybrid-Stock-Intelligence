# Prospective Earnings Schedule Receipt Readiness V1

**Status:** `PROSPECTIVE_RECEIPT_PATH_PARTIAL_ONE_BOUNDED_REPAIR_REQUIRED / DOCUMENTATION_ONLY / NOT_ACTIVE`.

This bounded audit follows the [earnings blackout horizon calibration contract](EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.md), [known-at semantics](EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1.md), [canonical identity bridge](EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1.md), and [coverage/window policy](EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1.md). Its machine record is the [readiness receipt artifact](EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1.json).

It does not implement a collector, register a runtime job, create a table, change Gate 6 V1, activate Gate 6 V2, choose a horizon, reconstruct historical PIT, provide absence clearance, or create a signal, trade, order, portfolio mutation, or AI decision authority.

## Result and exact boundary

**Result: B — `PROSPECTIVE_RECEIPT_PATH_PARTIAL_ONE_BOUNDED_REPAIR_REQUIRED`.**

Existing official source adapters and the current 31-company identity bridge are sufficient inputs for prospective *positive* notice observation. They are not an active prospective receipt path. `SourceBatch.retrieved_at` is supplied by its caller; the existing first-observed types are pure contracts whose automatic capture and persistence are deferred. A caller-provided retrieval time must not be relabelled `SYSTEM_FIRST_OBSERVED`.

The one required repair is **`EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1`**: a bounded, non-trading ingestion boundary that captures and durably saves an automatic first observation of each exact source row. It may reuse existing adapters, identity, purpose, known-at, coverage, calendar, and snapshot-store contracts. It must not search new providers or implement a general calendar platform.

## Bounded source and 31-company audit

The frozen identity receipt establishes the bounded population: **31/31** current NSE identities and **31/31** current BSE identities resolve from the existing official current-universe and BSE official-mapping authorities. It is current-forward identity only; it does not manufacture historical effectiveness or schedule knowledge.

A one-request-per-family, read-only probe on 2026-09-13 used the existing bounded transport. It received HTTP 200 from the public NSE rolling RSS and the BSE public recent-corporates list. The RSS returned zero rows in that instant; BSE returned ten recent links, none of which supplied an admitted financial-results purpose without a detail fetch. That is an empty/partial inventory at one observation, **not** a no-event result for any company. The unprivileged execution sandbox could not reach either source; the same bounded probe on the host network produced the HTTP 200 results. The source conclusion therefore rests on the adapter's explicit source state, not on a fabricated negative absence result.

| Family | Existing exact path | Current bounded observation | Exact identity when a retained detail exists | Qualifying purpose | Positive receipt suitability | Negative-absence suitability |
| --- | --- | --- | --- | --- | --- | --- |
| NSE | `NSEOfficialEarningsScheduleSource` → published rolling RSS → exact linked Prior Intimation XML/iXBRL | `HTTP 200`; `SOURCE_PARTIAL`; zero RSS rows at this observation | `PARTIAL`: structured linked document carries symbol and ISIN; existing bridge resolves only exact current evidence | `READY` only for exact structured/affirmative results text; ambiguity is retained | `PARTIAL`: a future retained linked, qualifying, exact-identity row can be collected | `NOT_READY`: rolling feed has no admitted company/window query or completeness proof |
| BSE | `discover_bse` public recent list → exact mobile `MAnnDet.aspx` detail | `HTTP 200`; `SOURCE_PARTIAL`; ten recent links; no detail purpose admitted by list alone | `PARTIAL`: detail carries exact six-digit code and bridge resolves only exact current BSE mapping | `READY` only after exact detail parsing; list headline never becomes a purpose | `PARTIAL`: an already discovered exact qualifying detail can be collected | `NOT_READY`: recent list is neither an exact company/window query nor a completeness proof |

The adapter states are intentionally `SOURCE_PARTIAL` even after successful HTTP transport. A source failure, parser error, unsupported schema, identity failure, or conflict remains a failed/partial receipt. It can never become `NO NOTICE FOUND`, `NO EVENT EXISTS`, a safe state, freshness proof, or Gate 6 clearance.

## Minimum prospective evidence chain

The following chain is sufficient to start collecting **positive** prospective evidence. It is not sufficient to calibrate a horizon, clear a negative window, or authorize a gate.

```text
bounded official response acquired
  -> automatic aware-UTC HSI boundary captures first_observed_at
  -> exact source row/document and payload fingerprint retained
  -> exact current canonical identity resolves
  -> explicit financial-results purpose is classified
  -> immutable source receipt and partial/failed coverage receipt are saved
  -> exact revisions/cancellations or conflicts remain independent lineage
  -> later actual-result and price-outcome attachment remains separate
```

| Class | Required inputs and rule |
| --- | --- |
| `MANDATORY_TO_START_COLLECTION` | One admitted official positive-discovery route; bounded transport result; exact current canonical identity; explicit qualifying purpose; automatic aware-UTC `HSI_FIRST_OBSERVED_AT`; immutable source-row/payload fingerprint; idempotent logical-receipt key; explicit revision/conflict handling; and a durable failed/partial collection receipt. |
| `MANDATORY_BEFORE_HORIZON_CALIBRATION` | Reconciled logical schedule event; final lifecycle/revision lineage; later actual-result publication linkage; proven reaction-session mapping; and the calibration contract's observation and decision lineage. Layer 2 additionally requires a genuine prospective HSI opportunity chain. |
| `OPTIONAL_ENRICHMENT` | Canonical ATR binding for ATR-normalized outcomes, sector benchmark context, volume/turnover, MFE/MAE after an approved outcome-window policy, and measured or separately governed proxy slippage. None blocks Layer 1 receipt collection. |

`SOURCE_PUBLIC_TIME`, `SOURCE_RECEIVED_TIME`, `HSI_FIRST_OBSERVED_AT`, and `EVENT_DATE` are distinct. The collector must retain raw source values and mark source timestamp semantics `UNPROVEN` where NSE/BSE field role or timezone is unproved. It may still record a prospective HSI observation. It must never infer an offset, turn a meeting date into publication time, backdate first observation, or replace a source field with HSI time.

## Existing components and the single missing runtime boundary

| Need | Existing reusable owner | State | Consequence |
| --- | --- | --- | --- |
| Official bounded transport and parsers | [`earnings_schedule_source.py`](../../app/filings/earnings_schedule_source.py), [`earnings_schedule_discovery.py`](../../app/filings/earnings_schedule_discovery.py) | `PARTIAL` | Positive discovery only; current routes have no complete window semantics. |
| Exact current identity | [`earnings_schedule_identity.py`](../../app/filings/earnings_schedule_identity.py) and accepted 31-company receipt | `READY` | Resolve only exact source symbol+ISIN or BSE code+ISIN; no name fallback. |
| Purpose, event date, source-row parsing | [`earnings_schedule_source.py`](../../app/filings/earnings_schedule_source.py) | `READY_FOR_OBSERVED_VARIANTS` | Unknown shapes and ambiguous purpose remain unadmitted. |
| First-observed contract | [`earnings_schedule_known_at.py`](../../app/filings/earnings_schedule_known_at.py) and [`earnings_schedule_coverage.py`](../../app/filings/earnings_schedule_coverage.py) | `PARTIAL` | Typed receipts exist, but neither is captured automatically nor persisted by a runtime collector. |
| Existing candidate lifecycle store | [`earnings_schedule_store.py`](../../app/filings/earnings_schedule_store.py) | `PARTIAL` | Its raw-row/replay mechanics are useful, but `OfficialEarningsScheduleCandidate` requires a proven exchange dissemination timestamp and cannot be a prospective-first-observed substitute. |
| Coverage receipt | [`earnings_schedule_coverage.py`](../../app/filings/earnings_schedule_coverage.py) | `PARTIAL` | Reuse for partial, failed, or conflicted query receipts; do not create a duplicate coverage model. |
| Immutable generic receipt persistence | [`core_api_snapshot_repository.py`](../../app/storage/core_api_snapshot_repository.py) | `READY_FOR_EXTENSION` | Existing immutable snapshot table/repository can hold one new typed receipt family; no database schema migration is required. |
| Generic corporate filings | [`filings/store.py`](../../app/filings/store.py) | `PARTIAL` | Useful later for result evidence, but requires `announced_at` and does not preserve this schedule collector's source-row/first-observed contract. It is not the prospective schedule receipt owner. |

### Minimal repair contract — defined, not implemented

`EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1` should add one typed, immutable record family to the existing `CoreApiSnapshotRepository`, not a new SQLite table or parallel calendar database. The proposed family is `EARNINGS_SCHEDULE_PROSPECTIVE_RECEIPT`; its two record types are `ProspectiveScheduleSourceReceipt / v1` and `ProspectiveScheduleCollectionRunReceipt / v1`.

`ProspectiveScheduleSourceReceipt` must retain:

- `logical_receipt_key = source_family + source_filing_identity + source_payload_fingerprint`;
- `canonical_instrument_id`, source exchange/family, exact source identifier, source reference, adapter/parser version, raw record field set, source-row fingerprint and enclosing response/batch fingerprint;
- qualifying-purpose state, raw event-date representation, source-native raw timestamp values and semantic states, without normalized timezone invention;
- automatic `first_observed_at` (aware UTC), first-observed receipt ID, collector run ID and in-run sequence; and
- lifecycle/revision/cancellation reference when an exact parent is available, otherwise explicit `REVISION_LINEAGE_UNRESOLVED` or `EVIDENCE_CONFLICTED`.

The source-receipt identity/fingerprint includes the immutable first observation and complete record lineage. Its **logical deduplication key excludes runtime time** so an unchanged replay returns `IDENTICAL_REPLAY` and preserves the original first observation. A changed payload under the same source filing identity never overwrites the old row: retain the incoming immutable receipt, then classify it only as an exact revision/cancellation when parent evidence is already explicit; otherwise record a conflict. A different source filing identity is a different receipt even if dates or names look alike.

`ProspectiveScheduleCollectionRunReceipt` should reuse the existing `EarningsScheduleCoverageReceipt` semantics rather than recreate its coverage fields. It records successful partial polls, source failures, parse/schema failures, pagination incompleteness, identity failures, and conflicts. It must set `SOURCE_SCOPE_UNPROVEN`, `pagination_complete=false`, and no absence certificate for the current routes. A new snapshot family is a typed use of an existing immutable receipt store; it is not a calendar-table migration or a parallel raw-data system.

## First-observed, restart, and failure rules

At the future collector's actual I/O boundary, capture one aware-UTC `retrieved_at` immediately after bounded response bytes are obtained. Bind it to the response fingerprint before parsing or queueing. This is the only value eligible to become `SYSTEM_FIRST_OBSERVED`; `processed_at` may describe later parsing/persistence but cannot replace it. On restart or delayed queued work, the persisted first-observed instant remains unchanged. A naive clock, absent run identifier, non-monotone sequence within a run, or missing payload fingerprint fails closed.

| Condition | Required collection receipt | Prohibited conclusion |
| --- | --- | --- |
| HTTP/TLS/timeout | `FAILED` coverage receipt with bounded safe source error | no notice / no event / clearance |
| Parser or schema change | `PARTIAL` or `FAILED` receipt with exact parser-state reason | fallback parsing or guessed purpose |
| Pagination/window uncertainty | `PARTIAL` receipt; all completeness flags false | complete-window absence |
| Exact identity fails | retained source evidence plus `IDENTITY_UNRESOLVED` | name-based association |
| Explicit purpose ambiguous | retained source evidence plus `PURPOSE_AMBIGUOUS` | qualifying event |
| Material changed source payload | immutable incoming receipt plus `EVIDENCE_CONFLICTED` unless exact parent lineage proves lifecycle | overwrite or arbitrary latest selection |
| Exact cancellation/reschedule parent exists | independent lifecycle receipt with its own first-observed time | retroactive alteration of prior receipt |

NSE and BSE are independent source observations. Either can start a positive source receipt; neither proves the other source absent. A future reconciler may form one logical calibration event only from exact canonical identity, retained source receipts, compatible purpose/date/lifecycle evidence, and an explicit reconciliation state. Until then, both provenance chains remain separate and a calibration event is not double-counted.

## Outcomes, layers, and canary

Existing `CorporateFilings`, `FinancialFacts`, and their filing lineage make later actual-result attachment **`PARTIAL`**: evidence exists, but no exact schedule-to-result reconciliation is implemented. The only future allowed link is exact filing/source lineage or separately governed evidence—not issuer/date matching. This does not block starting schedule receipts. Canonical daily OHLCV opens and closes are **`READY`** for the already-approved price-outcome formulas after a reaction session is proven; no new market-data source is needed.

The receipt collector starts **Layer 1** `MARKET_EVENT_RISK_CALIBRATION` evidence. It does not make **Layer 2** `HSI_ACTION_IMPACT_CALIBRATION` ready: the latter remains `PARTIAL` until a future genuine prospective, versioned setup/signal/gate/paper-outcome chain exists. Historical opportunities must not be fabricated.

A future canary is bounded to the already resolved 31 identities, uses existing official paths, emits only source and coverage receipts, and proves replay and revision behavior. It may not run as an unbounded daemon in this slice. It must not invoke Gate 6, signals, `ENTRY_READY`, portfolio code, broker/order code, or an outcome optimizer. The absence of a currently scheduled notice for one or all 31 companies is a valid empty positive-discovery observation, not an adapter failure and not a clearance.

## Readiness matrix

| Capability | State | Why |
| --- | --- | --- |
| NSE positive discovery | `PARTIAL` | Public rolling RSS and exact linked document parsing work; no complete company/window feed. |
| BSE positive discovery | `PARTIAL` | Public recent list and exact mobile detail parsing work; discovery is incomplete. |
| 31-company identity | `READY` | Existing accepted current NSE/BSE bridge resolves 31/31. |
| Purpose classification | `READY_FOR_OBSERVED_VARIANTS` | Explicit structured/affirmative rules only. |
| Automatic first-observed capture | `NOT_READY` | Contract exists; no active automatic capture boundary. |
| Raw source-row evidence retention | `PARTIAL` | Existing raw schedule mechanics exist but no prospective receipt owner for unproved source time. |
| Idempotency | `PARTIAL` | Candidate-store rules exist; prospective logical receipt replay is not implemented. |
| Revision/cancellation linkage | `PARTIAL` | Exact lifecycle mechanics exist; live prospective parent linkage is not produced. |
| Coverage receipt | `PARTIAL` | Typed model exists; no collector writes it. |
| Negative absence proof | `NOT_READY` | No exact source window, pagination, or revision completeness. |
| Actual-result linkage | `PARTIAL` | Filing/fact evidence exists; reconciled schedule-to-result link does not. |
| Price outcomes | `READY` | Existing canonical 1D OHLCV is available once reaction session is proven. |
| ATR | `PARTIAL` | Optional until its decision-time lineage is bound. |
| MFE/MAE | `OPTIONAL_ENRICHMENT` | Outcome-window/reference policy remains unset. |
| Slippage | `OPTIONAL_ENRICHMENT` | Measured bid/ask/execution lineage is absent. |
| Layer-2 HSI opportunity lineage | `PARTIAL` | Not required for Layer-1 positive schedule receipt collection. |

## Protected state and next continuation

This audit preserves `V1_ACTIVE=TRUE`, `GATE_POLICY_V2_ACTIVE=FALSE`, `SIX_GATES_EXACTLY_SIX=TRUE`, `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`, `NO_RETROACTIVE_BLACKOUT=TRUE`, `NO_FUTURE_LEAKAGE=TRUE`, `NO_HORIZON_GUESS=TRUE`, `PROSPECTIVE_FIRST_OBSERVED_ONLY=TRUE`, `PILOT_SIMPLICITY_RULE=ACTIVE`, and `AI_DECISION_AUTHORITY=FALSE`.

The exact next continuation is **`EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1`**. It is not started by this readiness audit.
