# Kotak Neo `dTickSize` Authoritative Evidence Review

**Status: SEMANTIC VERIFICATION — NOT PROVIDER APPROVAL — NOT IMPLEMENTED — NOT ACTIVE.**

This review keeps the U13B-5C audit intact. It does not approve Kotak Neo,
change a parser, retain a tick value, write a database record, resolve a tick,
or affect stops, policy, scanning, promotion, activation, or trading.

## Sources inspected

| Tier | Source | Relevant evidence | What it proves |
| --- | --- | --- | --- |
| 1 | Kotak Neo official Python SDK, `docs/functions/market_data/scrip_master.md` | `scrip_master(exchange_segment="nse_cm")` returns the exact NSE cash master URL. The sample URL contains a date-stamped folder and `nse_cm-v1.csv`. | Master delivery, NSE cash segment selection, and dated delivery location. |
| 1 | Kotak Neo official Python SDK source, installed `neo_api_client` 3.0.1 | `ScripMasterAPI.scrip_master_init()` selects a segment file URL; `scrip_cache.py` describes a daily master cache. | SDK transport/cache behavior only; no field schema. |
| 1 | Kotak Neo official SDK repository README | Identifies the repository as the official SDK and scrip master as market-data support. | First-party SDK provenance, not `dTickSize` semantics. |
| 1/2 | Kotak-Neo maintained legacy repository issue #57 | Shows the provider CSV header includes `dTickSize`, alongside `lPrecision`, price numerator/denominator, and quotation fields. | Raw header corroboration only; no formal field definition. |
| 2 | Local `tests/unit/test_kotak_neo_provider.py` fixture | One `nse_cm` / ISIN-linked NSE equity row has textual `dTickSize=0.05`. | One retained raw example only. |
| 2 | Local adapter `app/market_data/kotak_neo.py` | `_master_records()` normalizes headers but does not retain `dTickSize`. | Current parser loss; no existing tick implementation. |

The decisive official master documentation says the call returns a matching
file URL and that the folder is date-stamped and changes daily. It does **not**
define `dTickSize`, price units, scaling, or effectivity.

## Field semantic verdict

**MEANING_UNPROVEN.**

No Tier-1 source reviewed explicitly or unambiguously states that `dTickSize`
is the instrument's minimum valid price increment. The field name, its position
in a provider master, and the `0.05` example are insufficient under the
approved no-inference rule. The maintained issue is corroboration of the
header, not a maintainer field-definition response.

## Unit and scale verdict

**UNIT_SCALE_UNPROVEN.**

No first-party source says whether the textual value is direct INR price units,
paise, or an encoded/scaled value. Nearby CSV fields such as `lPrecision`,
`dPriceNum`, `dPriceDen`, `dGenNum`, and `dGenDen` make a name-only scale
assumption especially unsafe. `Decimal("0.05")` may be a future raw parse, but
it must not become a canonical INR tick until direct decimal INR encoding is
documented.

## NSE cash applicability and examples

The official call supports exact `nse_cm` master selection; it proves delivery
of the NSE cash master, not field applicability. The only retained raw sample
is therefore classified as follows:

| Instrument | Segment | ISIN | Raw `dTickSize` | Authoritative interpretation |
| --- | --- | --- | --- | --- |
| `ALPHA` / `ALPHA-EQ` (redacted fixture) | `nse_cm` | `INE000A01001` | `0.05` | UNPROVEN meaning and scale |

There are no retained official multi-instrument examples with a documented
interpretation. No derivatives or other segment result is generalized to NSE
cash equity.

## SDK and local parser trace

```text
Kotak scrip-master endpoint
  -> official SDK returns selected date-stamped master URL
  -> local bounded downloader obtains CSV
  -> _master_records() recognizes segment/token/symbol/ISIN
  -> dTickSize is ignored
  -> KotakNeoInstrumentRecord / ProviderInstrumentMapping retain routing identity only
  -> no tick observation, artifact, or resolver exists
```

The installed SDK source also does not model, rename, convert, divide, or
multiply `dTickSize`; it returns/uses the master location rather than a typed
field schema. Passing a raw value unchanged would not establish its semantics.

## Identity, timing, and PIT

`nse_cm` plus a valid ISIN can support a future exact NSE cash identity join,
but the current provider mapping is not a canonical tick-reference join. Symbol
text is descriptive only.

The official master URL's date-stamped path and the SDK's daily cache support a
future capture timestamp. They do not establish source publication time or
instrument-effective period. A future record without an explicit effective
interval may be eligible no earlier than its retained `observed_at`; it cannot
backdate tick evidence to prior historical evaluations.

## Contradictory evidence

No first-party semantic contradiction was found. The absence of an authoritative
definition is not treated as proof. The legacy issue's header-only evidence is
not elevated to a field dictionary.

## Final verdict

**OUTCOME B — STILL PARTIALLY PROVEN.**

Proven: Kotak Neo first-party master delivery, exact `nse_cm` selection,
date-stamped master URL behavior, and a retained NSE cash / ISIN-linked raw
field occurrence.

Still missing:

1. A Kotak first-party field dictionary or clearly authoritative maintainer
   response defining `dTickSize` as the minimum valid price increment.
2. Explicit direct INR/price-unit or exact scale/denominator semantics.
3. Explicit confirmation that the definition applies to NSE cash equity,
   rather than only another product class.
4. Separate human approval of Kotak as `APPROVED_LICENSED_REFERENCE_DATA`.
5. A future immutable captured master artifact with exact canonical identity,
   observed-at provenance, quality rules, and effective-period handling.

Kotak Neo remains unapproved. No implementation slice is ready until items
1–3 are obtained. If they are later proven and a human separately approves the
provider, the smallest future implementation would be: raw master retention,
exact `Decimal` decoding, canonical identity mapping, immutable tick
observation with `observed_at`, then a fail-closed reference resolver.

## Decisive source locations

- Official SDK master documentation: `docs/functions/market_data/scrip_master.md`
  (`scrip_master(exchange_segment="nse_cm")`, date-stamped `nse_cm-v1.csv`
  sample; master delivery/timing only).
- Official SDK source: `neo_api_client/services/scrip_master.py` and
  `neo_api_client/utils/scrip_cache.py` (URL selection/daily cache only).
- Maintained header corroboration: Kotak-Neo/Kotak-neo-api-v2 issue #57
  (`dTickSize` header only; non-decisive).
