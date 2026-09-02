"""Local approved-source U17 adapters for financial and ownership evidence.

The adapters intentionally do not acquire data.  Financial facts are accepted
only from manually staged official BSE XBRL files.  Shareholding remains an
official NSE Regulation 31 filing-lineage import: this repository has no
approved normalized ownership-percentage model, so it never invents one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from app.data_operations.models import (
    EvidenceRefreshOutcome, EvidenceRefreshRequest, EvidenceRefreshStatus,
    ReconciliationStatus,
)
from app.filings.store import CorporateFilingsStore
from app.fundamentals.bse_official import (
    BSE_OFFICIAL_PROVIDER, BseOfficialError, BSEOfficialLocalXbrlIngestionService,
    _raw_xbrl_value_scale,
)
from app.fundamentals.models import FinancialMetric, NumericScale
from app.fundamentals.store import FinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.nse_import.service import (
    ExportFamily, FrozenCohortInstrumentResolver, ImportStatus,
    ImportRunStore, NSEOfficialExportProvider, OfficialExchangeImportService,
)
from app.real_brain.service import RealBrainTrialStore
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)
from app.universe_analysis.service import CoreUniverseAnalysisStore
from app.data_operations.nse_shareholding_acquisition import APPROVED_NSE_REG31_TARGETS


NSE_OFFICIAL = "NSE_OFFICIAL"


@dataclass(frozen=True, slots=True)
class BseLegacyScaleFactCompatibility:
    """Immutable proof that a legacy display scale did not alter the value.

    This is operational reconciliation lineage, not a replacement financial
    fact.  The legacy ``FinancialFact`` stays immutable and retains its own
    historical availability; the compatibility evidence is visible only from
    ``known_at``.
    """

    legacy_fact_id: str
    legacy_fact_fingerprint: str
    incoming_fact_fingerprint: str
    metric: FinancialMetric
    value: Decimal
    currency: str
    unit: str
    legacy_scale: NumericScale
    official_raw_scale: NumericScale
    period_end: datetime
    legacy_available_at: datetime

    def __post_init__(self) -> None:
        if not all((self.legacy_fact_id, self.legacy_fact_fingerprint, self.incoming_fact_fingerprint, self.currency, self.unit)):
            raise ValueError("BSE legacy-scale compatibility identity is required.")
        if self.period_end.tzinfo is None or self.legacy_available_at.tzinfo is None:
            raise ValueError("BSE legacy-scale compatibility timestamps must be timezone-aware.")
        if self.legacy_scale is self.official_raw_scale:
            raise ValueError("BSE legacy-scale compatibility requires a representation difference.")


@dataclass(frozen=True, slots=True)
class BseLegacyScaleReconciliation:
    """Append-only, source-document-scoped legacy display-scale correction."""

    reconciliation_id: str
    source_checksum: str
    canonical_instrument_id: str
    known_at: datetime
    rule: str
    compatibilities: tuple[BseLegacyScaleFactCompatibility, ...]
    reconciliation_fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.reconciliation_id, self.source_checksum, self.canonical_instrument_id, self.rule, self.reconciliation_fingerprint)):
            raise ValueError("BSE legacy-scale reconciliation identity is required.")
        if self.known_at.tzinfo is None or not self.compatibilities:
            raise ValueError("BSE legacy-scale reconciliation requires known time and facts.")
        if self.rule != "LEGACY_SCALE_METADATA_CORRECTION":
            raise ValueError("Unsupported BSE legacy-scale reconciliation rule.")


class BseLocalFinancialResultsRefreshJob:
    """Append staged official BSE XBRLs through the existing canonical importer.

    A local XBRL with no exchange publication timestamp stays PIT-visible only
    from its original system observation.  A changed same-period value without
    explicit revision metadata is rejected before it can become a silent
    latest-wins replacement.
    """

    def __init__(
        self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore,
        filings: CorporateFilingsStore, facts: FinancialFactStore, source_directory: Path,
    ) -> None:
        self._repository, self._universe = repository, universe
        self._filings, self._facts, self._source_directory = filings, facts, source_directory

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        paths = _local_files(self._source_directory, (".xml", ".xbrl"))
        if not paths:
            return _source_unavailable("BSE_OFFICIAL_LOCAL_XBRL_REQUIRED", provider=BSE_OFFICIAL_PROVIDER)
        identities = _current_identities(self._universe)
        if not identities:
            return _source_unavailable("NSE_UNIVERSE_SNAPSHOT_REQUIRED", provider=BSE_OFFICIAL_PROVIDER)
        service = BSEOfficialLocalXbrlIngestionService(
            self._filings, self._facts, mapping_store=self._universe,
            clock=lambda: request.started_at.astimezone(UTC),
        )
        accepted = duplicates = conflicts = rejected = unresolved = 0
        warnings: set[str] = {"PIT_AVAILABLE_FROM_SYSTEM_FIRST_OBSERVED"}
        references: list[str] = []
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        for path in paths:
            try:
                inspection = service.inspect(path)
            except (BseOfficialError, OSError, UnicodeError, ValueError):
                rejected += 1
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, path.name, "BSE_LOCAL_XBRL_INVALID"))
                continue
            instrument = identities.get(inspection.document.isin.upper())
            if instrument is None:
                unresolved += 1
                findings.append((ReconciliationStatus.GAP_FOUND, path.name, "BSE_LOCAL_XBRL_EXACT_ISIN_UNRESOLVED"))
                continue
            compatibility, conflict_reason = _legacy_scale_compatibility(
                self._facts, instrument.instrument_id, inspection,
            )
            if conflict_reason is not None:
                conflicts += 1
                findings.append((ReconciliationStatus.CONFLICT_FOUND, path.name, conflict_reason))
                continue
            if compatibility is not None:
                outcome = self._save_legacy_scale_reconciliation(compatibility, request.started_at.astimezone(UTC))
                references.append("BSE_OFFICIAL_XBRL_SHA256:" + inspection.checksum)
                warnings.add("BSE_LEGACY_SCALE_METADATA_COMPATIBILITY")
                if outcome == "INSERTED":
                    accepted += 1
                else:
                    duplicates += 1
                findings.append((ReconciliationStatus.COMPLETE, path.name, "LEGACY_SCALE_METADATA_CORRECTION"))
                continue
            report = service.ingest(instrument, inspection.document.security_code, path)
            references.append("BSE_OFFICIAL_XBRL_SHA256:" + inspection.checksum)
            conflicts += report.facts_conflicted
            if report.facts_conflicted:
                findings.append((ReconciliationStatus.CONFLICT_FOUND, path.name, "BSE_LOCAL_XBRL_FACT_CONFLICT"))
            if report.filing_outcome is not None and report.filing_outcome.value == "INSERTED":
                accepted += 1
            else:
                duplicates += 1
            warnings.update(report.warnings)
        gaps = unresolved + rejected
        store_verified = bool(accepted or duplicates) and not (gaps or conflicts)
        status = (
            EvidenceRefreshStatus.INVALID_EVIDENCE if rejected and not accepted and not duplicates
            else EvidenceRefreshStatus.PARTIAL if gaps or conflicts
            else EvidenceRefreshStatus.NO_CHANGE if not accepted
            else EvidenceRefreshStatus.COMPLETE
        )
        return EvidenceRefreshOutcome(
            status, BSE_OFFICIAL_PROVIDER, discovered_count=len(paths), accepted_count=accepted,
            duplicate_count=duplicates, conflict_count=conflicts, rejected_count=rejected,
            gap_count=gaps, accepted_through=request.started_at.astimezone(UTC),
            source_fingerprint=_paths_fingerprint(paths), verified_from_store=store_verified,
            error_summary="BSE_LOCAL_XBRL_INVALID" if status is EvidenceRefreshStatus.INVALID_EVIDENCE else None,
            warnings=tuple(sorted(warnings)), source_references=tuple(sorted(set(references))), findings=tuple(findings),
        )

    def _save_legacy_scale_reconciliation(
        self, compatibility: "_LegacyScaleCompatibility", known_at: datetime,
    ) -> str:
        identifier = "bse-legacy-scale-reconciliation:" + compatibility.source_checksum
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            payload = existing.payload
            if (
                existing.family is CoreApiSnapshotFamily.RECONCILIATION_RESULT
                and isinstance(payload, BseLegacyScaleReconciliation)
                and payload.source_checksum == compatibility.source_checksum
                and payload.canonical_instrument_id == compatibility.canonical_instrument_id
                and payload.compatibilities == compatibility.compatibilities
                and payload.reconciliation_fingerprint == compatibility.fingerprint
            ):
                return "IDENTICAL"
            raise ValueError("BSE legacy-scale reconciliation artifacts are immutable and cannot be overwritten.")
        value = BseLegacyScaleReconciliation(
            identifier, compatibility.source_checksum, compatibility.canonical_instrument_id, known_at,
            "LEGACY_SCALE_METADATA_CORRECTION", compatibility.compatibilities, compatibility.fingerprint,
        )
        self._repository.save_snapshot(CoreApiSnapshot(
            identifier, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            "bse-legacy-scale-reconciliation-v1", value.reconciliation_fingerprint, known_at, value,
        ))
        return "INSERTED"


class NseReg31ShareholdingRefreshJob:
    """Ingest staged official NSE Regulation 31 filings, not synthetic holdings."""

    def __init__(
        self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore,
        filings: CorporateFilingsStore, facts: FinancialFactStore, runs: ImportRunStore,
        source_directory: Path,
    ) -> None:
        self._repository, self._universe = repository, universe
        self._filings, self._facts, self._runs, self._source_directory = filings, facts, runs, source_directory

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        paths = _preferred_reg31_artifacts(_local_files(self._source_directory, (".csv", ".xlsx", ".xml")))
        if not paths:
            return _source_unavailable("NSE_REG31_SHAREHOLDING_EXPORT_REQUIRED")
        resolver = _reg31_portfolio_xbrl_resolver(self._universe) if any(path.suffix.lower() == ".xml" for path in paths) else _frozen_cohort_resolver(self._repository, self._universe)
        if resolver is None:
            return _source_unavailable("FROZEN_COHORT_UNIVERSE_REQUIRED")
        service = OfficialExchangeImportService(
            NSEOfficialExportProvider(), resolver, self._filings, self._facts, self._runs,
            clock=lambda: request.started_at.astimezone(UTC),
        )
        accepted = duplicates = conflicts = rejected = unresolved = 0
        references: list[str] = []
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        for path in paths:
            try:
                # A P0 smoke proves one official reporting period.  The NSE
                # page export may include a company's history; retain the
                # original artifact/checksum but select only its latest
                # explicitly reported period for this bounded job.
                report = service.import_file(
                    path, family=ExportFamily.REGULATION_31, latest_reg31_period_only=True,
                )
            except (OSError, UnicodeError, ValueError):
                rejected += 1
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, path.name, "NSE_REG31_SHAREHOLDING_SOURCE_INVALID"))
                continue
            accepted += report.accepted; duplicates += report.duplicates; conflicts += report.conflicts
            rejected += report.rejected; unresolved += report.unresolved_symbols
            references.append("NSE_OFFICIAL_REG31_SHA256:" + report.checksum)
            if report.conflicts:
                findings.append((ReconciliationStatus.CONFLICT_FOUND, path.name, "NSE_REG31_SHAREHOLDING_CONFLICT"))
            if report.unresolved_symbols:
                findings.append((ReconciliationStatus.GAP_FOUND, path.name, "NSE_REG31_SHAREHOLDING_IDENTITY_UNRESOLVED"))
        gaps = rejected + unresolved
        store_verified = bool(accepted or duplicates) and not (gaps or conflicts)
        status = (
            EvidenceRefreshStatus.INVALID_EVIDENCE if rejected and not accepted and not duplicates
            else EvidenceRefreshStatus.PARTIAL if gaps or conflicts
            else EvidenceRefreshStatus.NO_CHANGE if not accepted
            else EvidenceRefreshStatus.COMPLETE
        )
        return EvidenceRefreshOutcome(
            status, NSE_OFFICIAL, discovered_count=len(paths), accepted_count=accepted,
            duplicate_count=duplicates, conflict_count=conflicts, rejected_count=rejected,
            gap_count=gaps, accepted_through=request.started_at.astimezone(UTC),
            source_fingerprint=_paths_fingerprint(paths), verified_from_store=store_verified,
            error_summary="NSE_REG31_SHAREHOLDING_SOURCE_INVALID" if status is EvidenceRefreshStatus.INVALID_EVIDENCE else None,
            warnings=("SHAREHOLDING_FILING_LINEAGE_ONLY", "SHAREHOLDING_PERCENTAGES_NOT_MATERIALIZED"),
            source_references=tuple(sorted(set(references))), findings=tuple(findings),
        )


def _current_identities(universe: CoreUniverseAnalysisStore) -> dict[str, InstrumentIdentity]:
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        return {}
    values: dict[str, list[InstrumentIdentity]] = {}
    for item in universe.instruments_as_of(snapshot.as_of):
        if not item.isin:
            continue
        identity = InstrumentIdentity(
            item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, item.series if hasattr(item, "series") else None,
            InstrumentType.NSE_EQUITY, item.company_name,
        )
        values.setdefault(item.isin.upper(), []).append(identity)
    return {key: entries[0] for key, entries in values.items() if len(entries) == 1}


def _frozen_cohort_resolver(repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore) -> FrozenCohortInstrumentResolver | None:
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        return None
    trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    if trial is None:
        return None
    identities = tuple(_current_identities(universe).values())
    return FrozenCohortInstrumentResolver(identities, trial.selected_instrument_ids)


def _preferred_reg31_artifacts(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Prefer an independently validated current XBRL over a same-symbol CSV.

    Legacy CSV bytes remain staged evidence; this selection merely prevents a
    current XBRL filing from being made to compete with known legacy CSV
    metadata for the same issuer.
    """
    approved_symbols = {target.symbol for target in APPROVED_NSE_REG31_TARGETS}
    xbrls = tuple(
        path for path in paths
        if path.suffix.lower() == ".xml"
        and path.name.startswith("SHP-Reg31-equities-")
        and len(path.name.split("-")) > 3
        and path.name.split("-")[3] in approved_symbols
    )
    return xbrls or paths


def _reg31_portfolio_xbrl_resolver(universe: CoreUniverseAnalysisStore) -> FrozenCohortInstrumentResolver | None:
    identities = _current_identities(universe)
    wanted = tuple(identities.get(target.isin) for target in APPROVED_NSE_REG31_TARGETS)
    if any(item is None for item in wanted):
        return None
    values = tuple(item for item in wanted if item is not None)
    return FrozenCohortInstrumentResolver(values, (item.instrument_id for item in values))


@dataclass(frozen=True, slots=True)
class _LegacyScaleCompatibility:
    source_checksum: str
    canonical_instrument_id: str
    compatibilities: tuple[BseLegacyScaleFactCompatibility, ...]
    fingerprint: str


def _legacy_scale_compatibility(
    facts: FinancialFactStore, instrument_id: str, inspection: object,
) -> tuple[_LegacyScaleCompatibility | None, str | None]:
    """Detect immutable same-period conflicts before writing a local XBRL.

    The current BSE normalizer treats the XBRL numeric value as raw units and
    retains ``LevelOfRounding`` only as provenance.  Earlier local pilot rows
    used that display-level rounding as the fact scale.  They must remain
    immutable and auditable; this job therefore reports the representation
    divergence instead of treating the same XML as a harmless duplicate or
    silently overwriting the older facts.
    """
    document = getattr(inspection, "document")
    candidates: list[BseLegacyScaleFactCompatibility] = []
    matched_metrics = 0
    for metric, value in document.facts:
        if not isinstance(metric, FinancialMetric):
            continue
        matches = facts.series(
            instrument_id, metric, period_type=inspection.period_type,
            scope=document.scope, end=inspection.period_end, limit=500,
        )
        for item in matches:
            if item.period_end != inspection.period_end:
                continue
            if item.value != value:
                return None, "BSE_LOCAL_XBRL_NONREVISION_VALUE_CONFLICT"
            matched_metrics += 1
            expected_scale = _raw_xbrl_value_scale(metric, document.scale or NumericScale.UNITS)
            if item.scale is expected_scale:
                break
            if not _attestable_legacy_fact(item):
                return None, "BSE_LOCAL_XBRL_LEGACY_REPRESENTATION_UNATTESTED"
            candidates.append(BseLegacyScaleFactCompatibility(
                item.fact_id, _financial_fact_fingerprint(item),
                _incoming_fact_fingerprint(instrument_id, inspection, metric, value, expected_scale),
                metric, value, item.currency, item.unit, item.scale, expected_scale,
                item.period_end, item.available_at,
            ))
            break
    if not candidates:
        return None, None
    if matched_metrics != len(document.facts) or len(candidates) != len(document.facts):
        return None, "BSE_LOCAL_XBRL_LEGACY_REPRESENTATION_MIXED_OR_INCOMPLETE"
    entries = tuple(sorted(candidates, key=lambda item: (item.metric.value, item.legacy_fact_id)))
    fingerprint = sha256(repr((instrument_id, getattr(inspection, "checksum"), entries)).encode("utf-8")).hexdigest()
    return _LegacyScaleCompatibility(getattr(inspection, "checksum"), instrument_id, entries, fingerprint), None


def _nonrevision_conflict_reason(
    facts: FinancialFactStore, instrument_id: str, inspection: object,
) -> str | None:
    """Compatibility wrapper retained for existing operational callers/tests."""
    _compatibility, reason = _legacy_scale_compatibility(facts, instrument_id, inspection)
    return reason


def _attestable_legacy_fact(item: object) -> bool:
    required = ("fact_id", "currency", "unit", "scale", "available_at", "published_at", "received_at")
    return all(hasattr(item, name) for name in required)


def _financial_fact_fingerprint(item: object) -> str:
    return sha256(repr(item).encode("utf-8")).hexdigest()


def _incoming_fact_fingerprint(
    instrument_id: str, inspection: object, metric: FinancialMetric, value: Decimal, scale: NumericScale,
) -> str:
    document = getattr(inspection, "document")
    semantic = (
        BSE_OFFICIAL_PROVIDER, getattr(inspection, "checksum"), instrument_id, metric.value, str(value),
        document.currency, getattr(inspection, "period_type").value, getattr(inspection, "value_basis").value,
        getattr(inspection, "period_end").isoformat(), document.scope.value if document.scope else None,
        scale.value,
    )
    return sha256(repr(semantic).encode("utf-8")).hexdigest()


def _local_files(directory: Path, suffixes: tuple[str, ...]) -> tuple[Path, ...]:
    return tuple(sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in suffixes),
        key=lambda item: item.name.casefold(),
    )) if directory.is_dir() else ()


def _paths_fingerprint(paths: tuple[Path, ...]) -> str:
    return sha256("|".join(sha256(path.read_bytes()).hexdigest() for path in paths).encode()).hexdigest()


def _source_unavailable(code: str, *, provider: str = NSE_OFFICIAL) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, provider, error_summary=code, warnings=(code,))


__all__ = (
    "BseLegacyScaleFactCompatibility", "BseLegacyScaleReconciliation",
    "BseLocalFinancialResultsRefreshJob", "NseReg31ShareholdingRefreshJob",
)
