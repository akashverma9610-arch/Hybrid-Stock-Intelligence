# Feature flags and runtime capabilities

## Automated self-improvement research

`FeatureSettings.automated_self_improvement_research_enabled` is the typed
capability boundary for a future automatic runtime/scheduler. It defaults to
`False`. The corresponding capability is:

| Field | Default |
| --- | --- |
| Name | `AUTOMATED_SELF_IMPROVEMENT_RESEARCH` |
| Enabled | `false` |
| Maturity | `EXPERIMENTAL` |
| Lifecycle status | `DEFERRED` |
| Production blocking | `false` |

`ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH` may explicitly opt in a future
runtime. Values use normal boolean spellings (`true`/`false`, `1`/`0`, etc.).
An invalid value fails closed during settings construction.

Calling `require_automated_self_improvement_research_enabled()` with the
default settings raises `AUTOMATED_RESEARCH_DISABLED`. It creates no research
run, future-OOS artifact, evidence package, promotion, approval, activation, or
account-side effect.

This setting does **not** guard the Phase 9B library services. They remain
available to tests, manual development, and controlled internal use. No
automatic Phase 9B production orchestrator currently exists.
