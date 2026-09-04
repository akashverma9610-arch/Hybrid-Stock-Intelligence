# NSE Session-Known Security Identity Activation V1

**Status: `IMPLEMENTED / ACTIVE_POLICY / SESSION_POINT_ONLY / NON_EXECUTABLE`.**

## Approval lineage

This activation is a new immutable approval and selection lineage for the
existing proposal
[NSE Security Master Session-Knownness Policy Proposal V1](NSE_SECURITY_MASTER_SESSION_KNOWNNESS_POLICY_PROPOSAL_V1.md).
That proposal remains the historical record of its original
`PROPOSED / NOT_APPROVED / NOT_ACTIVE` state. This document does not rewrite
it retroactively.

The active policy is `nse-session-known-security-identity-policy / v1`:

1. immutable human approval references the exact proposal ID, version, and
   deterministic proposal fingerprint;
2. immutable active selection references the exact approval ID and approval
   fingerprint; and
3. each session-point receipt references the active policy, approval, active
   selection, source snapshot, source row, and source fingerprints.

Approval/activation timestamps are governance/audit times only. They are not
historical publication or `known_at` timestamps for a source row.

## Exact active semantic

For a validated official NSE `NSE_CM_security_DDMMYYYY.csv.gz` row labelled for
canonical trading session `D`, the receipt may state only:

`KNOWN_FOR_SESSION_D`

It retains NSE exchange, exact symbol, ISIN, series, security code/name, and
the raw status/type fields actually supplied by the source. It also retains
the exact source snapshot/row identity and fingerprint. `historical_known_at`
is always `null`.

This is discrete `SESSION_IDENTITY_EVIDENCE`, not
`LISTING_INTERVAL_EVIDENCE`. A receipt cannot establish a publication time,
prior/later session presence, listing start/end, delisting, uninterrupted
listing, ISIN/company continuity, company type, investment eligibility, or
Compounder eligibility.

## Selector boundary

`resolve_nse_session_identity` is a dedicated read-only selector rather than
an extension of `HistoricalSecurityIdentity`. The existing interval model
contains listed/tradable/effective semantics that would be false for an
isolated session observation.

| Requested session relative to matching receipt | Result |
| --- | --- |
| same exact session | `SESSION_IDENTITY_PRESENT` |
| earlier than receipt | `FUTURE_SESSION_RECEIPT_EXCLUDED` |
| later than receipt | `LATER_SESSION_REQUIRES_OWN_RECEIPT` |
| no exact receipt | `RECEIPT_UNAVAILABLE` |
| multiple exact session receipts | `EVIDENCE_CONFLICTED` |

No selector path searches a current provider master, substitutes a nearest
date, or synthesizes an interval. Same ISIN/symbol observations on separate
dates remain separate. Changed ISINs are never stitched. Exact BSE delisted
ISIN cross-references remain descriptive exchange-separate lineage only.

## Activation and replay boundary

`activate_stored_nse_mii_snapshot` reads an already immutable NSE source
artifact only by exact report date. The source snapshot must have its full
validated row count, exact official path/filename/date binding, stable source
fingerprints, and a canonical trading-session date. Duplicate exact source
identity keys are conflict-counted and do not create receipts.

Receipt identity excludes runtime/acquisition time. Replaying the same policy
selection and exact snapshot is append-only/idempotent: existing equal receipts
are `ALREADY_PRESENT`; altered content is an immutable collision and fails
closed.

## Coverage and readiness

The approved policy was backfilled from the two existing immutable snapshots.
The direct SQLite audit and immediate replay are:

| Session | Valid source rows | Session-point receipts | Distinct ISINs | Distinct symbols | Rejected source rows | Conflicts | Replay new / already present |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2024-02-05` | 24,693 | 24,693 | 11,295 | 10,252 | 58 | 0 | 0 / 24,693 |
| `2026-08-31` | 37,155 | 37,155 | 16,520 | 16,019 | 60 | 0 | 0 / 37,155 |

Aggregate authoritative session-point receipts: **61,848**. The two records of
governance lineage are one immutable approval and one active selection. The
source observations still contain 729 same-ISIN changed-symbol observations;
these remain independent exact session facts. The 52 exact BSE
compulsory-delisted ISIN overlaps remain descriptive cross-exchange lineage.

The two sparse anchor sessions can establish only exact security identity on
those two dates. They do not make the historical universe survivorship-safe.

`NSE_SESSION_IDENTITY_POLICY = ACTIVE`
`SURVIVORSHIP_RECONSTRUCTION = NOT_READY`

Remaining blockers are sparse archive density, no continuous daily/monthly
historical universe, no listing-interval policy/evidence, and no approved
PIT company-type classification. No Compounder grid/backtest, portfolio,
Holding/Sell/Harvest/Rotation, Decision Score, Six Gates, API/UI, broker, or
order behavior is part of this activation.
