# NSE Taxonomy Company-Type Code-Map Activation V1

**Status:** `ACTIVE / EVIDENCE_MAPPING_ONLY / NON_EXECUTABLE / NO_FINAL_COMPANY_TYPE`

## Purpose and authority

This is the activated successor to the preserved, non-active
[NSE Taxonomy Company-Type Code-Map Proposal V1](NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_PROPOSAL_V1.md).
It records immutable taxonomy-category evidence from the explicitly
human-approved fixed map. It does not alter the proposal artifact or create a
final HSI company-type result.

The active policy is `nse-taxonomy-company-type-code-map / v1`; its policy
fingerprint binds the approved proposal fingerprint, the complete 19-pair map,
and the source contract `NSE_INDICES_OFFICIAL / nse-indices-taxonomy-v1`.
The required governance lineage is:

```text
preserved proposal -> immutable human approval -> immutable active selection -> immutable evidence receipt
```

No selection may silently apply to another taxonomy source or version. An
unseen exact code pair stays unmapped until a separately reviewed policy
version exists.

## Exact semantics

Each receipt contains only the canonical issuer/security bridge lineage, exact
taxonomy-assignment identity and source hash, macro/sector codes, taxonomy
known/effective fields, map-entry provenance, policy/approval/selection
lineage, category, PIT cutoff, and deterministic fingerprint. It is always
`WATCH_ONLY / NON_EXECUTABLE`.

The only receipt categories are:

| Category | Meaning at this boundary |
| --- | --- |
| `NON_FINANCIAL_CANDIDATE` | Positive current business-classification evidence consistent with a *future* non-financial determination. It is not that determination. |
| `UNSUPPORTED_FINANCIAL` | Current sector-level taxonomy is too broad for non-financial or regulated-financial interpretation. It fails closed for non-financial Compounder research. |
| `UNKNOWN_NON_COMPARABLE` | Exact taxonomy evidence is retained but cannot support a current research candidate. |

There is no `REGULATED_FINANCIAL_CANDIDATE` mapping in V1. In particular,
`IN05 / IN0501` remains `UNSUPPORTED_FINANCIAL`; no receipt at this layer can
mean `BANK`, `NBFC`, `INSURER`, or final `NON_FINANCIAL`.

The map is exact at the current NSE sector level. It does not inspect taxonomy
display names, free text, symbols, legal names, regulator absence, or named
stocks. If a more specific official taxonomy level becomes available, the
broad map does not reinterpret it.

## PIT and evidence boundaries

A receipt requires all of the following at the supplied `as_of`:

1. an active exact ISIN-to-issuer forward observation already eligible at the
   cutoff;
2. an exact canonical `NSE:<ISIN>` taxonomy assignment eligible at the cutoff;
3. the bound official source/version and first-observed snapshot semantics;
4. one of the approved exact macro-sector/sector code pairs.

The selection activation timestamp is governance provenance, not historical
market knowledge. It cannot make a taxonomy assignment known before its own
effective/as-of fields. Missing taxonomy remains unresolved. Current 2026
taxonomy is not used for the 2024 research anchor.

RBI/IRDAI evidence, RAW_EXACT regulator-to-issuer linkage, and historical
regulator policy remain independent. This activation creates no regulator
precedence or conflict-resolution rule. The future final classifier must
combine issuer identity, taxonomy evidence, regulator evidence/conflicts, and
an approved company-type policy.

## Persistence and replay

Policy, approval, selection, and receipts use the append-only
`TAXONOMY_CATEGORY_EVIDENCE` snapshot family. Each ID and payload fingerprint
is deterministic. Replaying the same inputs is restart-safe and creates no
equivalent new receipt; a divergent value at an existing immutable ID fails
closed.

### Activated production receipt

The approved production replay at `2026-08-31T23:59:59+00:00` produced the
following immutable evidence receipt, with no use of later taxonomy data:

| Measure | Result |
| --- | ---: |
| Active exact issuer observations | 335 |
| PIT-valid exact taxonomy assignments | 202 |
| Taxonomy-category evidence receipts | 202 |
| `NON_FINANCIAL_CANDIDATE` | 168 |
| `UNSUPPORTED_FINANCIAL` | 33 |
| `UNKNOWN_NON_COMPARABLE` | 1 |
| Unmapped exact assignments | 0 |
| Missing taxonomy linkage | 133 |
| Taxonomy/regulator conflicts resolved here | 0 (not compared or resolved at this boundary) |

The first persistence inserted 205 records: one policy, one human approval,
one active selection, and 202 evidence receipts. Its immediate exact replay
inserted zero and found 205 immutable records already present.

At the `2024-02-05` research anchor, both PIT-valid taxonomy assignments and
taxonomy-category evidence receipts are zero. Current taxonomy therefore has
not been projected backward.

## Explicit non-goals

This activation does not create final company types, backtests, Compounder
qualification, rankings, Discovery output, portfolio state, capital authority,
broker or order access, APIs, UI changes, or future-version compatibility.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` remains preserved: a receipt is
the bounded taxonomy evidence input, not a final interpretive conclusion.

## Historical dependency

The available official taxonomy source is first observed in 2026. It cannot
establish a taxonomy receipt at the 2024 research anchor. The required next
dependency is therefore:

`HISTORICAL_NSE_TAXONOMY_ASSIGNMENT_ACQUISITION_V1`

Only after usable historical company-type evidence exists may
`PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1` be considered; this activation
does not authorize `COMPOUNDER_BACKTEST_PANEL_READINESS_V2`.
