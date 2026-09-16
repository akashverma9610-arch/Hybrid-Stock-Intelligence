# Opening Gap / Overnight Intelligence operational closure V1

Baseline: `b5a6b612b7f65924abbd8d715213327a549ca817`, `main`.
Accepted predecessor: [Catalyst/Event closure](CATALYST_EVENT_INTELLIGENCE_OPERATIONAL_CLOSURE_V1.md).

Decision B: `OPENING_GAP_OVERNIGHT_INTELLIGENCE_OPERATIONAL_WITH_SOURCE_GAPS`.
This is a **bounded current-descriptive reported-open path**, not a live opening
canary or proof that today's reconstructed historical prices were known at an
earlier opening decision. Strict historical PIT remains blocked by the existing
certified reader. A source gap is not authorization to downgrade that request.

V1 remains ACTIVE; Execution Gate V2 remains NOT_ACTIVE. CAS primary-source
recovery, bootstrap/horizon work, advanced Gate-1 economics and Agent/Lyzr work
remain parked. There is ONE Brain and no new score or execution authority.

## Existing machinery and source readiness

| Area | Existing owner / contract | Finding and boundary |
| --- | --- | --- |
| Canonical price identity/provenance | `app.market_data.models.CanonicalOHLCVBar`, `InstrumentIdentity`, `MarketDataProvenance` | Reused, not replaced; source date/interval/received time are distinct. |
| Previous close and daily open | `nse_udiff_daily_technical_read`, `nse_udiff_daily_technical_eligibility` | READY conditionally for an exact certified adjacent NSE equity pair, current-descriptive only. Official reported close is not asserted to be a last trade, executable fill or auction equilibrium. |
| Provider alternatives | `upstox`, `nse_full_bhavcopy`, `historical` | Existing source stores remain unchanged. UNKNOWN adjustment/source timing cannot substitute for certified RAW observations. No fallback or source merge. |
| Session calendar | `canonical_market_session_event_time`, `nse_capital_market_session_evidence_2022_2026` | Reuse native `adjacent_trading_session` and source-visible day resolution, including holidays/weekends/special dates. Unknown coverage fails closed. |
| Security identity | `nse_udiff_effective_identity_coverage`, native daily certification | Exact source instrument/session/series/identity interval retained. Current symbol/ISIN mappings cannot stand in for historical identity. |
| Historical availability | Native `STRICT_HISTORICAL_PIT_TECHNICAL` reader mode | SOURCE_NOT_READY; always blocked, unchanged. Current-descriptive results cannot be relabelled as strict replay. |
| Daily availability | `daily_technical_bar_temporal_evidence` | Existing timing resolver distinguishes explicit, source-contract, forward observation and unresolved timing. Not used to backdate UDiFF retrieval or claim per-field opening publication. |
| Dhan prospective | `dhan_live`, `dhan_live_bar`, `prospective_fifteen_minute_bar`, `canonical_fifteen_minute_technical_reader` | Implemented prospective LTP/closed-minute evidence, but official session-opening observation/basis is SOURCE_NOT_READY here. First arbitrary tick/bar is not the open. No socket opened. |
| Pre-open | Calendar PRE_OPEN phase versus market-data session state | PREOPEN_SOURCE_NOT_READY; no retained validated auction indication admitted. Does not block certified daily reported-open facts. |
| Corporate actions | `technical_source_basis_action_coverage`, native daily certifier | Complete exact-window coverage and continuity required. Split/bonus require their separate derivation gate; rights/dividend/complex/lifecycle changes block this raw pair. No mechanical-gap inference. |
| Adjustment engine | `technical_price_adjustment_integrity` | Existing split/bonus derivative semantics are unchanged, not mixed into this RAW path. No dividend/total-return adjustment invented. |
| Raw gap | New `app.intelligence.opening_overnight` | Conditional READY mathematical evidence only; exact equations below. |
| ATR/volatility | `analysis.technical.TechnicalAnalysisEngine.atr`, `market_technical_artifact`, approved Pre-Breakout inputs | Existing ATR/Wilder calculation is implemented. Aligned prior-cutoff ATR on the same admitted basis is not supplied by this pair reader: normalization UNAVAILABLE, not a fabricated 14-bar calculation or significance threshold. |
| Benchmark/index open | Canonical index observations and official/provider index stores | SOURCE_NOT_READY for a certified aligned index open/prior-close pair here. Equity certification must not authorize an index merely because dates align. |
| Sector-relative opening | Canonical sector index/ranking inputs | SOURCE_NOT_READY for matched opening pairs. Closing-return rankings are not opening-gap differentials. |
| Overnight catalysts | Existing `StoredIntelligenceArtifact` NEWS_CATALYSTS references from accepted filing/News adapters | OPERATIONAL exact known-at window association; primary/secondary/conflict/freshness metadata retained. No causal claim. |
| Macro/global/policy | `MacroNewsEvidenceStoredSource`, `sector_economics`, `company_sensitivity`, policy-transmission research | Existing Brain context remains separate. No new global, commodity, FX or rates feed; policy transmission stays research-only. |
| Market regime / extremes | Existing market-regime diagnostics and `crisis` evidence | Not derived from a gap. `REPEATED_GAP_UPS` evidence vocabulary is not an approved single-gap euphoria rule. |
| Market-wide opening breadth | Existing `MarketBreadthObservation` and aggregation | NOT_EVALUATED; LTP-versus-previous-close breadth is not opening breadth. No full-market denominator/percentage claimed. Each successful projection covers exactly two daily observations for one security. |
| Portfolio / Watch | Existing instrument-centric Brain output contexts | Can explicitly compose this evidence source for a holding/candidate; no portfolio read/write or automatic action, Watch mutation, default UI or API integration added. |
| Setup / TradePlan | Existing Pre-Breakout/setup, `app.signals.models.TradePlan` and gate TradeManagementPlan contracts | Remain technical/structural. No new entry/trigger/stop/target/R:R or gap-driven invalidation rule. |
| Six Gates / circuit | V1 Gate 3 surveillance, Gate 4 plan, Gate 6 earnings | Separate authoritative inputs and thresholds unchanged. Gap facts neither prove band proximity/tradability nor grant a gate PASS. |
| Execution feasibility | `execution_simulation.service.ExecutionFeasibilityService` | Existing spread/slippage/size/liquidity/circuit/fill requirements remain separate. Missing evidence remains RESEARCH_REQUIRED, not permission to infer execution from a gap. |

The prior [session-price applicability audit](GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1.md)
remains intact. In particular, this slice does not resolve CAS membership,
closing-price formation, homogeneous auction research endpoints or executable
prices. It compares the admitted **reported** daily fields, not those unavailable
economic/execution concepts.

## Exact implemented semantics

`build_opening_overnight` delegates source selection to the unchanged certified
UDiFF reader. No raw values can be supplied in place of that reader's result.
The new immutable result retains its complete native read/certification, calendar
fingerprint, exact cutoffs, price facts, event references and blocker codes.

1. Resolve the previous exchange trading session at the explicit evaluation
   as-of with the canonical calendar; never subtract one calendar day. Require
   native certified expected sessions exactly `(previous, current)` and two bars.
   Missing security trade data cannot be skipped by selecting an older close.
2. Require NSE equity/INR identity, native RAW continuity certification, positive
   finite prior close/open and nonzero recorded session volume. No trade or a
   missing open yields no numerical gap. Known suspension/delisting/action
   discontinuities are delegated to the existing certifier. These facts do not
   establish current tradability or that a suspension was lifted.
3. Require each selected bar's end and received timestamp no later than as-of.
   This additional guard does not override native strict-PIT rejection. A
   complete daily bar cannot be used at its earlier opening time merely because
   it contains an `open` field.
4. Calculate `gap_inr = current_open - previous_close` and
   `gap_pct = (current_open / previous_close - 1) * 100`, using Decimal with a
   fixed 34-digit arithmetic context, independent of the caller's Decimal
   precision. This is numerical representation, not a materiality threshold.
5. Positive/negative/exact-zero differences mean GAP_UP/GAP_DOWN/FLAT. FLAT
   means exactly zero, not "immaterial" or a tolerance band. Failed price reads
   yield INSUFFICIENT_DATA, or CONFLICTED for native conflict/ambiguity reasons.
   Blocked outputs have no open/close/gap values exposed as accepted facts.
6. Event interval is `(prior_decision_cutoff, event_window_end]`. Both are
   explicit timezone-aware decision cutoffs on the previous/current session
   respectively; end must not exceed evaluation as-of. No unproven official
   market-close/open timestamp is invented. This window does not itself certify
   the availability of the later-observed price pair.
7. Accept only exact-security NEWS_CATALYSTS references with all native temporal
   fields present. `available_at` must be inside the interval; observed/evidence
   times must not exceed its end. A later article revision cannot explain an
   earlier opening. Missing known-at is rejected, not substituted with runtime
   time. Exact duplicate references coalesce; differing fingerprints for one ID
   remain explicit conflicts. Same ID/fingerprint with contradictory metadata
   is rejected. Future evidence does not change the earlier result.
8. Retain primary/secondary availability and explicit conflicts, not AI prose.
   An event conflict is a separate warning and conflicted Brain evidence; it
   does not alter an independently valid mathematical gap. No eligible references
   means unavailable context, not a claim that no material news occurred.
9. Output is always WATCH_ONLY / NON_EXECUTABLE. Freshness/materiality/causality,
   pre-open, normalized gap and benchmark/sector-relative fields remain explicit
   unavailable reasons. No prediction of continuation/fade or large-gap label.
10. Native source serialization, normalized UTC timestamps and deterministic
    reference ordering participate in a versioned SHA-256 content fingerprint.
    The content-addressed artifact identity has no wall-clock input. Verification
    recomputes the projection and rejects tampered values, fingerprint or authority.

## Brain and downstream composition

`OpeningOvernightEvidenceSource` implements the existing read-only Brain source
interface and supplies MARKET_DATA metadata with the full projection fingerprint.
It returns evidence only for the exact instrument and evaluated cutoff; it cannot
backdate or relabel a prior artifact. No new Brain domain or persistence is added.

The integration fixture passes it through the existing
`StoredSharedBrainEvidenceAssembler(..., market_technical_artifacts=source)`
composition slot. Native Brain aggregation receives PARTIAL descriptive evidence
(or CONFLICTED/UNAVAILABLE), never a score or gate decision. The complete numeric
projection remains available to the caller through its deterministic serializer.

This is explicit stored-evidence composition, not an installed automatic live
job. Default HTTP/worker flows are unchanged; no new endpoint or product is
activated. A future live source binding must supply independently approved open,
basis and timing evidence. It may not downgrade strict historical requests or
reinterpret arbitrary Dhan minute bars. Retrospective current-descriptive output
must stay labelled as such in every future consumer.

Rule 57 still needs its typed event and post-publication bars. Existing price/
structure and volatility diagnostics retain their own meanings; no additional
gap-pattern diagnostic is claimed. No Rule 62, registry change or new Decision
Score weight is introduced. Gate 3 continues
its authoritative ASM/GSM/circuit checks, Gate 4 its approved plan checks and
Gate 6 its verified earnings blackout. No opening artifact can grant PASS.

The authority boundary is explicit: `GAP_UP != BUY`, `GAP_DOWN != SELL`,
`large gap != automatic opportunity`, and `event + gap != causal proof`.
The implementation does not classify a gap as large or create any trade action.

## Proof and remaining gaps

Fixtures cover positive/negative/exact-zero values, weekend/holiday/special
sessions, nonadjacent missing-session rejection, event window endpoints,
duplicates/conflicts/future revisions, corporate actions, suspension/delisting,
missing/no-trade prices, source-basis/coverage/identity failure, historical PIT
rejection, tampering, UTC/Decimal determinism and native Brain composition.
The aligned-index fixture is intentionally a **fail-closed source-gap proof**,
not a successful benchmark differential: no approved index pair is manufactured.

No live source canary, acquisition, production DB access, portfolio mutation,
broker/order operation, source/schema/policy modification or remote push is part
of this slice. Only the new projection, its focused tests and this audit are added.

Remaining: live official opening observations/basis; historical opening-time
availability; pre-open; benchmark/sector opening pairs; aligned prior ATR;
market-wide coverage/denominator; automatic source composition; event-specific
freshness/materiality/causality policies. These are explicit source/product gaps,
not false claims of a complete real-time opening product.

## Validation and defensive review

- Focused opening/overnight tests: **34 passed**.
- Relevant daily/session/action/event/Brain/setup/gate/score regressions:
  **220 passed, 2 warnings**.
- Relevant Dhan/prospective-bar/action/Market-Extremes/Brain regressions:
  **76 passed**.
- Complete backend suite: **8,643 passed, 0 failed, 6 skipped, 2 warnings**;
  exit code 0. Skips are existing opt-in live-provider/PostgreSQL checks.
  Warnings are existing TestClient/httpx and anyio deprecations.
- Defensive review added an explicit NSE-equity/INR guard in this new consumer:
  aligned index dates do not confer equity-source certification authority.
  Existing certifier and Core behavior remain unchanged.
- Local documentation links, whitespace and staged `git diff --check` must pass
  before the three-file local commit. No existing tracked source is changed.

Exactly one next frozen continuation:
`SIGNAL_LIFECYCLE_OPERATIONAL_CLOSURE_V1`.
Not started.
