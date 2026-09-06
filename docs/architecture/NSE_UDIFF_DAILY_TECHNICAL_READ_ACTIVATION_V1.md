# NSE UDiFF Daily technical read activation V1

Status: `ACTIVE_FOR_CURRENT_DESCRIPTIVE_READS / PER_WINDOW_FAIL_CLOSED / NOT_INDICATOR_ACTIVATION`

## Purpose and exact boundary

`app.market_data.nse_udiff_daily_technical_read` is the single canonical
read boundary for an explicitly requested NSE UDiFF Daily technical-data
window.  It wraps—without duplicating—the existing Daily eligibility and
continuity certifier.  It returns either all requested certified observations
in canonical session order or a typed result with no bars and exact blocker
codes.  There is no partial N-minus-one result, provider fallback, provider
merge, adjustment materialisation, indicator, setup, signal, score, API,
portfolio access, broker/order action, or persistence operation.

The policy identity is:

`nse-udiff-daily-technical-read-policy / v1`

## Explicit use modes

| Requested mode | Result |
| --- | --- |
| `CURRENT_DESCRIPTIVE_TECHNICAL` | May read only a window that the existing UDiFF certifier marks ready with its applicable profile. |
| `STRICT_HISTORICAL_PIT_TECHNICAL` | Always fails closed as `STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE`; it does not inspect or cache backfilled UDiFF bars. |

Archive retrieval establishes current descriptive access, not that HSI had the
file at its original market date.  The two modes are intentionally separate
contracts and cannot be selected implicitly.

## Certifier reuse and lineage

For `CURRENT_DESCRIPTIVE_TECHNICAL`, the reader calls
`certify_daily_technical_eligibility` once, then calls
`read_eligible_udiff_daily_bars` only if that receipt is `READY`.  The result
retains the eligibility receipt and its policy/version/fingerprint, selected
source bar IDs and fingerprints, exact effective identity interval IDs and
fingerprints, action-coverage fingerprint and canonical action lineage,
continuity states, UDiFF source-observation identities, and retained source
references.  The reader serializes these inputs deterministically.

The caller supplies canonical expected sessions, raw UDiFF observations,
effective identity intervals, action coverage/actions, and same-provider
conflicts.  The reader owns no repository and performs no query, write,
provider request, or current-time lookup.  This keeps existing synthetic
snapshot/diagnostic tests independent of production storage.

## Series and continuity rules retained

- EQ is returned only when its exact window passes the existing certifier.
- BE or BZ may be independently certified by the already-approved policy; an
  EQ↔BE/BZ window remains blocked.
- BL and T0 never appear in an ordinary Daily technical read.
- Unsupported series fail closed.
- Price-only and price-plus-volume are distinct requirements.  The latter
  cannot receive a price-only window.
- Split/bonus returns `ADJUSTMENT_REQUIRED` through the existing receipt;
  rights, demerger, merger, suspension, relisting, and unapproved dividend
  semantics remain blocked.  A separate post-event segment may qualify when
  its requested window does not cross the action.

## Analysis integration seam

Future current-descriptive technical consumers must request this explicit
contract before transforming UDiFF Daily observations into an analysis series.
`app.analysis.series` remains unchanged: it continues to block raw UDiFF
snapshot observations, so this activation does not globally activate any
existing diagnostic or indicator.  Synthetic `AsOfSnapshot` fixtures retain
their current behavior.  A future integration must not route a raw generic
historical-bar query around this reader.

## Readiness consequences

| Capability | State | Reason |
| --- | --- | --- |
| Current descriptive Daily read | `READY_WITH_PER_WINDOW_FAIL_CLOSED` | A successful result requires the pre-existing exact certifier receipt. |
| Strict historical PIT Daily read | `NOT_READY` | Original archive availability time is not established. |
| Weekly derivation source boundary | `READY` | The reader preserves exact selected sessions and complete-window lineage; a future Weekly slice must still block action/series-crossing or incomplete weeks. |
| Monthly long-history readiness | `NOT_READY` | Daily reader activation does not establish long-horizon or price-adjustment readiness. |
| Production technical indicators/signals | `NOT_ACTIVE` | This is only a source read. |

`FACT → DATA → INTERPRETATION → INFERENCE` remains unchanged.  Certified
history is not historically known evidence; read activation is not indicator
activation; identity coverage is not series equivalence; action coverage is
not adjustment; `BL != EQ`; `T0 != EQ`.

## Initial read-path audit (superseded conflict assessment)

The counts below preserve the initial audit result. The
[resolved-conflict eligibility repair](NSE_UDIFF_RESOLVED_CONFLICT_ELIGIBILITY_REPAIR_V1.md)
subsequently proves that the retained structural collision artifacts were
incorrectly treated as current unresolved conflicts and records corrected
coverage. GENUSPOWER has two historical artifacts in total, but only its
2026-08-28 artifact lies inside this six-session window.

The read-only production audit used the immutable current-universe snapshot
`nse-universe:fundamental-probe:2d5692582f3f43fda4eb73aa3caf2d34`, the exact
latest completed UDiFF sessions 2026-08-24, 25, 26, 27, 28, and 31, and the
evidence-derived current-descriptive as-of
2026-09-05T21:05:05.485765+00:00.  It passed the same retained 8,157 effective
identity intervals, 37 official action-query receipts, 3,886 canonical action
receipts, and 784 retained UDiFF same-provider conflict artifacts into the
existing certifier.  No artifact or raw bar was changed.

| Exact required sessions | Certification eligible | Reader success | Reader blocked | Certifier/reader mismatch |
| --- | ---: | ---: | ---: | ---: |
| 4 | 2,462 | 2,462 | 91 | 0 |
| 5 | 2,443 | 2,443 | 110 | 0 |
| 6 | 2,430 | 2,430 | 123 | 0 |

For 4/5/6 sessions respectively, the retained blocker evidence was: missing
action/identity coverage 26/29/30; dividend policy unavailable 33/40/47;
rights adjustment unavailable 1/4/4; unresolved same-provider conflict
13/13/14; EQ↔BE/BZ transition 18/24/28; and one/two/one invalid or unsupported
source-row cases.  These counts are fail-closed reader blocks, not gaps filled
by another provider.

The five requested latest six-session price-and-volume reads were directly
proved as follows:

| Security | Result | Bars | Series | Price/volume continuity | Lineage | Blocker |
| --- | --- | ---: | --- | --- | --- | --- |
| APARINDS | `READY` | 6 | EQ | ready / ready | 6 observations, 6 source artifacts | — |
| DEEPINDS | `READY` | 6 | EQ | ready / ready | 6 observations, 6 source artifacts | — |
| GENUSPOWER | `NOT_READY` | 0 | EQ candidates | source conflict / source gap | retained only in blocked certificate | Historical 28 August BL/EQ collision incorrectly assessed as unresolved; now reconciled by the linked repair |
| GLAND | `READY` | 6 | EQ | ready / ready | 6 observations, 6 source artifacts | — |
| ICICIBANK | `READY` | 6 | EQ | ready / ready | 6 observations, 6 source artifacts | — |

Each corresponding strict-PIT request returned only
`STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE`; no current-descriptive
success altered that result.
