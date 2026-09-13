# Gate-3 ASM/GSM Completeness Governance Fallback V1

Status: **DECIDED / GOVERNANCE_ONLY / NOT_ACTIVE**.
Decision **C: `KEEP_GATE3_BLOCKED_UNTIL_MACHINE_COMPLETE`**.
Reviewed baseline: `cf4bd84aea7fffd6e4d4b4fbbe2cc9375ed4c8a1`, `main`.

## Decision and evidence boundary

Preserve the mandatory complete-evidence model. When required current ASM or
GSM completeness cannot be verified, the required component remains `UNKNOWN`
and the gate remains `INSUFFICIENT_DATA` or fails existing pre-formula source
admission. This decision changes no active engine, collector, source selection,
formula, policy version, or production state. Research remains useful and
available independently of execution eligibility.

Controlled human transport is a reasonable potential option for a 25–30-user
pilot. It is not rejected for lacking perfect automation or an NSE digital
signature. It cannot be recommended for Gate evidence **on the accepted current
record**: there are no retained, validated official UI-export bytes, no verified
export schema and whole-product coverage proof, and no established combined
file or exhaustive component manifest for GSM. A clean parse, zero rejected
rows, and an operator declaration cannot detect a well-formed omitted row or
prove that an unrepresented component is empty. Role/MFA controls cannot supply
the missing source-product evidence. Option A's required feasibility condition
is therefore not met.

The exact Decision-C label does not require automated transport forever:
"machine complete" means mechanically justified complete-product capture.
An unchanged file carried by an authorized operator could qualify after the
product and validation gaps close and its transport addendum is approved.
This decision does not require a new numerical threshold, historical archive,
commercial provider, perfect API availability, or enterprise-scale automation.

Evidence reused without new source requests:

- [Accepted complete-export feasibility decision](GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.md)
  and its [machine receipt](GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.json).
- [Capture-completeness repair](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.md)
  and [receipt](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.json).
- [Approved composite governance](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.md)
  and [exact approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json),
  incorporating the [Gate-3 .3 proposal](GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json).

Those records establish NSE official product authority, current API completeness
`UNPROVEN`, direct price-band CSV capture, and unresolved execution-master
continuity. The earlier bounded transport check is not a universal proof that
NSE could never expose another artifact. No broad discovery or new website,
API, UI, export, or production database access occurs in this slice.

## Frozen policy and source authority

| Obligation | Preserved decision |
| --- | --- |
| Active policy | `six-gates-production-v1 / v1`; unchanged |
| Composite candidate | `execution-gate-policy-v2-proposed / v2-proposal.3`; `GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS / NOT_ACTIVE` |
| Required components and thresholds | ASM >=2; GSM >0; static PRICE_BAND <=5%; exactly three substantive inputs |
| Other source metadata | SECURITY_STATUS remains descriptive; no predicate or fourth PASS input |
| Admission | Exact NSE authority and identity, PIT visibility, current source applicability, fresh complete captures, conflict-free lineage, then the complete three-component vector |
| Gate-3 result | Missing/invalid/unproven requirement -> `INSUFFICIENT_DATA`; fully admitted blocking vector -> existing `FAIL`; all three admitted non-blocking -> existing `PASS` |
| Blocking plus missing | `INSUFFICIENT_DATA`; independent positive-only veto order is not imported from Gate 6 |
| Freshness | Existing inclusive maximum of four trading sessions is necessary but not sufficient; actual current applicability remains required |
| Source authority | NSE official ASM/GSM product; transport operator is never the source or decision authority |

An API, an official UI download, authorized human carriage, and a future stable
machine export are different transports. None independently proves completeness.
Official product labels in HSI (`NSE_ASM_COMPLETE_LIST` and
`NSE_GSM_COMPLETE_STAGEWISE_LIST`) are governed identifiers, not an NSE signature
or a guarantee about arbitrary uploaded bytes.

## Controlled official-export option: conditional safeguards only

The following describes minimum future requirements for
`OFFICIAL_SURVEILLANCE_ARTIFACT_INGESTION_V1`; it does not create or approve an
ingestion contract, upload endpoint, importer, or security implementation.

| Area | Required future rule | Current gap |
| --- | --- | --- |
| Origin | Exact approved NSE product/page and export action context; unedited original bytes; preserve supplied filename and format; source declaration tied to upload/action audit ID | No retained official UI export in the accepted evidence set |
| Operator | Authenticated Admin or RA; a dedicated operator must have explicitly delegated ingestion authority; verified MFA and action authorization, with transport identity recorded by trusted authentication | This slice neither proves nor installs the future pilot access controls |
| Attestation | Only: "I obtained this unedited artifact from the named official NSE product." A claimed download time is separately labelled, unverified transport metadata | Cannot attest stock safety, absence/clearance, stage values, correctness, completeness, or a gate result |
| Immutable capture | Retain raw bytes before interpretation, SHA-256, byte length, original filename, file format, product/schema version, authenticated actor, action audit ID, source declaration, ingest/validation times and immutable receipt fingerprint | Existing raw store/hash/receipt patterns are reusable; operator provenance needs a reviewed compatible extension |
| Authenticity | `OFFICIAL_ORIGIN_ATTESTED` records a transport claim; `CRYPTOGRAPHIC_SOURCE_AUTHENTICITY = UNPROVEN` unless an independently verified NSE signature actually exists | SHA-256 proves retained content identity; it does not authenticate pre-upload content or the declarant |
| Parsing | Bounded non-executing format parser, full transfer/EOF, exact governed schema, all rows retained, zero rejected rows; no spreadsheet execution or manual repair | No approved UI-export schema or omission-proof structure has been established |
| ASM coverage | Mechanically verify the entire official product, including long-term and short-term scope; emptiness requires source-supported explicit proof, not an absent header or an operator checkbox | The known API has both sections; equivalence to complete UI-export scope remains unproven |
| GSM coverage | Verify an official combined-product definition or exhaustive source-declared stage/list component set; every component accounted for, with explicit empty components where applicable | Component set remains unproven; do not invent it from known numeric stages or drop composites |
| Identity | Reuse exact security/ISIN and source-symbol lineage; validate framework scope; retain ambiguity and conflicts, no fuzzy issuer matching | Current master and unsupported raw values remain separate admission constraints |
| Semantic admission | Separate product capture, row admissibility, source/effective state and target-context freshness; no unknown value becomes zero | Complete file alone cannot admit a non-blocking component |
| Audit/replay | Reopen verification, immutable action trail, original raw identity on retry, lossless operator/source separation, no discretionary Gate override | Hash/audit do not prevent a privileged coordinated rewrite; that residual risk needs explicit pilot acceptance |

An operator may not set ASM/GSM stage, change a band, mark a stock clear, repair
source content, force `PASS`/`FAIL`, or add execution authority. Internal exact
identity normalization may derive a separate traceable representation while
preserving raw bytes; it must not mutate the original file.

Mechanical checks can detect truncation, malformed rows, missing declared
sections, inconsistent totals when NSE actually supplies them, duplicates,
conflicts, or a wrong schema. They cannot infer hidden omissions from a valid
CSV with no complete-scope evidence. No expected row counts, minimum-size
heuristic, hash match to unrelated API bytes, or human completeness certificate
is approved. Equal API/export row counts remain insufficient.

## First observation, current state and operating burden

Future `HSI_FIRST_OBSERVED_AT` is automatic HSI time when the complete raw upload
becomes available to HSI, never request start. Source publication/list date,
filesystem creation/modification time, claimed download time and operator-entered
historical time cannot supply it. A later validation/authorization receipt has
its own availability; a later proof cannot be backdated to raw arrival.

Apply inclusive `known_at <= evaluation_as_of` before conflict, revision or
identity selection. A repeated identical artifact reuses its earliest retained
raw observation; each new upload/action retains a separate audit event. A changed
payload gets distinct content lineage. Reupload, rename or refetch cannot renew
effective age, rewrite history or create a new current-state claim. Later
discovered restrictions/removals cannot alter a frozen earlier decision.

No daily, pre-market, intra-market or minute-based collection requirement is
invented. For a potential pilot, an authorized operator would obtain and check
the relevant unfiltered official products when a source update is observed, on
an unresolved API change hint, or when current evidence is needed. Both families
need independent validation; a pre-market file is not automatically valid all
day. Unattended periods or an unstaffed change leave evidence insufficient.
The actual burden is bounded manual retrieval plus audit/exception review per
observed change; frequency is unmeasured. The existing four-session cap is not
an update schedule or permission to use stale/non-current evidence.

## API role and cross-transport conflict

Keep current API capture as `DISCOVERY_ONLY`. It may provide
`POSITIVE_EVIDENCE_CORROBORATION` and `CHANGE_DETECTION_HINT` when exact identity,
raw indicators, known-at and source context support the observation. It cannot
prove absence, removal or current complete coverage; an empty API response is
not clearance. A corroborating raw row is not an admitted numeric component,
and a blocking observation plus missing evidence still cannot change the
approved Gate-3 precedence.

| Situation at the explicit PIT cutoff | Required treatment |
| --- | --- |
| Visible official API positive absent from purported complete artifact | Material disagreement -> `CONFLICTED` -> `INSUFFICIENT_DATA`; no preference for transport, row count, operator or later timestamp |
| Different stages or exact security identities | Same fail-closed conflict; preserve both raw lineages and unresolved values |
| Applicability of either side is unknown | `UNKNOWN / INSUFFICIENT_DATA`; do not fabricate a common effective interval |
| Same source-product bytes/identity and semantic proof | Idempotent input; no duplicate evidence vote or new first observation |
| API or artifact is first observed after cutoff | Exclude it before conflicts/lineage selection; it cannot alter earlier evidence or earlier outcome |
| API lacks a row present in artifact | Unproven API absence cannot prove removal; investigate a change hint without fabricating contradiction or supersession |
| Removal or replacement claimed | Only a PIT-visible, verified official relation and compatible effective semantics may resolve it; no latest-timestamp shortcut |

Missing current artifact, schema drift, partial file, missing components,
rejected rows, absent operator authority/provenance, unproven product binding,
unsupported stage, exact-identity conflict, stale evidence and unresolved
API/artifact conflict all withhold non-blocking evidence. Preserve the specific
failure reason; neither a generic unknown nor a material conflict becomes PASS.

## Alternatives and pilot comparison

| Option | Source authority | Truthfulness | PIT safety | Pilot usability / liveness | Automation | Security risk | Complexity | Policy burden | Future migration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CONTROLLED_OFFICIAL_EXPORT_INGESTION` | NSE, with separately attested transport | Conditional; whole-product artifact proof currently missing | Automatic local receipt plus independent effective/validation proof required | Potentially practical for 25–30 users; unavailable for Gate admission today | Manual retrieval, deterministic future validation | Wrong/edited/stale file, false declaration, privileged upload | Bounded importer and audited access, only after scope proof | `SOURCE_GOVERNANCE_ADDENDUM` if execution semantics unchanged | Compatible evidence lineage can later accept machine transport |
| `POSITIVE_ONLY_GATE3_POLICY_AMENDMENT` | Official positives retained | Would accept unobserved restrictions as residual risk; no completeness-based clearance | PIT alone cannot repair missing negatives | Greater prospective eligibility, but possible missed restrictions | Existing APIs useful | Unobserved restrictions and outage-driven apparent clearance | Changes engine admission, downstream meaning and calibration/review | `COMPOSITE_POLICY_AMENDMENT_REQUIRED`; new composite revision, approval and eventual runtime version if adopted | Migration needs explicit policy/history isolation |
| `HARD_BLOCK_UNTIL_MACHINE_COMPLETE` | NSE remains required | Unknown stays insufficient; currently justified | Existing prospective and effective checks unchanged | Execution eligibility unavailable for affected cases; independent research still useful | Existing capture only | Availability/opportunity cost; no newly accepted clearance risk | No new runtime implementation | No execution policy change | Revisit source admission when mechanical evidence improves |
| `BROWSER_AUTOMATION` | NSE page remains source, browser is transport | Successful click/download cannot prove hidden completeness | Automatic receipt possible but source applicability still required | Unproven reliability and operator/support burden | UI selectors/session flow unproven | Wrong filters/tabs, stale downloads, session compromise; anti-bot dependency unproven | Additional browser/session operations | At least source-governance review; cannot waive completeness | Transport replaceable only if canonical evidence proves same product |

The positive-only option is not required merely to keep research usable. It
would alter both mandatory PASS evidence and potentially missing-versus-blocking
precedence. It needs a substantive composite policy amendment with explicit
source-gap risk acceptance, warnings and historical version isolation, not a
transport exception. No such amendment is approved here. Gate-6's separately
approved veto model does not authorize it.

Browser determinism, stable selectors, exhaustive scope, and prospective
auditability have not been proved. Browser-only or brittle anti-bot-dependent
transport is unsuitable for Gate authority; this slice does not assert that
NSE is necessarily browser-only or that such automation is required.

## Threat model and residual risk

| Risk | Deterministic mitigations / future controls | Residual limitation and fail-closed rule |
| --- | --- | --- |
| Wrong product/file | Exact source-product declaration, action audit, original filename/format and governed schema/sections | Filename can be forged; unresolved product binding -> `INSUFFICIENT_DATA` |
| Edited before upload | No-edit procedure, role/MFA/authorization, provenance audit and exact positive API corroboration | A valid edit can pass parsing and receive a new valid hash; no NSE signature is established; unresolved origin/content risk cannot be called authenticated |
| Altered after retention | Immutable raw retention, SHA-256, receipt fingerprint and reopen/parent verification | Privileged rewrite of bytes plus hashes remains a security risk; mismatch rejects evidence |
| Stale/reuploaded file | Stable raw identity, earliest first observation, source-supported effective state and existing freshness cap | Filesystem/user dates cannot prove currency; unresolved currentness -> `INSUFFICIENT_DATA` |
| Malicious upload | Future authenticated role/MFA/authorization, bounded format/size parser, no macros/evaluation/external links, filename treated only as metadata | No uploader/parser security is implemented or certified here; failed validation -> rejected/unknown evidence |
| False origin declaration | Authenticated actor, source declaration, immutable upload/action audit and separately recorded claimed time | Attestation can be false; no claim of cryptographic NSE authenticity or zero risk |
| Well-formed omitted rows/components | Source-defined complete-product scope, all declared sections/components and lossless rows, no filtering or silent dedup | Hash/schema/row count cannot prove undetectable omissions; currently unresolved -> `INSUFFICIENT_DATA` |
| API/artifact disagreement | Exact identity, preserve both lineages, PIT filter first, official supersession only | No voting, human arbitration of Gate result, or largest-timestamp winner; `CONFLICTED` -> `INSUFFICIENT_DATA` |

Future pilot security must demonstrate authenticated Admin/RA or explicitly
authorized operator role, MFA, action authorization, immutable audit/raw
retention, hashing, non-mutating validation, replay/idempotency and bounded
parsing. These are activation requirements from this directive, not a claim
that the current application already implements them. An unsigned artifact is
not automatically prohibited for a controlled pilot, but residual origin risk
and a verified complete-product procedure need explicit governed acceptance.

## Policy impact, independent blockers and reuse

The selected fallback changes **no execution policy**. A future controlled
transport with the same proven source scope, completeness, currentness, identity
and conflict semantics needs a `SOURCE_GOVERNANCE_ADDENDUM`, not automatically
a new execution-policy version. Waiving any of those admission requirements
would be a composite policy amendment; it must not be hidden in that addendum.
No artifact ingestion contract or trust exception is approved now.

PRICE_BAND retains its existing direct complete CSV capture. Its source capture
must not be downgraded because ASM/GSM transport differs. A future complete
ASM artifact, complete GSM artifact and direct price-band CSV may compose only
with independent valid provenance and compatible effective state for the exact
target context. This is a conditional composition rule, not present readiness.

`EXECUTION_MASTER_CONTINUITY = OPEN / SEPARATE_OPEN_BLOCKER`:
the accepted 2026-09-11 capture is incomplete (21,352 retained of 37,616 declared
rows); the reader uses the complete 2026-08-31 master. Those are inherited
measurements, not new database observations. Exact current price-band execution
identity remains blocked separately. Resolving it cannot close ASM/GSM capture
or source-effective-state blockers.

Reuse the [existing collector](../../app/market_data/surveillance_prospective.py),
[raw/evidence/completeness contracts](../../app/market_data/surveillance_observations.py),
[snapshot store](../../app/storage/core_api_snapshot_repository.py), existing
first-observed clock, identity bridge and [MII master](../../app/historical/nse_mii_security_master.py).
Any eventual transport extension must preserve independent operator/action
provenance while using that source lineage; an earlier API observation cannot
backdate a later operator attestation or completeness proof. No second store,
clock, identity resolver, Surveillance Brain or Gate engine is proposed.

## Validation and exact continuation

The [governance tests](../../tests/unit/test_gate3_asm_gsm_completeness_governance_fallback.py)
check receipt identity and full-content fingerprint, authoritative file pins,
the deterministic four-option decision matrix, unsafe semantic changes even
when rehashed, threat cases, first-observation and no-human-Gate-authority
requirements. Existing collector/PIT/conflict tests and approved Gate-3
policy/reducer tests are rerun. These are static governance and existing-code
proofs; they do not validate a future importer or MFA system.

Completed validation: **36 static fallback tests passed** and **215 existing
surveillance/source-governance/composite/production-policy tests passed**, with
zero failures, skips or warnings in these runs. The latter exercise existing
first-observation/no-backdating, conflict and complete-vector precedence; no
future upload security or source completeness is claimed by a passing test.

Markdown links, receipt integrity and `git diff --check` must pass before commit.
No full backend suite is required. No live acquisition or production database
write is performed. The [machine decision receipt](GATE3_ASM_GSM_COMPLETENESS_GOVERNANCE_FALLBACK_V1.json)
uses repository canonical JSON/SHA-256 excluding only `fingerprint`; this is
tamper-evident content identity, not a human or NSE signature.

Final decision: **C. `KEEP_GATE3_BLOCKED_UNTIL_MACHINE_COMPLETE`**.

Exactly one next continuation:
**`NSE_EXECUTION_MASTER_CURRENT_CAPTURE_CONTINUITY_REPAIR_V1`**.
It is not started. It addresses the separate current-master capture blocker
while ASM/GSM completeness remains explicitly unresolved.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE
NO_HUMAN_GATE_OVERRIDE = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```
