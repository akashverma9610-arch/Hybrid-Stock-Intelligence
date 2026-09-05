# Historical Regulator Company-Type Evidence Acquisition V1

**Status: `IMPLEMENTED / EVIDENCE_ONLY / COMPANY_TYPE_NOT_ACTIVE / NON_EXECUTABLE`.**

This bounded acquisition extends the immutable
`HISTORICAL_REGULATOR_ENTITY_EVIDENCE` family described by
[PIT Regulator Company-Type Evidence Ingestion V1](PIT_REGULATOR_COMPANY_TYPE_EVIDENCE_INGESTION_V1.md).
It records primary regulator rows and their source-dated availability; it does
not classify a company, activate `BANK`, `NBFC`, `INSURER`, or
`NON_FINANCIAL`, create a company master, or make an investment inference.

## Knownness and vintage rule

An artifact retains three distinct facts:

| Field | Meaning |
| --- | --- |
| `source_as_of_date` | The regulator's stated report/list/event date. |
| `source_known_on` | The regulator's stated publication date, retained as a date only. No time of day is invented. |
| `observed_at` | The later local HSI receipt time. It never changes source content or its original published date. |

For an artifact with `source_known_on`, historical evidence is eligible only
when both its stated source date and its date-only knownness are no later than
the research as-of date. Undated/current adapters retain their existing
receipt-time rule. This prevents a current list from leaking backwards while
allowing a subsequently acquired, already-published primary report to retain
its authentic publication vintage.

The optional `cor_issued_on` and `event_reason` fields preserve a cancellation
or surrender event exactly as supplied. A CoR issue date is **not** a
registration-start inference, and cancellation is **not** expanded into a
lifecycle interval.

## Acquired primary evidence

| Regulator artifact | Source context | Source as-of | Known / published | Exact rows retained | Deliberate exclusions |
| --- | --- | --- | --- | ---: | --- |
| IRDAI Annual Report 2022–23, Annexure 1 | `List of Registered Insurers/Reinsurers Operating in India (as on 31 March 2023)` | `2023-03-31` | `2023-12-27` | 25 Life, 25 General, 6 standalone Health | Reinsurers, specialised insurers, brokers, TPAs, intermediaries, agents, and web aggregators. |
| RBI press release `prid=57298` | `RBI cancels Certificate of Registration of Three NBFCs` | `2024-02-09` | `2024-02-09` | 3 cancelled-NBFC events | No registration/lifecycle interval, no name-based issuer link, and no company type. |

The IRDAI Annexure preserves page/table identity, category and exact legal
name. The public/private `Non-Life Insurers` subsections are stored only in the
existing General-insurer evidence family; specialised insurers and reinsurers
have no approved family in this acquisition and are excluded rather than
reinterpreted. The standalone Health subsection is kept separately.

The RBI event rows retain the legal name, registered-office address, CoR
number, CoR issued-on date, cancellation/order date, publication date and
deterministic source/evidence fingerprints. None supplies a CIN, so none is
an exact-CIN issuer correspondence.

## Explicit source limitations

| Requested source | Result | Treatment |
| --- | --- | --- |
| RBI *Report on Trend and Progress of Banking in India 2022–23*, released `2023-12-27` | The official publication release is verified, but the primary report payload was not retrievable as a valid document through the bounded acquisition path. | No bank rows or artifact are created from release/narrative text. Historical RBI-bank evidence remains `DATA_UNAVAILABLE`. |
| RBI list stated as `as on 30 June 2024` | The requested official path currently serves a different document labelled `as on 31 December 2024`, dated `2025-05-09`. | It is excluded completely; it is not relabelled as June 2024 and cannot support a June-2024 CIN snapshot. |
| IRDAI Annual Report 2021–22 | Annexure 1 contains a deterministic registered-insurer table. | Readiness confirmed; not acquired in this bounded slice. |
| IRDAI Annual Report 2020–21 | Annexure 1 contains a deterministic insurer table. | Readiness confirmed; not acquired in this bounded slice. |

The ingestion adapter is ready for a valid official structured RBI bank table
and a valid official structured June-2024 NBFC/ARC payload. It requires an
explicit source snapshot date and publication/known date; no source URL,
search index, filename, or current payload is substituted for those facts.

## Production receipt and replay

The activation wrote four source artifacts and 59 entity-evidence receipts:

| Outcome | Artifacts | Evidence rows |
| --- | ---: | ---: |
| First immutable write | 4 | 59 |
| Immediate exact replay | 0 inserted / 4 already present | 0 inserted / 59 already present |

The production regulator-evidence family now contains 8 artifacts and 242
rows. The pre-existing current RBI/IRDAI rows remain intact; no historical
artifact overwrote a current vintage.

## PIT readiness audit

| As-of | RBI bank rows | RBI registered NBFC/ARC rows | RBI cancellation rows | IRDAI Life | IRDAI General | IRDAI Health | Exact issuer-linked rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2024-02-05T23:59:59Z` | 0 | 0 | 0 (published after anchor) | 25 | 25 | 6 | 0 |
| `2026-08-31T23:59:59Z` | 0 historical | 0 | 3 | 25 | 25 | 6 | 0 |

At the February-2024 anchor, the new IRDAI report evidence is source-dated
and known by the anchor, but there are no active issuer bridges at that date.
The evidence and issuer-linkage gaps are reported separately. At the
August-2026 anchor, the three RBI events and 56 IRDAI rows are source-date
eligible; none has an exact CIN bridge, and IRDAI rows produce no RAW_EXACT
correspondence under the active policy. Existing current RBI-bank candidates
remain too late for that anchor under their original receipt-time semantics.

## Five-target evidence audit

| Symbol | Historical issuer bridge at `2024-02-05` | Historical RBI/IRDAI counterpart by anchor | Exact correspondence | Later regulator evidence | Earliest supported counterpart evidence |
| --- | --- | --- | --- | --- | --- |
| APARINDS | No | No exact counterpart | None | None | Unavailable |
| DEEPINDS | No | No exact counterpart | None | None | Unavailable |
| GENUSPOWER | No | No exact counterpart | None | None | Unavailable |
| GLAND | No | No exact counterpart | None | None | Unavailable |
| ICICIBANK | No | No historical RBI bank-row artifact in this slice; no IRDAI counterpart | None at either anchor | Existing current RBI-bank RAW_EXACT correspondence is retained but too late for both audited historical cutoffs | Current RBI receipt only; not a historical result |

This table is generic: ICICIBANK receives no hardcoded treatment. The same
source-date, exact-identifier, RAW_EXACT, uniqueness and PIT rules apply to
every issuer. Absence of a counterpart is not `NON_FINANCIAL`.

## Boundary and next policy dependency

No code here imports a company-type evaluator, Compounder/backtest,
portfolio, discovery, broker, order, API, or UI component. It creates no
strategy, score, price, allocation, BUY/SELL/ROTATE result or execution path.

`HISTORICAL_REGULATOR_PIT_COVERAGE = PARTIAL`: source-dated insurer evidence
is now meaningful for historical research, but historical RBI bank evidence,
the exact June-2024 NBFC/ARC snapshot, and historical issuer bridge coverage
remain missing. The next independent policy remains
`NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_PROPOSAL_V1`. Company-type activation is
not authorized until that policy and sufficient exact historical linkage are
separately governed.
