# Post-V1 Long-Term Thesis Families — Research Shadow V1 Readiness

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_ACTIVE`.**

## Purpose

This is the bounded, shared readiness policy for the five Long-Term Thesis
families.  It is not a quality, compounder, inflection, policy-transmission,
or asymmetric-company evaluator.  It accepts only an injected, PIT-valid
`DeepAnalysis` dossier provenance plus canonical-domain coverage assertions,
and returns a deterministic research-readiness receipt.  It creates no second
dossier, persistence, score, forecast, target, action, portfolio access, API,
or execution surface.

`RESEARCH_SHADOW_V1` means that a receipt may state whether the retained
canonical inputs are usable for a later calibrated policy.  It may never claim
that a company qualifies for a thesis family, is high quality, will compound,
has an inflection, benefits from policy, or is asymmetric.

## Common immutable contract

The receipt identity is the SHA-256 canonical serialization of exactly:

- contract version, family identifier, canonical instrument identifier, and
  thesis as-of;
- Deep Analysis dossier identifier and fingerprint; and
- the canonical, sorted domain coverage references and their fingerprints.

Its content fingerprint additionally includes the coverage availability,
source-availability timestamps, and canonical blockers.  Timestamps normalize
to UTC; no current time, locale, environment, or input order participates.
Every coverage reference must be non-empty, fingerprinted, unique, and
available on or before the thesis as-of.  A later, missing, stale,
non-comparable, conflicted, or unverifiable reference fails closed.  Duplicate
or conflicting references are rejected rather than silently deduplicated.

Every receipt has `WATCH_ONLY` and `NON_EXECUTABLE` fixed by contract.  It has
no strength, confidence, materiality, horizon, expiry, valuation, scenario,
milestone, or portfolio field.  Those fields remain unavailable until a
separate family policy approves their exact semantics.

## Exact `RESEARCH_SHADOW_V1` state semantics

| State | Exact condition | Output |
| --- | --- | --- |
| `DATA_INSUFFICIENT` | A required coverage domain is missing, unavailable, stale, or non-comparable. | A canonical, sorted list of the missing domain reasons; no family conclusion. |
| `CONFLICTED` | Any required coverage domain is explicitly conflicted. | A conflict blocker; no selection of one source. |
| `TEMPORALLY_INVALID` | The dossier or any selected coverage is later than thesis as-of. | A PIT blocker; later evidence cannot repair the result. |
| `UNVERIFIABLE` | Dossier/coverage identity, fingerprint, or version cannot verify. | An integrity blocker; no interpretation. |
| `POLICY_UNAVAILABLE` | All required coverage is present and PIT-valid, but the exact family policy, thresholds, classification, lifecycle and shadow outcome are not approved. | A readiness receipt only; never a positive family signal. |

There is deliberately no `QUALIFIED`, `PASS`, `READY`, or favourable family
state in this version.  `POLICY_UNAVAILABLE` is not evidence insufficiency: it
means evidence could be retained and valid but a normative evaluator remains
unapproved.

## Family coverage requirements

| Family | Required canonical coverage for the readiness receipt | Current feasibility conclusion |
| --- | --- | --- |
| `LONG_TERM_QUALITY_FAIR_VALUE` | comparable financial periods and scope; governance/reliability; return-on-capital or return-on-equity; cash conversion; leverage or interest coverage; valuation comparability; review and shadow outcome lineage | Current facts/filings are partial, while normalized ROCE/ROE, cash conversion, valuation comparability, specialist financial-company taxonomy, cadence and shadow outcomes are absent. Positive evaluation is unavailable. |
| `LONG_TERM_FUNDAMENTAL_COMPOUNDER` | comparable revenue/profit periods; margin/operating-leverage basis; cash conversion; working-capital basis; debt trajectory; governance/reliability; review and shadow outcome lineage | Revenue/profit and finance-cost facts are partial; normalized margin, cash, working-capital, debt trajectory, sector treatment, growth duration and calibration are unapproved or absent. Positive evaluation is unavailable. |
| `LONG_TERM_FUNDAMENTAL_INFLECTION` | comparable baseline periods; confirmed later periods; restatement/revision selection; exceptional-item treatment; governance/reliability; review and shadow outcome lineage | Period and revision lineage exists partially, but baseline, confirmation, restatement and exceptional-item policy are not approved. Positive evaluation is unavailable. |
| `LONG_TERM_POLICY_TRANSMISSION` | primary policy/legal evidence; exact exposure; legal/rule, funding, tender/order, capacity, execution, revenue, cash-flow, cancellation/supersession stages; review and shadow outcome lineage | Existing external-intelligence stages and exposure facts are reusable, but the full verified chain, stage acceptance, freshness, cancellation and outcome policy are absent. Positive evaluation is unavailable. |
| `LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER` | comparable growth path; dilution, liquidity, governance, balance-sheet and valuation coverage; survivorship-safe shadow outcome lineage | No approved asymmetry definition, financial-company taxonomy, dilution source contract, valuation method, liquidity policy, or survivorship-safe calibration exists. Positive evaluation is unavailable. |

## Evidence basis and research findings

The repository’s retained-data receipt remains authoritative for local
coverage: 3,427 financial facts, 311 filing identifiers, 31 instruments, and
341 filings are descriptive, not an assertion of a complete policy input set.
It explicitly records no normalized ROCE/ROE, cash conversion, working-capital,
EBITDA-margin, order-book/capacity, governed valuation-comparability, milestone
or prospective-shadow contract.

Official sources reinforce why one industrial ratio policy must not be applied
to every issuer.  [Ind AS 7](https://www.icai.org/post/10450) treats cash-flow
presentation as a financial-statement requirement; it does not supply HSI’s
cash-conversion formula.  The [Companies Act, 2013](https://www.mca.gov.in/content/dam/mca/pdf/CompaniesAct2013.pdf)
requires a cash-flow statement subject to statutory exceptions.  RBI’s
[financial-statement disclosure direction](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12158%281%29.html)
and [Basel III capital regulations](https://www.rbi.org.in/Scripts/BS_ViewMasterCirculars.aspx?Id=12815)
show bank-specific capital, asset-quality and liquidity disclosure contexts.
IRDAI’s [solvency regulations inventory](https://irdai.gov.in/consolidated-gazette-notified-regulations)
shows separate insurance solvency contexts.  These are regulatory sources, not
approved HSI formulas or thresholds.

SEBI’s [LODR Regulations](https://www.sebi.gov.in/web/?file=https%3A%2F%2Fwww.sebi.gov.in%2Fsebi_data%2Fattachdocs%2Fjun-2026%2F1780915347745.pdf)
provide listed-company financial-results disclosure context; they do not
choose long-term growth, fair-value, or invalidation parameters.

## Explicitly deferred policy choices

Before a positive evaluator, a family-specific approval must define its
formulae, scope and revision selection, financial-company branch, historical
lookback, categorical thresholds, valuation method and price basis where
applicable, freshness, milestones, invalidation, outcome window, chronological
calibration and prospective shadow measurement.  The readiness layer neither
selects nor recommends any of them.

## Rollback and dependency boundary

This receipt is a pure module dependent only on injected canonical provenance.
It does not import a repository, SQLite, portfolio, API, UI, broker, order,
`app.signals`, runtime clock, or external provider.  Deleting its isolated
module and tests rolls it back without altering Core V1.
