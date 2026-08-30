# Financial Metric Observation Materializer

`materialize_financial_metric_observation(fact, selection=..., schema=...)`
is a pure, deterministic boundary from one already-selected PIT
`FinancialFact` to one factual `FinancialMetricObservation`.

It validates the selected-fact binding, exact frozen selector and schema
lineage, finite Decimal and representation fields, accounting-period identity,
and `visible_as_of = fact.available_at`. It preserves source, filing, revision,
quality and provenance lineage without conversion or inference.

Materialization is not fact-vintage selection: it accepts no fact collection
and never chooses a revision. It is not trajectory construction, QoQ/YoY/TTM,
directionality, research interpretation, alerting, recommendation, or action.
It is derived only: no database, store, provider, network, persistence,
filesystem, current-clock, API, worker, or scheduler dependency exists.
