# Long-Term Compounder Policy Research Proposal V1

**Status: `PROPOSED / NOT APPROVED / NOT ACTIVE`.**

## Purpose and authority boundary

This document converts the explicit `LONG_TERM_FUNDAMENTAL_COMPOUNDER`
research-shadow gaps into candidate definitions, data requirements, and a
future validation protocol. It is not a qualification policy, evaluator,
ranking, thesis, portfolio review, or strategy activation. A candidate grid is
research input only; documentation never makes a value selected, approved, or
active.

The existing `FundamentalCompounderResearchShadow` remains unchanged. Its
`POLICY_PARAMETER_UNAVAILABLE`, `DATA_INSUFFICIENT`,
`EVIDENCE_CONFLICTED`, and `NOT_APPLICABLE` states remain the only truthful
runtime outcomes. This proposal does not enable `SHADOW_CANDIDATE` or
`SHADOW_NOT_QUALIFIED`.

Every future implementation must retain `FACT → DATA → INTERPRETATION →
INFERENCE`, exact canonical identity, statement scope, value basis, units,
scale, period identity, publication/receipt visibility, revision lineage, and
same-as-of evidence lineage. No output may mean BUY, SELL, HOLD, ADD, TRIM,
EXIT, ROTATE, portfolio action, capital authority, setup, Six-Gates result,
broker access, or order placement.

## Existing reusable contracts and factual limits

| Contract | Reusable fact | Compounder limitation |
| --- | --- | --- |
| `FinancialFact`, `FinancialFactStore` | Immutable Decimal facts retain exact report, filing, scope, basis, revision, publication, and receipt lineage. | A fact's existence is not a quality, growth, cash, or capital-efficiency conclusion. |
| PIT fact-vintage selector and `FinancialMetricObservation` | `max(published_at, received_at)` visibility, exact semantic key, revision/conflict exclusion, and immutable fingerprints. | No implicit latest value, scope conversion, or ratio is permitted. |
| `FinancialResearchObservationBundle` and factual trajectory | Same-as-of artifact bundle; exact annual/quarterly/point-in-time pair semantics; positive-base relative delta only. | No persistence, CAGR, median, margin, ratio, materiality, or durability interpretation is supplied. |
| Fundamentals engine adapter and Core diagnostics | Legacy factual analysis can expose existing exact diagnostics without providers. | Its rules and thresholds are not a Compounder policy. |
| Corporate filings and historical corporate actions | Immutable official disclosure/action provenance and PIT eligibility. | No canonical binding from a share action to share-count/EPS normalization or economic dilution. |
| `InstrumentTaxonomyClassification` | PIT-effective sector/industry identity when present. | It has no approved peer-set, financial-sector branch, or historical peer-comparability policy. |
| Reliability/governance/diagnostic evidence | Exact upstream lineage and explicit missing/conflict states. | No Compounder-specific mandatory-veto or severity policy exists. |
| Pre-Breakout governance | Immutable draft → approval → selection lineage and PIT selection are established patterns. | It is the only strategy policy currently approved; it must not be reused as Compounder semantics. |
| Walk-forward, benchmark, and OOS contracts | Frozen candidate lineage, train/validation/test isolation, benchmark references, and audit boundaries exist. | No Compounder candidate-data set, outcome schema, or selected Compounder candidate exists. |

### Read-only local coverage finding

At the proposal audit cutoff, the production SQLite store contained 341
corporate filings across 31 instruments. Its reported financial-fact coverage
contained at most two distinct annual period ends per stored metric/scope and
six distinct quarterly period ends. Direct stored metrics were revenue, PBT,
PAT, basic EPS, finance cost, depreciation, total assets, and total
liabilities. This is an observation about current local coverage, not a
coverage promise or a substitute for a reproducible frozen research dataset.

The official BSE mapper deliberately does not infer EBITDA/EBIT, CFO, capex,
total debt, total equity, cash, shares outstanding, COGS, or working-capital
components. Upstox fundamentals remain a bounded reconciliation feasibility
surface with `OBSERVED_AT_FETCH_ONLY` timestamps; they are not canonical
PIT-safe `FinancialFact` input for this policy.

## Candidate non-financial dimensions

All grids below are **unapproved candidate regions** for future sensitivity
research. They are not defaults, pass/fail rules, weights, or production
thresholds. A future policy may use none of them after chronological research.

| Dimension | Candidate definition to research | Candidate research grid only | Required factual boundary | Current disposition |
| --- | --- | --- | --- | --- |
| Revenue persistence | Comparable annual revenue has a positive, defined growth relation in each required period. Zero/negative prior base has no percentage growth result. | successful observations `{3/3, 4/5, 5/5}`; annual windows `{3Y, 5Y}` | `REVENUE`, `FULL_YEAR`, same scope/currency/unit/scale, exact annual adjacency and PIT vintage. | `PARTIALLY_READY`: pairwise factual trajectories exist; current annual depth is insufficient. |
| Operating-profit persistence | Comparable annual EBITDA, operating profit, or EBIT growth, with metric identity fixed before testing. | same successful-period and window grids; no selected metric. | Direct `EBITDA`, `OPERATING_PROFIT`, or `EBIT`; no substitution among them. | `CANONICAL_DATA_MISSING` in current official coverage. |
| PAT persistence | Comparable annual PAT growth and sign-domain retention. | successful observations `{3/3, 4/5, 5/5}`; annual windows `{3Y, 5Y}` | `PAT`, `FULL_YEAR`, same representation; negative/zero prior base is unavailable for percentage growth. | `PARTIALLY_READY`: factual contract exists; current annual depth is insufficient. |
| Organic versus debt-funded growth | Compare growth with separately defined capital/debt movement only where all inputs have same PIT and accounting parity. | no threshold until debt-growth linkage and calibration are approved. | Revenue/PAT plus direct debt, cash, equity/capital-deployed definitions and corporate-event treatment. | `DEFINITION_MISSING` and `CANONICAL_DATA_MISSING`. |
| Capital efficiency | Candidate ROCE, ROIC, incremental return on capital, annual median, minimum, or consistency measure. | candidate ROCE regions `{12%, 15%, 18%, 20%}`; aggregation `{latest, 3Y median, 5Y median, minimum}`. | A separately approved numerator/denominator, exact annual dates, and sector/financial-company applicability. | `DEFINITION_MISSING`: existing factual ROCE variants are not a persistent Compounder metric. |
| Cash conversion | Cumulative `CFO / PAT`, annual `CFO / PAT`, or FCF conversion only on comparable annual flows. | ratio regions `{0.70, 0.80, 0.90, 1.00+}`; windows `{3Y, 5Y}`. | Direct annual CFO/PAT; FCF also needs approved capex sign and compatible CFO/capex basis. Zero/negative PAT has no ratio result. | `CANONICAL_DATA_MISSING` in current official coverage; FCF definition also requires policy. |
| Margin durability | Operating-margin median, variability, worst deterioration, or current versus median. | no selected margin floor; candidate variability/deterioration grid requires separate research. | One chosen direct operating metric divided by same-scope revenue, comparable annual periods, and sector context if used. | `DEFINITION_MISSING` and direct operating-metric coverage missing. |
| Debt quality | Debt/equity, net debt, net debt/EBITDA, interest coverage, and debt trajectory. | no universal debt or coverage threshold; candidate regions require branch and sector research. | Direct debt/equity/cash, direct EBITDA or EBIT, finance cost, exact point-in-time/flow alignment. | `CANONICAL_DATA_MISSING`; ratio definitions remain unapproved. |
| Dilution/capital allocation | Diluted share-count CAGR, absolute count change, buyback/issue/rights/QIP/ESOP/acquisition issuance. | no approved threshold; later research may test change regions only after action-normalized share lineage. | PIT share counts plus exact action, issue, and split/bonus/rights linkage. | `CANONICAL_DATA_MISSING` and normalization contract missing. |
| Reinvestment quality | Reinvestment rate, capital deployed, incremental return, and growth per unit reinvested. | no grid: the formula, denominator, and treatment of acquisitions are not defined. | Approved capital-deployed, cash-flow, capex, working-capital, acquisition, and period-comparability contracts. | `DATA CONTRACT MISSING`. |
| Persistence/deterioration | Number of successful periods, rolling window, deterioration tolerance, and review cadence. | windows `{3Y, 5Y}`, successful periods `{3/3, 4/5, 5/5}`; no tolerated failure count selected. | A separately approved metric result and chronological comparable history. | `DEFINITION_MISSING`; current depth insufficient. |

Candidate CAGR is only mathematically eligible when an approved annual window
has positive beginning and ending values and a fixed count of compatible annual
periods. No candidate formula may repair zero, negative, missing, restated,
mixed-scope, mixed-unit, shortened-period, or corporate-action-ambiguous data.

## Separate financial-sector branches

Non-financial ratios must not be applied to a bank, NBFC, or insurer. The
current long-term research-shadow branch is caller-supplied and has no
canonical company-type resolver. That classification gap must be closed before
any branch is evaluated.

| Branch | Candidate dimensions for later research | Current canonical status |
| --- | --- | --- |
| Bank | ROA, ROE, NIM, GNPA, NNPA, credit cost/provisioning, CET1/CRAR, deposit/loan growth, cost efficiency, asset-quality persistence, dilution. | `CANONICAL_DATA_MISSING`: no prudential financial extractor or approved branch taxonomy. |
| NBFC | ROA/ROE, asset quality, credit cost, capital adequacy, leverage, funding quality/cost, liquidity/ALM, AUM growth, dilution. | `CANONICAL_DATA_MISSING`: banking definitions cannot be copied; no approved NBFC source/metric contract. |
| Life insurer | Solvency, premium/APE growth, persistency, and new-business economics where PIT-complete. | `CANONICAL_DATA_MISSING`: life/general insurer classification and insurer metric extractor absent. |
| General insurer | Solvency, combined ratio, claims/loss ratio, underwriting profitability, premium growth, and retention. | `CANONICAL_DATA_MISSING`: no insurer subtype taxonomy or canonical measurement contract. |
| Unknown or structurally non-comparable | No Compounder comparison. | `NOT_APPLICABLE`; do not guess branch from text, name, or ticker. |

## Canonical data-feasibility matrix

`READY_FOR_CANDIDATE_TESTING` means a metric contract and sufficient frozen
historical corpus both exist. None is currently ready at the required
Compounder-policy level.

| Metric/dimension | Branch | Exact inputs | PIT historical depth | Calculation definable today | Normalization / peer need | Status and blocker |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue annual pair delta | non-financial | direct `REVENUE`, annual full-year, same representation | contract yes; local corpus <=2 annual ends | factual delta/positive-base relative delta only | no peer; no action normalization | `PARTIALLY_READY`: needs ≥3/5 comparable annual periods and policy. |
| PAT annual pair delta | non-financial | direct `PAT`, annual full-year, same representation | same constraint | factual only | no peer; no action normalization | `PARTIALLY_READY`: needs depth and policy. |
| Revenue/PAT CAGR or consistency | non-financial | annual pair/series plus exact count | insufficient | no: aggregation, windows, and zero/negative semantics not approved | no peer required | `DEFINITION_MISSING`. |
| EBIT/EBITDA growth and operating margin | non-financial | direct EBIT/EBITDA plus revenue | missing official metric coverage | no policy calculation | exact metric choice; sector optional | `CANONICAL_DATA_MISSING`. |
| ROE/ROCE/ROIC/incremental ROIC | non-financial | PAT/EBIT plus chosen equity/capital/debt/cash inputs | missing inputs/depth | no: formulas and aggregation unapproved | company-type and period alignment required | `DEFINITION_MISSING`. |
| CFO/PAT | non-financial | annual direct CFO and PAT | CFO missing | ratio formula simple but policy not approved | no action normalization | `CANONICAL_DATA_MISSING`. |
| FCF conversion | non-financial | direct CFO, compatible capex with explicit sign, PAT | CFO/capex missing | no: FCF sign/aggregation policy incomplete | capex definition required | `CANONICAL_DATA_MISSING`. |
| Debt/equity, net debt, interest cover | non-financial | debt/equity/cash, EBIT/EBITDA, finance cost | finance cost only currently present | no: ratio and sector policy absent | stock-flow alignment required | `CANONICAL_DATA_MISSING`. |
| Working-capital/reinvestment | non-financial | inventory, receivables, payables, COGS, capex, capital inputs | missing | no | business/sector and acquisition treatment | `DATA CONTRACT MISSING`. |
| Share-count dilution | non-financial | `SHARES_OUTSTANDING`, issue/buyback/ESOP lineage, action binding | share count missing | no | split/bonus/rights/QIP normalization required | `DATA CONTRACT MISSING`. |
| Governance/reliability availability | all | existing exact evidence/diagnostic lineage | conditional PIT coverage | factual availability/conflict only | no peer | `PARTIALLY_READY`: Compounder veto/requirement policy absent. |
| Sector-relative comparison | non-financial | PIT taxonomy, peer universe, metric parity, peer calculation | taxonomy contract only | no | historical peer set/selection and survivorship control | `DEFINITION_MISSING`. |
| Bank/NBFC/insurer dimensions | financial | branch-specific regulatory/issuer measurements | absent | no | explicit subtype taxonomy and source policy | `CANONICAL_DATA_MISSING`. |

## Candidate-grid and validation protocol

Future research must pre-register one or more candidate grids, then evaluate
their stability rather than select an isolated historical optimum. Candidate
regions listed here are limited to annual consistency `{3/3, 4/5, 5/5}`;
windows `{3Y, 5Y}`; ROCE regions `{12%, 15%, 18%, 20%}`; and CFO/PAT regions
`{0.70, 0.80, 0.90, 1.00+}`. They remain unapproved and may be rejected in
full. Debt, margin, dilution, reinvestment, and financial-sector regions need
their own exact data contracts before a grid can even be constructed.

Any later candidate study must require:

1. a frozen historical universe/membership definition for every evaluation
   date, not today's universe;
2. only financial facts visible at the historical as-of, with period end never
   substituted for publication/receipt visibility;
3. immutable revisions and explicit same-period conflict handling;
4. unchanged statement scope, currency, unit, scale, fiscal identity, and
   corporate-action comparability within each metric computation;
5. chronological train/validation/test partitions with purge/embargo and
   candidate identity frozen before test, reusing the existing walk-forward
   contract where compatible;
6. multiple market regimes, sectors, and nearby parameter choices; and
7. a recorded non-selection outcome for insufficient, conflicted, or
   non-comparable evidence.

The candidate assessment should inspect forward 3Y and, only when depth
permits, forward 5Y return, benchmark-relative return, maximum drawdown,
profitability/cash/capital-efficiency persistence, balance-sheet deterioration,
failure/distress incidence, sector concentration, turnover, and valuation
interaction. Price return must use the declared benchmark and adjustment basis;
it cannot be the sole objective. The primary question is durable business
quality, not retrospective price maximisation.

An isolated best threshold, a current-universe survivor sample, current-period
consensus, a later restatement, later corporate-action mapping, later sector
classification, or a hand-picked successful issuer invalidates candidate
selection. If a metric cannot meet every PIT and comparability requirement, it
is not ready rather than treated as neutral or zero.

## Intended future governance lifecycle

The existing Pre-Breakout implementation demonstrates immutable draft,
approval, fingerprint verification, temporal selection, and active-policy
separation. A future Compounder policy should reuse that governance direction:

```text
RESEARCH_PROPOSAL
  -> CANDIDATE_GRID
  -> BACKTESTED
  -> HUMAN_REVIEWED
  -> APPROVED
  -> SELECTED
  -> ACTIVE
```

No state in that lifecycle is created by this document. An approved policy must
have its own exact identity/version/fingerprint, required-evidence matrix,
company-branch scope, insufficiency/conflict behavior, candidate-data lineage,
historical validation receipt, human approval, temporal selection, and a
separate activation decision. It must remain non-executable even after a
future research-shadow evaluator is approved.

## Explicit non-goals

This proposal creates no data provider, scraper, canonical fact, derived
metric, formula evaluator, candidate qualification, stock list, ranking,
Decision Score input, Six-Gates change, holding review, harvest/sell/rotation
logic, persistence, API/UI, portfolio access, broker/order capability, or
performance claim. Missing evidence remains missing evidence, not an adverse
business conclusion.

## Recommended next step

Choose **A — canonical data-contract work**, not a Compounder candidate-grid
backtest harness. The narrowest useful prerequisite is an approved,
PIT-rebuildable non-financial annual Compounder research dataset contract for
direct EBITDA/EBIT, CFO, capex, total debt, total equity, cash, and share-count
facts, including statement scope/basis, corporate-action linkage, and a frozen
historical coverage receipt. It must remain factual and create no Compounder
qualification. Only after that contract is populated with adequate immutable
annual history should a candidate-grid harness be proposed.
