# Factual Research State Delta

`ResearchStateDelta` is a pure, non-persisted comparison of two immutable
`BrainResearchComparisonState` artifacts for one canonical instrument:

```text
BrainResearchComparisonState(T1)
  + BrainResearchComparisonState(T2)
  + explicit brain-research-comparability-policy / v1-approved
  -> ResearchStateDelta
```

It records only factual comparison outcomes: `COMPARABLE`, `INSUFFICIENT`,
`NON_COMPARABLE`, and `NOT_APPLICABLE`; and factual change kinds such as
`VALUE_CHANGED`, `ADDED`, `REMOVED`, or lineage/methodology/dependency drift.

Examples are factual only:

- a comparable revenue value changed;
- a governed setup eligibility value changed under identical policy lineage;
- a comparable score value changed under identical score methodology;
- sector RS remains insufficient when only current-only evidence exists.

None of those facts are good/bad, thesis/opportunity/risk conclusions, alerts,
recommendations, or trading instructions. The module does not query stores,
providers, or workers; does not run diagnostics, scores, setups, or gates; and
does not persist a comparison result.

`IntelligenceDelta` remains separate. It compares Unified Intelligence evidence
references/statuses. `ResearchStateDelta` compares the normalized factual
research observations and comparability lineage already held by two research
states.
