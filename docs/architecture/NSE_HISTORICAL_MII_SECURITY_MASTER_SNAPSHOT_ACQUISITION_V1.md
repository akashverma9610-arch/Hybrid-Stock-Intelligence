# NSE Historical MII Security Master Snapshot Acquisition V1

**Status: `IMPLEMENTED_BOUNDED_INGESTION / PRIMARY_SOURCE_ONLY / DATE_LEVEL_AVAILABILITY / NOT_ACTIVE / NON_EXECUTABLE`.**

## Scope

This boundary acquires only the official NSE Capital Market MII Security File:

```text
https://nsearchives.nseindia.com/content/cm/NSE_CM_security_DDMMYYYY.csv.gz
```

NSE's `All Reports` page labels this report **CM - MII - Security File (.gz)**.
NSE's member circulars name the file `NSE_CM_security_ddmmyyyy.csv.gz` and
state it is to be loaded before trading hours. The implementation uses the
fixed official archive path, an HTTPS-only host allowlist, and a supplied
report date. It has no crawler, generic URL input, browser automation, or
secondary source.

## Retrieval and validation contract

For a requested report date, the transport:

1. builds only the documented filename/path;
2. treats HTTP 404 as deterministic `NSE_HISTORICAL_MII_REPORT_UNAVAILABLE`;
3. rejects other HTTP/transport failures without leaking request internals;
4. requires a gzip content type or an allowed binary equivalent and gzip magic;
5. decodes only UTF-8 BOM-safe CSV; and
6. requires the NSE fields `FinInstrmId`, `TckrSymb`, `SctySrs`,
   `FinInstrmNm`, `ISIN`, `SctyStsNrmlMkt`, `ListgDt`, `RmvlDt`,
   `FinInstrmTp`, and `SctyTp`.

HTML error responses, empty data, filename/date mismatch, invalid gzip, and
schema changes fail closed. An archive date is reported as available only
after a valid official gzip/CSV file passes this contract.

## Immutable evidence

Each accepted file creates a date-labelled immutable snapshot plus immutable
rows in the dedicated `HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT` snapshot
family. The artifact preserves:

- requested/report date and fixed source reference;
- expected filename, raw-file SHA-256 and schema fingerprint;
- exact symbol, ISIN, series, NSE financial-instrument ID, security name;
- raw normal-market status, security/instrument type, listing/removal fields
  only as they appear in the file;
- deterministic row fingerprint and row ordinal; and
- local document-observation metadata.

Rows require an exact non-empty symbol, NSE security ID and name, plus a
structurally valid ISIN. Invalid identity rows are counted and not repaired.
Company names are descriptive only. There is no fuzzy name matching,
company-type classification, changed-ISIN stitching, current-master
substitution, or inferred listing/delisting interval.

## Availability and PIT boundary

The source has a report/session date and documented before-trading use, but a
publicly verifiable publication timestamp is not present in the downloaded
file. The evidence therefore records:

```text
availability_semantics = DOCUMENTED_PRE_TRADING_DATE_ONLY
historical_known_at = unavailable
```

`document_observed_at` is local acquisition provenance only and is not a
historical known time. Snapshot rows can be filtered descriptively to an
explicit report-date boundary, but they cannot be promoted to a PIT identity,
establish a listing start, establish an uninterrupted listing interval, or
establish a final delisting from a missing later snapshot. A smallest future
contract would need a governed conservative known-by-session rule before that
promotion is allowed.

## Exact continuity and BSE cross-check

Repeated same-ISIN/symbol rows are repeat observations. A same-ISIN changed
symbol is reported as an exact observation pair only; it does not create a
symbol interval or identity continuity by itself. A changed ISIN creates no
relationship.

BSE compulsory-delisted ISINs are cross-referenced by exact structural ISIN
only. An overlap preserves both source lineages and does not transfer BSE
observation time, BSE delisting semantics, or any NSE lifecycle conclusion.

## Explicit non-goals

This source does not run a backtest, calculate financial metrics, classify a
company, rank/candidate-screen securities, create a strategy signal, change a
portfolio, call a broker, place an order, expose an API/UI, or persist a
PIT identity.
