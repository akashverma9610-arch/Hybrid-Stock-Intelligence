from datetime import datetime, timezone, date
from decimal import Decimal

from app.storage.sqlite_core_api_snapshot_repository import (
    SQLiteCoreApiSnapshotRepository,
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
)
from app.portfolio.engine import PortfolioEngine
from app.gates.engine import (
    ExchangeCalendar,
    ActionContext,
    ExecutionEligibility,
    ExecutionGateEvaluation,
    GateDecisionRecord,
    GateOutcome,
)
from app.portfolio.models import (
    CashPosition,
    HoldingAnalytics,
    Portfolio,
    PortfolioStatus,
    PortfolioTransaction,
    PriceReference,
    TransactionType,
)
from app.analysis.models import AnalysisStatus, MarketRegime, MarketRegimeResult
from app.api.stock_query import (
    AnalysisSectionQueryRecord,
    DiagnosticCoverageQueryRecord,
    StockAnalysisQueryResult,
)
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DataQuality, DiagnosticResult, StrategyVersionReference
from app.scoring.engine import DecisionScorecard, ScoredComponent

T0 = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
AS_OF = datetime(2026, 8, 20, 10, tzinfo=timezone.utc)
ANALYZED_AT = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)
DATA_AS_OF = datetime(2026, 10, 1, 15, 15, tzinfo=timezone.utc)
STRATEGY = StrategyVersionReference("stock-api", "1")

# 1. Portfolio Snapshot Construct
portfolio = Portfolio("api-portfolio", "API fixture", "INR", T0, "strategy/1", None, PortfolioStatus.ACTIVE, {})
cash = CashPosition(Decimal("20000"), "INR", Decimal("0"), T0)
transactions = (
    PortfolioTransaction(
        "api-buy", portfolio.portfolio_id, TransactionType.BUY, T0, T0, "fixture", "api-buy",
        "RELIANCE", Decimal("100"), Decimal("100"), Decimal("10000"), Decimal("0"), Decimal("0"), Decimal("-10000"),
    ),
)
prices = (PriceReference("api-price", "RELIANCE", Decimal("120"), AS_OF, AS_OF),)
analytics = (
    HoldingAnalytics(
        "RELIANCE", AS_OF, AS_OF, raw_decision_score=Decimal("8.8"), score_status="COMPLETE",
        data_confidence=0.9, gate_status="EXECUTABLE", structural_stop=Decimal("90"), sector="ENERGY",
    ),
)
port_snapshot = PortfolioEngine(ExchangeCalendar("nse-api", frozenset({date(2026, 8, 19)}))).reconstruct(
    portfolio=portfolio,
    as_of_timestamp=AS_OF,
    initial_cash=cash,
    transactions=transactions,
    actions=(),
    prices=prices,
    analytics=analytics,
)

# 2. Stock Analysis Snapshot Construct
def diagnostic(rule: int, result: str) -> EvaluatedDiagnostic:
    rec = DiagnosticResult(
        f"diagnostic-{rule}", "COFORGE", str(rule), STRATEGY, result, None, 0.81,
        (f"evidence-{rule}",), (f"obs-{rule}",), ANALYZED_AT, DATA_AS_OF,
    )
    return EvaluatedDiagnostic(rec, rule, "diagnostic-v1", EvaluationEligibility.ELIGIBLE, (), (("source_type", "INTERPRETATION"),))

regime_res = MarketRegimeResult(
    "regime-1", "NIFTY50", STRATEGY, MarketRegime.SELECTIVE_BULL,
    ("trend=uptrend",), ("nifty-1",), "market-regime-v1", ANALYZED_AT,
    DATA_AS_OF, DataQuality.HIGH, 0.92, AnalysisStatus.VALID, (),
)

score_comp = ScoredComponent(
    "market_regime", "COMPLETE", Decimal("8"), Decimal("0.10"), Decimal("0.80"),
    (1,), (), ("diagnostic-1",), ("evidence-1",), 0.81, (),
)
scorecard = DecisionScorecard(
    "scorecard-1", "COFORGE", STRATEGY, "reg-1", "score-v1", DATA_AS_OF,
    ANALYZED_AT, (score_comp,), Decimal("8.20"), "COMPLETE", 0.74, ("SCORECARD_AUDITABLE",),
)

decisions = tuple(
    GateDecisionRecord(f"gate-{i}", GateOutcome.PASS, f"gate {i} ok", 0.8, (f"gate-ev-{i}",), {"v": "v1"})
    for i in range(1, 7)
)
gates = ExecutionGateEvaluation(
    "gate-eval-1", "COFORGE", STRATEGY, "reg-1", "score-v1", "gates-v1",
    "scorecard-1", "snap-1", ActionContext.FRESH_ENTRY, DATA_AS_OF, ANALYZED_AT,
    Decimal("8.20"), Decimal("0"), Decimal("8.20"), decisions, ExecutionEligibility.EXECUTABLE,
    (), (), ("GATES_AUDITABLE",), tuple(item for d in decisions for item in d.evidence_ids),
    ("diagnostic-1",), {"config": "gates-v1"},
)

items = (diagnostic(1, "SELECTIVE_BULL"), diagnostic(10, "HH_HL_BULLISH"), diagnostic(24, "ACCELERATING"))
section = lambda item: AnalysisSectionQueryRecord("COMPLETE", (item,), ())
stock_snap = StockAnalysisQueryResult(
    "COFORGE", "NSE", "Coforge Limited", "TECHNOLOGY", "IT Services", ANALYZED_AT, DATA_AS_OF,
    "COMPLETE", regime_res, "ROTATING_IN", 3,
    DiagnosticCoverageQueryRecord(61, 45, 4, 8, 4, items), scorecard, gates,
    section(items[1]), section(items[2]), section(diagnostic(30, "CATALYST_PRESENT")),
    section(diagnostic(29, "REASONABLE")), section(diagnostic(45, "ACCEPTABLE")), section(diagnostic(7, "PROXY_BULLISH")),
    ("PROXY_NOT_DIRECT_INSTITUTIONAL_KNOWLEDGE",),
    ("snapshot-1", "scorecard-1", "gate-eval-1"),
)

# 3. Save to database
repo = SQLiteCoreApiSnapshotRepository("stock_canonical.db")
repo.save_snapshot(CoreApiSnapshot("portfolio-1", CoreApiSnapshotFamily.PORTFOLIO, "v1", "api-read-model-v1", "fp-p1", AS_OF, port_snapshot))
repo.save_snapshot(CoreApiSnapshot("stock-coforge-1", CoreApiSnapshotFamily.STOCK_ANALYSIS, "v1", "api-read-model-v1", "fp-s1", ANALYZED_AT, stock_snap))
print("[SUCCESS] Database seeded successfully!")
