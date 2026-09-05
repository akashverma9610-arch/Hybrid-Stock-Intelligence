# PIT Company-Type Classification Activation V1

**Status:** `ACTIVE / PIT_SAFE / IMMUTABLE / WATCH_ONLY / NON_EXECUTABLE / NO_COMPOUNDER_QUALIFICATION`

## Purpose and authority

This records the human-approved activation of HSI's final descriptive
company-type classifier. It succeeds the preserved research contract in
[PIT Company-Type Classification Research and Contract V1](PIT_COMPANY_TYPE_CLASSIFICATION_RESEARCH_AND_CONTRACT_V1.md),
which remains historical context and is not rewritten.

The active policy is `pit-company-type-classification-policy / v1`. It
combines only existing immutable canonical evidence:

1. active exact ISIN-to-CIN forward observations;
2. active exact-code NSE taxonomy-category evidence;
3. active RAW_EXACT regulator-to-issuer links; and
4. the corresponding RBI or IRDAI regulator evidence.

It controls only a future research branch. It does not evaluate a Compounder,
price, financial metric, score, setup, gate, holding, or trade action.

## Active governance chain

| Layer | Identity | State |
| --- | --- | --- |
| Policy | `pit-company-type-classification-policy / v1` | Immutable approved semantic contract |
| Human approval | `pit-company-type-v1-human-approval` | `APPROVED` at `2026-09-05T00:00:00Z` |
| Active selection | `pit-company-type-v1-active-selection` | `ACTIVE` at `2026-09-05T00:00:01Z` |
| Receipt contract | `pit-company-type-classification-activation / v1` | Append-only final classification receipt |
| Snapshot family | `PIT_COMPANY_TYPE_CLASSIFICATION` | Separate from every input-evidence family |

The policy fingerprint binds the semantics below. Approval/selection time is
governance provenance; it never makes evidence knowable before its canonical
PIT fields.

## Exact classification rules

| Output | Required positive evidence at explicit `evaluated_as_of` | Explicitly prohibited inference |
| --- | --- | --- |
| `NON_FINANCIAL` | Exact active issuer/security observation and matching active `NON_FINANCIAL_CANDIDATE` taxonomy receipt, with no incompatible exact regulator type. | Regulator-list absence, names, symbols, taxonomy display text, or a missing financial link. |
| `BANK` | Exact active issuer/security observation, matching active RAW_EXACT RBI scheduled-commercial-bank link and matching RBI evidence, with no incompatible type. | Taxonomy alone, financial-sector category, company name, or omitted NBFC/IRDAI evidence. |
| `NBFC` | Exact active issuer/security observation, matching active RAW_EXACT RBI registered-NBFC link and matching listed RBI NBFC evidence, with no incompatible type. | Company name, finance taxonomy, ARC status, or bank-list absence. |
| `INSURER` | Exact active issuer/security observation, matching active RAW_EXACT IRDAI link and matching listed IRDAI insurer evidence, with no incompatible type. | Taxonomy, company name, or unlinked insurer-directory evidence. |
| `UNSUPPORTED_FINANCIAL` | Matching `UNSUPPORTED_FINANCIAL` taxonomy receipt and no exact supported regulator proof. | Reclassification as non-financial, bank, NBFC, or insurer. |
| `NON_COMPARABLE` | Matching `UNKNOWN_NON_COMPARABLE` taxonomy receipt, absent a compatible supported regulator path. | A hidden precedence rule or a positive research branch. |
| `DATA_INSUFFICIENT` | Exact issuer/security, taxonomy, regulator-linkage, or regulator-evidence path unavailable at cutoff. | A guessed type from absence or current evidence. |
| `EVIDENCE_CONFLICTED` | Incompatible exact type paths, incompatible taxonomy states, or invalid exact regulator provenance. | Choosing a convenient branch, including for Compounder research. |

`INSURER` preserves `LIFE`, `GENERAL`, or `HEALTH`. The present corpus has no
exact linked insurer receipt; subtype preservation is implemented and tested
without manufacturing one.

`UNSUPPORTED_FINANCIAL` taxonomy may coexist with a valid exact regulator path
for `BANK`, `NBFC`, or `INSURER`; the regulator supplies the positive subtype.
A positive non-financial taxonomy receipt and a regulated-financial path fail
closed as conflicting exact evidence.

## PIT, identity, and provenance

Each receipt retains canonical CIN and `NSE:<ISIN>`, issuer-observation
ID/fingerprint, cutoff, policy/approval/selection provenance, taxonomy receipt
IDs/fingerprints, regulator-link IDs/fingerprints, regulator-evidence
IDs/fingerprints, explicit reason codes, deterministic receipt identity, and
deterministic content fingerprint.

Issuer observations are eligible only when their session and all anchor
known-at timestamps are at or before the cutoff. Taxonomy evidence requires
its `evaluated_as_of` at or before the cutoff. A RAW_EXACT regulator link and
its linked regulator record both require their exact known/observed timestamps
at or before the cutoff. Later evidence is excluded; it is never replayed
backward, normalized, or used as a fallback.

The report keeps distinct issuer count separate from observation/receipt count:
independent immutable forward observations for the same issuer/security retain
their own source lineage. No duplicate or conflicting input lineage is silently
discarded.

## Production receipts and replay

The activation used three explicit cutoffs. The current-supported cutoff is the
latest exact stored RAW_EXACT link timestamp, not a runtime clock:
`2026-09-04T19:30:59.533938Z`.

| Evaluation cutoff | Active issuer observations | Distinct issuers | `NON_FINANCIAL` | `BANK` | `NBFC` | `INSURER` | `UNSUPPORTED_FINANCIAL` | `DATA_INSUFFICIENT` | `EVIDENCE_CONFLICTED` | `NON_COMPARABLE` | Taxonomy unavailable | Regulator linkage unavailable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2024-02-05T23:59:59Z` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `2026-08-31T23:59:59Z` | 335 | 332 | 168 | 0 | 0 | 0 | 33 | 133 | 0 | 1 | 133 | 335 |
| `2026-09-04T19:30:59.533938Z` | 335 | 332 | 168 | 7 | 0 | 0 | 28 | 131 | 0 | 1 | 133 | 328 |

The first append-only write added 676 snapshots: common policy, approval, and
selection; one empty historical report; and two reports with 335 final receipts
each. An exact immediate replay inserted zero snapshots. No record was updated.

## Five-target audit

These are generic results of canonical CIN/ISIN and source lineage; there is
no symbol-specific logic.

| Symbol | Canonical CIN | 2024-02-05 | 2026-08-31 | Current supported result | Exact blocker or lineage |
| --- | --- | --- | --- | --- | --- |
| APARINDS | `L91110GJ1989PLC012802` | `DATA_INSUFFICIENT`: no PIT issuer observation | `NON_FINANCIAL` | `NON_FINANCIAL` | Exact `NON_FINANCIAL_CANDIDATE` taxonomy receipt; no regulator link is required or inferred. |
| DEEPINDS | `L14292GJ2006PLC049371` | `DATA_INSUFFICIENT`: no PIT issuer observation | `DATA_INSUFFICIENT` | `DATA_INSUFFICIENT` | Taxonomy and regulator-linkage receipt unavailable. |
| GENUSPOWER | `L51909UP1992PLC051997` | `DATA_INSUFFICIENT`: no PIT issuer observation | `DATA_INSUFFICIENT` | `DATA_INSUFFICIENT` | Taxonomy and regulator-linkage receipt unavailable. |
| GLAND | `L24239TG1978PLC002276` | `DATA_INSUFFICIENT`: no PIT issuer observation | `NON_FINANCIAL` | `NON_FINANCIAL` | Exact `NON_FINANCIAL_CANDIDATE` taxonomy receipt; no regulator link is required or inferred. |
| ICICIBANK | `L65190GJ1994PLC021012` | `DATA_INSUFFICIENT`: no PIT issuer observation | `UNSUPPORTED_FINANCIAL` | `BANK` | RBI RAW_EXACT bank linkage is known only at the current cutoff; 2026-08-31 taxonomy never established a bank type. |

## Historical limitation and panel preparation

`HISTORICAL_COMPANY_TYPE_COVERAGE_BEFORE_FIRST_GENUINE_PIT_EVIDENCE = LIMITED`

The earliest meaningful PIT company-type coverage is
`2026-08-31T23:59:59Z`, when current NSE taxonomy and exact issuer-forward
observations are both available. The February-2024 research start remains
impossible: zero PIT-valid active issuer observations yield zero final receipts.
Current 2026 regulator evidence does not repair that gap.

The next review is `COMPOUNDER_BACKTEST_PANEL_READINESS_V2`. It must determine
whether 2026 coverage and available financial history can support a genuine
research panel without inventing sample size. If not, the permitted follow-on
is `COMPOUNDER_PROSPECTIVE_SHADOW_VALIDATION_V1` from genuine current/future
PIT evidence. This does not activate candidate thresholds or qualification.

## Deliberate non-goals

This emits no Compounder result, research-shadow candidate, threshold, CAGR,
ROE, cash-flow metric, score, rank, setup, Six-Gates authorisation, decision,
portfolio mutation, discovery output, API/UI change, provider call,
broker/order action, or `BUY`/`SELL`/`HOLD`/`ADD`/`TRIM`/`EXIT`/`ROTATE`
vocabulary.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` is preserved: source artifacts
are facts, immutable source receipts are data, and this bounded classifier is
the only approved interpretation. Every output is `WATCH_ONLY / NON_EXECUTABLE`.
