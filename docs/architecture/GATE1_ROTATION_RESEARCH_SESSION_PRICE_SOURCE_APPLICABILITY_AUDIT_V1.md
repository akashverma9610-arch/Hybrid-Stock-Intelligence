# Gate 1 research session and price source applicability audit V1

Status: `SOURCE_APPLICABILITY_AUDIT / NO_PARAMETER_APPROVAL / NOT_ACTIVE`

Slice: `GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1`

Audit: `gate1-rotation-research-session-price-source-applicability-audit / v1`

Baseline: `43da29f531990c47fa605c08c494e7b4adf7f182` on `main`.
Disposition: **ACCEPTED/CLOSED** (audit complete; prerequisites remain blocked).

## Decision and scope

**C — `SESSION_PRICE_SOURCE_APPLICABILITY_SOURCE_GAPS`**

The official global live date and CAS close mechanism are recovered, but the detailed security-master applicability specification, dated membership/revision evidence and legacy non-CAS close clause are not recovered. Existing capture/identity/PIT primitives do not prove security-specific regime at D or terminal price admissibility. Audit closure is not source, parameter or research activation.

The answer is **not yet**: security-specific regime at original D and terminal
boundary is not proven. This does not erase implemented calendars, identity,
daily/intraday evidence or integrity controls. This is one governance/source
audit, not a classifier, policy, producer or cohort. No production DB contents,
credentials, live provider, portfolio or broker/orders were accessed.
Production coverage counts are **not measured**. DB presence was checked only.

## Canonical artifact and preservation

[Machine-readable audit](GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1.json) contains exact inventories, 18 matrix rows,
price candidates, boundary cases and rejection rules. Its content fingerprint:
`sha256:e587cfb98e32610f6a0485c87d62a8546400ac19498c0aef18ad0b38b22e967c`.

Existing `content_fingerprint` / `canonical_json` exclude only
`artifact_fingerprint`; source pins normalize CRLF to LF. No clock-dependent
interpretation. [Independent-prior predecessor](GATE1_ROTATION_RESEARCH_BOOTSTRAP_INDEPENDENT_PRIOR_EVIDENCE_V1.md)
remains `INDEPENDENT_PRIOR_EVIDENCE_PARTIALLY_SUFFICIENT`,
`sha256:b2c7e7913384dce1b76691d89cb59a9b38737f9fb365eed3392a0f55292359f6`.
[Parameter proposal](GATE1_ROTATION_RESEARCH_BOOTSTRAP_PARAMETER_POLICY_PROPOSAL_V1.md)
remains UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE,
`sha256:e751cc6d7f4585d58b081ed9be9d876d399166059cb6d4836f7ff062ce7d8eb3`.

All **nine** predecessor JSON fingerprints and **153**
frozen source/document/test pins are preserved, including active gates,
Decision Score and TradePlan. Every effective parameter remains null.
No historical artifact, application, runtime, schema or source policy changes.

## Official evidence

Reviewed 2026-09-15 via extracted primary-source text. No raw response bytes
retained/hashed; no false historical HSI `known_at` or exact publication instant.
Audit hashing attests the dossier, not PDF bytes. Operational use later needs
immutable originals, native fingerprints, effective intervals and actual knownness.
Access failure is an audit-time limitation, not proof a document never exists.

| Source | Date / locator | Access / permissible use |
| --- | --- | --- |
| [O01: NSE/CMTR/75479 live CAS and separate mock notice](https://nsearchives.nseindia.com/content/circulars/CMTR75479.pdf) | 2026-07-30; p1 live date; p4 master delivery; p5 mock obligations | PRIMARY_BODY_READ; Qualified findings in JSON; no security membership inferred. |
| [O02: NSE/CMTR/73362 CAS SOP](https://nsearchives.nseindia.com/content/circulars/CMTR73362.pdf) | 2026-03-18; sections 1.1, 2.1-2.2, 5.1, 6 | PRIMARY_BODY_READ; Qualified findings in JSON; no security membership inferred. |
| [O03: NSE CAS product/session page](https://www.nseindia.com/static/products-services/closing-auction-session) | unknown publication; page updated 2026-08-12; Introduction; CAS Structure; session timings; circular list | PRIMARY_PAGE_READ; Qualified findings in JSON; no security membership inferred. |
| [O04: NSE/CMTR/73845 security-master modification](https://nsearchives.nseindia.com/content/circulars/CMTR73845.pdf) | 2026-04-22; Referenced by O01/O03; required detailed field attachment | BODY_UNAVAILABLE; Detailed body NOT admitted. |
| [O05: NSE/CMTR/74466 trading modalities](https://nsearchives.nseindia.com/content/circulars/CMTR74466.pdf) | 2026-05-29; Referenced by O01/O03; full modalities required | BODY_UNAVAILABLE; Detailed body NOT admitted. |
| [O06: NSE/CMTR/67774 legacy non-CAS close](https://nsearchives.nseindia.com/content/circulars/CMTR67774.pdf) | 2025-04-30; Section 3.4 referenced by O02 section 5.1.2 | BODY_UNAVAILABLE; Detailed body NOT admitted. |
| [O07: SEBI CAS introduction](https://www.sebi.gov.in/legal/circulars/jan-2026/introduction-of-closing-auction-session-cas-in-the-equity-cash-segment-and-certain-modifications-in-the-pre-open-auction-session_99122.html) | 2026-01-16; Landing metadata; linked PDF | LANDING_ONLY_BODY_UNAVAILABLE; Detailed body NOT admitted. |

The global live date is **2026-08-03**, not the mock date. [NSE live notice](https://nsearchives.nseindia.com/content/circulars/CMTR75479.pdf)
CAS close can be a reference rather than a new matched trade. [NSE SOP](https://nsearchives.nseindia.com/content/circulars/CMTR73362.pdf)
Current phases differ from the retained generic regular phase. [NSE CAS page](https://www.nseindia.com/static/products-services/closing-auction-session)

Exact timings, delivery metadata and bounded findings are recorded in JSON once.
O04 master-field names/codes/completeness/revisions, O05 detailed modalities and
O06 non-CAS section 3.4 remain unread. O07's landing cannot replace its PDF.
No third-party summary or remembered market rule supplies missing details.

Phased eligibility is not a permanent member list. Additions/removals,
per-security effectivity, revisions and special-day exceptions require dated
proof. A delivery schedule does not prove actual HSI receipt, or equivalence
between a public archive mirror and member extranet contents.

## Existing HSI inventory

Exact contract versions, source fingerprints, authority and coverage fields are
in JSON; IDs below identify existing owners, not proposed parallel components.

| ID / owner | Purpose / scope | Effective / known / coverage limitation |
| --- | --- | --- |
| I01: [app/historical/canonical_market_session_event_time.py](../../app/historical/canonical_market_session_event_time.py) | Date/phase/event-time resolution; explicit publication/effectivity/conflict evidence. NSE CAPITAL_MARKET; phase rows not security-specific. | Injected calendar bounds, not intrinsic universal history. Native source and phase intervals. Native known_at/published_at/date-only guard; no fabricated instant. DERIVABLE; needs security-regime binding. |
| I02: [app/historical/nse_capital_market_session_evidence_2022_2026.py](../../app/historical/nse_capital_market_session_evidence_2022_2026.py) | Annual holidays, amendments, selected specials and ordinary-forward phases. Generic cash segment weekday/continuous 09:15-15:30; no per-stock CAS. | 2022-01-01 through 2026-12-31; not complete all-regime timing. Ordinary-forward 2026-09-05; source-specific historical holiday/special dates. Ordinary source 2026-09-05T16:47:00Z; others retain dated notices. SOURCE_NOT_READY for general CAS-aware pair; individual holidays represented. |
| I03: [app/historical/nse_mii_security_master.py](../../app/historical/nse_mii_security_master.py) | Official date-labelled security IDs/status/type fields; complete prospective capture receipt. FinInstrmId/ISIN/symbol/series/status/list/removal/type; no typed CAS flag. | Caller supplied exact report date; actual archive span not audited. Report date is not automatic live applicability effective interval. document_observed_at/first_observed_at; historical_known_at absent. Existing complete-capture/reopen reusable; exact CAS parsing not implemented. |
| I04: [app/historical/nse_session_identity.py](../../app/historical/nse_session_identity.py) | Exact session identity with human-approved native provenance. Identity only; no company-type, tradability or CAS proof. | Each separately receipted session only. Approved session D semantics, no inferred interval. Session knownness is not precise intraday CAS announcement time. DERIVABLE for exact join once source recovered. |
| I05: [app/historical/security_identity_selector.py](../../app/historical/security_identity_selector.py) | Immutable effective/knownness identity selection; ambiguity rejected. Canonical ID, ISIN, exchange symbol/series; lifecycle changes need proof. | Supplied source intervals and lifecycle proof only. Native effective start/end. Native source as-of constraints. DERIVABLE not CAS membership. |
| I06: [app/market_data/models.py](../../app/market_data/models.py) | OHLCV/quote fields with provider/reference/timestamps/adjustment provenance. Exact canonical instrument; no CAS mechanism flag. | Individual received observations, not completeness. Bar interval or quote event; not applicability interval. Received timestamp plus optional exchange/provider timestamp. Reusable values; not executable fills or authorized research choices. |
| I07: [app/market_data/historical.py](../../app/market_data/historical.py) | Preserve observations/conflicts; as_of filters end and received_at; native canonicalization. Instrument/timeframe/provider keyed, not security-regime calendar. | Persisted rows only; no production counts inspected. Source bar bounds. Explicit as_of filters; caller must use it; date label alone not availability. Reusable store, not source precedence for Gate-1 price policy. |
| I08: [app/market_data/nse_full_bhavcopy.py](../../app/market_data/nse_full_bhavcopy.py) | Copies OPEN/HIGH/LOW/CLOSE_PRICE; exact supplied EQ symbol target. EQ plus supplied canonical ISIN target; not a historical symbol bridge. | Exact retained session file. Legacy midnight-labelled bar, not actual market close. retrieved_at; exchange label not publication. Existing importer not invoked; adjustment UNKNOWN. |
| I09: [app/market_data/nse_udiff_daily_history.py](../../app/market_data/nse_udiff_daily_history.py) | CM/NSE/STK exact identity, raw OHLCV; source row includes LastPric distinct from ClsPric. FinInstrmId/ISIN/symbol/series/session source lineage. | Retained report dates only. Logical daily interval midnight to next midnight, not close instant. observed_at; warning publication unknown. Reusable RAW bars; no CAS equilibrium/reference discriminator. |
| I10: [app/market_data/upstox.py](../../app/market_data/upstox.py) | Preserves provider candle interval-start; no declared session-end or adjustment guarantee. Exact provider mapping; equities vs index distinct. | Provider daily candles, actual coverage not queried. start_time=end_time source-start representation; session end unbound. received_at plus raw provider timestamp; not daily-close completion. Existing adapter remains operational; no network call here. |
| I11: [app/historical/nse_corporate_action_coverage.py](../../app/historical/nse_corporate_action_coverage.py) | Exact identity and action-date evidence; split/bonus factor completeness separated. Exact instrument/transition evidence; symbol-only insufficient for ambiguous action. | Bounded retained official receipts; no DB inspection. Native action effective/ex dates. Observed/publication lineage; not inferred from price change. Reusable provenance, not total-return policy. |
| I12: [app/market_data/technical_price_adjustment_integrity.py](../../app/market_data/technical_price_adjustment_integrity.py) | Immutable raw and split/bonus derivative lineage; complex actions fail closed. Exact instrument; raw/unknown/provider-adjusted/index basis separated. | Exact supplied bars and action window. Action effective_at <= as_of required. source_known_at <= as_of; native fingerprint. Reusable integrity; no Gate-1 return-method choice. |
| I13: [app/market_data/daily_technical_bar_temporal_evidence.py](../../app/market_data/daily_technical_bar_temporal_evidence.py) | Separates explicit publication, after-close source contract, forward observation, unresolved. Calendar phase context still needs correct security regime. | Per supplied bar/session evidence. Actual governed session end, not date-label end. Resolved/forward-only/unknown; strict PIT blocked when unproven. Reusable temporal rejection controls; CAS binding missing. |
| I14: [app/market_data/dhan_live.py](../../app/market_data/dhan_live.py) | Exact-mapped LTP with provider trade time, receive time, staleness. Mapped security-specific quote, not CAS final-price authority. | Current retained in-memory state; not historical tick archive. Provider trade event time. received_at not backdated. Existing live state; no connection made for audit. |
| I15: [app/market_data/dhan_live_bar.py](../../app/market_data/dhan_live_bar.py) | One-minute fully observed closed bars; no-trade/incomplete/conflict distinct. Current calendar binding lacks per-security CAS membership. | Prospective received events only. Only REGULAR_CONTINUOUS on regular day, selected at receive cutoff. Receipt/bar completion knownness, not retroactive capture. Reusable regular minute evidence; generic 15:30 close unsafe as CAS-wide assumption. |
| I16: [app/market_data/prospective_fifteen_minute_bar.py](../../app/market_data/prospective_fifteen_minute_bar.py) | Closed 1m lineage -> 15m; no-trade has no OHLC; no hole filling. Same calendar limitation, no CAS auction-price receipt. | Only complete constituent minute receipts. Explicit regular trading period, not arbitrary resample. Actual finalized receipt known_at; no historical invention. Reusable pure derivation; no full-market coverage claim. |
| I17: [app/market_data/canonical_fifteen_minute_technical_reader.py](../../app/market_data/canonical_fifteen_minute_technical_reader.py) | AS_OF_PROSPECTIVE_PIT vs CURRENT_DESCRIPTIVE; fail-closed missing/conflict/no-trade. Canonical per-instrument receipts, no new auction regime. | Only explicit retained receipt range. Requested period bounds, no boundary-price selection. known_at <= as_of for strict mode; descriptive mode not PIT. Reusable query boundary; not a research start/terminal policy. |
| I18: [app/historical_integrity/service.py](../../app/historical_integrity/service.py) | Delegates native fact/membership eligibility; VALID/PARTIAL/INVALID/UNAVAILABLE. Exact fact/universe identity; not price adjustment algorithm. | Supplied historical fact and universe records only. Native guard effective/lifecycle checks. Caller as_of and native metadata. Reuse facade plus adjustment contract, not a parallel integrity system. |
| I19: [app/market_data/nse_udiff_weekly_technical_bar.py](../../app/market_data/nse_udiff_weekly_technical_bar.py) | Aggregates verified eligible daily bars; completeness/receipt lineage retained. Not a terminal-price fallback or auction semantic normalizer. | Supported closed exchange weeks only. Explicit source/calendar week endpoints. Finalized derived receipt known_at; no future constituent use. Reusable technical evidence only. |

### Generic calendar and identity boundaries

The calendar has dated phases, holidays, amendments and selected special
sessions, not dates alone. PRE_OPEN/closing/closing-auction types exist, but
retained phases are **not security-specific**; the instrument argument in event
alignment does not resolve CAS membership.

Ordinary forward timing starts **2026-09-05**, known-at
**2026-09-05T16:47:00Z**, and cannot be backcast. It is not a safe pre-CAS regime.
Selected Muhurat/Budget sessions have phases; retained 2026 Muhurat has only
its date. Not every emergency or shortened session is covered.

Complete MII capture/reopen and **approved** exact-session identity already
exist; the older proposed knownness contract is not the only identity capability.
Reuse the approved path, but session identity is not an interval, intraday
publication, company-class or CAS receipt. Hashing unknown raw columns does
not interpret their semantics.

## Applicability requirements (not implemented)

Necessary conditions only, not a new runtime classifier:

| Outcome | Required evidence / fail-closed rule |
| --- | --- |
| CAS_APPLICABLE | Only positive exact dated membership under a verified effective and D-known policy; no assumption that all EQ or current derivative stocks were eligible historically. |
| NON_CAS | Only explicit dated non-membership, or exhaustive official scoped membership plus verified complement semantics, under a D-known effective policy. Global pre-live date alone is not a security/price classification. |
| UNKNOWN | Missing/partial/unread applicability, future publication/effectivity, unknown coverage, unmapped identity, unsupported segment, mock-only evidence or absent source; never promote absence in a partial list. |
| SOURCE_CONFLICT | Contradictory applicable official versions, identity collisions or unresolved exact-session regime conflict; retain both native fingerprints; no input-order winner. |

Each leg needs exact security/session membership, source/body/version,
effectivity, native knownness, complete scope or explicit negative evidence,
fingerprints/corrections and canonical ID/ISIN/token/symbol/series/class/segment.
No partial-list complement, current-member backcast, symbol-only join,
all-EQ inference or global-launch shortcut.

Candidate scope remains NSE cash equities or a separately approved narrower
set; no population selected. ETFs, SME, indexes, derivatives or other classes
are not silently included. Existing Core capabilities are not deactivated.

Identity states: READY only for verified exact native session identity;
DERIVABLE for a possible join using existing contracts; SOURCE_NOT_READY for
missing applicability; AMBIGUOUS for competing identities; BLOCKED for
invalid/future/unsupported mapping. **CAS join: SOURCE_NOT_READY.**
Renames/relisting/merger/demerger/suspension need dated lifecycle proof.
Stable identity does not imply tradability.

## Publication, D, effectivity, corrections and R

Keep publication date/time, effectivity, first-observed/native knownness and
correction/supersession separate. Reuse native semantics: calendar known-at,
then precise publication, then date-only publication strictly before cutoff
local date. Never invent midnight publication.

D classification requires session-effective and D-known evidence. Announced
future effectivity is not current membership. Late notices cannot authorize
earlier D. Corrections need explicit authoritative supersession **and** an
approved replay policy; original receipts remain immutable.

Original D and the frozen paired endpoint remain unchanged. Realized terminal
regime/price is proven later at R, after end/completion and known by R; never
use it to select D's binding or choose a better endpoint retrospectively.
Treatment of future regime changes remains POLICY_REQUIRED, not chosen here.

## Price candidates

Every candidate is a **market observation, never an executable fill**.
No price is selected and no complete production coverage is claimed.

| Candidate / fields | Owners | Timestamp / session | Adjustment / PIT / replay | CAS / research suitability |
| --- | --- | --- | --- | --- |
| DAILY_OPEN_HIGH_LOW: open, high, low | `I06`, `I08`, `I09`, `I10` | Source interval/label, not a time for each extrema. Daily session aggregation; open may be auction-derived; extrema not original-D instant. | UDiff RAW; full-bhavcopy/Upstox UNKNOWN. D can use only native-known complete evidence; full-day high/low cannot enter intraday D. BOUNDED stored versions; no counted coverage proof. | NONE explicit; POLICY_REQUIRED; extrema cannot be chosen as favorable entry/exit. |
| OFFICIAL_DAILY_CLOSE: close, CLOSE_PRICE, ClsPric | `I08`, `I09`, `O02`, `O06` | Legacy CSV label or UDiff logical date; not certified close dissemination time. Source-labelled close; formation varies by CAS regime and no-match condition. | UDiff RAW; full CSV UNKNOWN. Needs regime, official-field semantics, exact availability and action lineage. INSUFFICIENT for homogeneous D/end price. | SOURCE_GAP; POLICY_REQUIRED; not automatically final fresh auction trade. |
| PROVIDER_DAILY_CLOSE: close | `I10`, `I13` | Provider candle start; explicit end unbound. Provider aggregation, not proved official final exchange close. | UNKNOWN SOURCE_TIMING_UNRESOLVED unless native temporal evidence resolves it. INSUFFICIENT | NONE explicit; POLICY_REQUIRED plus source/adjustment proof. |
| LTP_QUOTE: last_price, ltp, provider_trade_timestamp, received_at | `I06`, `I14` | Last trade event may precede D; receipt time distinct. Live quote may be stale, not phase-completion proof. | Not a documented action-adjusted series. Only retained known-at evidence; current state never reconstructs historical D. ABSENT historical tick archive in live-state component. | NONE final-vs-indicative; POLICY_REQUIRED; no stale-LTP or perfect-fill inference. |
| SOURCE_LAST_PRICE: LastPric | `I09` | Daily row context, not an exact intraday quote. Raw UDiff LastPric and ClsPric distinct; LastPric not separate canonical OHLC close. | Raw source semantics require verification. Full artifact and native receipt required. BOUNDED source receipts; separate canonical projection not established. | NONE explicit; SOURCE_NOT_READY for dedicated research observation. |
| FINAL_CAS_PRICE: equilibrium_or_published_reference_close | `O02`, `O04`, `O05` | Actual auction result/publication and no-match flags needed. Published final vs indicative/no-match must be distinct. | Official source/action basis needs retained evidence. No canonical dedicated final CAS receipt verified. ABSENT typed CAS price history demonstrated. | SOURCE_NOT_READY; SOURCE_NOT_READY; do not reconstruct from daily/15m/LTP. |
| REGULAR_ONE_MINUTE: open, high, low, close, volume | `I15` | Explicit closed minute and receipt known_at. Regular-only phase; generic calendar not security-specific. | Native source basis plus separate adjustment checks. Strict finalized received-event lineage. BOUNDED prospective; no backfill. | NONE membership; POLICY_REQUIRED and security-regime exclusion before research use. |
| REGULAR_FIFTEEN_MINUTE: open, high, low, close, volume | `I16`, `I17` | Closed 15m constituent boundaries and known_at. Regular-minute aggregation; cannot cover unknown CAS or special session by default. | Preserved source/action basis; cannot mix. AS_OF_PROSPECTIVE_PIT only; CURRENT_DESCRIPTIVE not replay proof. BOUNDED receipt coverage. | NONE auction; POLICY_REQUIRED; no nearest bar to original D/end. |
| ADJUSTED_DERIVATIVE: derived_OHLCV, price_factor, action_receipts | `I12` | Raw event/interval plus action effective/known time. Comparable supported split/bonus action window only. | Versioned SPLIT_BONUS_ADJUSTED with raw fingerprints. All native action/source evidence PIT-valid. DERIVABLE for exact supported windows; other actions unresolved. | Does not establish underlying close regime.; POLICY_REQUIRED; not total-return/fill. |
| WEEKLY_OR_INDEX_CONTEXT: weekly_OHLCV, index_close | `I19`, `I06` | Aggregate period/index observation, not single-security D instant. Different observation contract; no substitution for pair legs. | Contract-specific; index basis separate. Own lineage needed, cannot cure missing security observations. BOUNDED context only. | No inferred CAS membership from index constituents.; NOT_APPLICABLE as automatic D/terminal substitute. |

Full-bhavcopy labels, UDiff daily intervals and Upstox interval-start are not
equivalent exchange-close instants. UDiff LastPric and ClsPric are distinct raw
fields; LastPric is not a separate canonical final-auction field.
Historical store as-of end/received filtering cannot supply phase/formation or
completeness. Its provider canonicalization is not research-price authority.

### Reconciliation

**PRICE_SOURCE_PRECEDENCE_POLICY_REQUIRED**.

No averaging or daily/live/CAS preference by convenience. Equal numbers do not
prove equal semantics. Align security/series, session, label versus interval,
availability, adjustment and final/indicative status first. Different last-15m
and daily closes need not mean corruption. No precedence or price is approved.

## Start-D coverage

| D case | Potential observations | Readiness / blocker |
| --- | --- | --- |
| BEFORE_OPEN | Earlier retained evidence may be D-known; a later opening print is not D-known. | POLICY_REQUIRED: No observation-at-D convention approved; do not roll D to opening auction. |
| DURING_REGULAR | Exact received quote or completed earlier interval may exist; in-progress/full-day future aggregate excluded. | SOURCE_NOT_READY: Exact security/phase/knownness and admissible relation-to-D policy required; no nearest bar. |
| DURING_CAS_OR_CLOSING | LTP, regular bars or indicative data can be different from final CAS result. | SOURCE_NOT_READY: Dated membership/phase and final-vs-indicative source missing; no substitution. |
| AFTER_CLOSE | Final daily/CAS source may not yet have been published/received. | PIT_NOT_READY: A scheduled close does not imply known price; no fill at reported close. |
| NON_TRADING_DAY | No same-session observation guaranteed; prior close is stale context. | POLICY_REQUIRED: No automatic prior/next-session roll or selection. |
| SPECIAL_SESSION | Only exact special-day phases and corresponding native observations potentially usable. | SOURCE_NOT_READY: Holiday/special date alone insufficient; no ordinary-timing assumption. |

No nearest bar, perfect fill, date roll or default previous close.
Future full-day extrema/close never enter intraday D-known evidence.

## Terminal coverage

| Terminal case | Potential evidence | Readiness / blocker |
| --- | --- | --- |
| REGULAR_CLOSE | Completed eligible session observation only if exact R-known evidence exists. | POLICY_REQUIRED: Endpoint convention and security-specific phase binding not approved. |
| CAS_CLOSE | Official final result or source-published reference with exact reason lineage. | SOURCE_NOT_READY: Dedicated CAS receipt and applicability history missing. |
| NON_CAS_CLOSE | Official non-CAS close field may exist. | SOURCE_NOT_READY: Recover O06 detailed semantics and exact source mapping. |
| SPECIAL_SESSION | Exact announced special phases and completion evidence. | SOURCE_NOT_READY: No ordinary end-time or post-hoc endpoint rewrite. |
| SUSPENSION | Status/identity receipts may establish suspension; price may be absent. | BLOCKED: No synthetic close; preserve unavailable; no automatic maturity extension. |
| MISSING_FEED_BAR | No exact observation at governed endpoint proven. | SOURCE_NOT_READY: Verified mature plus missing price stays excluded per parent; no nearest/carry. |
| DELISTING | Lifecycle receipt may establish delisting, not realizable liquidation value. | BLOCKED: No zero, final-LTP, delisting-consideration or carry-forward default. |
| CORPORATE_ACTION | Raw observations plus exact effective/PIT actions may be available. | POLICY_REQUIRED: Comparable basis/continuity required; no mixed/estimated adjustment. |

A source-published reference is descriptive evidence, not HSI fallback permission.
Before pinned end, PENDING_MATURITY retains its meaning. Verified maturity plus
missing exact terminal price is EXCLUDED/terminal observation missing under the
parent, not automatic non-maturity/deferral. No new lifecycle.
No-trade, suspension, missing feed and delisting cannot produce zero, carry or
nearest prices; delisting identity is not liquidation value.

## Corporate actions and exceptional sessions

Reuse Historical Integrity's native guard and technical adjustment contract,
not a second integrity engine or a new return method.

| Action | Readiness | Boundary |
| --- | --- | --- |
| SPLIT | DERIVABLE | Exact official PIT factor semantics and matching raw/action lineage; separately approved target basis. |
| BONUS | DERIVABLE | Exact official PIT ratio and immutable raw/action lineage; not arbitrary factor. |
| DIVIDEND | POLICY_REQUIRED | Existing DIVIDEND_PRICE_POLICY_NOT_APPROVED; no total-return substitution. |
| RIGHTS | SOURCE_NOT_READY | Existing RIGHTS_ADJUSTMENT_NOT_READY; no estimated entitlement/factor. |
| MERGER_DEMERGER | BLOCKED | Existing COMPLEX_ACTION_NON_COMPARABLE; exact continuity and consideration lineage required. |
| SYMBOL_SECURITY_RELISTING | BLOCKED | Existing SECURITY_CONTINUITY_NON_COMPARABLE until exact effective identity continuity is proven. |

Raw bars stay immutable; no adjusted/raw mixing, action inferred from price,
rights proceeds or total-return substitution. Start/terminal windows both need
exact source and identity continuity.

Muhurat/shortened/extraordinary sessions need explicit dated phase evidence.
Date-only notice does not authorize ordinary hours. Mock/test/simulation sessions
are not real trading and cannot count/mature research horizons. Unexpected
closure cannot rewrite the frozen endpoint; no live calendar repair here.

## Conflicts

| Conflict | State | Finding | Prerequisite |
| --- | --- | --- | --- |
| OFFICIAL_CAS_VS_GENERIC_CALENDAR | CONFLICTED | Generic 09:15-15:30 regular phase lacks security-level CAS selection. This is a retained-scope mismatch, not evidence that all official sources irreconcilably disagree. | Versioned security/date regime binding and native calendar applicability/supersession governance; keep predecessor immutable. |
| DAILY_INTRADAY_LTP_AUCTION | POLICY_REQUIRED | Price fields/intervals/formation can differ; apparent disagreement is not proof of data corruption or equivalence. | PRICE_SOURCE_PRECEDENCE_POLICY_REQUIRED after semantic alignment; retain conflicts without averaging. |
| IDENTITY_MEMBERSHIP_COLLISION | BLOCKED | Symbol/series/token/lifecycle incompatibility cannot be resolved by current mapping. | Exact dated native identity and completeness proof; no fuzzy join. |
| LATE_NOTICE_OR_CORRECTION | PIT_NOT_READY | A notice retrieved now cannot establish prior HSI knowledge; corrected body does not erase the earlier receipt. | Native knownness and explicit supersession/replay policy; no retrospective authorization. |
| INCOMPLETE_SOURCE | SOURCE_NOT_READY | Missing body/member rows/final-price observations cannot establish negative applicability or tradability. | Recover complete scope, field definitions and dated retained evidence; no title/landing inference. |

Decision C reflects unrecovered critical details, not proof that two fully
recovered official authorities irreconcilably disagree. The retained generic/CAS
scope conflict is explicit. No reputation-based automatic winner is created.

## Prospective and historical readiness

**PROSPECTIVE_SOURCE_BLOCKED**. Source delivery and reusable capture/identity/PIT
infrastructure exist; exact CAS semantics are SOURCE_NOT_READY. CAS-field
ingestion and security-regime binding require implementation, not reinvention
of generic MII capture.

New D events need not await all historical reconstruction once sources, access,
completeness, immutable originals, knownness, identity and separately governed
policies are proven. No existing cohort/scenario authority is claimed.

| Historical component | Classification | Finding |
| --- | --- | --- |
| CAS_NON_CAS_APPLICABILITY | ABSENT | No dated CAS membership/known-at chain demonstrated in repository source; no production inventory inspected. Official historical specifications alone do not reconstruct memberships. |
| SESSION_CALENDAR | BOUNDED | 2022-2026 holidays and selected specials/amendments; ordinary forward timing starts 2026-09-05, security-specific CAS/unknown specials/emergencies not complete. |
| PRICE_OBSERVATIONS | INSUFFICIENT | Versioned daily and prospective minute/15m receipts exist as infrastructure; aligned D/R security-regime coverage not proven. No DB coverage counts or cohorts claimed. |
| SECURITY_IDENTITY | BOUNDED | Historical interval and approved exact-session identity contracts; actual per-date complete CAS join not proven. |
| CORPORATE_ACTION_CONSISTENCY | INSUFFICIENT | PIT receipts and split/bonus derivatives reusable; rights/dividend/complex transitions and matched price windows not generally approved. |

## Source applicability matrix

All rows: **AUTHORITY_NOT_REGISTERED for new research use**, not a statement
that underlying Core inputs are inactive. Native provenance is in JSON.

| Component | Readiness / sources | PIT | Historical | Prospective | Blocker |
| --- | --- | --- | --- | --- | --- |
| REGULAR_NSE_SESSION_SOURCE | DERIVABLE; `I01`, `I02` | NATIVE_PIT_SUPPORTED_SCOPE_LIMITED | BOUNDED | REQUIRES_REGIME_BINDING | Reuse phase calendar; do not apply generic close to CAS securities. |
| CAS_APPLICABILITY_SOURCE | SOURCE_NOT_READY; `O02`, `O03`, `O04`, `O05` | PIT_NOT_READY | INSUFFICIENT | SOURCE_RECOVERY_REQUIRED | Phase-one rule identified; detailed field/schema/revision evidence missing. |
| CAS_SECURITY_MEMBERSHIP | SOURCE_NOT_READY; `O01`, `O04`, `I03` | PIT_NOT_READY | ABSENT | SOURCE_RECOVERY_REQUIRED | Complete dated exact membership needed; partial-list absence is UNKNOWN. |
| CAS_EFFECTIVE_DATES | SOURCE_EVIDENCE_SUFFICIENT; `O01` | GLOBAL_DATE_ONLY_NOT_SECURITY_KNOWNNESS | BOUNDED | PER_SECURITY_EFFECTIVITY_REQUIRED | Global live date recovered, not row-level known/effective transitions. |
| SECURITY_IDENTITY_MAPPING | DERIVABLE; `I03`, `I04`, `I05` | SESSION_IDENTITY_NOT_INTRADAY_CAS_KNOWNNESS | BOUNDED | JOIN_SOURCE_REQUIRED | Reuse active core session identity; verify actual CAS dictionary and lifecycle. |
| PROSPECTIVE_CALENDAR | SOURCE_NOT_READY; `I01`, `I02`, `O03` | PIT_NOT_READY_FOR_SECURITY_REGIME | BOUNDED | REQUIRES_IMPLEMENTATION | Generic forward calendar is not CAS-aware authority. |
| HISTORICAL_CALENDAR | SOURCE_NOT_READY; `I01`, `I02` | NATIVE_PIT_BOUNDED | BOUNDED | NOT_A_HISTORICAL_COMPLETENESS_CLAIM | No backcast of Sep-05 timing or current CAS membership. |
| SPECIAL_SESSIONS | SOURCE_NOT_READY; `I02`, `O01` | NOTICE_AND_PHASE_REQUIRED | BOUNDED | PER_NOTICE_CAPTURE_REQUIRED | Selected specials represented; missing timings/emergency notices block; mocks never count. |
| DAILY_CLOSE_SEMANTICS | POLICY_REQUIRED; `I08`, `I09`, `I10`, `O02`, `O06` | FIELD_AND_COMPLETION_UNPROVEN | INSUFFICIENT | SOURCE_AND_POLICY_REQUIRED | Heterogeneous formation; legacy clause missing; source close not automatic fill. |
| INTRADAY_COVERAGE | SOURCE_NOT_READY; `I14`, `I15`, `I16`, `I17` | STRICT_RECEIPTS_ONLY | BOUNDED | REGULAR_ONLY_NOT_CAS_COMPLETE | In-memory LTP not historical archive; no exact count or full coverage claimed. |
| START_D_OBSERVATION_COVERAGE | POLICY_REQUIRED; `I06`, `I07`, `I13`, `I17` | ORIGINAL_D_ONLY | INSUFFICIENT | CONVENTION_AND_RECEIPT_REQUIRED | Keep D; no nearest, stale quote or future full-day bar. |
| TERMINAL_OBSERVATION_COVERAGE | POLICY_REQUIRED; `I07`, `I13`, `O02`, `O06` | R_COMPLETION_AND_KNOWNNESS_REQUIRED | INSUFFICIENT | CONVENTION_AND_RECEIPT_REQUIRED | Missing mature price excluded per parent, no carry-forward/automatic deferral. |
| ADJUSTED_PRICE_INTEGRITY | DERIVABLE; `I11`, `I12` | EXACT_ACTION_EFFECTIVE_AND_KNOWN | INSUFFICIENT | SUPPORTED_WINDOWS_ONLY | Split/bonus derivable under native policy; return-method approval separate. |
| SUSPENSION_NO_TRADE | SOURCE_NOT_READY; `I03`, `I15`, `I16`, `O02` | STATUS_AND_PRICE_LINEAGE_REQUIRED | INSUFFICIENT | EXACT_STATUS_REQUIRED | Official reference may be descriptive; HSI cannot synthesize price. |
| DELISTING | BLOCKED; `I05`, `I18` | LIFECYCLE_PROOF_REQUIRED | INSUFFICIENT | SOURCE_AND_POLICY_REQUIRED | Lifecycle proof is not exit value; no invented zero/final print. |
| CORPORATE_ACTION_TRANSITIONS | POLICY_REQUIRED; `I11`, `I12`, `I05` | NATIVE_ACTION_AND_IDENTITY_PIT | INSUFFICIENT | SUPPORTED_WINDOWS_ONLY | Rights/dividend/complex actions not uniformly comparable; no adjustment mixing. |
| SOURCE_PRECEDENCE | POLICY_REQUIRED; `I07`, `I13`, `I17`, `O02` | NO_CONVENIENCE_PRIORITY | INSUFFICIENT | POLICY_REQUIRED | PRICE_SOURCE_PRECEDENCE_POLICY_REQUIRED; store canonicalization not economic observation approval. |
| CONFLICT_HANDLING | CONFLICTED; `I01`, `I03`, `I07`, `O01`, `O03` | FAIL_CLOSED | INSUFFICIENT | BINDING_POLICY_REQUIRED | Known retained-vs-CAS scope mismatch and unresolved source combinations retained, no arbitrary winner. |

## Parameter-policy impact

No predecessor mutation or parameter approval.

| Parameter | Impact | Finding |
| --- | --- | --- |
| DURATION_UNIT | UNCHANGED | No duration unit is approved; closing-regime evidence is not a duration prior. |
| COUNTING | NARROWED | Counting must use exact applicable live sessions, not generic/all-EQ calendar; special/partial counting still unapproved. |
| START_PRICE | NARROWED | Canonical values exist but exact original-D temporal/phase/price relation remains unapproved. |
| TERMINAL_BOUNDARY | NARROWED | Global CAS phase difference documented; security membership and future regime handling remain unresolved; no frozen-end rewrite. |
| TERMINAL_PRICE | NEW | Official close can be source-published reference without new trade; explicit formation/no-match lineage and admissibility policy required. |
| CALENDAR_AUTHORITY | NARROWED | Retained generic forward date and special/holiday bounds explicit; no security-regime authority registered. |
| INSTRUMENT_ELIGIBILITY | NARROWED | Stable session identity reusable; CAS fields/completeness unavailable and EQ alone does not establish eligible equity scope. |

Recovered global date closes an evidence lookup, not any seed/count/price
decision. No-match formation is an additional explicit admissibility gap.

## Defensive boundary and validation

Tests cover predecessor/pins, complete matrices, date-aware/native-known
applicability witnesses, incomplete complement/backcast rejection, identity/
segment, unread bodies, conflicts, D/R separation, no invented prices,
corporate actions, mock exclusion, no authority and one unstarted continuation.
Symbolic witnesses are test-only necessary-condition checks, not a CAS
implementation, source registry or observation generator.

Required closure: focused audit/predecessor tests; relevant calendar, identity,
price, adjustment, provider normalization and gates regression; local Markdown
links/tables/whitespace; git diff --check; fingerprints and source pins; exact
four-file staged review. Actual counts belong to the checkpoint, not a forecast.

Full backend suite **not required**: documentation/conformance only, no runtime/
shared behavior changed. No old full-suite result is presented as a new run.

V1 remains ACTIVE. Execution Gate V2 remains NOT_ACTIVE. Bootstrap remains
UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE; numeric seed UNSET.
SOURCE_EVIDENCE_SUFFICIENT is not POLICY/PRODUCER AUTHORIZED.
No source/horizon/price registration, model, labels, calibration, gate changes,
DB/portfolio mutation or broker authority. Commit locally; no push.

## One next frozen continuation

`NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1`

Recover official CMTR73845 master-field semantics, complete dated security applicability/revision evidence, CMTR74466 modalities and CMTR67774 clause 3.4 through permitted primary-source access; prove exact PIT/identity/completeness requirements in a bounded source-recovery dossier. No credentials request unless access truly requires it; no live acquisition/cohort, parameter choice, runtime authority or activation. This continuation is not started.
