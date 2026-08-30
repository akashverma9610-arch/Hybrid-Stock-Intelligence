# Fundamental data

Mock filings use `FUNDAMENTAL` observations with explicit `period_type` (`quarterly`, `annual`, or explicitly derived `ttm`), `period_end`, and `publication_timestamp`. Period end is not knowledge time: a filing is excluded from an as-of snapshot until publication. Indian fiscal periods are retained as reported; the engine never assumes a calendar fiscal year. Restatements are append-only observations with `supersedes_observation_id`, allowing historical reproduction.

Financial facts may also be populated from a user-supplied official NSE
structured/XBRL-converted local export through the frozen real-Brain cohort
import boundary. Reported values remain immutable and retain their filing,
publication/receipt times, period, scope, currency, unit, scale, and revision
lineage. The import never parses a PDF, invents a zero for a missing metric, or
mixes standalone and consolidated facts in a derived calculation.

Financial payloads can include `cogs`/cost of revenue, total assets, and
current liabilities for the canonical CCC and ROCE methods. Missing or
incomparable periods yield `INSUFFICIENT_DATA`; missing COGS yields an
explicitly labelled partial CCC rather than a revenue approximation. Order-book
and working-capital metrics may be `NOT_APPLICABLE` when explicitly marked.
