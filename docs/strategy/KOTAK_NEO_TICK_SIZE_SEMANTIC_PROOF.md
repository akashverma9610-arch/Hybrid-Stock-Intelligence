# Kotak Neo `dTickSize` Semantic Proof Audit

**Status: AUDIT — NOT PROVIDER APPROVAL — NOT IMPLEMENTED — NOT ACTIVE.**

No Kotak request, ingestion, parser change, storage, resolver, stop, policy change, or governance action occurs in this audit.

## Local evidence

The only retained local `dTickSize` appears in `tests/unit/test_kotak_neo_provider.py`:

```text
headers: pSymbol,pGroup,pExchSeg,pInstType,pSymbolName,pTrdSymbol,pISIN,dTickSize,...
row:     12345,EQ,nse_cm,EQUITY,ALPHA,ALPHA-EQ,INE000A01001,0.05,1,Y
```

Raw value is textual `0.05`, attached to `nse_cm`, provider token `12345`, `ALPHA` / `ALPHA-EQ`, and ISIN `INE000A01001`. This is one redacted fixture sample, not an official field dictionary, artifact checksum, or effective-date record. No local samples cover zero, negative, missing, malformed, duplicate, conflicting, or alternate-segment `dTickSize` values.

Official Kotak scrip-master documentation proves that `scrip_master(exchange_segment="nse_cm")` returns the segment master-file URL for caller download. It does not define `dTickSize` meaning or scale in reviewed documentation.

## Meaning and scale

| Question | Finding | Classification |
| --- | --- | --- |
| Is it a minimum valid price increment? | Name and sample are consistent, but no authoritative field definition was found. | UNPROVEN |
| Is `0.05` INR 0.05, paise, or another scale? | Plausibility is not a scale specification. | UNPROVEN |
| Is it master/reference rather than quote data? | It occurs in the scrip-master CSV family, not quote payloads. | LIKELY |
| Is Kotak official exchange truth? | No; it is provider/broker evidence only. | PROVEN classification |

Values such as `5`, `0.05`, `50`, or `500` must not be decoded until authoritative field semantics define the exact unit/scale. A future decoder can use `Decimal(raw_text)` only after direct INR decimal encoding is proven; scaled integers need separately documented scale.

## Identity and authority

The fixture's `pExchSeg=nse_cm` plus ISIN identifies an NSE cash provider record. Current adapter conversion yields `Exchange.NSE`, `InstrumentType.NSE_EQUITY`, and a Kotak token mapping. This does not prove a canonical tick-reference identity join: the provider-local record is not joined/persisted as a tick fact against `NseEquityInstrument` or historical canonical identity. Future import requires exact ISIN plus NSE cash segment; symbol text remains descriptive.

Kotak can only be a candidate `LICENSED_REFERENCE_DATA` source. This audit does not approve it or establish an allow-list.

## Timing and PIT

The fixture has no artifact publication, download, source, or effective timestamp. Current `load_instrument_master()` downloads a master for bounded resolution, but `_master_records()` retains neither observation time nor artifact record. Future bounded capture can use existing timezone-aware provenance/clock patterns. Without explicit effective time, a future value is usable only from captured `observed_at`; it cannot be backdated.

| Usability | Finding |
| --- | --- |
| Current/forward | Not ready until semantic proof, exact canonical join, provider approval, and observed-at capture exist. |
| Historical before first capture | Unavailable. |

## Parser-loss trace

```text
CSV dTickSize -> _master_records() normalizes header but ignores value
-> KotakNeoInstrumentRecord has no tick field
-> _identity() creates identity/provider mapping only
-> ProviderInstrumentMappingRecord persists routing metadata only
-> no canonical tick/reference record
```

The smallest future work is not a direct parser patch. First implement the approved reusable immutable reference-data boundary; only then retain/parse this raw field after its semantics and scale are proven.

## Outcome

**OUTCOME B — PARTIALLY PROVEN.**

Proven: master-file delivery; raw field presence; NSE cash segment/ISIN in the sample; Kotak is not an official exchange; future observed-at capture is possible.

Missing: authoritative field meaning; exact scale; provider allow-list approval; retained timed master artifact; exact canonical tick join; data-quality coverage; and explicit effective-period metadata.

Kotak remains **unapproved** and cannot supply governed tick evidence.

## Next decision

First obtain authoritative Kotak documentation or supported field dictionary proving `dTickSize` means NSE cash minimum price increment and defining exact unit/scale. Then a human may consider explicit licensed-reference-data allow-list approval. No implementation or approval is requested now.
