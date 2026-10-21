# HSI lens foundation isolated reconciliation and canonical binding V1

Status: IMPLEMENTED_IN_ISOLATION / VALIDATED / NOT_ACTIVE

## Provenance and exclusions

Base: `f88b44d514fc9a2654040aa04e5350fc9e8660fe`, retaining both local source-acquisition/binding commits.
Reviewed draft PR: [#1](https://github.com/akashverma9610-arch/Hybrid-Stock-Intelligence/pull/1), head `243b20eae80e3c3d76803549c41500c7fa016821`.
JSON definitions: Lite `fcf288918591b0b6383dbc66bac70d7e9a4010fc`, copied verbatim.
This is a selective working-tree integration, NOT a merge or claim that the remote
history is reconciled. Main and its three uncommitted audit documents are preserved.
No remote seed, binary database, default deployment URL, or migration change was
imported. The two remote parent-reference repairs are static-valid candidates but
remain separate; no migration or production database access occurred.

## Implemented boundary

- [Canonical binding](../../app/lens_knowledge/canonical_binding.py) consumes native
  Daily certification, benchmark/sector and financial typed contracts with exact
  identity and aware UTC cutoff. Existing owner validators verify fingerprints.
- Existing canonical governance reader must resolve the approved diagnostic V1
  definition, with exact reference, semantic fingerprint, limitations, and
  creation/registration no later than the requested cutoff. No latest-now lookup.
- A fresh page-scoped existing runner evaluates each selected security at most
  once per call. Typed canonical diagnostic records use the existing domain
  fingerprint factory. All 35 lenses share that run; no diagnostic formulas change.
- If native Daily certification is unavailable, the existing technical contract
  cannot represent wholly absent bars. The row remains UNAVAILABLE and the runner
  is not invoked for that security: no generic/raw fallback or synthetic snapshot.
  This conservative page path does not independently evaluate other domains for
  that security. Their owner evidence is retained by fingerprint.
- Ordinary observations pass through the existing PIT assembler; future receipts
  are excluded. Current-descriptive certification is never labelled strict
  historical PIT. No claim of fresh market data or complete NSE coverage follows.
- A pure call has no writes. Optional draft-page saving uses the existing snapshot
  repository and a separate explicit `recorded_at >= as_of`; original acquisition,
  publication and known-at semantics remain in the referenced owner records.
  Retention time is NOT source known-at, detection time, or a P1 start receipt.
- Same page/cutoff/catalog/basis plus different diagnostic or input content is a
  conflict. Exact replay retains the first retention time. Replay still recomputes:
  no cross-run compute cache or compute-once-across-runs claim.
- 35 JSON definitions and the 350-cell matrix remain non-active. All 21 unresolved
  dependency labels survive; source availability is not lens fit. The older generic
  coverage helper remains explicitly SUPPLIED_UNVERIFIED, not a production binding.

## Safety and packaging

Core V1 ACTIVE; Execution Gate V2 NOT_ACTIVE. P1 prospective start UNSET and recorder
NOT_ACTIVE. No strategy activation, portfolio mutation, source acquisition,
provider connection, scheduler/API/UI wiring, public deployment or broker/order call.
No Analytics AI implementation, lens-fit evaluator, shared-calculation refactor,
or funnel deletion. The runner module has existing Core dependencies; this slice
does not call its gate, portfolio, scorecard or orchestration services.

Only one appended snapshot-family enum entry changes shared storage source; all
existing enum positions remain unchanged. JSON
package-data declarations keep the catalog available in installed wheels. No table,
schema migration, producer registration, runtime flag or active policy is changed.
Synthetic fixtures live only in tests and temporary test databases.

## Review findings corrected before regression

The draft store previously copied evaluation as-of into created_at; it now requires
explicit retention time. Canonical input proof and exact governed diagnostic
fingerprints are retained separately from unverified supplied coverage. Missing
native evidence cannot exploit the Core assembler's generic technical fallback.
An empty financial comparability scope change is not an actual content-vintage
change; the replay test uses a real changed source input instead. Tests use a new
workspace-local temporary directory because the shared Windows pytest temp
directory was inaccessible; no ACL or security settings were changed.

The first full run exposed four failures: the imported enum insertion shifted
existing positions; an exact historical source guard did not allow the new family;
five ignored archive test inputs were absent in the isolated checkout; and an
existing mocked route test still tried to open a host database. The enum is now
appended, and the conformance test permits exactly that appended line while keeping
the original receipt and every other byte pinned. The route test injects empty
comparison facts instead of touching a host database; its runtime code is unchanged.
The five existing archive CSVs were copied byte-identically into ignored test
storage. This archive test still requires those local inputs.

## Validation

Completed fixture-based results:

- Lens-focused: 45 passed, 3 subtests passed.
- Initial relevant regression: 91 passed, 2 warnings.
- Corrected focused and four failure areas: 526 passed, 2 warnings, 3 subtests passed.
- Final full backend: 9,002 passed, 0 failed, 6 skipped, 2 warnings,
  3 subtests passed in 444.30 seconds. Skips are opt-in provider/PostgreSQL canaries.
- Wheel: 35 taxonomy JSON files, dependency matrix and canonical binding verified;
  no database or .env payload. Build used declared isolated setuptools dependencies.
- All 36 catalog JSON files match pinned Lite bytes. 300 documentation links,
  whitespace and git diff --check passed.

No operational completeness claim is made. Source reads and live coverage have
not been certified by this isolated fixture-based validation.

## Remaining integration gates

1. Owner authorized a normal push of this validated review branch. Main remains
   divergent and requires a separately reviewed reconciliation. A review-branch
   push is not main synchronization or deployment.
2. Bind an actual owner-controlled read-only acquisition handoff in a separately
   bounded runtime slice, validate retained source provenance/freshness and a frozen
   eligible universe. The typed composition is not proof of physical store origin.
3. Keep every proposed lens UNKNOWN until its separately governed applicability,
   required evidence and policy are implemented and validated. Do not manufacture
   thresholds or treat the existing Pre-Breakout policy as approving Lite aliases.

## Lite retention warning

This imports 36 catalog JSON files, not all 227 tracked Lite files or its complete
history. Do not delete Lite based on this review-branch push. Full backup and
remaining-file disposition are separate work.
