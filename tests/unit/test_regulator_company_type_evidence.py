from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.historical.regulator_company_type_evidence as evidence
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 5, 10, tzinfo=UTC)
AS_OF = date(2026, 8, 31)
CIN = "L65190GJ1994PLC021012"


RBI_BANKS = b"""<table><tr><td>Domestic Private Sector Banks</td></tr><tr><td>Sr.No.</td><td>Name of the Bank</td></tr><tr><td>1.</td><td>ICICI Bank Limited</td></tr><tr><td>2.</td><td>Example Bank Limited</td></tr><tr><td>Small Finance Banks</td></tr><tr><td>1.</td><td>Example Small Finance Bank</td></tr></table>"""
IRDAI = b"""<table><tr><th>Sl.No</th><th>Name</th><th>Regn. No</th><th>Address</th></tr><tr><td>1</td><td>Example Life Insurance Limited</td><td>101</td><td>Official Address</td></tr></table>"""


def _bank():
    return evidence.rbi_scheduled_bank_batch(payload=RBI_BANKS, observed_at=T, source_as_of_date=AS_OF)


def _xlsx(tmp_path: Path, *, cancelled: bool = False) -> bytes:
    from openpyxl import Workbook
    book = Workbook(); sheet = book.active
    sheet.append(["Name of the Company", "Category", "CoR No", "CIN", "Address", "Cancellation Date"])
    sheet.append(["Example ARC Limited", "ARC", "R-1", "L12345MH2010PLC123456", "Address", "05-02-2024" if cancelled else None])
    sheet.append(["Example NBFC Limited", "NBFC-ICC", "R-2", "L12345MH2011PLC123456", "Address", "05-02-2024" if cancelled else None])
    path = tmp_path / "rbi.xlsx"; book.save(path); return path.read_bytes()


def _bridge(*, cin: str = CIN, isin: str = "INE090A01021", observation_id: str = "forward:one", day: date = AS_OF):
    return SimpleNamespace(cin=cin, isin=isin, observation_id=observation_id, later_session_date=day, anchor_known_ats=(datetime(2024, 1, 1, tzinfo=UTC),))


def _instrument() -> NseEquityInstrument:
    return NseEquityInstrument("NSE:INE090A01021", "ICICIBANK", "INE090A01021", None, None, "ACTIVE", None, True, T, "NSE")


def _taxonomy() -> InstrumentTaxonomyClassification:
    return InstrumentTaxonomyClassification(
        "taxonomy:icici", "NSE:INE090A01021", "Banks", "Financial Services", "Financial Services", "NSE_INDICES_OFFICIAL",
        ClassificationSourceStatus.OFFICIAL, datetime(2026, 8, 27, tzinfo=UTC), None, datetime(2026, 8, 27, tzinfo=UTC),
        None, "v1", macro_economic_sector_code="IN05", sector_code="IN0501", industry_code="IN050101", basic_industry_code="IN050101001",
    )


def test_rbi_scheduled_bank_evidence_parses_and_preserves_subtypes():
    batch = _bank()
    assert {item.legal_name for item in batch.evidence} == {"Example Bank Limited", "Example Small Finance Bank", "ICICI Bank Limited"}
    assert {item.regulator_subtype for item in batch.evidence} == {"Domestic Private Sector Banks", "Small Finance Banks"}
    assert all(item.entity_kind is evidence.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK for item in batch.evidence)


def test_rbi_registered_nbfc_and_arc_are_explicit_and_not_collapsed(tmp_path):
    batch = evidence.rbi_nbfc_arc_batch(payload=_xlsx(tmp_path), source=evidence.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, observed_at=T, source_as_of_date=AS_OF, source_reference=evidence.RBI_REGISTERED_NBFC_ARC_XLSX_URL)
    assert {item.entity_kind for item in batch.evidence} == {evidence.RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC, evidence.RegulatorEntityEvidenceKind.RBI_REGISTERED_ARC}
    assert {item.regulator_registration_id for item in batch.evidence} == {"R-1", "R-2"}


def test_rbi_cancelled_cor_is_a_separate_lifecycle_fact(tmp_path):
    batch = evidence.rbi_nbfc_arc_batch(payload=_xlsx(tmp_path, cancelled=True), source=evidence.RegulatorEvidenceSource.RBI_CANCELLED_NBFC_ARC, observed_at=T, source_as_of_date=AS_OF, source_reference=evidence.RBI_CANCELLED_NBFC_ARC_XLSX_URL)
    assert all(item.entity_status is evidence.RegulatorEntityStatus.CANCELLED for item in batch.evidence)
    assert all(item.cancellation_on == date(2024, 2, 5) for item in batch.evidence)
    assert all(item.temporal_status is evidence.RegulatorTemporalStatus.CANCELLATION_DATE_PRESENT for item in batch.evidence)


@pytest.mark.parametrize(("source", "kind"), [
    (evidence.RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, evidence.RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER),
    (evidence.RegulatorEvidenceSource.IRDAI_GENERAL_INSURERS, evidence.RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER),
    (evidence.RegulatorEvidenceSource.IRDAI_HEALTH_INSURERS, evidence.RegulatorEntityEvidenceKind.IRDAI_HEALTH_INSURER),
])
def test_irdai_approved_insurer_families_preserve_registration_and_subtype(source, kind):
    batch = evidence.irdai_insurer_batch(payload=IRDAI, source=source, observed_at=T, source_as_of_date=AS_OF)
    item = batch.evidence[0]
    assert (item.entity_kind, item.regulator_registration_id, item.address) == (kind, "101", "Official Address")


def test_irdai_rejects_non_insurer_source():
    with pytest.raises(evidence.RegulatorCompanyTypeEvidenceError, match="IRDAI_INSURER_SOURCE_INVALID"):
        evidence.irdai_insurer_batch(payload=IRDAI, source=evidence.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, observed_at=T)


def test_exact_cin_linkage_is_the_only_issuer_linkage_mechanism():
    artifact = evidence.source_artifact_from_payload(source=evidence.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, source_reference="https://rbi.example/official", payload=b"official", content_type="application/xlsx", observed_at=T, source_as_of_date=AS_OF, schema=("CIN", "Name"))
    item = evidence._entity(artifact=artifact, source_record_id="row:1", entity_kind=evidence.RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC, entity_status=evidence.RegulatorEntityStatus.LISTED, legal_name="Any Legal Name", cin=CIN)
    audit = evidence.audit_exact_regulator_issuer_links(evidence=(item,), active_bridges=(_bridge(),), as_of=T)[0]
    assert audit.linkage_status is evidence.IssuerLinkageStatus.EXACT_CIN_LINKED and audit.issuer_bridge_ids == ("forward:one",)


def test_missing_cin_stays_unresolved_even_when_name_is_identical_to_target():
    item = _bank().evidence[-1]
    audit = evidence.audit_exact_regulator_issuer_links(evidence=(item,), active_bridges=(_bridge(),), as_of=T)[0]
    assert audit.linkage_status is evidence.IssuerLinkageStatus.ISSUER_LINKAGE_UNRESOLVED and audit.reason == "REGULATOR_CIN_ABSENT"


def test_name_text_cannot_enter_exact_linkage_function():
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    body = source[source.index("def audit_exact_regulator_issuer_links"):source.index("def audit_nse_taxonomy_issuer_evidence")]
    assert "legal_name" not in body and "normalize" not in body


def test_future_active_bridge_is_excluded_from_pit_link_audit():
    item = _bank().evidence[0]
    audit = evidence.audit_exact_regulator_issuer_links(evidence=(item,), active_bridges=(_bridge(day=AS_OF + timedelta(days=1)),), as_of=T)[0]
    assert audit.linkage_status is evidence.IssuerLinkageStatus.ISSUER_LINKAGE_UNRESOLVED


def test_current_regulator_observation_without_a_list_date_cannot_link_backward_even_with_exact_cin():
    artifact = evidence.source_artifact_from_payload(source=evidence.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, source_reference="https://rbi.example/official", payload=b"official", content_type="application/xlsx", observed_at=T, source_as_of_date=None, schema=("CIN", "Name"))
    item = evidence._entity(artifact=artifact, source_record_id="row:date-gap", entity_kind=evidence.RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC, entity_status=evidence.RegulatorEntityStatus.LISTED, legal_name="Exact", cin=CIN)
    audit = evidence.audit_exact_regulator_issuer_links(evidence=(item,), active_bridges=(_bridge(),), as_of=T - timedelta(days=1))[0]
    assert not audit.pit_eligible and audit.issuer_bridge_ids == () and audit.reason == "SOURCE_DATE_UNAVAILABLE"


def test_incompatible_exact_regulator_paths_are_retained_as_a_conflict_not_prioritized():
    one = evidence.source_artifact_from_payload(source=evidence.RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, source_reference="https://rbi.example/bank", payload=b"bank", content_type="text/html", observed_at=T, source_as_of_date=AS_OF, schema=("CIN", "Name"))
    two = evidence.source_artifact_from_payload(source=evidence.RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, source_reference="https://irdai.example/life", payload=b"life", content_type="text/html", observed_at=T, source_as_of_date=AS_OF, schema=("CIN", "Name"))
    bank = evidence._entity(artifact=one, source_record_id="bank:1", entity_kind=evidence.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK, entity_status=evidence.RegulatorEntityStatus.LISTED, legal_name="Exact", cin=CIN)
    insurer = evidence._entity(artifact=two, source_record_id="life:1", entity_kind=evidence.RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER, entity_status=evidence.RegulatorEntityStatus.LISTED, legal_name="Exact", cin=CIN)
    audits = evidence.audit_exact_regulator_issuer_links(evidence=(bank, insurer), active_bridges=(_bridge(),), as_of=T)
    assert all(item.linkage_status is evidence.IssuerLinkageStatus.EVIDENCE_CONFLICTED for item in audits)
    assert all(item.reason == "INCOMPATIBLE_EXACT_REGULATOR_EVIDENCE" for item in audits)


def test_regulator_evidence_cannot_be_constructed_with_invalid_cin():
    artifact = _bank().artifact
    with pytest.raises(evidence.RegulatorCompanyTypeEvidenceError, match="CIN_INVALID"):
        evidence._entity(artifact=artifact, source_record_id="row:bad", entity_kind=evidence.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK, entity_status=evidence.RegulatorEntityStatus.LISTED, legal_name="Exact", cin="invalid")


def test_deterministic_evidence_and_source_fingerprints():
    first, second = _bank(), _bank()
    assert first.artifact == second.artifact and first.evidence == second.evidence


def test_replay_is_idempotent_and_uses_existing_snapshot_family(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "evidence.sqlite")
    store = evidence.RegulatorCompanyTypeEvidenceStore(repository)
    first = evidence.persist_regulator_evidence(store=store, batch=_bank())
    replay = evidence.persist_regulator_evidence(store=store, batch=_bank())
    assert first == (1, 0, 3, 0) and replay == (0, 1, 0, 3)
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE, limit=10)) == 4


def test_immutable_replay_conflict_is_rejected(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "evidence.sqlite")
    store = evidence.RegulatorCompanyTypeEvidenceStore(repository); batch = _bank(); store.save_artifact(batch.artifact)
    item = batch.evidence[0]; store.save_evidence(item)
    with pytest.raises(evidence.RegulatorCompanyTypeEvidenceError, match="IMMUTABILITY_CONFLICT"):
        store._save(item.evidence_id, object(), T)


def test_source_without_official_date_is_explicitly_not_historically_classifying():
    artifact = evidence.source_artifact_from_payload(source=evidence.RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, source_reference=evidence.RBI_SCHEDULED_BANKS_URL, payload=RBI_BANKS, content_type="text/html", observed_at=T, source_as_of_date=None, schema=("name",))
    assert artifact.temporal_status is evidence.RegulatorTemporalStatus.SOURCE_DATE_UNAVAILABLE


def test_taxonomy_codes_are_preserved_without_a_non_financial_mapping():
    audit = evidence.audit_nse_taxonomy_issuer_evidence(classifications=(_taxonomy(),), instruments=(_instrument(),), active_bridges=(_bridge(),), as_of=T)[0]
    assert audit.taxonomy_codes == ("IN05", "IN0501", "IN050101", "IN050101001") and audit.issuer_bridge_ids == ("forward:one",)


def test_taxonomy_current_evidence_is_not_leaked_backwards():
    audit = evidence.audit_nse_taxonomy_issuer_evidence(classifications=(_taxonomy(),), instruments=(_instrument(),), active_bridges=(_bridge(),), as_of=datetime(2024, 2, 5, 23, 59, tzinfo=UTC))[0]
    assert not audit.pit_eligible and not audit.issuer_bridge_ids


def test_ambiguous_taxonomy_instrument_is_not_linked_to_an_issuer():
    other = NseEquityInstrument("NSE:INE090A01021", "OTHER", "INE000A01001", None, None, "ACTIVE", None, True, T, "NSE")
    audit = evidence.audit_nse_taxonomy_issuer_evidence(classifications=(_taxonomy(),), instruments=(_instrument(), other), active_bridges=(_bridge(),), as_of=T)[0]
    assert audit.isin is None and not audit.issuer_bridge_ids


def test_no_company_type_policy_or_compounder_dependency_leaks_into_evidence_boundary():
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    forbidden = ("app.intelligence", "company_type_classification", "compounder", "portfolio", "broker", "order")
    assert not any(any(value in module for value in forbidden) for module in imports)


def test_no_runtime_clock_or_http_client_dependency_exists_in_the_boundary():
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source and "requests" not in source and "urllib" not in source


def test_all_evidence_is_immutable_slots_dataclasses():
    item = _bank().evidence[0]
    with pytest.raises((AttributeError, TypeError)):
        item.legal_name = "changed"  # type: ignore[misc]


def test_unsupported_html_has_no_supported_entity_rows():
    with pytest.raises(evidence.RegulatorCompanyTypeEvidenceError, match="NO_SUPPORTED_ENTITY_ROWS"):
        evidence.rbi_scheduled_bank_batch(payload=b"<table><tr><td>no records</td></tr></table>", observed_at=T)


def test_nbfc_non_xlsx_provider_response_fails_closed():
    with pytest.raises(evidence.RegulatorCompanyTypeEvidenceError, match="NOT_VALID_XLSX"):
        evidence.rbi_nbfc_arc_batch(payload=b"<html>access denied</html>", source=evidence.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, observed_at=T, source_as_of_date=AS_OF, source_reference=evidence.RBI_REGISTERED_NBFC_ARC_XLSX_URL)


def test_snapshot_family_is_dedicated_evidence_not_company_type_activation():
    assert CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE.value == "HISTORICAL_REGULATOR_ENTITY_EVIDENCE"
    assert "COMPANY_TYPE" not in CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE.value
