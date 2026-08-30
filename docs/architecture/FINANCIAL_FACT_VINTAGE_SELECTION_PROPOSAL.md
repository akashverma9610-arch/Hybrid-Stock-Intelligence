# Financial Fact-Vintage Selection Proposal

**Proposed policy identity:** financial-fact-vintage-selection-policy / v1-proposed  
**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This U14D-6E document is a governance audit and proposal only. It creates no
selector, repository query, batch materializer, observation schema, observation
mapper, trajectory, directionality, materiality, thesis, opportunity, alert,
recommendation, signal, trade, or execution behavior.

## 1. Purpose and current boundary

The future factual chain is:

    Canonical FinancialFactStore
      -> PIT fact-vintage selector
      -> pure single-fact FinancialMetricObservation materializer
      -> deterministic observation collection
      -> FinancialMetricTrajectory
      -> later governed interpretation

The selector answers one factual question: for an instrument and one exact
financial semantic identity, which stored FinancialFact was knowable and
canonically selectable at a timezone-aware as-of time? It does not evaluate
whether a fact is good, bad, improved, degraded, investable, or actionable.

The current stores retain immutable FinancialFact payloads. Their series
methods apply an as-of filter requiring both published_at and received_at not
after the requested time. SQLite orders records by period end, published time,
and fact ID; PostgreSQL applies the equivalent in-memory filter after stable
database ordering. The existing FundamentalsEngineAdapter is a legacy consumer,
not a complete selector: its local choice only accepts one fact or a newest
fact that explicitly points to another candidate. It has no complete semantic
key, revision-graph validation, duplicate-equivalence rule, provider
precedence, or batch result. A future selector must replace neither the store
nor the legacy adapter implicitly; its introduced read boundary must be
deliberate and independently governed.

## 2. Existing fact facts and non-facts

FinancialFact already provides immutable source identity, Decimal value,
currency, unit, NumericScale, FinancialMetric, FinancialPeriodType,
FinancialValueBasis, period start/end, fiscal year/quarter, StatementScope,
fact kind, filing/source references, publication/receipt timestamps,
normalization version, parent references, revision_of_fact_id, provenance, and
quality flags. Its available_at is exactly the later of published_at and
received_at. Both stored timestamps and period end are required to be
timezone-aware; receipt cannot precede publication.

The canonical model has no separate statement or domain field beyond metric,
period type, value basis, scope, and fact kind. It also has no native fact
fingerprint, provider-priority policy, withdrawal/tombstone type, or generic
revision graph validator. These absences must remain visible rather than be
filled by inference.

Current FinancialQualityFlag values are COMPLETE, PARTIAL, INCONSISTENT,
REVISED, INSUFFICIENT_HISTORY, and UNKNOWN_BASIS. There is no stored INVALID,
ESTIMATED, provider-degraded, or withdrawn fact flag. A proposal must not
pretend those are current canonical values.

## 3. Proposed exact semantic key

A future FinancialFactSemanticKey should be the sole grouping identity under
which facts can be revision competitors. Its structural fields should be:

| Key component | Proposed treatment |
| --- | --- |
| Canonical instrument | Exact instrument_id only. |
| Metric and fact kind | Exact FinancialMetric and FundamentalFactKind only. Reported and derived facts do not silently compete. |
| Scope | Exact StatementScope. CONSOLIDATED, STANDALONE, and UNKNOWN are separate. |
| Period semantics | Exact FinancialPeriodType, FinancialValueBasis, timezone-normalized period_end, and period_start where supplied. |
| Fiscal identity | Fiscal year and fiscal quarter are retained and checked where supplied. Contradictory supplied values make identity ambiguous; absent metadata remains explicitly partial, not guessed. |
| Representation | Exact currency, unit, NumericScale, computed FinancialValueDimension, and normalization_version. |
| Lineage identity | Filing/source/fact IDs are candidate lineage, not winner-key substitutes. They identify evidence and revisions; they do not make two different economics equivalent. |

Different keys are never revision alternatives. In particular, consolidated
and standalone revenue, quarterly and annual PAT, quarter-only and
year-to-date cash flow, monetary and per-share values, reported and derived
facts, and distinct currency/unit/scale representations must remain separate.
No selector conversion, scope promotion, fiscal-calendar inference, or
cross-domain equivalence is authorized.

A supplied fiscal-year, fiscal-quarter, or period-start disagreement is an
AMBIGUOUS_SEMANTIC_KEY condition, not a reason to choose a newer row. A missing
optional fiscal field can remain a selected factual vintage only when all
minimum key fields above are valid; its downstream observation period identity
must be PARTIAL and later trajectory pairing may reject it.

## 4. PIT knowledge-at-the-time rule

The only proposed knowledge mode is KNOWLEDGE_AT_THE_TIME. For an as-of time T,
a fact is eligible exactly when:

    fact.available_at <= T

where available_at remains max(published_at, received_at). T and all fact
timestamps must be timezone-aware. A future receipt, later correction, later
revision, later discovery, or later re-ingest can never enter an earlier state.

For local official XBRL whose publisher time is unknown, the existing truthful
first-observed convention remains controlling: received_at and the assumed
available time are the local observation time, not an inferred official filing
time. Such a fact is not eligible before that observation time. This permits
current/future factual use while retaining PIT limitations; it must never
backdate an old reporting period into prior knowledge.

A later revision of an old reporting period changes the selected knowledge only
from that child fact’s own available_at. Thus an original Q1 fact remains the
answer before an August revision becomes available, and the revision may be
the answer only from August onward.

## 5. Revision graph and winner proposal

Revision_of_fact_id is an explicit directed edge from a child fact to a parent
fact. REVISED quality alone is evidence that revision context exists, not a
permission to infer a parent. A valid revision graph, for each semantic key,
must satisfy all of the following:

- Each edge stays within the exact semantic key and canonical instrument.
- A referenced parent exists in the supplied canonical fact collection.
- A child available_at is greater than or equal to its parent available_at.
  Equal timestamps are permitted only because timestamp precision can tie; the
  explicit parent edge still supplies ordering.
- The directed graph is acyclic.
- A component is linear: no parent has more than one eligible child unless a
  later explicit edge resolves the branch into one terminal node.
- Revision links never cross metric, scope, period semantics, representation,
  fact kind, or instrument identity.

For one key and T, the future selector must first retain only PIT-eligible
facts, validate relevant lineage, then mark a fact superseded only by an
eligible explicit descendant. It selects the unique terminal fact in a valid
linear component. Future descendants never rewrite earlier selections.

Malformed graph conditions fail closed for the affected key:

| Condition | Proposed reason |
| --- | --- |
| Referenced parent absent | REVISION_PARENT_MISSING |
| Parent in another key or instrument | CROSS_SEMANTIC_REVISION |
| Child known before parent | INVALID_REVISION_CHRONOLOGY |
| Cycle | REVISION_CYCLE |
| Unresolved eligible fork | REVISION_BRANCH_CONFLICT |

A fact marked REVISED without revision_of_fact_id is not automatically
malformed: it is independently auditable but cannot supersede another fact by
timestamp. If it is the sole eligible candidate it may be selected with
REVISION_RELATION_UNPROVEN warning. If it competes with another same-key fact,
the result is CONFLICTED; the selector must not assume it revises the newest
prior candidate.

A fact with an explicit missing parent is a broken asserted lineage and is not
safe to select. This stricter result preserves auditability and avoids
inventing ancestry.

## 6. Duplicate and conflict closure

The store already rejects same-ID payload alteration and SQLite also rejects a
different payload for the same stored source identity. A re-save of an equal
object is IDENTICAL; a changed object with that identity is CONFLICT. It does
not, however, define a universal same-period financial winner across sources.

The proposal distinguishes:

| Candidate relationship | Proposed result |
| --- | --- |
| Same fact ID and same immutable payload | Storage-level IDENTICAL; one stored fact. |
| Distinct evidence that has exact key, Decimal value, representation, fact kind, normalization, compatible PIT lineage, and provably the same filing/source document identity | Equivalent duplicate provenance. It may be collapsed for selection only while retaining all fact IDs and source lineage in the result. |
| Explicit valid revision lineage | Terminal eligible revision wins. |
| Same key, no valid supersession, different numeric value or incompatible source/document identity | UNRESOLVED_SOURCE_CONFLICT and CONFLICTED. |
| Same apparent economic period but different unit, scale, currency, scope, period type, basis, kind, or normalization identity | Separate key or AMBIGUOUS_SEMANTIC_KEY; never hidden conversion. |

Value equality alone does not prove duplicate evidence. A source filing identity
such as filing_id together with source/source_reference, plus compatible
semantics and lineage, is needed to classify duplicate provenance. Duplicate
collapse preserves every duplicate fact ID, filing reference, and reason in the
result; it never deletes or overwrites evidence.

There is no governed financial provider priority today. The legacy adapter
prefers consolidated scope then standalone fallback for its own old diagnostic
input, but this is not provider precedence and cannot settle a factual
contradiction. Official and secondary reproductions can be duplicate
provenance only when the same underlying filing is provable; otherwise they are
separate candidates. No source-specific rule for BSE, NSE, Upstox, or any
future provider is proposed here.

## 7. Quality, scope, period, and representation disposition

Quality flags describe evidence state but current canonical rules do not supply
a global quality ladder. The selector therefore must not use flags to
arbitrate a conflict.

- COMPLETE is eligible if base identity and PIT are valid.
- PARTIAL, INSUFFICIENT_HISTORY, and UNKNOWN_BASIS may be selected as factual
  unique vintages with retained warnings; later observation/trajectory
  admission decides whether they are usable for that purpose.
- REVISED needs explicit parent linkage to supersede another fact, as defined
  above.
- INCONSISTENT is retained as a warning on a unique factual vintage and cannot
  be used to select among conflicting facts. A later policy may decide that it
  blocks observation use; this proposal does not invent that policy.
- UNKNOWN scope is its own key. It never competes with CONSOLIDATED or
  STANDALONE, and no inferred upgrade is allowed.

The selector minimum is factual: valid instrument/metric/kind/scope/period
type/basis/period end/representation/PIT identity and finite Decimal data as
already required by the source model. Period-start and fiscal metadata
partiality remain attached to a selected result. They must not be fabricated
solely to make a selector or trajectory happier.

Unit, scale, and currency differences are separate representations because no
selector conversion contract exists. A batch must expose them as separate
selected groups or an ambiguity reason, never sum, divide, or compare them.
EPS and face value retain PER_SHARE and shares outstanding retains COUNT; they
must never inherit statement monetary scaling.

## 8. Proposed result contracts and reason vocabulary

A future minimal contract should contain only:

- FinancialFactSemanticKey
- FinancialFactVintageSelection
- FinancialFactVintageSelectionStatus
- FinancialFactSelectionReason

The top-level vocabulary should stay small:

| Status | Meaning |
| --- | --- |
| SELECTED | Exactly one terminal factual vintage is selected; warnings may remain. |
| UNAVAILABLE | No PIT-eligible fact exists for the key. |
| CONFLICTED | Eligible candidates cannot be deterministically reconciled. |
| INVALID_LINEAGE | Revision graph or semantic identity validation failed. |
| INSUFFICIENT_IDENTITY | Required base key/PIT input is invalid or absent. |

A selection should include semantic key, as_of, status, selected fact ID and
future source-fact semantic fingerprint when selected, eligible candidate IDs,
superseded IDs, excluded future IDs, equivalent duplicate IDs, conflicting IDs,
revision lineage IDs, warnings, typed reasons, and a deterministic result
fingerprint. It contains no direction or investment semantic.

Proposed fail-closed reasons are:

- NO_PIT_ELIGIBLE_FACT
- INVALID_AVAILABLE_AT
- AMBIGUOUS_SEMANTIC_KEY
- MULTIPLE_UNRESOLVED_FACTS
- UNRESOLVED_SOURCE_CONFLICT
- REVISION_RELATION_UNPROVEN
- REVISION_PARENT_MISSING
- CROSS_SEMANTIC_REVISION
- INVALID_REVISION_CHRONOLOGY
- REVISION_BRANCH_CONFLICT
- REVISION_CYCLE
- TAMPERED_FACT_PAYLOAD
- INVALID_SELECTOR_INPUT

The exact enum and serialization remain future work. These labels are proposed
governance vocabulary, not implemented API constants.

## 9. Batch, storage, and fingerprint governance

A future batch takes one canonical instrument, a timezone-aware as_of, and a
bounded immutable collection of canonical facts. It produces a deterministically
ordered selection result for every discovered semantic key, including selected,
unavailable, conflicted, invalid-lineage, and insufficient-identity outcomes,
plus reason counts. It must not silently omit four failed metrics merely because
thirty selected successfully.

Ordinary metric-key conflict is local and permits a partial batch. Foundational
failure invalidates the whole batch only for invalid request identity, naive or
invalid as_of, an internally inconsistent supplied collection identity, or an
invalid selector schema/mode. It is not an excuse to turn a metric-level
conflict into global failure.

Selection must be independent of database row order, insertion order, Python
list order, and any latest-row shortcut. It must not be implemented as only
maximum publication time or maximum receipt time. The fact set, policy/schema
version, and as_of must determine the same result and fingerprint every time.

FinancialFact currently has no fingerprint. The future source-fact semantic
fingerprint must have one owner: the future financial-metric-observation schema
contract should define it once, with the selector consuming that same helper or
its frozen specification. The selector must not introduce a second incompatible
fingerprint computation. A selection-result fingerprint, if later materialized,
will own its own candidate/lineage/reason set separately.

## 10. Policy, schema, and integration boundary

The key definition, PIT treatment, revision rules, duplicate equivalence, and
conflict closure can change which fact is selected. They are therefore governed
selection behavior, not merely a convenience schema. A future frozen
financial-fact-vintage-selection-policy is justified:

    financial-fact-vintage-selection-policy / v1-proposed

No policy artifact, fingerprint, approval, selection, or activation is created
by this proposal. A separate schema version may describe result wire shape, but
must not substitute for the policy decisions.

The strict future boundary is:

    stored facts -> selected fact vintage -> pure one-fact observation ->
    period-strength classification -> trajectory pairing

The observation mapper must consume an already PIT-selected fact and never
query raw history or decide a revision/provider winner. The trajectory builder
must consume observations only, with no provider lookup, scope inference,
scale conversion, fact repair, or hidden pair selection. BrainResearchComparisonState
should eventually reference materialized financial observation lineage rather
than rerunning selector logic.

## 11. Historical rebuildability audit

Current storage behavior is conditionally reconstructible.

- FinancialFact is frozen and the SQLite store uses INSERT only. It has no
  update, replace, or delete repository method. Same identity changed payloads
  conflict; identical re-ingest is retained as identical.
- BSE revision ingestion creates a new fact with revision_of_fact_id rather than
  overwriting the old fact. The original can therefore remain available for an
  earlier as_of.
- Re-ingest of a changed parse under the same fact/source identity fails closed
  as CONFLICT instead of silently mutating stored history. A distinct source
  identity can add a new immutable fact.
- Current stores preserve all saved facts while the database itself is retained,
  but they do not yet validate complete revision graphs or expose formal
  tombstone/withdrawal/invalidation semantics.

Therefore historical reconstruction is possible for retained, correctly
timestamped, linked evidence, but not guaranteed complete where source
publication time is unknown, revision parents were never stored, relationships
are malformed, external database tampering occurred, or a withdrawn filing has
no canonical withdrawal record. There is currently no withdrawal, tombstone,
or destructive deletion model to invent in this slice.

## 12. Explicit non-semantic boundary and next work

Selector output must never contain improved, degraded, favorable, unfavorable,
growth, decline, thesis strengthened/weakened, opportunity improved/degraded,
bullish/bearish, BUY, HOLD, SELL, TRIM, or ROTATE. It is factual provenance
governance only.

Recommended next implementation sequence, subject to a separate approved
slice, is: freeze a policy and schema; implement a stored-only selector with
tamper-closed tests; add pure one-selected-fact observation materialization;
then separately consider trajectory and directionality. No provider/network
call is justified by selector construction.

## 13. Status

The U14D-6E proposal is preserved as historical governance input. Its first
approved successor is recorded in
[FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_APPROVED.md](FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_APPROVED.md):
financial-fact-vintage-selection-policy / v1-approved. That frozen policy is
approved but remains not selected and not active; this proposal has not been
destructively replaced.

**U14D-6E = FINANCIAL FACT-VINTAGE SELECTION GOVERNANCE AUDIT COMPLETE / PROPOSAL ONLY**

**NO PIT FACT-VINTAGE SELECTOR, OBSERVATION MATERIALIZER, TRAJECTORY BUILDER, DIRECTIONALITY RULE, THESIS/OPPORTUNITY SEMANTIC, ALERT, RECOMMENDATION, OR EXECUTION HAS BEEN APPROVED, FROZEN, IMPLEMENTED, SELECTED, OR ACTIVATED.**
