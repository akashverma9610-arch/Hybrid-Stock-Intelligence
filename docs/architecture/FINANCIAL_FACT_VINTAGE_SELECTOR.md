# Financial Fact-Vintage Selector

**Status: IMPLEMENTED AS PURE DOMAIN LOGIC — NOT OPERATIONALLY ACTIVATED.**

The selector is a stored-only, deterministic domain function. It accepts
already-loaded immutable FinancialFact values, one explicit canonical instrument,
one timezone-aware as-of timestamp, and the exact frozen
financial-fact-vintage-selection-policy / v1-approved policy. It performs no
database read, provider request, filesystem operation, policy lookup, runtime
clock lookup, persistence, API call, worker action, or scheduler action.

## Boundary

    immutable supplied FinancialFact collection
      -> select_financial_fact_vintages
      -> FinancialFactVintageSelectionBatch
      -> per-key FinancialFactVintageSelection

The implementation is in
app/fundamentals/financial_fact_vintage_selector.py. It is only invoked by an
explicit caller supplying the frozen policy; there is no global active-policy
registry and no operational wiring.

Selection is factual provenance closure only:

- selection is not FinancialMetricObservation materialization;
- selection is not period-identity or completeness classification;
- selection is not a FinancialMetricTrajectory;
- selection is not financial direction, materiality, thesis, opportunity,
  recommendation, alert, signal, trade, or execution.

## Policy gate

The selector accepts only the approved policy identity:

| Field | Required value |
| --- | --- |
| Policy ID | financial-fact-vintage-selection-policy |
| Version | v1-approved |
| Fingerprint | 862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13 |
| Mode | KNOWLEDGE_AT_THE_TIME |
| Selected | false |
| Active | false |

Wrong policy identity/version/fingerprint, a malformed policy, an unsupported
mode, or an active/selected policy fails closed before fact evaluation.

## Result contract

FinancialFactSemanticKey carries the policy identity dimensions: canonical
instrument, metric, fact kind, scope, period type/basis, period start/end,
fiscal metadata where supplied, value dimension, currency, unit, scale, and
normalization version. Different keys never compete.

Each immutable per-key result retains as applicable:

- semantic key and as-of;
- status and selected fact ID;
- all candidate IDs and future-excluded IDs;
- superseded, duplicate, conflict, and revision-lineage IDs;
- frozen typed warnings/reasons;
- policy lineage; and
- a deterministic selection-result fingerprint.

The batch retains deterministic ordered results and aggregate status/reason
counts. It preserves partial success: a selected revenue fact remains visible
when debt conflicts or cash is unavailable.

The selector does not create a source-fact semantic fingerprint. That ownership
remains with the future FinancialMetricObservation schema boundary. Result
fingerprints cover selector output and canonical fact IDs only.

## PIT, revision, duplicate, and conflict behavior

PIT uses available_at equal to the later of published_at and received_at.
Only facts available on or before as-of participate. First-observed data with
unknown official publication time never becomes visible earlier merely because
its reporting period is old.

Within a key, eligible explicit revision edges must have a present same-key
parent, child availability no earlier than parent, no cycle, no unresolved
branch, and one terminal candidate. A later revision affects knowledge only
from its own visibility time. Missing parent, cross-key parent, invalid
chronology, branch, and cycle are INVALID_LINEAGE.

A REVISED-marked fact without a parent can be selected only as the sole
otherwise-valid candidate and retains the frozen
REVISED_WITHOUT_EXPLICIT_PARENT warning. It never guesses a parent. Exact
duplicates require same underlying filing/source identity, same value, same
key/representation, compatible lineage, and preserved provenance. Equal values
from different filing/source evidence remain unresolved conflict unless valid
revision or duplicate proof exists. Neither timestamp, input order, storage
order, insertion order, nor provider identity resolves a conflict.

Quality flags and partial period metadata remain factual lineage. The selector
does not rank quality, convert representations, infer fiscal identity, promote
UNKNOWN scope, or decide downstream trajectory eligibility.

## Purity and rebuildability

For a fixed fact set, canonical instrument, as-of, and frozen policy, shuffled
input produces identical keys, outcomes, reason counts, ordering, and
fingerprints. The output is derived and rebuildable, never stored.

No FinancialFact store, service, ingestion adapter, observation module,
trajectory module, Brain state, API, provider, network, filesystem mutation,
migration, repository, listener, worker, or scheduler was changed to call this
selector in this slice.

