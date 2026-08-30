# Pre-Breakout Tick Reference-Data Contract Proposal

**Status: PROPOSED — NOT APPROVED — NOT IMPLEMENTED — NOT ACTIVE.**

This proposal changes no source ingestion, schema, resolver, grid validator, stop, policy successor, governance action, candidate, or scanner behavior.

## Existing architecture to reuse

- `NseEquityInstrument` and `HistoricalSecurityIdentity` provide canonical instrument, ISIN, exchange, and effective identity intervals.
- `HistoricalSecurityMasterStore` provides append-only payload snapshots and as-of filtering.
- `HistoricalCorporateAction` provides source, revision, effective date, as-of, and source reference lineage.
- `ProviderInstrumentMappingRecord` provides immutable effective provider routing, not reference facts.
- Market-data provenance and monetary values already use timezone-aware timestamps and `Decimal`.

None currently represents tick size, tick effective periods, authority classes, reference conflicts, or grid alignment.

## Proposed immutable record

Conceptual reusable record: `NseTickSizeObservation`.

```text
record_id                       immutable unique identity
canonical_instrument_id         required primary identity
exchange = NSE                  required
segment = NSE_CASH_EQUITY       required scope
isin                            optional exact corroboration
exchange_symbol                 descriptive lineage only
tick_size: Decimal              required; positive and finite
source_class                    OFFICIAL_EXCHANGE | LICENSED_REFERENCE_DATA
source_name                     required approved source identifier
source_identity                 required artifact/provider observation identity
source_artifact_fingerprint     required immutable raw-lineage fingerprint
observed_at                     required timezone-aware first observation
effective_from                  optional explicit source-effective time
effective_to                    optional effective end
created_at                      required timezone-aware ingestion/audit time
normalization_version           required
warnings                        immutable tuple
evidence_fingerprint            deterministic semantic fingerprint
```

Primary binding is `canonical_instrument_id`, cross-checked against an eligible NSE identity interval and ISIN when supplied. Ticker text is never authoritative. A symbol/ISIN replacement, relisting, or security substitution needs a new canonical-identity record; tick metadata does not transfer by similar ticker text.

Records are append-only. Later exchange/provider changes create new observations/effective periods. Same `record_id` with different semantic payload fails under immutable-record convention; no update or replacement rewrites history.

## Effective-period and PIT rule

```text
eligible_from = max(observed_at, effective_from) when effective_from exists
eligible_from = observed_at                       when it does not
eligible interval = [eligible_from, effective_to)
```

At `as_of = T`, evidence is eligible only when `eligible_from <= T` and `effective_to` is absent or `T < effective_to`. Explicit source effectivity cannot make data known before first valid observation. First-observed current data is never backdated. If `T < eligible_from` and no other record qualifies, return `TICK_SIZE_UNAVAILABLE_FOR_AS_OF`.

## Authority, precedence, and conflicts

Resolve only after temporal eligibility, exact identity, and Decimal validation.

1. Eligible official NSE reference evidence is preferred.
2. Approved licensed exact-identity NSE cash evidence is fallback.
3. No eligible evidence returns `TICK_SIZE_UNAVAILABLE_FOR_AS_OF`.

| Evidence | Result |
| --- | --- |
| Official only | Use official. |
| Licensed only | Use licensed. |
| Official and licensed with same exact Decimal | Use official lineage; retain licensed corroboration. |
| Official and licensed with different Decimal | `REFERENCE_DATA_CONFLICT`, fail closed. |

Within a source name, overlapping eligible values that differ are conflicts; database insertion order is never a resolver. Same-valued records corroborate one another. For sequential eligible records, select the record with greatest legally eligible `eligible_from`; then `observed_at`, then immutable `record_id` order lineage only. Licensed providers in the same class with different eligible values conflict.

`LICENSED_REFERENCE_DATA` requires explicit allow-list/governance approval. A configured provider is not automatically approved.

## Decimal and grid contract

Tick must be a positive finite `Decimal` decoded with proven exact source scale. No binary-float comparison, silent quantization, or tick inference is permitted.

`PRICE_ON_TICK_GRID` is exact Decimal modulo:

```text
P % tick_size == Decimal("0")
```

No epsilon, nearest rounding, floor, or ceil. A non-aligned expected exchange price gives `TICK_GRID_ALIGNMENT_ERROR` and fails closed. Future materialization must verify a support low and a derived one-tick subtraction are positive and aligned before use; this proposal computes neither.

`tick_size <= 0` or non-finite is `INVALID_TICK_REFERENCE_DATA`. Future support `<= tick_size` fails closed; no clamp to zero.

## Provenance and current feasibility

Required provenance includes source class/name, source identity/artifact, artifact fingerprint, observed time, effective interval, canonical identity mapping, normalization version, and evidence fingerprint. `instrument_id + tick_size` is insufficient.

| Candidate | Status | Finding / prerequisite |
| --- | --- | --- |
| Official NSE local universe/security evidence | NOT_AVAILABLE | Existing ordinary identity exports have no tick field. A documented official artifact with tick, effective, and provenance semantics is required. |
| Kotak Neo `dTickSize` master field | NEEDS_SEMANTIC_PROOF | Fixture contains field but production parser/model discard it. Unit/scale, authority status, identity mapping, observed time, persistence, and historical effectivity require proof. |
| Upstox BOD master | NOT_AVAILABLE | Parsed model has no tick field; none is invented. |

No candidate is `READY_TO_MODEL` today.

## Future data flow and statuses

```text
official or approved licensed artifact
  -> exact canonical NSE cash identity
  -> immutable TickSizeObservation
  -> PIT/effective eligibility
  -> authority precedence and conflict resolver
  -> Decimal grid validation
  -> later stop materializer
```

Proposed statuses/errors: `TICK_SIZE_AVAILABLE`, `TICK_SIZE_UNAVAILABLE_FOR_AS_OF`, `REFERENCE_DATA_CONFLICT`, `INVALID_TICK_REFERENCE_DATA`, and `TICK_GRID_ALIGNMENT_ERROR`.

## Human decisions required before implementation

Humans must approve/reject/modify: this schema; `[eligible_from, effective_to)` PIT convention; source allow-list; conflict fail-closed behavior; exact Decimal grid rule; and feasibility classifications. Only then may a bounded reusable reference-data implementation be designed. This does not approve a successor strategy policy or final-stop rule.
