# Model Governance and Drift

Promotion governance is the existing immutable chain:
`proposal → OOS evidence → eligibility → explicit human review → approved
strategy version → separate prospective activation → rollback reference`.

The drift facade observes frozen `ModelVersionPerformance` records across
performance, calibration, regime, benchmark, and data/score-distribution
measures when supplied. It stores immutable `DriftObservation` and
`GovernanceAssessment` records and can recommend `WATCH`, `DEGRADED`, or
`DISABLE_RECOMMENDED`. A recommendation is never a promotion or deployment.

Self-improvement may observe, attribute, hypothesize, and create a governed
controlled-experiment draft. It cannot silently deploy any candidate. Previous
approved versions remain immutable and rollback reactivates an existing approved
version through explicit human-reviewed governance.
