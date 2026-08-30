# Self-improvement governance boundary

Self-improvement records use the same insert-only repository boundary as historical and promotion governance records. Attribution runs, observations, policies, rulesets, attributions, patterns, and summaries are immutable and round-trip through typed serializers.

Audit reconstruction recomputes the complete chain from the frozen run, observation dataset, evidence policy, and attribution ruleset. It compares reconstructed attributions, recurring patterns, and summaries to stored records and raises an audit error on mismatch. It never substitutes later evidence or a newer ruleset, and never repairs stored history.

Hypothesis reviews are separately immutable and require a human-attested reviewer and the exact frozen evidence fingerprint. An approval is only approval to proceed to later controlled research; it cannot write approved versions, active activations, score/gate/rotation/signal/paper configurations, brokers, orders, or real portfolios.

The experiment bridge additionally requires a matching current approved baseline and frozen ExperimentBudget. It writes no promotion proposal, eligibility, promotion review, approved strategy version, or activation.

Future OOS policy, assignment, and execution records are likewise insert-only. Audit reconstruction uses their exact queue, candidate, policy, and TEST-window references; it never substitutes a newer policy, strategy, candidate, or TEST window.
