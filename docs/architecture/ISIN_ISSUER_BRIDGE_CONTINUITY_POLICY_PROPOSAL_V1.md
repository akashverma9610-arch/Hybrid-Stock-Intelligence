# ISIN ↔ Issuer Bridge Continuity Policy Proposal V1

**Status: `APPROVED_SEMANTICS / ACTIVE / IDENTITY_ONLY / NON_EXECUTABLE`.**

The anchor and strictly forward same-ISIN continuity semantics in this document
have human approval. That approval does **not** activate a bridge, selection,
or issuer master. The bounded
[`BRSR Issuer Anchor Session-Master Backfill V1`](BRSR_ISSUER_ANCHOR_SESSION_MASTER_BACKFILL_V1.md)
is primary-evidence acquisition only. The separately governed
[`ISIN Issuer Bridge Continuity Activation V1`](ISIN_ISSUER_BRIDGE_CONTINUITY_ACTIVATION_V1.md)
implements the approved semantics; its production receipt determines active
coverage without expanding the policy.

## Purpose and fixed boundary

This V1 policy defines two separate questions:

```text
anchor:      exact BRSR symbol S ↔ CIN C at known time T
             + exact NSE MII symbol S ↔ ISIN I for session D
             → candidate exact I ↔ C anchor

continuity:  approved exact I ↔ C anchor at T0
             + later exact session observation of the same I
             → candidate forward-only issuer continuity
```

This policy document does not itself write a bridge, continuity receipt,
issuer master, company type, strategy result, or investment output. The active
V1 implementation reuses the existing immutable primary evidence and
preserves:

```text
FACT → DATA → INTERPRETATION → INFERENCE
```

The source BRSR symbol is a dated filing fact, not a timeless security
identity. A session MII row is a one-session security fact, not a listing
interval. An issuer bridge is not a company type, portfolio fact, or trade
authority. This document has no API, UI, persistence, provider, runtime,
portfolio, Discovery, Holding, Sell, Harvest, Rotation, Compounder/backtest,
broker, order, or execution effect.

## Existing canonical primitives

| Primitive | Exact retained fact | Explicitly not inferred |
| --- | --- | --- |
| [`ExactIssuerIdentifierEvidence`](BRSR_PRIMARY_ISSUER_IDENTIFIER_BACKFILL_V1.md) / `NSE_BRSR_ARCHIVE` | Immutable official BRSR application ID, direct NSE symbol, direct CIN, source document/record fingerprints, and submission timestamp. Legal name is display metadata only. | ISIN, issuer master, name match, company type, or continuity. |
| [`NseSessionPointIdentity`](NSE_SESSION_KNOWN_SECURITY_IDENTITY_ACTIVATION_V1.md) | Active `KNOWN_FOR_SESSION_D` receipt with exact NSE symbol, ISIN, series, security code, and MII source snapshot/row lineage for one date. | Legal issuer, listing interval, rename, or ISIN continuity. |
| `IssuerSecurityBridge` | Existing exact-session security-to-stable-issuer immutable contract and resolver. | A generic historical issuer master or a forward rule. |
| `NseTradingSessionCalendar` | Existing caller-supplied `is_trading_day(date)` decision. | New holiday data or intraday market-hours semantics. |
| `HistoricalSecurityIdentity` and lifecycle evidence | Exact source-linked lifecycle evidence only when already retained. | Continuity from absence, current data, names, or symbols. |
| Existing immutable snapshot/approval patterns | Fingerprinted append-only evidence and human-governed approval/selection. | Approval, selection, persistence, or activation in this slice. |

No new identity system is authorised. Future work must consume this lineage
directly and must not use a current master, fuzzy legal names, aliases,
parent/group inference, source ordering, or a parallel issuer table.

## Proposed policy object

```text
ISIN_ISSUER_BRIDGE_CONTINUITY_POLICY / v1
PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE
```

Its future deterministic policy fingerprint must cover only policy ID/version,
required primary fields, anchor/continuity rules, states, and prohibitions. It
must not depend on runtime/download time, locale, source order, legal name, or
a current master. No approval, active selection, implementation contract, or
migration is authorised here.

## Proposed exact anchor semantic

An `EXACT_ANCHOR_BRIDGE_READY` research state is possible only when all of the
following independent, immutable facts are present and internally valid:

| BRSR issuer-side fact | NSE security-side fact |
| --- | --- |
| Official NSE BRSR General archive record with evidence ID/fingerprint. | Official date-labelled NSE CM-MII snapshot and active session-point receipt. |
| Structural CIN `C`. | Structural ISIN `I`. |
| Exact source-labelled NSE symbol `S`. | Exact source-labelled NSE symbol `S`. |
| Exact application/source-record identity and document fingerprint. | Exact source snapshot/row ID and fingerprints. |
| Exact source submission/known timestamp `T`. | Exact canonical trading session `D`. |

The symbol must agree exactly as retained from both source rows. Neither
legal/display name, normalisation, BSE code, sector, current master, current
symbol, ISIN similarity, or company/group relationship can repair a missing or
conflicting field.

Future anchor identity inputs must be exactly:

```text
policy ID + policy version + policy fingerprint
+ BRSR evidence ID + BRSR evidence fingerprint
+ session receipt ID + session receipt fingerprint
+ session D + ISIN I + CIN C
```

The non-circular content fingerprint must additionally cover retained source
lineage, `historical_known_at = T`, source dates, state, and reasons. It must
not silently omit a field needed to reproduce the result.

### Filing-date, calendar, and intraday boundary

The BRSR source preserves exchange-displayed India filing date and the exact
UTC submission timestamp `T`. The candidate anchor session is that labelled
filing date **only if** the existing supplied `NseTradingSessionCalendar`
affirms it as a trading day. The MII file must be dated exactly `D`; a nearby,
earlier, current, or later snapshot is never a substitute.

The repository has no canonical NSE intraday open/close boundary. The public
MII source has `DOCUMENTED_PRE_TRADING_DATE_ONLY` semantics and no verifiable
`historical_known_at`. This policy therefore must not hard-code hours or
pretend to determine intraday ordering:

| Required filing context | Current proposed handling | Forbidden shortcut |
| --- | --- | --- |
| During session | `INTRADAY_FILING_SESSION_CLASSIFICATION_UNAVAILABLE`; preserve `T`, never treat issuer evidence as known before `T`. | Assuming a time window from general market knowledge. |
| After close | Same unavailable intraday classification; no earliest tradable-session assertion. | Treating the issuer fact as usable earlier that day. |
| Before open | Same unavailable intraday classification; date-only MII evidence cannot prove HH:MM:SS ordering. | Assuming the MII file preceded the BRSR filing. |
| Non-trading day | `NON_COMPARABLE` for an exact-session V1 anchor absent separately approved explicit effective evidence. | Binding it to the next session merely because it is next. |

This limitation does not discard the source filing. Any later as-of consumer
must honour `T`; the policy cannot fabricate a daily/intraday availability
rule.

### Exact same-session requirement

The candidate anchor requires all of:

```text
BRSR evidence (S, C, T)
+ canonical trading session D
+ validated MII snapshot dated D
+ exactly one active session receipt (S, I, D)
```

If the required source snapshot or row is absent, return
`ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING`. Symbol absence, multiple
incompatible ISINs, invalid source/date/row binding, BRSR CIN conflict, or
conflicting filing metadata returns `SYMBOL_SESSION_CONFLICT` or
`EVIDENCE_CONFLICTED`, retaining all source lineage. No arbitrary row or
source priority may select a winner.

## Proposed forward ISIN-continuity semantic

`ISIN_CONTINUITY_READY` is possible only after an approved exact anchor and
only for a strictly later session `D1 > D0` when:

1. the immutable anchor binds `I ↔ C`, retains `T0`, and has valid policy and
   source lineage;
2. the later active `NseSessionPointIdentity` has exactly the same ISIN `I`;
3. the later observation is after the anchor known time;
4. no exact primary bridge binds `I` to a different CIN;
5. no exact linked lifecycle/corporate-action source proves discontinuity; and
6. there is no source, identity, fingerprint, policy, or lifecycle conflict.

The CIN is inherited only from the anchor, never from a later symbol match.

| Later observation | Required treatment |
| --- | --- |
| Same ISIN, changed symbol | May be a descriptive candidate if every condition above holds. It does not create a rename interval. |
| Same symbol, changed ISIN | `NON_COMPARABLE`; it cannot inherit the CIN. |
| Same ISIN, exact later CIN `C2 ≠ C` | `CONTINUITY_CONFLICTED` / `EVIDENCE_CONFLICTED`; retain both, no update. |
| Session/date before `T0` | `PRE_ANCHOR_DATE_UNSUPPORTED`; no backward propagation. |
| Later exact session receipt missing | `ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING`; no inferred continuity. |

Absence of lifecycle evidence is not proof of eternal continuity. It simply
does not override an otherwise exact forward candidate. An exact merger,
amalgamation, demerger, cancellation, ISIN replacement, or legal issuer change
must fail closed and require a separate lifecycle review.

## Future receipt design, without implementation

No record is created in this slice. A later approved implementation must reuse
existing `IssuerSecurityBridge`, `ExactIssuerIdentifierEvidence`, and
`NseSessionPointIdentity` lineage rather than build an issuer master.

| Future record | Required lineage | It must not claim |
| --- | --- | --- |
| Anchor bridge | ISIN, CIN, BRSR evidence ID/fingerprint, MII session receipt ID/fingerprint, `D`, `T`, approved policy/selection lineage, deterministic ID/content fingerprint. | Knowledge before `T`, an issuer master, or a continuity interval. |
| Forward observation | Same ISIN, inherited CIN, original anchor ID/fingerprint, later MII receipt ID/fingerprint, forward session, exact conflict/lifecycle checks, approved continuity policy/selection, deterministic ID/content fingerprint. | A new anchor, symbol continuity, backward availability, or independent issuer evidence. |

The current `IssuerSecurityBridge` models exact-session or source-supplied
effective-interval evidence; it does not model a derived forward observation.
An activation must make an explicit additive representation decision. This
proposal authorises neither a new snapshot family nor a contract change.

## Draft policy-state vocabulary

This is proposal vocabulary only, not a runtime enum:

| State | Exact meaning | Fail-closed rule |
| --- | --- | --- |
| `EXACT_ANCHOR_BRIDGE_READY` | All required exact anchor facts and checks pass after approval. | Retain primary lineage only; no company type or action. |
| `ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING` | Exact required MII date/source/row/receipt absent. | No snapshot substitution. |
| `ISSUER_EVIDENCE_MISSING` | Valid BRSR direct CIN+symbol evidence absent. | No name/symbol inference. |
| `SYMBOL_SESSION_CONFLICT` | Exact same-session symbol rows are incompatible or ambiguous. | No row-order choice. |
| `ISIN_CONTINUITY_READY` | Approved exact anchor and exact forward same-ISIN observation pass every check. | Descriptive research state only. |
| `CONTINUITY_CONFLICTED` | Exact same ISIN has incompatible CIN or lifecycle evidence. | No update or source priority. |
| `PRE_ANCHOR_DATE_UNSUPPORTED` | Requested point predates anchor known time. | No backward propagation. |
| `NON_COMPARABLE` | Non-trading filing date, changed ISIN, or another explicit unsupported relation. | No interval/replacement inference. |

Existing `EVIDENCE_CONFLICTED` vocabulary remains applicable. A future
implementation must reuse equivalent existing states rather than duplicate a
state system unnecessarily.

## Read-only impact audit

### FY23-24 corpus and bounded anchor evidence

The persisted official FY23-24 BRSR General evidence has 1,199 accepted direct
CIN+NSE-symbol rows, 1,174 symbols, 1,171 CINs, and 138 filing dates. It has
no ISIN. It includes 133 weekend-dated rows, which cannot receive an
exact-session anchor under this proposal without separately approved explicit
effective evidence.

The primary-evidence backfill has now retained a bounded exact-date population.
Its immutable production receipt, including date availability and conflict
counts, is maintained in
[`BRSR Issuer Anchor Session-Master Backfill V1`](BRSR_ISSUER_ANCHOR_SESSION_MASTER_BACKFILL_V1.md).
It does not activate this continuity policy.

| Audit item | Result |
| --- | ---: |
| FY23-24 BRSR rows in corpus | 1,199 |
| Candidate snapshot dates | 138 filing dates, subject to exact-date validation |
| `v2` terminal MII date receipts | 55 (52 acquired; 3 unavailable) |
| Exact non-active anchor-ready records | 358 |
| Active issuer/security bridges under this policy | 0 |

Any candidate can use only the existing official fixed path:

```text
https://nsearchives.nseindia.com/content/cm/NSE_CM_security_DDMMYYYY.csv.gz
```

Remote availability is not asserted until the existing bounded acquisition
validates gzip, filename, schema, report-date binding, and source fingerprint.

### Named-target requirements

The identity boundary still stores no durable NSE holiday dataset. For the five
rows below, however, the exact official date-labelled MII report was validated
successfully and is retained as direct primary evidence for that labelled
session. This source fact does not create a general weekday/holiday rule or an
intraday availability claim.

| Symbol | BRSR known time | Required MII session / file | Exact anchor result | 2026 same-ISIN read-only potential |
| --- | --- | --- | --- | --- |
| `DEEPINDS` | `2024-06-20T10:38:09+00:00` | `2024-06-20` / `NSE_CM_security_20062024.csv.gz` | `ISSUER_ANCHOR_READY` / `INE0FHS01024` | Potential only; not a forward bridge. |
| `APARINDS` | `2024-07-31T11:41:17+00:00` | `2024-07-31` / `NSE_CM_security_31072024.csv.gz` | `ISSUER_ANCHOR_READY` / `INE372A01015` | Potential only; not a forward bridge. |
| `ICICIBANK` | `2024-08-05T17:45:27+00:00` | `2024-08-05` / `NSE_CM_security_05082024.csv.gz` | `ISSUER_ANCHOR_READY` / `INE090A01021` | Potential only; not a forward bridge. |
| `GLAND` | `2024-08-07T13:57:13+00:00` | `2024-08-07` / `NSE_CM_security_07082024.csv.gz` | `ISSUER_ANCHOR_READY` / `INE068V01023` | Potential only; not a forward bridge. |
| `GENUSPOWER` | `2024-09-06T05:41:15+00:00` | `2024-09-06` / `NSE_CM_security_06092024.csv.gz` | `ISSUER_ANCHOR_READY` / `INE955D01029` | Potential only; not a forward bridge. |

Each target's earliest possible issuer-known time remains its exact BRSR `T`.
FY23-24 BRSR cannot make 2024-02-05 issuer-complete: all 1,199 facts are
later, and the earliest BRSR source date is 2024-04-05.

At 2026-08-31, 1,150 exact symbols / 7,465 session receipts have earlier BRSR
symbol+CIN observations. This is a maximum potential population only: every
candidate still needs its own exact snapshot, calendar decision, approved
policy, anchor, same-ISIN confirmation, and conflict check.

### Older BRSR dependency

The [official NSE compliance archive](https://www.nseindia.com/regulations/listing-compliance)
lists FY21-22, FY22-23, FY23-24, and FY24-25 BRSR archive families. FY22-23 is an official 160 MiB workbook that
was deliberately not parsed by the bounded FY23-24 adapter. It **could**
contain submissions before 2024-02-05 for a meaningful subset, but this task
claims no count, field coverage, timestamp, or bridge until a separately
bounded primary-source parse validates the direct labelled fields. It is a
future historical-anchor dependency, not a substitute for this corpus.

## Company-type and investment boundary

If approved and if every exact MII anchor snapshot were later acquired, the
only possible result is issuer-bridge readiness:

| Research point | Maximum current potential | Still prohibited |
| --- | ---: | --- |
| 2026-08-31 | 1,150 symbols / 7,465 session receipts, subject to every anchor and conflict check. | Company type, financial comparability, investment eligibility, signals, or actions. |
| 2024-02-05 | 0 from FY23-24 BRSR because all evidence is later. | Backward propagation, a Compounder panel, or backtest. |

Issuer identity is not company type. No `BANK`, `NBFC`, `INSURER`,
`NON_FINANCIAL`, metric, rank, candidate, portfolio change, or trade output is
permitted.

## Future validation and sequence

After approval, isolated tests must cover exact BRSR+MII anchor proof, missing
same-session file, arbitrary later-symbol rejection, same-ISIN changed-symbol
description, same-symbol changed-ISIN rejection, no backward propagation,
future-filing exclusion, conflicting CINs, non-trading/intraday limitations,
deterministic identity/fingerprint/serialization, proposed-state invariants,
and absence of company-type, Compounder/backtest, portfolio, Discovery, or
execution dependencies.

The only permitted sequence after explicit approval is:

```text
BRSR_ISSUER_ANCHOR_SESSION_MASTER_BACKFILL_V1
→ ISIN_ISSUER_BRIDGE_CONTINUITY_ACTIVATION_V1
→ PIT_REGULATOR_COMPANY_TYPE_EVIDENCE_INGESTION_V1
→ PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1
→ COMPOUNDER_BACKTEST_PANEL_READINESS_V2
```

No stage may be skipped.

**`CONTINUITY_ACTIVATION_REMAINS_REQUIRED`** — the approved semantics do not
by themselves create an active bridge or forward observation. Activation still
requires exact anchor receipts, governed receipt representation and selection,
the retained intraday/calendar limitation, and conflict treatment.
