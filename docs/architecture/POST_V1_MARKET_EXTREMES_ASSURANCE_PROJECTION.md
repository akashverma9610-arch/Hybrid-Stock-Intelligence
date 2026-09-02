# Post-V1 Market-Extremes Assurance Projection

**Status: `APPROVED_FOR_IMPLEMENTATION / READ_ONLY_ASSURANCE_PROJECTION / NOT_ACTIVE`.**

## Purpose and boundary

This projection is a pure Post-V1 consumer-safety contract. It answers whether
an explicitly supplied immutable `UpsideExcessAssessment` candidate is usable
at a supplied `as_of`; it neither calculates nor reinterprets Core V1
Market-Extremes regimes.

The underlying `UpsideExcessState` vocabulary remains exactly `NORMAL`,
`OPTIMISM`, `CROWDING`, `SPECULATION`, `EUPHORIA`, `DISTRIBUTION`, and
`BREAKDOWN`. Assurance uses the separate vocabulary `READY`, `CONFLICTED`,
`UNAVAILABLE`, `STALE`, `TEMPORALLY_INVALID`, and `UNVERIFIABLE`.

`READY` means only that a snapshot is usable under this projection. It does
not mean that a regime is correct, bullish, bearish, confirmed, or
trade-authorized. `EUPHORIA` remains an existing regime state; `top_confirmed`
is not used by this projection and is never interpreted as euphoria
confirmation.

## Input and fingerprint contract

The caller injects a tuple of immutable candidate snapshots and an immutable
context containing `as_of`, `freshness_floor`, optional exact consumer
identity, expected Core policy version, and expected candidate fingerprint
scheme/version. `freshness_floor <= as_of` is mandatory. There is no
repository query, runtime clock, default freshness duration, or fallback.

Each candidate carries a snapshot identity, its stored fingerprint, its
fingerprint scheme/version, and an unchanged Core `UpsideExcessAssessment`.
The projection canonicalizes and hashes the complete assessment payload:
identity, Core policy version, level/entity, regime and all Core descriptive
fields, normalized timestamps, factor tuples, warnings, evidence identifiers,
and provenance identifiers. A stored fingerprint mismatch is rejected; it is
never repaired. The assurance fingerprint is not a Core V1 snapshot-fingerprint
format and does not modify the generic snapshot wrapper.

## Selection and precedence

1. Validate `as_of` and `freshness_floor` as timezone-aware timestamps, and
   reject `freshness_floor > as_of` with `FRESHNESS_FLOOR_AFTER_AS_OF`.
2. Canonically order candidates and deduplicate exact duplicate candidates.
3. Verify each candidate identity, scheme, Core policy version, timestamps,
   fingerprint, and non-empty provenance. Preserve every rejection as a
   reason-coded lineage reference.
4. Exclude verified candidates whose Core `data_as_of` **or** `assessed_at` is
   later than `as_of`, retaining `MARKET_EXTREMES_AFTER_REQUESTED_AS_OF` in
   rejected lineage. A historical consumer cannot use an assessment that was
   not yet assessed at its requested cutoff.
5. Select the greatest remaining `data_as_of`. At that timestamp, differing
   verified content fingerprints yield `CONFLICTED`; exact duplicates do not.
6. A unique selected candidate is `STALE` only when `data_as_of` is earlier
   than the caller-supplied `freshness_floor`; otherwise it is `READY`.

When no candidate can be selected, deterministic status precedence is:

| Condition | Assurance state | Required reason |
| --- | --- | --- |
| No candidate supplied | `UNAVAILABLE` | `MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE` |
| At least one verified candidate exists, but all verified candidates are after `as_of` | `TEMPORALLY_INVALID` | `MARKET_EXTREMES_AFTER_REQUESTED_AS_OF` |
| Candidates were supplied but none verifies | `UNVERIFIABLE` | All candidate-specific rejection reasons, including `MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE` where applicable |
| Multiple verified candidates at selected timestamp have distinct content fingerprints | `CONFLICTED` | `MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT` |

Invalid candidates cannot override a verified eligible candidate. Older
conflicts cannot override a unique newer verified candidate. There is no
locally inferred conflict from warnings, factors, scores, or regime values.

## Reason codes and output

The contract uses: `MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE`,
`MARKET_EXTREMES_FINGERPRINT_MISMATCH`, `MARKET_EXTREMES_IDENTITY_INVALID`,
`MARKET_EXTREMES_POLICY_VERSION_MISMATCH`,
`MARKET_EXTREMES_TIMESTAMP_INVALID`,
`MARKET_EXTREMES_AFTER_REQUESTED_AS_OF`,
`MARKET_EXTREMES_STALE_AT_FRESHNESS_FLOOR`,
`MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT`,
`MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE`, and
`FRESHNESS_FLOOR_AFTER_AS_OF`.

An immutable result contains deterministic projection identity and full-content
fingerprint, assurance state, selected regime only when usable, selected
snapshot identity/fingerprint/effective time when applicable, context lineage,
candidate and rejected-candidate references, canonical reason codes, and a
deterministic verification summary. It exposes no mutable payload.

## Non-goals and future consumer boundary

This is not Profit-Harvesting and cannot map `EUPHORIA` to a review status. It
does not calculate returns, valuations, prices, targets, quantities, or any
regime. It has no persistence, SQL, API, UI, portfolio, broker/order, action,
capital-authorization, or side-effect dependency. A later consumer may use a
`READY` result only after a separately approved mapping policy.
