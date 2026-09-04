# Issuer / Legal-Entity ↔ Listed-Security Identity Bridge — Primary Evidence V1

**Status: `IMPLEMENTED_CONTRACT / PRIMARY_SOURCE_ONLY / NOT_ACTIVE / NON_EXECUTABLE`.**

## Purpose and boundary

This foundation is a frozen, point-in-time-safe receipt linking one exact listed-security session record to one exact stable issuer identifier. It is not an issuer/company master, company-type policy, investment policy, discovery system, or strategy.

The security-side fact is the existing [`NseSessionPointIdentity`](NSE_SESSION_KNOWN_SECURITY_IDENTITY_ACTIVATION_V1.md): one official NSE row proves its exact exchange, symbol, series, ISIN, security code, and identity only for its labelled trading session. `IssuerSecurityBridge` can bind that receipt only when a separately supplied approved primary artifact proves both the exact security and stable issuer identifier.

The contract itself has no source acquisition, API, UI, provider, scoring, portfolio, broker, order, or execution dependency. The separately bounded [exact primary acquisition](EXACT_ISSUER_IDENTIFIER_PRIMARY_ACQUISITION_V1.md) stores supplied, structured source receipts and their same-session bridges in the existing immutable snapshot repository. Neither component can classify a company, establish investment qualification, calculate a metric, or run a backtest.

## Identity levels remain separate

| Level | Permitted meaning | Prohibited conclusion |
| --- | --- | --- |
| Legal entity / issuer | Stable CIN, LEI, regulator registration, official listing issuer ID, or future canonical issuer ID. | Free-form name is a legal identifier. |
| Listed security | Exact NSE session-security receipt. | It identifies a parent/group. |
| ISIN | Security identifier in that session receipt. | It is a legal-entity ID or proves continuity. |
| Exchange listing | Exact NSE session context. | It establishes an interval. |
| Symbol | Descriptive exchange symbol for that security. | It proves issuer identity. |
| Corporate group / parent | Separate economic/legal relationship. | It may be inferred from a security link. |

```text
listed security → exact issuer: permitted only with primary bridge evidence
listed security → parent group: prohibited
subsidiary → listed parent: prohibited
same ISIN across sessions → issuer continuity: prohibited without explicit evidence
changed ISIN → predecessor/successor: prohibited without explicit lifecycle evidence
```

No edit distance, case-folded name equality, aliases, manual mapping, LLM inference, symbol-to-company guess, sector, or provider display name is a bridge key.

## Existing model and artifact audit

There is no populated canonical issuer/legal-entity model or issuer table in the active production database. The acquisition adapter now has an append-only primary-evidence receipt/bridge store; it does not create an issuer master. The old proposed company-type contract has a small `ExactIssuerSecurityBridge` input shape, but it is neither a canonical issuer store nor a stored receipt.

The gap is both model absence (no populated legal issuer entity/identifier registry) and mapping absence (no stored primary artifact linking an NSE session security to CIN, LEI, regulator registration, official listing issuer ID, or another stable legal key).

| Existing Core artifact | Exact security fields | Current issuer-grade ID | Bridge treatment |
| --- | --- | --- | --- |
| NSE MII / `NseSessionPointIdentity` | NSE, symbol, series, ISIN, `FinInstrmId`, session/source lineage | None | Security side only. |
| `HistoricalSecurityIdentity` | Canonical instrument, ISIN, exchange, symbol, lifecycle fields | None; production count 0 | Untouched. |
| BSE master / `BseSecurityMapping` | ISIN, BSE scrip code, BSE security ID, security name | None | Reconciliation only. |
| BSE XBRL / `BseXbrlDocument` | BSE security code, ISIN, security name, document lineage | No structured CIN/LEI/legal issuer field | Financial evidence stays separate. |
| `CorporateFiling` | `InstrumentIdentity`, source provenance | No issuer/entity field | Cannot bridge. |
| `FinancialFact` | Upstream instrument, filing ID, fact provenance | No issuer/entity field | Cannot bridge. |
| NSE Reg31 record | Exact ISIN, symbol, source issuer text | No stable issuer ID | Text consistency only, never a bridge. |
| BSE lifecycle evidence | BSE scrip/ISIN plus descriptive company text | No issuer/legal ID | Lifecycle only. |
| Provider master | Provider mapping and display identity | Not approved canonical legal evidence | Reconciliation only. |

The [NSE circular describing the daily MII security file](https://nsearchives.nseindia.com/content/circulars/MSD67344.pdf) confirms its security-master role. The [BSE standardised security-master format](https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=e99e2ca5-95d7-4173-83da-7774412bbb2d&id=20220531-44) documents security code, instrument code, scrip name, and ISIN. Neither source shape, as currently retained, supplies a legal-entity ID.

## Immutable bridge receipt

`app.historical.issuer_security_identity` provides a frozen pure `IssuerSecurityBridge` retaining exact session-security receipt ID/fingerprint; copied session date/exchange/symbol/ISIN; issuer identifier type and exact value; deterministic `issuer_legal_entity_id` as `issuer:<identifier-type>:<identifier-value>`; source evidence ID/fingerprint/family/reference/date/observed time; optional historical-known/effective dates; temporal semantic; bridge ID; content fingerprint; and stable JSON serialization.

| Identifier type | Exact validation | Current coverage |
| --- | --- | ---: |
| `CIN` | Upper-case Indian CIN structure | 0 |
| `LEI` | Upper-case 20-character LEI | 0 |
| `REGULATOR_REGISTRATION_ID` | Exact source-keyed registration value | 0 |
| `OFFICIAL_LISTING_ISSUER_ID` | Exact source-keyed listing issuer value | 0 |
| `CANONICAL_ISSUER_ID` | Future stable canonical issuer value | 0 |

Legal names are not supported identifier types. The contract does not replace, trim, case-fold, normalize, tokenize, or compare name text.

The only admissible source-family declarations are `NSE_OFFICIAL_LISTING_RECORD`, `BSE_OFFICIAL_LISTING_RECORD`, `OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY`, `APPROVED_DEPOSITORY_SECURITY_REFERENCE`, `OFFICIAL_REGULATOR_ENTITY_RECORD`, and `GLEIF_ANNA_CERTIFIED_ISIN_LEI_RELATIONSHIP`. The bridge contract fetches none. The separate source-specific adapter accepts only a supplied structured NSE/BSE row or a supplied dated GLEIF/ANNA archive; it does not fetch a current security master, parse prose, or infer an identifier.

| Temporal semantic | Required assertion | PIT rule |
| --- | --- | --- |
| `EXACT_SESSION_DATE` | Source date equals the bound session; no effective interval supplied. | Eligible only for that receipt. |
| `EXPLICIT_EFFECTIVE_INTERVAL` | Source supplies `effective_from` and optional `effective_to`. | Dates are preserved, but do not make another session receipt eligible. |

`historical_known_at` or source date after the session is rejected. An explicit interval must contain the bound session. Source observation time is provenance, never a runtime clock or proof it was known earlier. The resolver never reads a current master and never uses ISIN/symbol continuity to bridge another session.

## Fail-closed resolver

`resolve_issuer_security_bridge` is deterministic and read-only.

| Readiness | Condition | Output |
| --- | --- | --- |
| `EXACT_ISSUER_BRIDGE` | Exact same-session records all name the same legal issuer ID. | Retain corroborating lineage; `EXACT_PRIMARY_BRIDGE_PRESENT`. |
| `ISSUER_EVIDENCE_UNAVAILABLE` | No exact bridge for the supplied session receipt. | No bridge; `EXACT_ISSUER_EVIDENCE_REQUIRED`. |
| `SECURITY_IDENTITY_UNRESOLVED` | No valid exact session receipt supplied. | No bridge; `EXACT_SESSION_SECURITY_REQUIRED`. |
| `PIT_DATE_UNSUPPORTED` | Same exact security fields have bridge evidence for another session only. | Retain incompatible audit lineage; `SESSION_SCOPED_BRIDGE_REQUIRED`. |
| `EVIDENCE_CONFLICTED` | Exact same-session evidence names different issuer IDs. | Retain all lineage; `CONFLICTING_EXACT_ISSUER_EVIDENCE`. |
| `NON_COMPARABLE` | Reserved consumer vocabulary. | This identity-only contract cannot create it. |

Repeated identical inputs are canonicalized and do not create false ambiguity. Different issuer IDs fail closed; no source order or priority selects a winner.

## Read-only current-anchor audit

Scope: read-only production SQLite inspection of `HISTORICAL_NSE_SESSION_IDENTITY`. No bridge was written, no regulator source was acquired, and no company type was evaluated.

| Anchor session | Session receipts | Exact rows with ISIN | Bridges | Distinct issuers | CIN | LEI | Other keys | Conflicts | Issuer unresolved | PIT unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2024-02-05` | 24,693 | 24,693 | 0 | 0 | 0 | 0 | 0 | 0 | 24,693 | 0 |
| `2026-08-31` | 37,155 | 37,155 | 0 | 0 | 0 | 0 | 0 | 0 | 37,155 | 0 |

There are 11,295 distinct ISINs / 10,252 symbols at the 2024 anchor and 16,520 ISINs / 16,019 symbols at the 2026 anchor. These are security facts, not issuer counts. The unresolved column means issuer linkage is absent; it does not claim the exact session-security receipt is missing.

| Symbol | ISIN | 2024 rows | 2026 rows | Bridge readiness |
| --- | --- | ---: | ---: | --- |
| `APARINDS` | `INE372A01015` | 5 | 7 | `ISSUER_EVIDENCE_UNAVAILABLE` |
| `GENUSPOWER` | `INE955D01029` | 5 | 7 | `ISSUER_EVIDENCE_UNAVAILABLE` |
| `GLAND` | `INE068V01023` | 5 | 7 | `ISSUER_EVIDENCE_UNAVAILABLE` |
| `DEEPINDS` | `INE0FHS01024` | 5 | 5 | `ISSUER_EVIDENCE_UNAVAILABLE` |
| `ICICIBANK` | `INE090A01021` | 6 | 8 | `ISSUER_EVIDENCE_UNAVAILABLE` |

Row multiplicity is exchange session-security data, not separate issuers. No target is classified as bank, non-financial, or comparable.

If the separate PIT company-type proposal were later approved, **zero** session-security receipts at either anchor currently have enough exact issuer linkage to attempt regulator/taxonomy classification. No `BANK`, `NBFC`, `INSURER`, or `NON_FINANCIAL` result exists here.

## Non-goals and dependency

This slice does not ingest RBI/IRDAI evidence, assign a taxonomy, construct a Compounder universe, run a candidate grid, rank securities, evaluate holdings, or change Discovery, Harvest, Sell, Rotation, Decision Score, Six Gates, portfolio state, or execution. It creates no issuer registry or database migration.

Meaningful issuer/security linkage has not yet been established, so the conditional next roadmap step is not started. After a separately approved source-specific bridge acquisition establishes it, the sequence is `PIT_REGULATOR_COMPANY_TYPE_EVIDENCE_INGESTION_V1`, then `PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1`, then `COMPOUNDER_BACKTEST_PANEL_READINESS_V2`.

Listed security is not issuer, issuer is not parent group, current identity is not historical identity, missing bridge is not inferred issuer, and company type is not investment qualification.
