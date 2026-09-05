from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
import ast
import inspect
from pathlib import Path

import pytest

import app.historical.filing_timestamp_timezone_provenance as module
from app.filings.models import (
    CorporateFiling,
    FilingTimestampSourceEvidence,
    FilingType,
    PrimarySourceQuality,
)
from app.historical.filing_timestamp_timezone_provenance import (
    EventKnownTimeStatus,
    FilingTimestampAuditRecord,
    FilingTimestampTimezoneError,
    RawTimestampRetentionState,
    SourceTimestampEncoding,
    TimestampProvenanceState,
    TimestampResolutionState,
    audit_filing_timestamp_receipts,
    canonical_event_timestamp_from_receipt,
    make_filing_timestamp_input,
    make_source_timezone_rule,
    receipt_from_corporate_filing,
    resolve_filing_timestamp,
    serialize_filing_timestamp_receipt,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance


T = datetime(2026, 9, 5, tzinfo=UTC)
FP = "sha256:" + "a" * 64
SOURCE = "BSE_OFFICIAL_FINANCIAL_RESULTS"
FIELD = "BSE_RESULT_ARCHIVE.CSV.filing_date_time"


def _input(*, source: str = SOURCE, field: str | None = FIELD, raw: str | None = "05/28/2026 6:31:40 PM",
           parsed: datetime | None = datetime(2026, 5, 28, 18, 31, 40), filing_date: date | None = None,
           declared_zone: str | None = None, encoding: SourceTimestampEncoding = SourceTimestampEncoding.TEXT):
    return make_filing_timestamp_input(
        filing_id="bse-filing:fixture", canonical_instrument_id="NSE:INE372A01015", source_family=source,
        source_document_identity="https://www.bseindia.com/XBRLFILES/fixture.xml",
        source_payload_identity="https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd=532259",
        source_payload_fingerprint=FP, raw_timestamp_field_path=field, raw_timestamp_value=raw,
        parsed_local_timestamp=parsed, filing_date=filing_date, declared_timezone_id=declared_zone,
        encoding=encoding, event_known_time_status=EventKnownTimeStatus.SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED,
    )


def _rule(*, source: str = SOURCE, field: str = FIELD, known_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
          effective_from: date = date(2026, 1, 1), historical: bool = False,
          timezone: str = "Asia/Kolkata"):
    return make_source_timezone_rule(
        rule_id="bse-results-archive-timestamp-v1", source_family=source, raw_timestamp_field_path=field,
        timezone_id=timezone, provenance_state=TimestampProvenanceState.SOURCE_SCHEMA_DOCUMENTED,
        source_evidence_identity="BSE-SCHEMA-2026", source_evidence_fingerprint="sha256:" + "b" * 64,
        evidence_known_at=known_at, effective_from=effective_from, historical_continuity_proven=historical,
    )


def _filing(*, evidence: FilingTimestampSourceEvidence | None, warning: str | None = None) -> CorporateFiling:
    instrument = InstrumentIdentity("NSE:INE372A01015", Exchange.NSE, "APARINDS", "APARINDS", "INE372A01015", "EQ", InstrumentType.NSE_EQUITY, "APAR")
    return CorporateFiling(
        "bse-official:fixture", instrument, Exchange.BSE, "BSE_OFFICIAL", PrimarySourceQuality.PRIMARY_EXCHANGE,
        FilingType.FINANCIAL_RESULTS, "Quarter", "BSE result", datetime(2026, 5, 28, 13, 1, 40, tzinfo=UTC),
        datetime(2026, 5, 28, 13, 2, tzinfo=UTC), evidence.source_payload_identity if evidence else "source",
        evidence.source_document_identity if evidence else "document",
        MarketDataProvenance("BSE_OFFICIAL", "532259", None, None, T, "bse-official-xbrl-v1"),
        warnings=(warning,) if warning else (), timestamp_evidence=evidence,
    )


def test_raw_timestamp_is_retained_but_never_interpreted_without_source_timezone_evidence():
    receipt = resolve_filing_timestamp(_input(), as_of=T)
    assert receipt.raw_retention_state is RawTimestampRetentionState.RETAINED
    assert receipt.raw_timestamp_value == "05/28/2026 6:31:40 PM"
    assert receipt.raw_timestamp_field_path == FIELD
    assert receipt.parsed_local_timestamp == datetime(2026, 5, 28, 18, 31, 40)
    assert receipt.resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED
    assert receipt.normalized_utc_timestamp is None


def test_explicit_offset_and_z_resolve_deterministically_without_ist_assumption():
    offset = _input(raw="2026-05-28T18:31:40+05:30", parsed=datetime(2026, 5, 28, 18, 31, 40, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")))
    utc = _input(raw="2026-05-28T13:01:40Z", parsed=datetime(2026, 5, 28, 13, 1, 40, tzinfo=UTC))
    first, second = resolve_filing_timestamp(offset, as_of=T), resolve_filing_timestamp(utc, as_of=T)
    assert first.normalized_utc_timestamp == second.normalized_utc_timestamp == datetime(2026, 5, 28, 13, 1, 40, tzinfo=UTC)
    assert first.timezone_provenance_state is TimestampProvenanceState.EXPLICIT_OFFSET
    assert second.original_timezone_id == "+00:00"
    assert canonical_event_timestamp_from_receipt(first) is not None


def test_documented_source_local_timezone_is_field_scoped_pit_safe_and_historical_scope_is_explicit():
    current = _rule(effective_from=date(2026, 1, 1))
    resolved = resolve_filing_timestamp(_input(), rules=(current,), as_of=T)
    assert resolved.resolution_state is TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN
    assert resolved.normalized_utc_timestamp == datetime(2026, 5, 28, 13, 1, 40, tzinfo=UTC)
    assert resolved.timezone_evidence_ids == (current.rule_id,)

    old = _input(raw="05/28/2023 6:31:40 PM", parsed=datetime(2023, 5, 28, 18, 31, 40))
    unresolved = resolve_filing_timestamp(old, rules=(current,), as_of=T)
    assert unresolved.resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED
    historical = _rule(effective_from=date(2026, 1, 1), historical=True)
    assert resolve_filing_timestamp(old, rules=(historical,), as_of=T).resolution_state is TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN


def test_source_rule_never_leaks_to_other_source_or_before_its_own_pit_visibility():
    rule = _rule(known_at=datetime(2026, 9, 6, tzinfo=UTC))
    assert resolve_filing_timestamp(_input(), rules=(rule,), as_of=T).resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED
    visible = _rule()
    nse = _input(source="NSE_OFFICIAL_FINANCIAL_RESULTS")
    assert resolve_filing_timestamp(nse, rules=(visible,), as_of=T).resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED


def test_identical_rule_duplicates_do_not_create_false_ambiguity_but_conflicting_records_fail_closed():
    rule = _rule()
    assert resolve_filing_timestamp(_input(), rules=(rule, rule), as_of=T).resolution_state is TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN
    conflict = make_source_timezone_rule(
        rule_id="bse-results-archive-timestamp-conflict-v1", source_family=rule.source_family, raw_timestamp_field_path=rule.raw_timestamp_field_path,
        timezone_id="UTC", provenance_state=TimestampProvenanceState.SOURCE_SCHEMA_DOCUMENTED,
        source_evidence_identity="BSE-SCHEMA-CONFLICT", source_evidence_fingerprint="sha256:" + "c" * 64,
        evidence_known_at=rule.evidence_known_at, effective_from=rule.effective_from,
    )
    receipt = resolve_filing_timestamp(_input(), rules=(rule, conflict), as_of=T)
    assert receipt.resolution_state is TimestampResolutionState.TIMEZONE_EVIDENCE_CONFLICTED


def test_date_only_never_receives_fake_midnight_and_missing_timestamp_fails_closed():
    dated = _input(raw="2026-05-28", parsed=None, filing_date=date(2026, 5, 28), encoding=SourceTimestampEncoding.DATE_ONLY)
    receipt = resolve_filing_timestamp(dated, as_of=T)
    assert receipt.resolution_state is TimestampResolutionState.FILING_DATE_KNOWN
    assert receipt.parsed_local_timestamp is None and receipt.normalized_utc_timestamp is None
    missing = _input(field=None, raw=None, parsed=None, encoding=SourceTimestampEncoding.MISSING)
    assert resolve_filing_timestamp(missing, as_of=T).resolution_state is TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE


def test_conflicting_offset_and_documented_source_timezone_is_preserved_fail_closed():
    source = _input(raw="2026-05-28T18:31:40+05:30", parsed=datetime(2026, 5, 28, 18, 31, 40, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")))
    conflict = _rule(timezone="UTC")
    receipt = resolve_filing_timestamp(source, rules=(conflict,), as_of=T)
    assert receipt.resolution_state is TimestampResolutionState.TIMEZONE_EVIDENCE_CONFLICTED
    assert receipt.normalized_utc_timestamp is None
    assert receipt.timezone_evidence_ids == (conflict.rule_id,)


def test_legacy_filing_does_not_reuse_its_normalized_assumption_as_raw_evidence():
    legacy = receipt_from_corporate_filing(_filing(evidence=None, warning="TIMESTAMP_EXCHANGE_LOCAL_ASSUMPTION"), as_of=T)
    assert legacy.raw_retention_state is RawTimestampRetentionState.NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD
    assert legacy.resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED
    assert legacy.raw_timestamp_value is legacy.normalized_utc_timestamp is None
    local = receipt_from_corporate_filing(_filing(evidence=None, warning="SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN"), as_of=T)
    assert local.resolution_state is TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE


def test_new_bse_evidence_retains_source_field_and_text_while_leaving_timezone_unresolved():
    evidence = FilingTimestampSourceEvidence(SOURCE, "https://www.bseindia.com/XBRLFILES/fixture.xml", "https://api.bseindia.com/archive", FIELD, "05/28/2026 6:31:40 PM", "BSE_RESULT_FILING_OR_REVISION_TIMESTAMP")
    receipt = receipt_from_corporate_filing(_filing(evidence=evidence), as_of=T)
    assert receipt.raw_timestamp_value == evidence.raw_timestamp_value
    assert receipt.raw_timestamp_field_path == FIELD
    assert receipt.resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED


def test_identity_is_separate_from_tamper_evident_fingerprint_and_serialization_is_stable():
    one = resolve_filing_timestamp(_input(), rules=(_rule(),), as_of=T)
    two = resolve_filing_timestamp(_input(), rules=(_rule(),), as_of=T)
    assert one.receipt_id == two.receipt_id and one.fingerprint == two.fingerprint
    assert serialize_filing_timestamp_receipt(one) == serialize_filing_timestamp_receipt(two)
    with pytest.raises(FilingTimestampTimezoneError, match="RECEIPT_INVALID"):
        replace(one, raw_timestamp_value="05/28/2026 6:31:41 PM")
    with pytest.raises(FrozenInstanceError):
        one.fingerprint = "sha256:" + "c" * 64  # type: ignore[misc]


def test_audit_is_deterministic_for_all_332_and_generic_five_target_coverage():
    names = ("NSE:INE372A01015", "NSE:INE0FHS01024", "NSE:INE955D01029", "NSE:INE068V01023", "NSE:INE090A01021")
    receipts = []
    for index in range(332):
        item = _input()
        item = replace(item, filing_id=f"bse-filing:{index}", canonical_instrument_id=names[index % len(names)])
        receipts.append(FilingTimestampAuditRecord(resolve_filing_timestamp(item, as_of=T), 2022 + (index % 5)))
    first, second = audit_filing_timestamp_receipts(receipts), audit_filing_timestamp_receipts(reversed(receipts))
    assert first == second and first.total == 332
    assert dict(first.resolution_counts)[TimestampResolutionState.TIMEZONE_UNRESOLVED] == 332
    assert {bucket.key for bucket in first.instrument} == set(names)
    assert sum(bucket.total for bucket in first.coverage_year) == 332


def test_static_boundary_contains_no_clock_storage_price_portfolio_or_execution_dependency():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("sqlite3", "app.signals", "app.portfolio", "app.orders", "app.api")
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    assert "datetime.now" not in source
