# Regulator–Issuer RAW_EXACT Linkage Activation V1

**Status: `IMPLEMENTED / ACTIVE / RAW_EXACT_ONLY / REPRESENTATION_EXACT_NOT_APPROVED / NON_EXECUTABLE`.**

This activation implements the human-approved narrow policy in
[Regulator–Issuer Exact Legal-Name Correspondence Policy Proposal V1](REGULATOR_ISSUER_EXACT_LEGAL_NAME_CORRESPONDENCE_POLICY_PROPOSAL_V1.md).
The proposal remains the historical research and decision record; this document
records its immutable production activation. It creates regulator-to-issuer
evidence correspondence only. It does not classify a company, select an
investment, backfill a historical fact, or access a portfolio, broker, order,
API, or UI surface.

## Active immutable governance chain

| Layer | Identity | State |
| --- | --- | --- |
| Policy | `regulator-issuer-raw-exact-linkage-policy / v1` | Active semantic contract |
| Human approval | `human:regulator-issuer-raw-exact-linkage-v1-approval` | `APPROVED` |
| Active selection | `human:regulator-issuer-raw-exact-linkage-v1-active` | `ACTIVE` |
| Contract | `regulator-issuer-raw-exact-linkage-activation / v1` | Immutable, append-only linkage receipts |

The policy permits only:

```text
Unicode NFC(issuer legal name).strip() == Unicode NFC(regulator legal name).strip()
```

It does not case-fold, remove punctuation, normalize whitespace beyond leading
or trailing whitespace, map a suffix or abbreviation, repair spelling, map an
alias or former name, perform fuzzy/edit-distance matching, or infer a parent,
group, or subsidiary. `REPRESENTATION_EXACT` is not activated or evaluated by
this implementation.

## Link receipt and PIT invariant

Each active receipt retains the canonical CIN and legal name; issuer evidence
ID/fingerprint and known-at; regulator evidence ID/fingerprint, legal name,
family, and subtype; policy/approval/selection provenance; deterministic link
ID/fingerprint; and the exact boundary:

```text
link_known_at = max(issuer_evidence_known_at, regulator_evidence_known_at)
```

Both source timestamps must be compatible with existing PIT contracts. Current
regulator observation establishes a link only at or after that observation; it
never establishes an earlier historical link. One-to-many/many-to-one legal
name correspondence, a canonical CIN with multiple legal names, duplicate
regulator rows, or a cross-family collision is a conflict. No priority rule is
used.

## Production activation receipt

Activation at `2026-09-04T20:16:42.160462+00:00` wrote 10 immutable records:
one policy, one approval, one active selection, and seven raw-exact links. An
immediate replay wrote `0` records and found all `10` already present.

| Regulator family | Identity-valid RAW_EXACT candidates | Current PIT-valid active links | Notes |
| --- | ---: | ---: | --- |
| RBI scheduled commercial banks | 7 | 7 | All seven are separate one-to-one receipts. One additional raw match is blocked by a canonical CIN/legal-name ambiguity. |
| RBI registered NBFC/ARC | `DATA_UNAVAILABLE` | 0 | The official XLSX source has no persisted production rows after the earlier bounded acquisition failure. |
| RBI cancelled NBFC/ARC | `DATA_UNAVAILABLE` | 0 | The official XLSX source has no persisted production rows after the earlier bounded acquisition failure. |
| IRDAI life insurers | 0 | 0 | No normalization was broadened. |
| IRDAI general insurers | 0 | 0 | No normalization was broadened. |
| IRDAI health insurers | 0 | 0 | No normalization was broadened. |

The active link receipts are all in the RBI scheduled-commercial-bank family.
They preserve the regulator's raw subtype only; that subtype is not converted
to `BANK`, `NBFC`, `INSURER`, `NON_FINANCIAL`, or any other HSI company type.

## Historical PIT coverage

| As-of | Active issuer CINs | Raw identity candidates | PIT-valid regulator links | Result |
| --- | ---: | ---: | ---: | --- |
| `2026-08-31T23:59:59Z` | 332 | 7 | 0 | All seven candidates are `PIT_EVIDENCE_TOO_LATE`: the current RBI evidence was observed on `2026-09-04T19:30:59.533938Z`. One canonical-name conflict remains blocked. |
| `2024-02-05T23:59:59Z` | 0 | 0 | 0 | No active issuer bridge or regulator linkage is available. |

`HISTORICAL_REGULATOR_PIT_COVERAGE` is therefore `INSUFFICIENT`: current
regulator lists have value for a current, timestamped correspondence but cannot
be used as historical regulator evidence.

## Five-target audit

| Symbol | Canonical CIN | RAW_EXACT correspondence | Current link | Valid at 2026-08-31 | Valid at 2024-02-05 | Blocker / result |
| --- | --- | --- | --- | --- | --- | --- |
| APARINDS | `L91110GJ1989PLC012802` | No | No | No | No | No raw-exact regulator correspondence. |
| DEEPINDS | `L14292GJ2006PLC049371` | No | No | No | No | No raw-exact regulator correspondence. |
| GENUSPOWER | `L51909UP1992PLC051997` | No | No | No | No | No raw-exact regulator correspondence. |
| GLAND | `L24239TG1978PLC002276` | No | No | No | No | No raw-exact regulator correspondence. |
| ICICIBANK | `L65190GJ1994PLC021012` | Yes — RBI scheduled bank / `Domestic Private Sector Banks` | Yes, known at `2026-09-04T19:30:59.533938Z` | No | No | Current linkage only; the RBI observation is too late for both historical cutoffs. |

## Deliberate non-goals

This activation does not create company-type classifications, positive
non-financial evidence, Compounder eligibility, a backtest, a decision score,
or a trade/sell/rotation result. No match is not `NON_FINANCIAL`.

The independent next policy dependency for positive non-financial evidence is
`NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_PROPOSAL_V1`; it is not activated here.

## Historical evidence follow-through

The approved bounded follow-through,
[Historical Regulator Company-Type Evidence Acquisition V1](HISTORICAL_REGULATOR_COMPANY_TYPE_EVIDENCE_ACQUISITION_V1.md),
has now retained source-dated IRDAI 2022–23 Life/General/Health insurer rows
and a bounded set of RBI cancellation events. Those immutable records remain
evidence only. They do not repair the zero historical issuer-bridge count at
the February-2024 anchor, alter the current RAW_EXACT receipts, or activate a
company type. Historical RBI-bank rows and the exact June-2024 RBI NBFC/ARC
snapshot remain separate, unfilled primary-source gaps.
