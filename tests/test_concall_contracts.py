from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.concall.models import (
    ConcallDocument, ConcallGuidance, ConcallSegment,
    GuidanceMatchStatus, reconcile_guidance,
)
from app.fundamentals.models import (
    FinancialMetric, FinancialPeriodType, FinancialValueBasis,
    NumericScale, StatementScope,
)

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def sample_document():
    return ConcallDocument("NSE:TEST", "filing-1", "official-local-file", "a" * 64, NOW, NOW, 2027, 2)


def sample_guidance():
    return ConcallGuidance(
        sample_document().document_id, 0, FinancialMetric.REVENUE,
        Decimal("100"), NOW, FinancialPeriodType.QUARTERLY,
        FinancialValueBasis.QUARTER_ONLY, StatementScope.CONSOLIDATED,
        "INR", "crore", NumericScale.CRORES,
    )


def test_idempotent_document_identity():
    d = sample_document()
    assert d.document_id == sample_document().document_id
    assert d.document_id != replace(d, checksum="b" * 64).document_id


def test_point_in_time_visibility():
    d = sample_document()
    assert d.visible_at(NOW)
    assert not d.visible_at(NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        d.visible_at(datetime(2026, 10, 23))


def test_missing_actual_is_not_fabricated():
    result = reconcile_guidance(sample_guidance(), None, as_of=NOW)
    assert result.status is GuidanceMatchStatus.NOT_AVAILABLE
    assert result.difference is None


def test_invalid_input_rejected():
    with pytest.raises(ValueError):
        replace(sample_document(), checksum="invalid")
    with pytest.raises(ValueError):
        replace(sample_guidance(), target=Decimal("NaN"))
    with pytest.raises(ValueError):
        ConcallSegment(sample_document().document_id, 0, "", "text")
