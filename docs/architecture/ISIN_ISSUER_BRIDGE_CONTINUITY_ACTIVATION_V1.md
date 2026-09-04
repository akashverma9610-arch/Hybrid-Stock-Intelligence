# ISIN Issuer Bridge Continuity Activation V1

**Status: `IMPLEMENTED / ACTIVE / IDENTITY_ONLY / NON_EXECUTABLE`.**

## Scope

This additive activation consumes only immutable `ISSUER_ANCHOR_READY`
evidence and later immutable NSE session-point identities. It activates the
human-approved `isin-issuer-bridge-continuity-policy / v1`; it does not create
an issuer master, listing interval, company classification, signal, score,
portfolio change, or execution capability.

The existing generic `IssuerSecurityBridge` is intentionally unchanged. Its
temporal contract permits only exact-session or source-supplied effective
interval records, whereas this slice must preserve a derived, policy-governed
forward observation. The new receipts use the same immutable
`HISTORICAL_ISSUER_SECURITY_BRIDGE` snapshot family, not a second database.

## Governed activation chain

```text
approved V1 policy semantics
  → immutable human approval
  → immutable active selection
  → exact active anchor bridge(s)
  → strictly later exact same-ISIN observation(s)
```

The policy fingerprint fixes these semantics: exact BRSR/MII anchor required;
issuer known-at equals the BRSR submission timestamp; forward propagation is
strictly later and same-ISIN only; changed ISIN is not continuity; no backward
propagation; and an exact NSE lifecycle discontinuity blocks a forward receipt.
The implementation requires caller-supplied, aware approval/activation times;
it never reads a runtime clock to interpret historical evidence.

## Active anchor bridge

Each activated anchor retains the policy/approval/selection lineage, source
anchor ID and fingerprint, ISIN, CIN, anchor symbol/session, exact BRSR
known-at, BRSR evidence ID/fingerprint, MII snapshot fingerprint, and every
compatible MII row ID/fingerprint. Multiple anchor sources with one ISIN and
one CIN remain separate immutable bridges. If one ISIN has different CINs,
every such anchor is withheld from activation; no earliest/latest source wins.

The timestamp-aware selector accepts an active anchor only at or after its
exact `issuer_known_at`. Before that instant it returns
`PRE_ANCHOR_KNOWN_AT`. It does not infer market-open or anchor-session-start
availability, and it creates no security observation without an exact later
session receipt.

## Forward observations and conflict handling

A forward receipt requires one or more later active NSE session-point
identities sharing the exact same ISIN and symbol for one session date, a
strictly later session date than every retained compatible anchor, and one
unconflicted CIN. It retains every compatible later receipt ID/fingerprint in
canonical receipt-ID order, the later symbol, inherited CIN, and all anchor
ID/fingerprint/known-at pairs in canonical bridge-ID order. Different symbols
for the same session-date/ISIN remain separate exact descriptive observations;
they do not infer a rename interval or create an issuer conflict. Thus a
changed symbol is descriptive evidence only; the ISIN, not the symbol,
supplies continuity.

Same-symbol/different-ISIN rows are never stitched. Missing later ISIN evidence
does not imply a lifecycle result. The only lifecycle blocker accepted by this
contract is a caller-supplied exact NSE primary discontinuity with an ISIN,
known time, effective date, source fingerprint, and official NSE reference.
Existing BSE lifecycle evidence is neither imported nor used to infer an NSE
discontinuity.

## Persistence and replay

Approval, selection, anchor bridges, and forward observations are insert-only
records in the existing core snapshot repository. Their identities and
fingerprints exclude observation/download/runtime time. An equal replay is
`ALREADY_PRESENT`; changed content at an existing ID fails closed as an
immutable collision.

## Explicit boundaries

This activation must not:

- propagate an issuer backward before the exact BRSR known-at timestamp;
- infer continuity from symbol, name, current master, or a changed ISIN;
- join BSE lifecycle evidence into NSE continuity;
- classify `BANK`, `NBFC`, `INSURER`, or `NON_FINANCIAL`;
- run a Compounder/backtest, discovery, Holding, Harvest, Sell, Rotation,
  Decision Score, or Six Gates workflow; or
- access a portfolio, broker, order, API, UI, or runtime execution path.

The production receipt records actual coverage separately. Older PIT coverage
remains unavailable unless an anchor's exact BRSR known-at predates the
requested as-of. FY22-23 primary BRSR extraction remains the explicit gap for
pre-FY23-24 issuer coverage.

## Production activation receipt — 2026-09-05

Human approval `isin-issuer-continuity-v1-human-approval` and active selection
`isin-issuer-continuity-v1-active-selection` activated exactly
`isin-issuer-bridge-continuity-policy / v1` in the existing immutable
`HISTORICAL_ISSUER_SECURITY_BRIDGE` snapshot family.

| Receipt | Result |
| --- | --- |
| Exact BRSR anchor-ready receipts examined | 358 |
| Active authoritative anchor bridges | 358 |
| Distinct active CINs / ISINs | 347 / 349 |
| Compatible additional anchor lineages | 9 |
| Conflicting or unresolved anchors | 0 / 0 |
| 2026-08-31 NSE session-point receipts examined | 37,155 |
| Forward observations / distinct ISINs / distinct CINs | 335 / 334 / 332 |
| Same-symbol / changed-symbol forward observations | 325 / 10 |
| Absent anchored ISINs | 15 |
| Continuity conflicts / lifecycle blocks / non-forward anchors | 0 / 0 / 0 |
| Immediate immutable replay | 0 new anchors; 0 new forwards |

All five named target instruments have an exact active BRSR anchor and one
2026-08-31 same-ISIN forward observation: `APARINDS`, `DEEPINDS`,
`GENUSPOWER`, `GLAND`, and `ICICIBANK`. The activation has no company-type,
portfolio, broker, order, API, or UI effect.

At `2024-02-05T23:59:59Z`, zero active bridges are PIT-valid. The earliest
retained anchor session is 2024-04-05, and FY22-23-or-earlier exact BRSR/MII
anchor evidence remains required for older issuer coverage. SQLite integrity
is `ok` and foreign-key violations are `0`.
