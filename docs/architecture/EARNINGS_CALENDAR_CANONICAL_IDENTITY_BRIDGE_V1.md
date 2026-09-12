# Earnings Calendar Canonical Identity Bridge V1

Status: IMPLEMENTED_READ_ONLY / IDENTITY_ONLY / EARNINGS_AUTHORITY_NOT_ACTIVE

Parent: [source governance](EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1.md).
Prior immutable findings: [alternative-source research](EARNINGS_CALENDAR_ALTERNATIVE_OFFICIAL_SOURCE_RESEARCH_V1.md).
Evidence: [deterministic 31-company receipt](EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1_RECEIPT.json).

## Scope and measured repair

The accepted baseline is `125888c1b4ad8c4fa9f1ae558503e10b1955c6dc`. The previous adapter called only `resolve_historical_security_identity`; current NSE universe and official BSE mappings were invisible. This was a reader boundary gap, not an absence of canonical identity.

[Shared bridge](../../app/filings/earnings_schedule_identity.py) consumes existing typed snapshots through dependency injection. [Normalization](../../app/filings/earnings_schedule_ingestion.py) and [descriptive inspection](../../app/filings/earnings_schedule_discovery.py) use the same bridge. Historical tuple callers remain compatible. Supplying both a bridge and legacy identities is rejected. The supplied canonical target must agree with the resolved identity. There is no default database connection, provider call or runtime wiring.

Current identity query cutoff is `2026-09-12T10:00:00+00:00`. Historical evaluation cutoff is `2025-07-16T14:27:57+00:00`. These are explicit audit inputs, not newly certified source publication timestamps. A future event may use identity at its supplied source known-at/evaluation cutoff, not an inferred identity at the future meeting date.

## Existing authorities and hierarchy

| Existing store / reader | Exact identity fields | Effectiveness, expiry and PIT | Bridge role |
| --- | --- | --- | --- |
| `NSE_UNIVERSE`, `CoreUniverseAnalysisStore.instruments_as_of`, `OfficialNseUniverseImporter` | `instrument_id=NSE:<ISIN>`, ISIN, exact symbol, source | Latest `data_as_of <= cutoff`; snapshot creation matches that observation. No inferred listing start/end. No arbitrary equal-time tie-breaking. | Official current identity. Does not certify trading eligibility; stored UNKNOWN listing/tradability stays unknown. |
| `HISTORICAL_SECURITY_IDENTITY`, `HistoricalSecurityMasterStore`, existing PIT selector | canonical ID, ISIN, exchange, symbol, optional BSE code, source reference/fingerprint | Observation `as_of <= cutoff`; inclusive symbol, listing and tradability boundaries; existing latest-effective lifecycle/ambiguity rules reused. | Exact effective historical authority when the existing contract resolves. Known/effective history takes precedence only when concordant with other effective exchange evidence. |
| `PROVIDER_INSTRUMENT_MAPPING`, `CoreUniverseAnalysisStore`, official BSE ingestion | canonical ID, ISIN, exact six-digit BSE code, `BSE_EQ`, `bse-xbrl-v1`, immutable mapping ID, source checksum | Latest effective version at/before cutoff; retired or conflicting latest records never fall back to older active versions. No inferred expiry or historical extension. | Official BSE code authority only. Reuses the exact XBRL source lineage, not arbitrary broker routing metadata. |
| `NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL` and historical promotion records | exact ISIN/symbol/series/session runs, source lineage, anchor | Session-contiguous source addressability; `historical_known_at=None`. Retrospective source dates are not historical public-known-at evidence. Promoted historical identities retain their existing observation/effective checks. | Audited corroborating history, not a new schedule-known-at interval or an automatically activated historical reader. |
| `HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT`, `HISTORICAL_NSE_SESSION_IDENTITY` | exact MII session row / approved session-point identity | `KNOWN_FOR_SESSION_D`, not continuous identity or exact public publication time; `historical_known_at=None`. | Does not invent an interval, listing date or source-known-at timestamp. |
| BSE CorporateFilings / FinancialFacts | exact instrument, filing identity, XBRL source lineage | Filing/fact periods and publication/receipt times retain existing meanings. | Corroborates already-governed BSE mappings; never constructs one or interprets a financial period as a future meeting. |
| Upstox / Dhan mappings | canonical reference, provider transport identifier, effective timestamp | Existing provider-specific versions remain untouched. | Corroboration only in the audit. Ignored for identity admission and cannot override exchange conflicts. |
| Legacy `instruments` table / issuer bridges | legacy instrument table has zero rows; issuer bridges address different scopes | No authority inferred from an empty table or issuer name/CIN linkage. | Neither is promoted into a parallel master. |

This is exchange-specific concordance, not a blanket fallback hierarchy. Exact effective canonical conflicts fail closed. Symbol plus ISIN must agree; code plus ISIN must agree. Symbol/code-only resolution requires a unique exact canonical authority; ISIN-only resolution is not admitted because no applicable approved schedule contract removes the symbol/code requirement. Names and uppercase guesses are never used.

The importer explicitly permits incomplete `NSE:<symbol>` rows with no ISIN. Those are not competing canonical ISIN identities and cannot resolve alone; no other contradictory ID/ISIN row is suppressed. All 31 targets also have the exact ISIN-keyed identity.

### Existing fingerprint compatibility, not data repair

The core stores fingerprint payload `repr`. The original `ProviderInstrumentMappingRecord` at committed baseline `d64bb98` contained 12 fields through `mapping_version`; later metadata fields were additive optional fields. Decoding an old snapshot fills these with None, changing the modern repr.

The bridge verifies either the full current representation or that exact original 12-field representation **only when every extension is None**. It never drops populated fields, replaces a supplied fingerprint, rewrites an ID or repairs stored evidence. Both the stored snapshot identity and the deterministic BSE mapping ID are checked. Old direct-XBRL imports use `BSE_OFFICIAL_XBRL_SHA256:<checksum>`; that exact reference is accepted only when it equals the retained checksum. The existing official HTTPS XBRL reference form is also supported.

## Immutable resolution contract

Operations: `resolve_nse(source_symbol, source_isin, as_of)` and `resolve_bse(source_security_code, source_isin, as_of)`.

Output: source exchange/identifier/ISIN, UTC as-of, resolution state, stable reason codes, canonical instrument/ISIN, governed NSE symbol and/or BSE code, chosen authority, effective-from/to, sorted evidence ID/fingerprint pairs, version and content fingerprint. Missing optional cross-exchange fields remain null. Effective dates describe the chosen authority; every supplemental field is independently checked at the requested cutoff. This is not a tradability, listing-status, source-completeness or freshness receipt.

States: `RESOLVED`, `IDENTITY_UNAVAILABLE`, `IDENTITY_NOT_EFFECTIVE`, `IDENTITY_CONFLICTED`, `SOURCE_IDENTITY_INCOMPLETE`, `AMBIGUOUS`. Unavailable states contain no resolved canonical fields. Exact duplicate inputs are idempotent; conflicting equal-time records are retained as conflict evidence, never chosen by iteration order. Receipts validate their own content fingerprint; source snapshots are verified, not repaired.

Only RESOLVED can proceed into existing normalization. Purpose, revision linkage, exact source timestamps, timezone provenance, candidate verification and storage rules are unchanged. Descriptive identity is evaluated at explicit observation time; normalization separately checks identity at the verified publication time. Neither substitutes observation time for known-at.

## Before / after: exact financial-fact population

The target set is the 31 distinct canonical IDs in FinancialFacts. Query keys below come from retained identity inventory; this table is not a claim that 31 live upcoming events were acquired. Current/future columns measure identity only.

| Symbol | Canonical ID / ISIN | BSE code | Old adapter at current cutoff | Current NSE / BSE | Historical NSE / BSE |
| --- | --- | --- | --- | --- | --- |
| RELIANCE | `NSE:INE002A01018` | 500325 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| SJVN | `NSE:INE002L01015` | 533206 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| MGL | `NSE:INE002S01010` | 539957 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| SIEMENS | `NSE:INE003A01024` | 500550 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ASTRAL | `NSE:INE006I01046` | 532830 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| CRISIL | `NSE:INE007A01025` | 500092 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| IDBI | `NSE:INE008A01015` | 500116 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| INFY | `NSE:INE009A01021` | 500209 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| BIKAJI | `NSE:INE00E101023` | 543653 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ACUTAAS | `NSE:INE00FF01025` | 543349 | NOT_EFFECTIVE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| SWIGGY | `NSE:INE00H001014` | 544285 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| CRAFTSMAN | `NSE:INE00LO01017` | 543276 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| DALBHARAT | `NSE:INE00R701025` | 542216 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| AFFLE | `NSE:INE00WC01027` | 542752 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ZYDUSLIFE | `NSE:INE010B01027` | 532321 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| TEJASNET | `NSE:INE010J01012` | 540595 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| LTTS | `NSE:INE010V01017` | 540115 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| TEGA | `NSE:INE011K01018` | 543413 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ACC | `NSE:INE012A01025` | 500410 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ONESOURCE | `NSE:INE013P01021` | 544292 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| DABUR | `NSE:INE016A01026` | 500096 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| GESHIP | `NSE:INE017A01032` | 500620 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| LT | `NSE:INE018A01030` | 500510 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| GLAND | `NSE:INE068V01023` | 543245 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ICICIBANK | `NSE:INE090A01021` | 532174 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| DEEPINDS | `NSE:INE0FHS01024` | 543288 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| ORIENTTECH | `NSE:INE0PPK01015` | 544235 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| APARINDS | `NSE:INE372A01015` | 532259 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| SAFARI | `NSE:INE429E01023` | 523025 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| APOLLOHOSP | `NSE:INE437A01024` | 508869 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |
| GENUSPOWER | `NSE:INE955D01029` | 530343 | DATA_UNAVAILABLE | RESOLVED / RESOLVED | NOT_EFFECTIVE / NOT_EFFECTIVE |

Current NSE: **31/31 resolved**. Current BSE: **31/31 resolved**. Current unresolved/conflicted: **0/0**. Historical: **0/31 resolved**, all **IDENTITY_NOT_EFFECTIVE**, no fabricated historical identity.

Each receipt row includes full authority, effective dates, evidence IDs/fingerprints and separate NSE/BSE results. All current NSE selections begin `2026-08-24T20:38:50.218348+00:00` with no invented end date. BSE effective times differ and are retained exactly in the receipt.

APARINDS, DEEPINDS, GENUSPOWER, GLAND and ICICIBANK each resolve current exact NSE/BSE identity without exceptions. ACUTAAS also resolves from the current exact NSE universe and official BSE mapping. Its two AMIORG historical intervals remain expired in May 2025 and are known only in September 2026; neither is extended, refreshed or rewritten.

The already-discovered [APARINDS Prior Intimation](https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_59958_16072025195757_iXBRL_WEB.html) supplies the exact APARINDS / INE372A01015 pair used as a deterministic historical fixture. At the historical audit cutoff it stays NOT_EFFECTIVE; at the current cutoff the pair resolves descriptively. No download, special case, synthetic public-known-at time or Gate 6 event is created.

## Replay and protected-data proof

[Read-only audit command](../../scripts/audit_earnings_schedule_identity.py):

```powershell
python scripts/audit_earnings_schedule_identity.py --database data/nse_stock_manager.db --as-of 2026-09-12T10:00:00+00:00 --historical-as-of 2025-07-16T14:27:57+00:00
```

The command uses SQLite `mode=ro`, `query_only=ON` and one read transaction, prints JSON, and writes no report or database. A reader cache avoids repeated scans while preserving the existing paged-reader contract. Receipt fingerprint: `sha256:41d67388f45a2232c8d9454e458aea65cd06d348ad008732fd75414322126ad2`.

Protected ordered-row hashes and schema hash were captured before editing and matched after the audit. They include all 206,749 core snapshots (all identity/mapping/MII/UDIFF/read-model families), 6,118 FinancialFacts, 455 CorporateFilings, 1 portfolio snapshot, all portfolio rows, 1 canonical strategy definition, 2,074 canonical diagnostic results, production Six Gates approval and evaluation tables. Generic strategies/results, paper trades and trade plans remain zero. Complete hashes are in the receipt. No production store initializer or migration is called.

Final validation: **67 focused tests passed; 209 affected regressions passed; one complete backend run passed with 4,394 passed / 0 failed / 6 skipped / 2 warnings** (294.90 seconds). Warnings are the existing FastAPI/Starlette httpx and AnyIO deprecations. No repeated full run was used. All six source/test/audit-script file hashes remained unchanged across the final run.

Post-suite SQLite full integrity check: **ok**; FK violations: **0**. Exact production receipt replay passed; every protected ordered-row hash and schema hash matched the pre-edit baseline. SQLite writes by the audit: **0**. Cash remains **UNKNOWN**. No broker/order tables or new earnings-calendar tables were created. Local Markdown links: **260 passed**; nine-file whitespace/conflict-marker validation and `git diff --check` passed.

Tests cover both mapping representation versions, exact source concordance, missing/expired/future identity, inclusive historical boundaries, no backdating, deterministic replay, fingerprint tampering, adapter compatibility and the no-clearance boundary. This validates identity reuse, not earnings-event completeness or strict public-known-at authority.

## Separate remaining blocker and safety

Next continuation only: **EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1**. Current identity no longer blocks admission, but bare source publication timestamps still lack approved public-known-at timezone provenance. This stops strict normalization before window/freshness/absence policy can establish clearance. Complete-window coverage is also separately unproven and is not solved here. No next slice starts in this change.

- V1_ACTIVE = TRUE; V2_ACTIVE = FALSE; V2_SHADOW_ONLY = TRUE.
- B08 = CLOSED_FOR_ACTIVATION_COMPATIBILITY.
- NO_NAME_BASED_IDENTITY = TRUE.
- NO_CURRENT_MASTER_HISTORICAL_BACKDATING = TRUE.
- NO_UNVERIFIED_CALENDAR_CLEARANCE = TRUE.
- NO_HISTORICAL_RESULT_DATE_AS_FUTURE_SCHEDULE = TRUE.
- NO_UNDOCUMENTED_PRIVATE_SOURCE = TRUE.
- NO_AI_PREDICTED_EARNINGS_DATE = TRUE.
- AI_DECISION_AUTHORITY = FALSE.
- HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE.

No identity/provider/universe/UDIFF writes, additional discovery, Gate 6 wiring, earnings blackout/no-event clearance, freshness activation, AI, commercial provider, broker/order operation or portfolio mutation.
