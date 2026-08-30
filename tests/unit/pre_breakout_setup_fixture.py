from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutBaseWindow, GovernedPreBreakoutPivot,
    GovernedPreBreakoutResolvedInputs, GovernedPreBreakoutStructuralResult,
    PreBreakoutResolvedInputStatus, PreBreakoutStructuralStatus,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment, PreBreakoutSetupAssessmentStatus,
)

T = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT_ID = "NSE:SETUP-EVIDENCE"


def assessment(*, eligible: bool = True, at: datetime = T) -> GovernedPreBreakoutSetupAssessment:
    technical = GovernedPreBreakoutResolvedInputs(
        INSTRUMENT_ID, at, at, PreBreakoutResolvedInputStatus.COMPLETE_RESOLVED_INPUTS,
        "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        252, Decimal("470"), Decimal("8"), True, Decimal("1"), (Decimal("2"),) * 5,
        Decimal("2"), True, at, Decimal("60"), True, Decimal("61"), True,
        Decimal("500"), 252, Decimal("6"), True, 499_999, Decimal("1000000"), "PASS",
        (1_000_000,) * 20, Decimal("1000000"), Decimal("0.50"), Decimal("500000"),
        "STRICT_LESS_THAN", True, at, (), (),
    )
    high = GovernedPreBreakoutPivot("h", at - timedelta(days=10), Decimal("500"), at - timedelta(days=7))
    low = GovernedPreBreakoutPivot("l", at - timedelta(days=9), Decimal("450"), at - timedelta(days=6))
    base = GovernedPreBreakoutBaseWindow(at - timedelta(days=20), at, 20, (high, high), (low, low), Decimal("500"), high.session)
    structural = GovernedPreBreakoutStructuralResult(
        INSTRUMENT_ID, at, at, PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY,
        "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        252, 1, base, Decimal("500"), Decimal("500"), low, Decimal("450"), False,
        "AVAILABLE", Decimal("0.05"), "tick-id", True, Decimal("449.95"), Decimal("550"), True,
        None, None, None, None, (), Decimal("500"), "CONFIRMATION_NOT_INITIAL_ENTRY",
        Decimal("470"), at, "PASS", Decimal("474.9625"), Decimal("474.95"), Decimal("20.05"),
        Decimal("80"), Decimal("80") / Decimal("20.05"), True, None, "NOT_EVALUATED_AT_SCAN", "PASS", False,
    )
    return GovernedPreBreakoutSetupAssessment(
        INSTRUMENT_ID, at, at,
        PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE if eligible else PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP,
        eligible, "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        "Metals", "TOP3_ELIGIBLE", True, at, ("STORED_ONLY",), technical, structural,
        "NOT_EVALUATED_AT_SCAN", (), (),
    )
