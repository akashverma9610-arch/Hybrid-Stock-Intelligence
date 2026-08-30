# NSE Tick-Size Alternate Source Audit

**Status: SOURCE-SELECTION AUDIT — NOT PROVIDER APPROVAL — NOT IMPLEMENTED — NOT ACTIVE.**

This audit does not ingest reference data, add a source, write a database
record, create a resolver, calculate a stop, or change Pre-Breakout policy or
scanner behavior. It preserves the approved official-first, observed-at,
exact-identity, Decimal, and fail-closed governance rule.

## Evidence classifications

- **FACT** — directly stated by the cited source.
- **DOCUMENTED PROVIDER SEMANTIC** — explicit provider/exchange schema wording.
- **INFERENCE** — never used as proof in this audit.
- **UNAVAILABLE** — not documented or not accessible in the current composition.

## Ranked source comparison

| Rank | Source | Class | Meaning proven? | Unit proven? | NSE cash proven? | Exact identity | PIT quality | Current readiness | Historical readiness | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | NSE/NDAL Masters Data, CM `security.gz` / `security.txt` | OFFICIAL_EXCHANGE | Yes | Yes: paise / 100 = INR | Yes | Token + symbol + series + ISIN | EOD snapshot; explicit source header/date fields | Ready after separately approved product access and retained `observed_at` | Only from retained dated files or a separately documented archive; do not backdate | READY_FOR_HUMAN_APPROVAL |
| 2 | Upstox official NSE BOD instrument JSON / Instrument Search | LICENSED_REFERENCE_DATA | Yes | No explicit BOD/search unit or scale statement | Yes: `NSE_EQ`, `NSE`, ISIN | ISIN + `NSE_EQ` + instrument key + exchange token | First-observed/current snapshot only | PARTIALLY_PROVEN | Unavailable without historical BOD snapshots | PARTIALLY_PROVEN |
| 3 | Kotak Neo NSE cash master | LICENSED_REFERENCE_DATA candidate | No | No | Master selection only | Raw `nse_cm` + ISIN sample | First observation only if future capture is implemented | PARTIALLY_PROVEN | Unavailable | PARTIALLY_PROVEN |
| 4 | NSE public securities-available-for-trading files | OFFICIAL_EXCHANGE | No tick field documented | No | Yes for identity/listing universe | Symbol/series and ordinary universe identity as published | Publication snapshot | Not a tick source | Not a tick source | NOT_SUITABLE |

## Recommended source: official NSE/NDAL Masters Data

The official NSE **Masters Data** specification is the strongest source path.
It defines the Capital Market master as `security.gz` / `security.txt`, generated
once at EOD. The file contains all securities traded daily and its `Tick Size`
field is explicitly described as the tick size of the security.

### Documented semantic and unit

| Requirement | Evidence | Classification |
| --- | --- | --- |
| Field meaning | CM `security.txt`: `Tick Size` (LONG) — “Tick size of the security.” | DOCUMENTED OFFICIAL SEMANTIC |
| Unit / scale | Specification: currency is INR; prices are in paise; for CM, all price fields are divided by 100 to obtain rupees. | DOCUMENTED OFFICIAL SCALE |
| NSE cash applicability | CM `security.txt` is the Capital Market Segment security master, containing securities traded daily. | DOCUMENTED OFFICIAL APPLICABILITY |
| Exact identity | Fields include exchange token, exchange-assigned symbol, series, and ISIN. Token is unique for a symbol-series combination. | DOCUMENTED OFFICIAL IDENTITY FIELDS |
| Timing | Files are generated once at EOD; the info header includes date, and fields include local DB update datetime. | DOCUMENTED SNAPSHOT TIMING |

For a future canonical observation, exact decoding is:

```text
raw_tick_paise: integer from Tick Size
tick_size_inr: Decimal(raw_tick_paise) / Decimal("100")
```

This is not an inferred `0.05` convention. It follows the official CM
price-field unit rule. It must be applied only after an immutable raw file is
captured and exact ISIN + NSE cash identity mapping succeeds.

### Access and PIT boundary

The official product page labels this **Paid Master Data** and describes SFTP
delivery; its technical specification states that master files are generated at
EOD. No subscription, credential, file, or access configuration is present in
this repository.

- **Current/forward:** technically suitable after a human approves this source
  path and the organisation has lawful product access. Each retained EOD master
  can be eligible no earlier than its recorded `observed_at` / delivered file
  date.
- **Historical:** the specification proves dated snapshot generation, not that
  this installation has an archive of earlier snapshots. Before the first
  retained eligible file, return `TICK_SIZE_UNAVAILABLE_FOR_AS_OF`. Historical
  use requires delivered dated archive files or separately documented archive
  access; never backdate a current master.

## Upstox re-audit

Upstox’s official Instruments and Instrument Search documentation explicitly
defines `tick_size` for an `NSE_EQ` equity with ISIN and an
`NSE_EQ|<ISIN>` instrument key as the minimum price movement of the equity.
This is materially stronger than the earlier local model, which intentionally
retains only mapping fields and currently drops `tick_size`.

However, the BOD/search documentation reviewed labels the field only `number`
and does not state whether its values are INR, paise, or another scale. The IPO
API separately calls its own `tick_size` “in INR”; that different endpoint does
not establish the BOD/search field's unit. No conversion is approved by
association or sample plausibility.

Therefore Upstox is **PARTIALLY_PROVEN**, not ready for a governed tick
observation. It remains a possible future fallback only if Upstox publishes the
BOD/search unit contract and a human separately approves it as licensed source.

## Kotak update

No new first-party Kotak evidence changes U13B-5D. `dTickSize` remains
unproven for meaning, scale, and NSE cash applicability. Kotak remains
**PARTIALLY_PROVEN** and unapproved.

## Outcome and recommendation

**OUTCOME A — an official source is fully documented and ready for explicit
human source-path approval.**

Recommended path: **NSE/NDAL Masters Data CM `security.gz`**. The next human
decision is whether to procure/authorize lawful access to this official master
data product and approve it as the official first-precedence tick source. That
decision must not automatically create an allow-list entry or implementation.

The smallest later implementation, only after that decision, is: bounded
official EOD master acquisition -> immutable raw artifact/checksum -> exact
ISIN + NSE cash identity mapping -> `Decimal(raw)/100` tick observation with
`observed_at` -> existing proposed fail-closed resolver. No stop materializer
is included in that future slice.

## Source locations

- NSE Paid Master Data page and its **NSE Masters Data Specification v1.10**:
  CM `security.txt`, units, identity fields, EOD frequency, and tick field.
- NSE All Reports: identifies the public CM MII security-file report family,
  but this audit found no public field specification proving it exposes tick
  size; it is not substituted for the paid master contract.
- Upstox Instruments and Instrument Search documentation: `NSE_EQ`, ISIN,
  instrument key, exchange token, and `tick_size` field semantics; scale absent.
- U13B-5C/U13B-5D Kotak audit documents: retained unchanged.
