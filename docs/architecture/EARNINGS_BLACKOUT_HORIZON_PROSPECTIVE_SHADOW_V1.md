# Earnings Blackout Horizon Prospective Shadow V1

Status: `PROSPECTIVE_SHADOW_ACCUMULATION_ACTIVE / NON_ACTIVE_GATE_POLICY / WATCH_ONLY / NON_EXECUTABLE`.

Baseline: `6e1b3b675f9a6b7da671a5af98e9cc1030114567`. Authority: the bounded
`EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1` user directive. Accumulation
means an available one-shot shadow boundary, **not** a daemon, scheduler,
production decision integration, calibrated horizon or automatic activation.

## Authority and canonical reuse

This implements only the Layer-1 measurement definitions in the frozen
[calibration contract](EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.md)
and its [machine contract](EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.json).
Their earlier implementation/persistence restrictions describe the earlier
design checkpoint; this later explicit directive authorizes only the typed
shadow use of the existing snapshot repository. Those artifacts are unchanged.

Contract: `earnings-blackout-horizon-calibration-contract/v1`.
Fingerprint: `sha256:4b9a920620d1dfeebaa247721b234b60d7715b86e2cec0d436019719b1026a5b`.
Implementation/runner version: `earnings-horizon-prospective-shadow/v1`.

| Existing owner | Reuse, not a replacement |
| --- | --- |
| [Prospective collector](EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1.md) | Qualified schedule, official raw artifact, parsed detail, discovery, assessment, coverage and failed/partial poll receipts |
| [Identity bridge](../../app/filings/earnings_schedule_identity.py) | Exact NSE/BSE identity replay at the original observation timestamp; compare original identity fingerprint |
| [Known-at contract](../../app/filings/earnings_schedule_known_at.py) | Original immutable first-observed receipt and separately proven public timestamp semantics |
| [Schedule lifecycle](../../app/gates/official_earnings_schedule_candidate.py) | Existing lifecycle enum; explicit collector parent chain; no Gate engine dependency |
| [Exchange calendar](../../app/historical/canonical_market_session_event_time.py) | PIT-visible holiday/weekday/special-day evidence, regular session phases and exact adjacent-session resolution |
| [Daily temporal evidence](../../app/market_data/daily_technical_bar_temporal_evidence.py) | Canonical daily-bar session, completeness, availability and source-timing proof |
| [Canonical market bridge](../../app/market_data/bridge.py), [technical engine](../../app/analysis/technical.py) | Existing bar conversion and ATR14/Wilder calculation; no new ATR formula or technical series store |
| [CorporateFilings](../../app/filings/models.py), [FinancialFacts](../../app/fundamentals/models.py) | Exact official result relation and optional fact-to-filing lineage, without financial metric derivation |
| [Filing timestamp provenance](../../app/historical/filing_timestamp_timezone_provenance.py) | Exact source timestamp resolution; no timezone or source-publication invention |
| [Core snapshots](../../app/storage/core_api_snapshot_repository.py) | One additive enum family in the existing immutable table; no migration or separate calendar/outcome database |

Existing candidate reconciliation requires public-PIT candidate contracts and
does not establish economic equivalence from a company/date. The shadow does
not manufacture those candidates from unproven public timestamps. It applies
the conservative prospective reconciliation below to the existing collector
contracts instead. Existing paper/experiment promotion governance remains
separate; there are no synthetic entries or experiment/horizon selections.

## Admission, first-observed and source debt

`QualifiedShadowInput` verifies receipt, source observation, raw artifact and
exact identity resolution. The runner additionally verifies persisted envelope
identity/fingerprint, detail-to-discovery/raw links and qualified assessment.
Discovery-only, ambiguous-purpose or unresolved-identity rows never admit an
event. The initial date must be strictly later than the local date of completed
observation; first-seen-on-event-day notices are not invented as prospective.

The original `HSI_FIRST_OBSERVED_AT` is inherited byte-for-byte in its canonical
receipt, never generated from run time, event date or result publication.
**Collector v1 stamps the request start before fetch completion.** Therefore
shadow `known_at` deliberately uses its later `processed_at` as a conservative
completed-observation bound. Original first-observed remains source-lineage
and notice-lateness evidence, not an assertion of knowledge during the fetch.
No public-time authority or calendar clearance is conferred.

The collector is large; include it in the later repository-wide shared-logic /
complexity audit, including request-start versus post-response observation
precision. It was **not refactored** in this slice. Inferred generic revisions
without matching explicit source lifecycle are excluded as conflicted here.

## Logical event and immutable lifecycle

An exact parent chain identifies versions of the same source filing. Parent
instrument/source identity must match, effective time must increase, cycles,
missing parents, branches and reopening terminal parents fail closed. Exact
duplicate inputs reuse evidence; differing content under one identity rejects.

For independent notices of one instrument, overlapping notice-to-event intervals
form a **reconciliation/exclusion group**, not a guessed economic join. Multiple
roots are eligible only if their effective official document-byte fingerprints,
date, purpose and lifecycle agree. Otherwise the group is
`LOGICAL_EVENT_RECONCILIATION_UNRESOLVED / CONFLICTED` and contributes no
calibration-eligible event. Distinct non-overlapping later notices can proceed.
This intentionally conservative rule may exclude genuine dual-exchange events;
no date proximity, fuzzy names, inferred reporting period or source preference
can falsely count them twice. All source receipts remain in their original store.

Logical identity hashes `(implementation version, exact instrument, earliest
root scheduled date)`. It is stable when another exchange later supplies the
same document or a properly linked reschedule arrives. Conflicting overlapping
roots remain exclusions. Version/content fingerprint includes sorted source
versions, their first-observed/processed boundaries, lifecycle and reconciliation
state. Run time is not an event identity input. Raw downloads are referenced,
**not copied into every shadow record**.

| Stage | Descriptive state / rule |
| --- | --- |
| Qualified notice | `SCHEDULE_OBSERVED`, or `RESCHEDULED` for an exact effective reschedule |
| Session tracking | Immutable `ShadowSessionObservation`; separate decision cutoff and quality |
| Explicit cancellation/supersession | `CANCELLED`; retain old observations, exclude later outcomes |
| Broken/ambiguous source chain | `CONFLICTED`; no eligible session creation |
| No explicit result relation | `PENDING / RESULT_LINK_PENDING` |
| One exact result | `LINKED`; result observed separately from prior session truth |
| Insufficient temporal/price evidence | `TEMPORAL_OUTCOME_INCOMPLETE` with reason |
| Measurable result | `OUTCOME_READY`; not policy/promotion eligibility |

No disappearance-based cancellation. Versions effective after a decision are
excluded at that decision. Later runs load stored session records, retaining
their exact earlier schedule and market evidence when attaching later outcomes.

## Session observations and optional enrichment

The caller supplies an explicit timezone-aware decision cutoff and canonical
daily input. A session observation requires a closed, PIT-usable daily bar for
that session, received by that cutoff; provider/exchange timestamps must not
be future. Source/provider conflicts block that input. Conflicting data must
be supplied with its canonical reader's conflict state, not hidden by selection.

`TRADING_SESSIONS_TO_EVENT` counts canonical sessions **strictly after** the
decision session through the **exact** scheduled session. Zero is observable
on the scheduled day, but is not proof that publication is still in the future;
the outcome temporal check must establish that separately. A holiday,
unmappable date, missing calendar evidence or non-standard session makes that
distance unavailable; there is no next-day repair, calendar-day substitution
or 2/3/5/7 grid. No horizon is selected.

Sessions can be supplied ex post only when the original prospective receipt
was known at their cutoff. Later bars/changes do not enter that snapshot.
Stored observations carry event ID, schedule versions and original first-observed
receipt, decision time/date, distance, notice-distance, daily and temporal
fingerprints, calendar fingerprint, ATR lineage, available benchmark references,
mode, quality and explicit unavailable fields.

ATR uses the existing **ATR14** calculation with its Wilder smoothing and at
least 15 contiguous, same-adjustment-basis, PIT-visible canonical daily bars.
It reuses the existing market-observation conversion; the technical engine's
required version reference names this shadow artifact, not an executable or
persisted strategy. No generic strategy/result rows are created. Optional
supplied analysis snapshots must exactly match canonical inputs. Unsupported
technical source selection stays unavailable. Missing ATR does not invalidate
other event evidence or raw gap metrics.

PIT-valid `NIFTY_50`/`NIFTY_500` daily references can be retained without a new
benchmark calculation. Sector-context attachment remains explicitly unavailable:
the existing current-descriptive sector assembler is not proof of event-time
PIT membership. No sector mapping is inferred or falsely upgraded.

Notice-lateness is original first-observed local date → event session distance
under the same canonical calendar. It measures source feasibility only; the
request-start precision limitation is retained above. No early/late threshold
or optimal blackout number is asserted.

## Result links and Layer-1 outcomes

Only a primary-exchange `CorporateFiling` of type `FINANCIAL_RESULTS`, matching
the exact canonical instrument, can link. Its canonical
`board_meeting.related_filing_id` must explicitly identify an admitted schedule's
source filing on the same exchange. No nearest-date, fiscal-period or company-name
join. Multiple different explicit results are `AMBIGUOUS`; revisions are not
arbitrarily picked. Optional FinancialFacts must point to that filing/instrument
and be visible at the outcome cutoff. Their lineage is retained, not scored.
Current production availability of such explicit result relations is unproven;
ordinary unlinked results remain pending.

Exact public dissemination requires both canonical timestamp provenance and
separately proven field-role semantics. Legacy normalized time, date-only or
naive raw source time does not supply it. Raw local time is retained without
inventing a timezone. Publication must be later than the frozen session cutoff.

| Publication relationship | Outcome behavior |
| --- | --- |
| Before regular open | Same proven regular session |
| At/after regular close | Next proven regular exchange session (existing inclusive close boundary) |
| During regular session, including exact open | Incomplete: no governed intraday reaction path in this slice |
| Date-only, timezone ambiguous, unknown/non-standard session | Incomplete, no time/session guess |

The gap denominator must be the frozen close of the **immediately preceding**
regular session. Earlier session features remain available for distance-curve
analysis but their multi-day return is not mislabeled an opening gap. The
reaction daily bar must be unique, complete and visible by the outcome cutoff,
without conflict or adjustment-basis mismatch.

With `C` = previous visible close, `O` = reaction open, `R` = reaction close:

- Signed opening gap: `(O - C) / C`.
- Absolute opening gap: `abs((O - C) / C)`.
- Reaction-session return: `(R - O) / O`.
- Absolute reaction-session return: `abs((R - O) / O)`.
- ATR-normalized opening gap, only with canonical ATR lineage: `abs(O - C) / ATR`.

Positive denominators required. Decimal precision is fixed at 28 for these
mechanical ratios, independent of ambient process precision. Unknown adjustments
stay UNKNOWN; matching UNKNOWN is not proof of corporate-action neutrality or
total-return comparability. Metrics are observed raw-price changes, not a causal
earnings effect, forecast, performance claim or executable opportunity.

MFE, MAE, post-event/volatility windows, tail cutoff, slippage and all Layer-2
action-impact measurements remain explicitly unavailable. No zero filling.
Per-metric readiness and `PARTIAL / ELIGIBLE / TEMPORAL_INCOMPLETE / CONFLICTED`
are descriptive; `ELIGIBLE` means only the implemented metric inputs are present,
not adequate sample size, OOS/prospective validation or active-policy approval.

## Persistence and operator boundary

Family: `EARNINGS_HORIZON_PROSPECTIVE_SHADOW` in the existing Core snapshot table.
No new relational table/index, migration, calendar store, market store or generic
outcome database. Stable evidence reuses event/session/link/outcome IDs; new
source versions append; later outcomes never overwrite session records.
Each explicit invocation can append a timestamped run audit receipt, separately
from evidence identity. Partial writes are recoverable via immutable reuse.

[Pure composition](../../app/filings/earnings_horizon_prospective_shadow.py),
[one-shot runner](../../app/filings/earnings_horizon_shadow_runner.py),
[operator command](../../scripts/run_earnings_horizon_shadow.py).

```powershell
python scripts/run_earnings_horizon_shadow.py --database D:/nse-stock-manager/data/nse_stock_manager.db --as-of 2026-09-13T07:05:40+00:00 --max-receipts 1000
```

Use an actual explicit current cutoff for a later operational run; never reuse
it as a source timestamp. This command consumes persisted collector receipts
for admission/lifecycle only. The callable `run_shadow_once` additionally accepts
the existing canonical calendar, bounded `SessionRequest` daily/history inputs,
official result evidence and reaction bars supplied by canonical readers. No
provider call is embedded. Missing enrichment stays pending; it needs evidence,
not new policy semantics. A genuine new receipt is automatically admitted on a
later invocation. Result attachment reuses stored sessions after reopening.

The default cap is 1,000 snapshots **per accessed family** (collector and shadow);
exceeding the cap fails before writes rather than silently truncating. Caller
session/result/reaction batches are bounded. Empty admission bypasses identity,
market and result-universe scans. With positives, callers may inject the existing
identity bridge to avoid reloading its canonical inventories. No overlap,
scheduler, transport, polling loop, token, browser or broker capability is added.

## Bounded current persisted-receipt canary

Exactly one production invocation, at `2026-09-13T07:05:40+00:00`:

| Measure | Result |
| --- | --- |
| Collector snapshots inspected | 184 |
| Qualified / admitted / open events | 0 / 0 / 0 |
| Session observations / linked results / ready outcomes | 0 / 0 / 0 |
| Partial source polls | 4 |
| Failed source polls | 20 |
| BSE `SOURCE_SHAPE_UNSUPPORTED` | 20 |
| Run state | `WAITING_FOR_QUALIFYING_EVENT` |
| Live event proof / live outcome proof | `PENDING_EVENT / PENDING_EVENT` |

Run ID: `earnings-shadow:ShadowRunReceipt:79299c01035cb040b96c11564b4cd0cc3cf877a17b6b3f8b6e325a22e800a1a3`.
Fingerprint: `sha256:79299c01035cb040b96c11564b4cd0cc3cf877a17b6b3f8b6e325a22e800a1a3`.
No network acquisition, fake events, market-wide rescan or large DB backup.
NSE zero-row partial discovery and BSE partial discovery/unsupported details
remain visible source debt, **not** evidence of no earnings event.

## Readiness, safety and next continuation

- `SHADOW_STRUCTURE_READY = PROVEN` by isolated tests, not by zero-event counts.
- `LIVE_SHADOW_EVENT_ADMITTED = PENDING_EVENT`.
- `LIVE_OUTCOME_COMPLETED = PENDING_EVENT`.
- Layer 1 structure ready; prospective live event/result proof still pending.
- Layer 2 `PARTIAL_NOT_IMPLEMENTED`; no hindsight setups or entries.
- `EVENT_RISK_HORIZON = POLICY_UNSET / CALIBRATION_REQUIRED`.
- `V1_ACTIVE = TRUE`; `GATE_POLICY_V2_ACTIVE = FALSE`; `SIX_GATES_EXACTLY_SIX = TRUE`.
- `NO_UNVERIFIED_CALENDAR_CLEARANCE`, `NO_RETROACTIVE_BLACKOUT`,
  `NO_FUTURE_LEAKAGE`, `NO_HORIZON_GUESS`, `PROSPECTIVE_FIRST_OBSERVED_ONLY` = TRUE.
- `SHADOW_EXECUTION_AUTHORITY = FALSE`; `AI_DECISION_AUTHORITY = FALSE`.
- `PILOT_SIMPLICITY_RULE = ACTIVE`.

No production Gate, Decision Score, signal, alert, portfolio, execution or
provider configuration change. Tests use synthetic isolated databases and
existing collector/calendar/bar/timestamp/ATR contracts. The full backend suite
is not required: the only existing source edit adds a snapshot enum member;
no shared production runtime behavior changed.

Validation: **29 focused tests passed**; **336 combined focused/affected tests
passed** (0 failures, 0 skips, 0 warnings). The latter includes collector,
admission, identity, known-at, coverage, lifecycle, source adapters/discovery,
calendar, daily timing, filing timing, technical calculations and calibration
contract tests. **279 local Markdown links passed** across this document and
README; edited Markdown whitespace and `git diff --check` passed. The single
production shadow run reopened with its original fingerprint verified and
exactly one row in the new family. No full DB scan or backup was performed.

Final: `SHADOW_PIPELINE_READY_WAITING_FOR_LIVE_EVENT`.
Exactly one next continuation: `GATE3_SURVEILLANCE_SOURCE_READINESS_V1`.
It is **not started** by this slice.
