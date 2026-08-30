# Promotion evidence package

`PromotionEvidencePackage` is an immutable reference container for research and OOS evidence. It can reference the source hypothesis, experiment, research run, frozen selection, candidate/baseline fingerprints, assignments, execution results, window results, aggregate, and benchmark evidence.

It is evidence only. Creating a package cannot create a `StrategyPromotionProposal`, approve or activate a strategy, alter strategy configuration, or affect any real portfolio or broker.

The package builder includes every terminal assignment for the frozen selection, including losing, zero-trade, insufficient, and failed windows. It rejects mixed candidate fingerprints and overlapping TEST windows. Its coverage classification is neutral (`ACCUMULATING`, `INSUFFICIENT`, `DEGRADED`, or `FAILED_AUDIT`) and is never promotion eligibility, human approval, or activation.
