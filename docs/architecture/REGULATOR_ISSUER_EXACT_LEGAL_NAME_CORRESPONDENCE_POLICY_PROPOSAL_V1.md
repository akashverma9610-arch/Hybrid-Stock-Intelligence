# Regulator–Issuer Exact Legal-Name Correspondence Policy Proposal V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## Purpose and narrow decision boundary

This proposal asks whether a strictly one-to-one correspondence between two
independent primary records may become a future *candidate identity bridge*:

```text
active canonical issuer: CIN C <-> legal name N
official regulator row: legal regulated-entity name N <-> category/subtype R
```

It is not a company-type policy, company-type activation, issuer-master
change, or investment qualification. It cannot select `BANK`, `NBFC`,
`INSURER`, or `NON_FINANCIAL`; it cannot backfill history, run a Compounder
backtest, access a portfolio, or produce a broker/order/API/UI action.

Existing exact issuer bridges remain the only active identity mechanism. The
current regulator-evidence code intentionally does **not** use legal names for
linkage. This document does not change that behavior.

## Evidence fields inspected

| Evidence side | Existing immutable field(s) | Current use in this proposal |
| --- | --- | --- |
| Canonical issuer | BRSR `ExactIssuerIdentifierEvidence`: exact NSE symbol, CIN, `issuer_legal_name`, filing/source fingerprints, `historical_known_at`; active forward ISIN/CIN observations | Supplies a candidate CIN/name only after exact active issuer lineage is already present. |
| RBI scheduled bank | `RegulatorEntityEvidence`: `legal_name`, exact RBI table subtype, source row/artifact fingerprints and observation semantics | Separate `RBI_SCHEDULED_COMMERCIAL_BANKS` candidate set. |
| RBI NBFC / ARC / cancelled CoR | Same immutable regulator receipt fields, including CoR/CIN/category/date if an official XLSX actually supplies them | Structurally supported only; production rows are unavailable. |
| IRDAI Life / General / Health | Separate immutable legal name, registration number where supplied, explicit subtype and source lineage | Three separate candidate sets; they are never merged. |

No repository legal-name normalization utility or fuzzy-name library provides
an approved issuer identity bridge. `IssuerIdentifierType` intentionally does
not treat a legal name as a stable identifier. That boundary remains correct.

## Proposed comparison tiers

### `RAW_EXACT`

The first, preferred candidate tier is exactly:

```text
Unicode NFC(name).strip() == Unicode NFC(other_name).strip()
```

NFC is permitted only to stabilize equivalent Unicode representation; `strip`
removes leading/trailing presentation whitespace. No other transformation is
permitted. In particular this tier must not case-fold, collapse interior
whitespace, remove punctuation, reorder words, remove corporate suffixes,
expand abbreviations, translate/transliterate, repair spelling, or use an
alias/former/brand name.

### `REPRESENTATION_EXACT` — research candidate only

Read-only source inspection found six additional RBI bank strings differing
from their BRSR issuer name only by letter case:

`Indian Overseas Bank`, `Union Bank of India`, `Au Small Finance Bank Limited`,
`Jana Small finance Bank Limited`, `UCO Bank`, and `Bank of Maharashtra`.

If separately approved, this tier would be restricted to:

```text
Unicode NFKC(name)
-> replace ASCII/non-breaking spaces with ASCII space
-> collapse repeated whitespace
-> Unicode casefold
```

It still must not delete punctuation, substitute `Ltd`/`Limited`, expand an
acronym, reorder tokens, or make any lexical/legal-name change. There was no
observed punctuation, suffix, abbreviation, alias, former-name, or word-order
variant in the proposed additions. This is a **candidate definition only**;
case-folding has no existing human-approved legal-identity policy.

## Mandatory one-to-one and source-isolation rules

For either tier, a future candidate correspondence requires all of the
following:

1. exactly one regulator row in its one regulator family/subtype candidate
   set for the compared name;
2. exactly one active canonical issuer CIN for that compared name;
3. exactly one canonical legal name for that CIN in the active BRSR lineage;
4. no competing regulator family/subtype, no competing CIN, and no retained
   exact-evidence conflict;
5. the canonical issuer itself is the named regulated entity; and
6. both evidence sides are PIT-eligible at the requested evaluation time.

`RBI BANK`, `RBI NBFC`, `RBI ARC`, `IRDAI LIFE`, `IRDAI GENERAL`, and
`IRDAI HEALTH` are evaluated separately. A row in two different families is a
conflict, never an automatic merged result. A parent, holding company,
subsidiary, group, common brand, or similarly named affiliate is outside this
proposal and remains unresolved.

Any one-to-many, many-to-one, duplicate regulator name, duplicate issuer name,
cross-family collision, missing name, future evidence, or source-date gap is
`EVIDENCE_CONFLICTED` or `DATA_UNAVAILABLE`; no candidate is chosen.

## PIT rule

Candidate string equality is insufficient. A future receipt may be considered
only when the BRSR issuer `historical_known_at` and the regulator row's
explicit source-date/known-time semantics are both no later than the requested
as-of time. A current regulator page with no date is not repaired from its
retrieval time. It cannot establish 2024 status and, in the current data, it
also cannot establish 2026-08-31 status.

## Read-only production audit

Audit scope: active 2026-08-31 forward issuer observations, mapped back through
their immutable BRSR anchor evidence. It contains 335 observations, 332 CINs,
and 333 distinct canonical legal-name facts. One CIN is associated with two
different canonical legal names; this is an ambiguity, not a name-linking
shortcut.

| Family | Rows | Raw string matches | Raw one-to-one candidates | Representation string matches | Representation one-to-one candidates | Duplicate regulator names | Canonical-name/CIN conflicts | PIT-valid candidates at 2026-08-31 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RBI BANK | 121 | 8 | 7 | 14 | 12 | 0 | 1 raw / 2 representation rows blocked by the one ambiguous CIN | 0 |
| RBI NBFC | 0 | 0 | 0 | 0 | 0 | 0 | `DATA_UNAVAILABLE` | 0 |
| RBI ARC | 0 | 0 | 0 | 0 | 0 | 0 | `DATA_UNAVAILABLE` | 0 |
| RBI cancelled CoR | 0 | 0 | 0 | 0 | 0 | 0 | `DATA_UNAVAILABLE` | 0 |
| IRDAI LIFE | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| IRDAI GENERAL | 28 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| IRDAI HEALTH | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The current RBI/IRDAI records have `SOURCE_DATE_UNAVAILABLE` and were observed
after 2026-08-31. Thus the 7/12 bank values are correspondence *research
candidates*, not PIT-usable identity bridges or classifications. No
cross-subtype insurer collision was observed. At `2024-02-05T23:59:59Z`, there
are zero active issuer bridges and zero PIT-valid regulator/taxonomy records.

### Five-target audit

| Symbol | CIN | Canonical legal issuer name | Raw candidate | Representation candidate | Regulator source/subtype | PIT-valid | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| APARINDS | `L91110GJ1989PLC012802` | `APAR Industries Limited` | No | No | None | No | `NO_EXACT_REGULATOR_CORRESPONDENCE` only. |
| DEEPINDS | `L14292GJ2006PLC049371` | `Deep Industries Limited` | No | No | None | No | `NO_EXACT_REGULATOR_CORRESPONDENCE` only. |
| GENUSPOWER | `L51909UP1992PLC051997` | `Genus Power Infrastructures Limited` | No | No | None | No | `NO_EXACT_REGULATOR_CORRESPONDENCE` only. |
| GLAND | `L24239TG1978PLC002276` | `GLAND PHARMA LIMITED` | No | No | None | No | `NO_EXACT_REGULATOR_CORRESPONDENCE` only. |
| ICICIBANK | `L65190GJ1994PLC021012` | `ICICI Bank Limited` | Yes | Yes | RBI BANK / `Domestic Private Sector Banks` | No | Exact text candidate only; RBI row supplies no CIN and is not PIT-valid. |

An unmatched issuer is never `NON_FINANCIAL` under this proposal.

## Future pure receipt, if separately authorized

A future research-only receipt may contain: CIN; canonical issuer legal name
and its source ID/fingerprint; regulator evidence ID/fingerprint; regulator
family/subtype; `RAW_EXACT` or `REPRESENTATION_EXACT`; issuer known-at;
regulator source/known/effective timestamps; requested evaluation as-of;
one-to-one proof; conflict state; policy identity/version; deterministic ID and
fingerprint. It would be pure and immutable, with no persistence in this
proposal. It must not contain a company type, investment score, price, sizing,
portfolio object, trade action, or execution authority.

## Approval recommendation

`RAW_EXACT_POLICY_APPROVAL_RECOMMENDED = YES` — conditioned on the mandatory
one-to-one and PIT rules above. The observed canonical ambiguity is safely
fail-closed rather than resolved by choice.

`REPRESENTATION_EXACT_POLICY_APPROVAL_RECOMMENDED = NO` — the observed six
case-only differences are plausibly presentation-only, but case-folding still
needs an explicit human legal-identity decision. The raw tier provides useful
strict coverage without that expansion.

Even after a future positive regulator-link policy, positive non-financial
classification remains separately blocked by:

`NSE_TAXONOMY_COMPANY_TYPE_CODE_MAP_PROPOSAL_V1`

Only after both governed dependencies and the existing proposed company-type
policy are approved could `PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1` be
considered. This proposal neither approves nor activates any of them.

**`HUMAN_APPROVAL_REQUIRED`**
