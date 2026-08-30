# Historical execution timing

Historical signal generation, trigger detection, and paper-fill eligibility are distinct. A trigger records both the market timestamp and the time it became knowable. The timing adapter reads the frozen replay schedule, then supplies only the legal entry window to the existing paper engine.

`NEXT_BAR_OPEN` excludes the trigger bar and selects the next tradable bar, recording weekends and holidays. `NEXT_ELIGIBLE_BAR` can continue only over explicitly recorded stale, invalid, or suspended bars. `SIGNAL_CLOSE` is permitted only when trigger knowledge is available at that close; otherwise it fails closed as `INVALID_TIMING`.

The chosen entry bar is separate from later management bars. The timing layer neither derives a fill price nor alters canonical gap, stop, target, expiry, MFE/MAE, or tranche behavior. Contexts are immutable and audit reconstruction rejects policy, calendar, trigger, skipped-bar, or selected-bar mismatches.

Stale, invalid, missing, and suspended bars never become entry candidates. A required missing `NEXT_BAR_OPEN` session is an explicit data gap; `NEXT_ELIGIBLE_BAR` records its skips. Pre-fill bars do not contribute to excursions, and post-close bars cannot amend the frozen result.
