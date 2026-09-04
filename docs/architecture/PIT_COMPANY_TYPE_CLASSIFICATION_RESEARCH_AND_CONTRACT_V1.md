# PIT Company-Type Classification Research and Contract V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## Decision boundary

This is the narrow evidence-contract prerequisite for a future historical
company-type filter. It does not classify any production security, select an
authoritative type, change the Long-Term Thesis research shadows, create a
Compounder panel, or reconstruct a historical universe. Human approval is
required before a research receipt can become an authoritative input to any
backtest-universe construction.

`Company type` means an exact issuer/legal-entity fact, not a ticker, display
name, provider label, sector-name heuristic, financial ratio, or screening
result. The intended factual chain is:

```text
primary regulator or approved official classification evidence
  -> exact legal entity
  -> exact entity-to-listed-security bridge
  -> PIT company-type research receipt
  -> exact NSE session security
```

The contract in
[`app/intelligence/pit_company_type_classification.py`](../../app/intelligence/pit_company_type_classification.py)
is a pure, immutable research receipt. It has no store, migration, selection,
API, UI, provider call, score, financial metric, portfolio, order, or execution
path. Its `WATCH_ONLY / NON_EXECUTABLE` labels are boundary labels only; they
do not activate a strategy.

## Proposed source hierarchy and evidence families

Only these primary families may support the proposed receipt. A source row must
retain its own ID, checksum/fingerprint, explicit snapshot or effective date,
known/available time when supplied, exact category/subtype, and temporal
semantics.

| Proposed branch | Primary family | Exact source category/subtype retained | Promotion condition | Explicitly insufficient |
| --- | --- | --- | --- | --- |
| `BANK` | [RBI Scheduled Commercial Banks](https://systemhealth.rbi.org.in/Scripts/bs_viewcontent.aspx_Id%3D3657.html) or a dated RBI banking-regulation artifact | e.g. public/private/small-finance/payments/other exact RBI category | The listed issuer itself is exactly bridged to the regulated bank entity and the dated record is PIT-eligible. | A parent/affiliate bank, name/symbol match, or current list used before its source date. |
| `NBFC` | [RBI registered NBFC/ARC list](https://systemhealth.rbi.org.in/Scripts/BS_NBFCList.aspx.html) or a dated RBI registry artifact | exact RBI category and CoR/registration identity when supplied | Exact legal entity + exact bridge + an RBI category that is actually an NBFC branch. | Treating an ARC or another specialized row as a generic NBFC; inferring registration start from first observation. |
| `INSURER` | [IRDAI licensed-entity lists](https://irdai.gov.in/policyholders) or an exact dated IRDAI registry/order | `LIFE`, `GENERAL`, or `HEALTH`, and registration identity when supplied | The exact listed issuer is the regulated insurer and the relevant dated evidence is PIT-eligible. | Classifying an insurance holding company from its subsidiary, or using a current list for an earlier session. |
| `NON_FINANCIAL` | [NSE Indices industry classification](https://www.niftyindices.com/resources/industry-classification) | exact macro/sector/industry/basic-industry **code** and source snapshot | Exact listed-security/issuer receipt, an approved explicit non-financial code mapping, and no conflicting exact regulated evidence. | Absence from RBI/IRDAI, loose sector text, or a current code used backward. |
| `FINANCIAL_TYPE_UNSUPPORTED` | Exact primary evidence of a financial entity outside the supported branches | e.g. RBI ARC or a future approved exact financial taxonomy code | Evidence is retained, but the entity is not admitted to the non-financial branch. | Recasting broker, exchange, asset manager, holding company, or other intermediary as `NON_FINANCIAL`. |

NSE Indices describes its four-tier classification as revenue-business based;
the source is useful descriptive official taxonomy, but its codes are not yet
an approved company-type mapping. The current code therefore requires an
explicit positive taxonomy-code field for a synthetic research receipt and
never derives `NON_FINANCIAL` from a missing regulator result.

## Exact identity and PIT rules

### Entity-to-security bridge

An evidence item may be considered only after a separately verified,
deterministic `ExactIssuerSecurityBridge` binds one legal-entity ID to one
`NseSessionPointIdentity` receipt. The admissible bridge kinds are:

- `CIN`;
- `LEI`;
- regulator registration plus an existing canonical entity identity;
- exact canonical issuer ID;
- official ISIN; or
- exact official security ISIN-and-symbol identity.

The bridge retains its own identity fingerprint and the exact session receipt
ID/fingerprint. It cannot be built from company-name similarity, aliases,
ticker text, edit distance, LLM matching, or a parent/subsidiary relationship.
The repository has no populated canonical issuer/legal-entity model or stable
security-to-issuer bridge today; this is therefore a first-class readiness
blocker, not a field to backfill from existing names.

### Time eligibility

The contract evaluates only the `session_date` embedded in the supplied
`NseSessionPointIdentity`; callers cannot substitute a current time or a
nearby session. Each source evidence record declares one of:

| Temporal semantic | Candidate rule | Prohibited conclusion |
| --- | --- | --- |
| `EXACT_SNAPSHOT_DATE` | eligible only for the same labelled session date | that the entity had the type before or after the snapshot date |
| `EXPLICIT_EFFECTIVE_INTERVAL` | eligible only inside the stated interval and never before its known/available date | an unstated registration start/end |
| `FIRST_OBSERVED_FROM_SOURCE_DATE` | no earlier than the source date and never before its known/available date | a historical status before first official observation |

An exact cancellation date/effective-to bound remains evidence and excludes an
otherwise expired record. A source available after the session is excluded as
future evidence. If all supplied evidence is too late or not effective, the
receipt is `PIT_DATE_UNSUPPORTED`; it is never repaired with a current list.
No intraday availability claim is fabricated from a date-labelled source.

Multiple PIT-eligible primary branches for the same exact entity/security are
`EVIDENCE_CONFLICTED`. There is no hidden bank/NBFC/insurer/taxonomy priority
order. Regulator status and business taxonomy remain separately retained
lineages even when they conflict.

## Proposed contract and states

The contract is deliberately research-only. `ProposedPitCompanyTypePolicy`
has the fixed status tuple:

```text
PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE
```

`PitCompanyTypeEvidence` retains source family/category, source and issuer
fingerprints, exact source date, optional actual known time, optional actual
effective dates, subtype/code, and deterministic fingerprint. The contract
rejects malformed identifiers/fingerprints, unknown evidence families,
unsupported family/category/branch combinations, unordered duplicate evidence
IDs or fingerprints, and tampered evidence fingerprints.

`PitCompanyTypeResearchReceipt` retains the policy fingerprint, exact session
security lineage, exact bridge lineage when present, evidence lineage, branch,
state, reasons, deterministic receipt ID, and content fingerprint. Its stable
serialization normalizes timezone-aware values to UTC and is independent of
wall clock, locale, source order, or runtime environment.

| Receipt state | Meaning | Required branch/reason behaviour |
| --- | --- | --- |
| `EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE` | One exact, PIT-eligible, non-conflicting supported primary branch exists. | `BANK`, `NBFC`, `INSURER`, or positively coded `NON_FINANCIAL`; retains `EXACT_PRIMARY_EVIDENCE_PRESENT`. This remains a proposed research observation, not an active classification. |
| `DATA_EVIDENCE_UNAVAILABLE` | No eligible primary evidence was supplied. | `UNKNOWN` with `PRIMARY_EVIDENCE_REQUIRED`; never `NON_FINANCIAL`. |
| `IDENTITY_LINKAGE_UNAVAILABLE` | No exact issuer-to-session-security bridge, or it does not bind the supplied session receipt. | `UNKNOWN` with `EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED`. |
| `PIT_DATE_UNSUPPORTED` | Evidence is future, has no allowed source-date semantics, or is outside an explicit effective bound. | `UNKNOWN` with `FUTURE_EVIDENCE_EXCLUDED` or `SOURCE_EVIDENCE_NOT_EFFECTIVE`. |
| `EVIDENCE_CONFLICTED` | More than one distinct eligible primary branch applies. | `UNKNOWN` with all exact source lineages retained. |
| `FINANCIAL_TYPE_UNSUPPORTED` | Exact primary evidence identifies a financial entity outside bank/NBFC/insurer support. | Fail closed with `UNSUPPORTED_FINANCIAL_ENTITY`; it is never non-financial by exclusion. |
| `NON_COMPARABLE` | An exact future-approved taxonomy mapping says the entity is structurally non-comparable. | Fail closed with `STRUCTURALLY_NON_COMPARABLE_ENTITY`. |
| `NOT_APPLICABLE` | Reserved for a future approved use that supplies no listed-security research question. | No inference or current use is authorized. |

`UNKNOWN`, `STRUCTURALLY_NON_COMPARABLE`, and `FINANCIAL_TYPE_UNSUPPORTED`
are compatible with the existing long-term research-shadow branch vocabulary.
They are descriptive fail-closed states; this proposal does not change those
existing research shadows.

## Read-only current-anchor readiness audit

Audit scope: production SQLite read-only inspection at the active NSE
session-point anchors. Counts below are evidence/readiness counts, not company
types, investment eligibility, metrics, or backtest rows.

| Anchor session | Exact NSE session receipts | Distinct ISINs / symbols | Exact issuer bridge | Stored RBI bank/NBFC evidence | Stored IRDAI insurer evidence | PIT taxonomy records matching session ISIN | Safely classifiable branches | Non-financial research-universe entries if later approved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2024-02-05` | 24,693 | 11,295 / 10,252 | 0 | 0 / 0 | 0 | 0 | 0 | 0 |
| `2026-08-31` | 37,155 | 16,520 / 16,019 | 0 | 0 / 0 | 0 | 711 | 0 | 0 |

The 711 taxonomy records are all current first-observed official records with
`as_of/effective_from = 2026-08-27T15:33:21.747410+00:00`; their source
semantics are `FIRST_OBSERVED_OFFICIAL_SNAPSHOT`. They do not establish any
2024 type and are not a legal-entity bridge. For the 2026 anchor they are only
potential security-taxonomy inputs: the code mapping, exact issuer bridge,
regulator comparison, and policy approval are still absent.

Consequently, all 24,693 and 37,155 receipt-level session securities remain
unresolved for company type. The direct scan found no persisted RBI bank/NBFC,
RBI cancellation, IRDAI insurer, CIN, LEI, canonical issuer, or exact
issuer-security bridge receipt. There are therefore zero current candidate
conflicts and zero positive bank/NBFC/insurer/non-financial classifications;
that is a lack of evidence comparison, not evidence that no conflicts exist.

The resulting proposed Compounder-panel impact is exactly **zero** eligible
`NON_FINANCIAL_COMPOUNDER_RESEARCH_UNIVERSE` rows at both anchors. A future
approved panel would require all four independently: exact NSE session
identity, exact issuer bridge, exact PIT `NON_FINANCIAL` receipt, and no
company-type conflict. Financial-history readiness is intentionally not tested
here.

## Reuse and non-goals

The proposal reuses `NseSessionPointIdentity` and its fingerprint only as the
exact session-security fact. It does not reinterpret the receipt as a listing
interval. `HistoricalSecurityIdentity` remains unpopulated and untouched.
`InstrumentTaxonomyClassification` remains a sector/industry record; this
contract does not transform its labels into company type by string matching.

It does not modify Multi-Funnel Discovery, Holding Review, Sell, Harvest,
Rotation, Decision Score, Six Gates, provider connections, UI/API, portfolios,
or any broker/order path. It does not calculate Revenue/PAT/ROE/CFO metrics,
candidate grids, persistence windows, ranks, thresholds, backtests, or an
investment qualification.

## Future activation path

Before activation, a separate human-approved policy must define the exact
official acquisitions, allowed entity/security bridge records, approved NSE
taxonomy-code map, date/known-time semantics, cancellation treatment, conflict
review, immutable storage, and selector behaviour. It must first acquire
supportable dated source artifacts without fabricating entity linkage or
historical availability.

Only after that approval and an activation audit may the next dependency be
considered:

`PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1`

Then `COMPOUNDER_BACKTEST_PANEL_READINESS_V2` must re-audit sparse universe,
company type, and financial-history requirements before any candidate grid is
contemplated.

**`HUMAN_APPROVAL_REQUIRED`**
