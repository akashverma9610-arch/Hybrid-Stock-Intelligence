# Market extremes engine: downside dislocation and upside excess

## Two independent tails

The Market Extremes Engine composes two independent risk dimensions without
replacing the normal Market Regime Engine:

- downside: the existing crisis/dislocation lifecycle;
- upside: `NORMAL`, `OPTIMISM`, `CROWDING`, `SPECULATION`, `EUPHORIA`,
  `DISTRIBUTION`, and `BREAKDOWN`.

Normal regime, downside state, and upside state remain separate. Examples
include `BULL + NORMAL_EXTREMES`, `SELECTIVE_BULL + sector EUPHORIA`, and
`BEAR + CRISIS`. Market, sector, and stock assessments are also independent;
sector euphoria does not establish market or stock euphoria.

The permanent principle remains: there can be an opportunity in most market
conditions, but there need not be a BUY opportunity at every instant. Cash/no
new entry is a valid, deliberate outcome.

## Evidence, not narrative

`MarketExtremesEngine` is provider-neutral and accepts only immutable,
point-in-time factor signals. It can consume normalized evidence for price
extension/acceleration, structure, breadth, valuation, participation, IPO and
primary-market intensity, narrative quality, ownership/distribution proxies,
earnings, and leadership. Missing inputs remain unavailable. Critical missing
inputs and low-quality/low-coverage narrative sources cap confidence.

No entity, sector, or theme is hard-coded as euphoric. A user narrative such as
“Engineering is euphoric” remains unconfirmed if the configured multifactor
evidence does not support it. High score, confidence, and top confirmation are
separate values.

`IPOIntensityObservation` and `NarrativeIntensityObservation` are future-feed
contracts only. Many IPOs, retail interest, listing premiums, or social activity
alone do not prove a top. Narrative/social sources are explicit proxies, never
direct claims about market participants.

## Euphoria, distribution, and leadership

High euphoria is a risk/cycle condition, not a confirmed top and not a sell
signal. Top confirmation requires separate transition evidence—structural
breakdown plus configured distribution evidence. `DISTRIBUTION` is distinct from
`EUPHORIA`; it can use breadth divergence, weakening leaders, failed breakouts,
weak high-volume closes, earnings deterioration, and ownership/OFS proxies.
State transitions use confirmation to avoid an unsupported `EUPHORIA →
BREAKDOWN` jump, except where structural-breakdown evidence exists.

Leadership quality is a separate upstream-evidence interpretation:
`HEALTHY`, `BROADENING`, `SPECULATIVE_BROADENING`,
`LOW_QUALITY_LEADERSHIP`, `DETERIORATING`, or `UNKNOWN`. Price acceleration
with earnings acceleration is supported acceleration; price outpacing earnings
raises excess risk but does not itself prove a top. Public-excitement versus
distribution-proxy divergence is represented by factors and warnings, not a
claim of institutional intent.

## Policy and portfolio boundaries

The upside overlay can restrict chasing, require stronger R:R and structure,
reduce new-entry sizing, prevent aggressive add-ons, request profit protection,
increase trailing vigilance, and set rotation readiness. In `EUPHORIA` it can
say `DO_NOT_CHASE` while preserving an existing winner as
`HOLD_AND_TRAIL`/`PROTECT_PROFIT`. It never emits automatic SELL, EXIT, or
rotation. Existing structure, thesis, portfolio, six gates, and canonical
capital-rotation comparisons remain authoritative.

The composed effective policy reconciles a normal regime with downside and
upside overlays. It does not duplicate or replace Decision Score or gates. Its
intended placement is:

`data → market regime → market extremes (downside + upside) → sector phase → diagnostics → Decision Score → confidence → six gates → extremes overlay → portfolio competition → capital rotation → trade management`

At all levels, cash/no entry is legitimate when qualified risk/reward is absent.
An euphoria/distribution context may inform later rotation comparison but cannot
bypass the existing rotation thresholds or create a trade.

## Persistence and future integrations

`MarketExtremeEvent`, `PaperTradeUpsideExtremeContext`, and forward-outcome
references are immutable/versioned V1 contracts and fit the existing core API
snapshot convention. They retain entity level/ID, lifecycle, peak score,
drivers, transition evidence, provenance, and eventual future-outcome references
at later approved horizons. Existing paper trades are not rewritten.

Future controlled self-improvement/performance research can group frozen results
by excess state, cycle stage, level, sector, leadership quality, distribution,
and forward horizon. Research evidence is never strategy approval or activation.

## #027 data requirements and calibration

No live provider, IPO source, news/social source, broker, order flow, or runtime
is implemented here. Future #027 infrastructure must normalize timestamped,
fresh, provenance-carrying price/OHLCV, market/sector index, breadth, VIX,
valuation/fundamental, ownership/proxy, IPO/OFS, narrative, and participation
inputs. Sources may differ by data class.

All thresholds and weights are explicit `UpsideExcessPolicySettings` values for
deterministic tests. They are not claimed to be optimal or predictive. Historical
episode calibration and any production runtime activation require a future,
separately approved phase.

## Canonical market-data feed boundary

#027A provides provider-neutral, timestamped OHLCV, index/sector/VIX, breadth,
participation, liquidity, session, quality, freshness, and provenance facts for
future factor assembly. It provides no upside interpretation and no non-price
source. Valuation/fundamental, IPO, ownership/OFS, narrative, and retail/social
families remain distinct future provider boundaries.
## Primary-market evidence

The primary-market adapter can populate the existing `IPOIntensityObservation` with coverage-aware factual IPO counts, amount composition, final-subscription facts, listing premiums, and sector clustering.  It introduces no new Euphoria threshold or formula.  IPO activity is never a standalone market-top, exit, or sell instruction.
