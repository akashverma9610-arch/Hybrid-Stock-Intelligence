# Crisis and market-dislocation engine

## Purpose and boundary

The Crisis & Market Dislocation Engine is a provider-neutral, deterministic
emergency risk overlay over the normal Market Regime Engine. It implements this
permanent principle: the market can offer different kinds of opportunity, but a
BUY opportunity is not required at every moment. Cash is a deliberate defensive
allocation and preserved optionality, not a failure to find a stock.

It is not a replacement for normal market regime. A normal regime and a crisis
state remain independent dimensions, for example `BULL + NORMAL`, `BEAR +
STRESS`, and `NEUTRAL + STABILIZING`.

The V1 foundation has no live feed, provider adapter, execution route, broker,
demat access, paper-engine mutation, promotion, approval, or activation path.
It consumes only frozen inputs supplied by a later composition layer.

## States and multi-factor evidence

The typed state lifecycle is `NORMAL`, `ELEVATED_RISK`, `STRESS`, `CRISIS`,
`STABILIZING`, and `RECOVERY`. It is based on an explicit collection of
factor signals—not a single Nifty percentage move. Supported input identities
include price velocity, drawdown/gap, ATR and realised volatility, India VIX,
market/sector breadth, correlation convergence, abnormal volume, liquidity,
exchange/circuit status, portfolio drawdown/concentration, and data freshness.

Signals may be unavailable. Missing or stale critical market data lowers
confidence and emits explicit warnings; it never produces artificial precision
or a high-confidence result. Severity and confidence are independent values.
The immutable assessment retains triggered, non-triggered, and unavailable
factors, timestamps, prior state, duration when known, transition reason,
evidence, and provenance.

`CrisisPolicySettings` holds explicit, versioned test/configuration values for
multifactor confirmation, escalation/de-escalation, and critical-data confidence
limits. They are conservative fixtures, not claims of calibrated production
thresholds. Future historical validation must calibrate them.

## Transitions and risk overlay

The policy permits justified direct escalation such as `NORMAL → CRISIS` on a
severe factor. It also has de-escalation confirmation and stabilization evidence
to avoid one-tick oscillation. `STABILIZING` requires evidence such as slowing
selling velocity, improving breadth, volatility/liquidity normalization, fewer
new lows, reclaim behavior, or recovery leadership. `RECOVERY` restores
permissions and sizing gradually rather than jumping from crisis controls to
normal risk.

`CrisisExecutionPolicyService` returns an analytical `CrisisExecutionOverride`:
entry restriction, position/risk multipliers, stabilization/quality requirements,
breakout restrictions, watch permissions, stop/slippage mode, review/cash
preference, warnings, and reasons. It never places a trade.

The ordering is deliberately:

`diagnostics → Decision Score → confidence → six execution gates → crisis/dislocation overlay → portfolio or capital-rotation decision`

The overlay does not rewrite the Decision Score, confidence, or any of the six
gate results. A high-scoring setup in `CRISIS` can therefore become `DEFERRED`
or `WATCH`, rather than a BUY. Crisis is neither “sell everything” nor “buy the
dip”: individual holding action remains a separate structural/liquidity/thesis/
concentration review, and new entries are policy-restricted.

## Opportunity, portfolio, and rotation contracts

The scanner emits only `WATCH`, `PRIORITY_RESEARCH`, or `NOT_ELIGIBLE` and can
classify exceptional relative-strength survivors, structure/low-drawdown
survivors, forced-selling/capitulation candidates, abnormal-volume reversals,
emerging sector leaders, recovery leaders, and post-crash reclaims. Exceptional
relative strength is research priority—not automatic BUY.

`PortfolioCrisisAssessmentService` is a read-only review contract. It consumes
portfolio drawdown/concentration/correlation/liquidity/cash and supplied holding
review actions. It does not liquidate holdings. A dislocation can be a leadership
reset: later capital rotation may compare broken prior leaders with emerging
post-crash leaders, while retaining cash when no candidate clears normal gates
and crisis policy.

## Execution realism and paper context

`CrisisSlippageAssumptionService` supplies a transparent future paper/backtest
assumption. For a long stop at ₹950 and a gap open at ₹925, it records the
opening/gap-based simulated fill (with mode-configured slippage), not a fictional
₹950 fill. This is an abstraction, not a microstructure simulator or order
router.

`PaperTradeCrisisContext` is a separate immutable, versioned associated record
for crisis state at signal/entry/exit, slippage mode, expected/simulated fill,
stabilization, opportunity category, policy restriction, provenance, and
fingerprint. Existing paper-trade records are never rewritten.

## Persistence, frontend, and future work

`CrisisAssessment`, `CrisisEvent`, and paper-trade crisis contexts fit the
existing immutable V1 core-snapshot convention. `CrisisEvent` is versioned and
retains start/end (open events have no end), peak state/severity, transitions,
triggers, market contexts, sectors, recovery time, provenance, and fingerprint.
There is no mutation API or normalized crisis database subsystem in V1.

The frontend-safe `CrisisDashboardReadModel` exposes only state, confidence,
distilled drivers, entry restriction, sizing multiplier, permitted opportunity
categories, warnings, and labels such as `CAUTION`, `DEFENSIVE`,
`WAIT_FOR_STABILIZATION`, and `RECOVERY_WATCH`. It deliberately excludes
internal formula details.

Future #027 data infrastructure may feed validated, point-in-time index/VIX,
breadth, sector, liquidity, market-status, and portfolio context signals. Later
performance and self-improvement work can attribute frozen evidence by crisis
state, signal category, regime, sector, relative strength, stabilization,
slippage, MFE/MAE, realised R, drawdown, and recovery behavior. Those research
results remain distinct from approval and activation.

## Canonical market-data feed boundary

#027A supplies provider-neutral canonical quote, OHLCV, index/VIX, breadth,
participation/liquidity, session, freshness, quality, and provenance facts. It
does not calculate a crisis factor, state, severity, confidence, or action.
Future factor assembly must preserve exact canonical source IDs/timestamps and
treat stale, degraded, missing, or low-coverage inputs as explicit limits.

## Composition with upside excess

The downside dislocation lifecycle is now one tail of the broader Market
Extremes framework. Its `CrisisAssessment` and execution override are composed
with an independent upside excess assessment/overlay; neither replaces normal
market regime, Decision Score, confidence, or the six gates. See
[`MARKET_EXTREMES_ENGINE.md`](MARKET_EXTREMES_ENGINE.md) for euphoria,
distribution, and leadership-reset contracts. A rare fast reversal is not
assumed to make separately scoped/time-horizon downside and upside evidence
logically impossible.
