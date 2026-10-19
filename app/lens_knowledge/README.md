# Draft lens coverage foundation

The 35 JSON taxonomy records and dependency matrix are copied without policy
changes from `akashverma9610-arch/HSI-Agent-Lite` commit
`fcf288918591b0b6383dbc66bac70d7e9a4010fc`. Their own provenance and proposed,
inactive lifecycle are preserved. They are not approvals or trading rules.

`assessment.assess_lenses` consumes existing `EvaluatedDiagnostic` results
for one instrument and cutoff and describes coverage of *proposed primary*
diagnostic references. It performs no provider calls or calculation. It does
not inspect the actual lens-specific evidence or determine applicability. Every
result remains `UNKNOWN`, including if all listed diagnostics are eligible.
The diagnostic references are an indicative design, not a full or approved
set of mandatory inputs. Callers must not use this function for screening,
ranking, score, setup, gates, trading or portfolio decisions.

No API, scheduler, persistence, analytics AI, whole-universe orchestration or
existing funnel is changed. To make a lens operational, specify and approve
its policy and instrument applicability, implement its named evidence and
as-of contracts, connect canonical stored sources, evaluate historical and
prospective examples, then explicitly authorize activation. In particular,
order-book/capex evidence, exitability and event-specific requirements cannot
be assumed satisfied just because a generic diagnostic result exists.

`universe.assess_universe_batch` accepts a supplied existing universe snapshot
and already-computed diagnostic results, with a bounded cursor and explicit
missing-result counts. It neither queries the database nor runs diagnostics;
the calling application is responsible for obtaining a trustworthy snapshot
and results from its stored-data path. A caller resuming a scan must retain the
same snapshot, cutoff, catalog version and diagnostic vintages. Results are
draft coverage only, with no fit evaluation. `DraftLensCoverageStore` can save
an immutable page in the existing snapshot repository. It records the exact
catalog fingerprint and per-security diagnostic-content fingerprints, rejects
changed content at an identical page identity, and verifies reads. This is not a
scheduler, a complete scan checkpoint, or a verified historical data lineage.
