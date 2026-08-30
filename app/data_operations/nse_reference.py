"""U17 adapters for already-acquired official NSE reference evidence.

These jobs do not download or discover sources.  They only validate the
approved local NSE artefacts through the existing canonical stores and retain
first-observed/PIT limitations when an official file does not provide an
effective history.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping

from app.data_operations.models import (
    EvidenceRefreshOutcome, EvidenceRefreshRequest, EvidenceRefreshStatus,
    ReconciliationStatus,
)
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import HistoricalSecurityMasterStore, NseOfficialCorporateActionCsvImporter
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.taxonomy.nse_indices import NseIndicesTaxonomyImporter
from app.taxonomy.nse_sector_indices import NseSectorIndexConstituent, NseSectorIndexMapping, SectorIndexMappingStatus
from app.taxonomy.service import TaxonomySnapshotStore
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


NSE_OFFICIAL = "NSE_OFFICIAL"
NIFTY_500_UNIVERSE_ID = "NIFTY_500"
_MEMBER_HEADERS = frozenset({"SYMBOL", "SERIES", "ISIN CODE"})


@dataclass(frozen=True, slots=True)
class _Member:
    universe_id: str
    symbol: str
    isin: str
    series: str
    source_reference: str
    source_fingerprint: str


def _all(repository: CoreApiSnapshotRepository, family: CoreApiSnapshotFamily) -> tuple[object, ...]:
    values: list[object] = []
    offset = 0
    while True:
        page = repository.list_snapshots(family, limit=100, offset=offset)
        values.extend(item.payload for item in page)
        if len(page) < 100:
            return tuple(values)
        offset += len(page)


class NseIndexMembershipRefreshJob:
    """Materialise first-observed current official memberships as PIT intervals.

    Current NSE constituent exports do not supply historic admission/removal
    dates.  Consequently this adapter never backdates them.  A disappearance
    in a later current-only export is a typed reconciliation finding rather
    than an invented interval closure.
    """

    def __init__(self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore,
                 source_root: Path, master: HistoricalSecurityMasterStore | None = None) -> None:
        self._repository, self._universe = repository, universe
        self._source_root, self._master = source_root, master or HistoricalSecurityMasterStore(repository)

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        path = self._source_root / "nifty500.csv"
        if not path.is_file():
            return _source_unavailable("NSE_NIFTY500_CONSTITUENT_EXPORT_REQUIRED")
        observed = request.started_at.astimezone(UTC)
        try:
            rows = (*_nifty_members(path), *_stored_sector_members(self._repository))
        except (OSError, UnicodeError, ValueError) as error:
            return _invalid("NSE_INDEX_MEMBERSHIP_SOURCE_INVALID", str(error))
        if not rows:
            return _invalid("NSE_INDEX_MEMBERSHIP_SOURCE_EMPTY", "NSE_INDEX_MEMBERSHIP_SOURCE_EMPTY")
        snapshot = self._universe.latest_universe_snapshot()
        if snapshot is None:
            return _source_unavailable("NSE_UNIVERSE_SNAPSHOT_REQUIRED")
        instruments = self._universe.instruments_as_of(snapshot.as_of)
        by_isin: dict[str, tuple[NseEquityInstrument, ...]] = {}
        for instrument in instruments:
            if instrument.isin:
                key = instrument.isin.upper()
                by_isin[key] = (*by_isin.get(key, ()), instrument)
        accepted = duplicates = unresolved = 0
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        current: dict[str, set[str]] = {}
        source_fingerprints: set[str] = set()
        prior_active: dict[str, set[str]] = {}
        historical_memberships = tuple(
            value for value in _all(self._repository, CoreApiSnapshotFamily.HISTORICAL_UNIVERSE_MEMBERSHIP)
            if isinstance(value, UniverseMembership)
        )
        findings.extend(_membership_interval_findings(historical_memberships))
        for value in historical_memberships:
            if value.status is not InstrumentLifecycle.ACTIVE:
                continue
            if value.known_at <= observed and value.effective_from <= observed and (value.effective_to is None or observed <= value.effective_to):
                prior_active.setdefault(value.universe_id, set()).add(value.instrument_id)
        for row in rows:
            source_fingerprints.add(row.source_fingerprint)
            # Membership requires exact canonical identity: an ISIN match and
            # the official current symbol must agree.  No fuzzy/symbol-only
            # fallback is permitted at this boundary.
            candidates = by_isin.get(row.isin, ())
            instrument = candidates[0] if len(candidates) == 1 else None
            if instrument is None or instrument.symbol.upper() != row.symbol:
                unresolved += 1
                findings.append((ReconciliationStatus.GAP_FOUND, f"{row.universe_id}:{row.symbol}", "NSE_MEMBERSHIP_EXACT_IDENTITY_UNRESOLVED"))
                continue
            current.setdefault(row.universe_id, set()).add(instrument.instrument_id)
            # A current-only export is corroboration, not a new historical
            # membership interval, when the same exact active membership is
            # already stored.  This avoids creating overlapping intervals.
            if instrument.instrument_id in prior_active.get(row.universe_id, set()):
                duplicates += 1
                continue
            identifier = "nse-membership:" + sha256(
                f"{row.universe_id}|{instrument.instrument_id}|{row.source_fingerprint}".encode()
            ).hexdigest()[:32]
            value = UniverseMembership(
                identifier, instrument.instrument_id, row.universe_id, observed, None, observed,
                NSE_OFFICIAL, f"{row.source_reference};mapping_method=EXACT_ISIN_AND_SYMBOL", InstrumentLifecycle.ACTIVE,
            )
            existing = self._repository.get_snapshot("historical-membership:" + value.membership_id)
            if existing is not None:
                if existing.payload != value:
                    return _invalid("NSE_MEMBERSHIP_IMMUTABLE_CONFLICT", "NSE_MEMBERSHIP_IMMUTABLE_CONFLICT")
                duplicates += 1
                continue
            self._master.save_membership(value, as_of=observed)
            accepted += 1
        for universe_id, current_ids in current.items():
            prior = prior_active.get(universe_id, set())
            # Do not infer a removal/effective date from a current-only export.
            # These findings keep the family PARTIAL until an approved source
            # supplies the missing interval closure evidence.
            for instrument_id in sorted(prior - current_ids):
                findings.append((ReconciliationStatus.GAP_FOUND, f"{universe_id}:{instrument_id}", "NSE_MEMBERSHIP_REMOVAL_EFFECTIVE_DATE_REQUIRED"))
        gaps = unresolved + sum(reason == "NSE_MEMBERSHIP_REMOVAL_EFFECTIVE_DATE_REQUIRED" for _, _, reason in findings)
        conflicts = sum(status is ReconciliationStatus.CONFLICT_FOUND for status, _, _ in findings)
        status = EvidenceRefreshStatus.PARTIAL if gaps or conflicts else EvidenceRefreshStatus.NO_CHANGE if not accepted else EvidenceRefreshStatus.COMPLETE
        warnings = tuple(sorted(set(
            (("NSE_MEMBERSHIP_EXACT_IDENTITY_UNRESOLVED",) if unresolved else ())
            + (("CURRENT_MEMBERSHIP_ONLY_HISTORICAL_REMOVAL_UNRESOLVED",) if any(reason.endswith("EFFECTIVE_DATE_REQUIRED") for _, _, reason in findings) else ())
            + ("FIRST_OBSERVED_CURRENT_MEMBERSHIP",)
        )))
        return EvidenceRefreshOutcome(
            status, NSE_OFFICIAL, discovered_count=len(rows), accepted_count=accepted,
            duplicate_count=duplicates, conflict_count=conflicts, gap_count=gaps, accepted_through=observed,
            source_fingerprint=sha256("|".join(sorted(source_fingerprints)).encode()).hexdigest(),
            verified_from_store=bool(accepted or duplicates), warnings=warnings,
            source_references=tuple(sorted({item.source_reference for item in rows})), findings=tuple(findings),
        )


class NseTaxonomyReferenceRefreshJob:
    """Run the existing strict NSE Indices importer against the approved archive."""

    def __init__(self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore, source_root: Path) -> None:
        self._repository, self._universe, self._source_root = repository, universe, source_root

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        required = {
            "nifty500.csv", "nifty_total_market.csv", "industry_classification_structure_2023-07.pdf",
            "industry_classification_page.html",
        }
        if any(not (self._source_root / name).is_file() for name in required):
            return _source_unavailable("NSE_TAXONOMY_REFERENCE_EXPORT_REQUIRED")
        snapshot = self._universe.latest_universe_snapshot()
        if snapshot is None:
            return _source_unavailable("NSE_UNIVERSE_SNAPSHOT_REQUIRED")
        paths = tuple(self._source_root / name for name in sorted(required))
        input_hashes = {sha256(path.read_bytes()).hexdigest() for path in paths}
        fingerprint = _paths_fingerprint(paths)
        existing_sources = _all(self._repository, CoreApiSnapshotFamily.NSE_INDICES_TAXONOMY_SOURCE)
        if input_hashes.issubset({getattr(item, "sha256", None) for item in existing_sources}):
            return EvidenceRefreshOutcome(
                EvidenceRefreshStatus.NO_CHANGE, NSE_OFFICIAL, duplicate_count=1,
                accepted_through=request.started_at.astimezone(UTC), source_fingerprint=fingerprint,
                verified_from_store=True, warnings=("NSE_TAXONOMY_SOURCE_ALREADY_INGESTED",),
                source_references=("NSE_INDICES_OFFICIAL_ARCHIVE",),
            )
        try:
            report = NseIndicesTaxonomyImporter(TaxonomySnapshotStore(self._repository), self._repository).import_files(
                nifty500_csv=self._source_root / "nifty500.csv",
                total_market_csv=self._source_root / "nifty_total_market.csv",
                structure_pdf=self._source_root / "industry_classification_structure_2023-07.pdf",
                classification_page=self._source_root / "industry_classification_page.html",
                instruments=self._universe.instruments_as_of(snapshot.as_of),
                fetched_at=request.started_at.astimezone(UTC),
            )
        except (OSError, UnicodeError, ValueError, RuntimeError) as error:
            return _invalid("NSE_TAXONOMY_REFERENCE_INVALID", str(error))
        gaps = report.unmapped_to_canonical_universe + report.exact_ambiguous + report.not_found + report.isin_symbol_conflicts
        status = EvidenceRefreshStatus.PARTIAL if gaps else EvidenceRefreshStatus.COMPLETE
        findings = []
        if report.unmapped_to_canonical_universe:
            findings.append((ReconciliationStatus.GAP_FOUND, "NSE_TAXONOMY", "NSE_TAXONOMY_CANONICAL_IDENTITY_UNRESOLVED"))
        if report.exact_ambiguous or report.isin_symbol_conflicts:
            findings.append((ReconciliationStatus.CONFLICT_FOUND, "NSE_TAXONOMY", "NSE_TAXONOMY_IDENTITY_CONFLICT"))
        if report.not_found:
            findings.append((ReconciliationStatus.GAP_FOUND, "NSE_TAXONOMY", "NSE_TAXONOMY_CLASSIFICATION_UNRESOLVED"))
        return EvidenceRefreshOutcome(
            status, NSE_OFFICIAL, discovered_count=report.valid_rows, accepted_count=report.classifications_saved,
            gap_count=gaps, conflict_count=report.isin_symbol_conflicts + report.exact_ambiguous,
            accepted_through=request.started_at.astimezone(UTC), source_fingerprint=fingerprint,
            verified_from_store=report.classifications_saved > 0,
            warnings=tuple(sorted(set(report.warnings))), source_references=("NSE_INDICES_OFFICIAL_ARCHIVE",), findings=tuple(findings),
        )


class NseCorporateActionsRefreshJob:
    """Ingest only manually staged, approved official NSE corporate-action CSVs."""

    def __init__(self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore, source_directory: Path,
                 master: HistoricalSecurityMasterStore | None = None) -> None:
        self._repository, self._universe, self._source_directory = repository, universe, source_directory
        self._master = master or HistoricalSecurityMasterStore(repository)

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        files = tuple(sorted(self._source_directory.glob("*.csv"), key=lambda item: item.name.casefold())) if self._source_directory.is_dir() else ()
        if not files:
            return _source_unavailable("NSE_CORPORATE_ACTION_EXPORT_REQUIRED")
        snapshot = self._universe.latest_universe_snapshot()
        if snapshot is None:
            return _source_unavailable("NSE_UNIVERSE_SNAPSHOT_REQUIRED")
        importer = NseOfficialCorporateActionCsvImporter(self._master)
        accepted = duplicates = supported = unmatched = ambiguous = non_equity = rejected = 0
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        references: list[str] = []
        for path in files:
            try:
                report = importer.preview(path, instruments=self._universe.instruments_as_of(snapshot.as_of), imported_at=request.started_at.astimezone(UTC))
            except (OSError, UnicodeError, ValueError) as error:
                rejected += 1
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, path.name, str(error) or "NSE_CORPORATE_ACTION_SOURCE_INVALID"))
                continue
            supported += report.supported_rows; unmatched += report.unmatched_rows; ambiguous += report.ambiguous_rows; non_equity += report.skipped_non_equity_rows
            references.append(f"NSE_OFFICIAL_CORPORATE_ACTION_EXPORT:{report.source_checksum}")
            for action in report.actions:
                existing = self._repository.get_snapshot("historical-action:" + action.action_id)
                if existing is not None:
                    # The action id is derived from immutable official source
                    # bytes, line, canonical identity, kind, and ex-date.
                    # Re-reading those exact bytes later must retain the
                    # original first-observed/PIT timestamp rather than
                    # treating receipt time as a source correction.
                    if not _same_official_corporate_action(existing.payload, action):
                        return _invalid("NSE_CORPORATE_ACTION_IMMUTABLE_CONFLICT", "NSE_CORPORATE_ACTION_IMMUTABLE_CONFLICT")
                    duplicates += 1
                    continue
                self._master.save_action(action)
                accepted += 1
            if report.unmatched_rows:
                findings.append((ReconciliationStatus.GAP_FOUND, path.name, "NSE_CORPORATE_ACTION_CANONICAL_IDENTITY_UNRESOLVED"))
            if report.ambiguous_rows:
                findings.append((ReconciliationStatus.CONFLICT_FOUND, path.name, "NSE_CORPORATE_ACTION_CANONICAL_IDENTITY_AMBIGUOUS"))
        gaps = unmatched + rejected
        status = (EvidenceRefreshStatus.INVALID_EVIDENCE if rejected and not accepted and not duplicates
                  else EvidenceRefreshStatus.PARTIAL if gaps or ambiguous
                  else EvidenceRefreshStatus.NO_CHANGE if not accepted else EvidenceRefreshStatus.COMPLETE)
        return EvidenceRefreshOutcome(
            status, NSE_OFFICIAL, discovered_count=len(files), accepted_count=accepted, duplicate_count=duplicates,
            rejected_count=rejected, conflict_count=ambiguous, gap_count=gaps,
            accepted_through=request.started_at.astimezone(UTC),
            source_fingerprint=sha256("|".join(sorted(references)).encode()).hexdigest() if references else None,
            verified_from_store=bool(accepted or duplicates),
            error_summary="NSE_CORPORATE_ACTION_SOURCE_INVALID" if status is EvidenceRefreshStatus.INVALID_EVIDENCE else None,
            warnings=tuple(sorted(set(
                (("NSE_CORPORATE_ACTION_CANONICAL_IDENTITY_UNRESOLVED",) if unmatched else ())
                + (("NSE_CORPORATE_ACTION_CANONICAL_IDENTITY_AMBIGUOUS",) if ambiguous else ())
                + (("NSE_CORPORATE_ACTION_NON_EQUITY_SKIPPED",) if non_equity else ())
            ))), source_references=tuple(sorted(set(references))), findings=tuple(findings),
        )


def _nifty_members(path: Path) -> tuple[_Member, ...]:
    raw = path.read_bytes(); checksum = sha256(raw).hexdigest()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = {(item or "").strip().upper() for item in reader.fieldnames or ()}
        if not _MEMBER_HEADERS.issubset(headers):
            raise ValueError("NSE_NIFTY500_CONSTITUENT_SCHEMA_UNSUPPORTED")
        rows = []
        for row in reader:
            value = {(key or "").strip().upper(): (item or "").strip().upper() for key, item in row.items()}
            if value.get("SERIES") != "EQ":
                continue
            symbol, isin = value.get("SYMBOL", ""), value.get("ISIN CODE", "")
            if symbol and isin:
                rows.append(_Member(NIFTY_500_UNIVERSE_ID, symbol, isin, "EQ", f"NSE_NIFTY500_CONSTITUENTS:sha256={checksum}", checksum))
    if not rows:
        raise ValueError("NSE_NIFTY500_CONSTITUENT_SOURCE_EMPTY")
    return tuple(rows)


def _stored_sector_members(repository: CoreApiSnapshotRepository) -> tuple[_Member, ...]:
    allowed_indices = {
        value.official_index_name
        for value in _all(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING)
        if isinstance(value, NseSectorIndexMapping)
        and value.official_index_name
        and value.status in {
            SectorIndexMappingStatus.EXACT_OFFICIAL,
            SectorIndexMappingStatus.DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS,
        }
    }
    values = []
    for item in _all(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT):
        if (
            not isinstance(item, NseSectorIndexConstituent)
            or item.official_index_name not in allowed_indices
            or item.series.upper() != "EQ"
            or not item.symbol
            or not item.isin
        ):
            continue
        values.append(_Member(item.official_index_name, item.symbol.upper(), item.isin.upper(), "EQ",
                              f"NSE_SECTOR_INDEX_CONSTITUENTS:sha256={item.source_artifact_sha256}", item.source_artifact_sha256))
    return tuple(sorted(values, key=lambda item: (item.universe_id, item.isin, item.symbol)))


def _membership_interval_findings(values: tuple[UniverseMembership, ...]) -> list[tuple[ReconciliationStatus, str, str]]:
    """Surface invalid/overlapping immutable membership intervals; never repair them."""
    findings: list[tuple[ReconciliationStatus, str, str]] = []
    grouped: dict[tuple[str, str], list[UniverseMembership]] = {}
    for value in values:
        subject = f"{value.universe_id}:{value.instrument_id}"
        if value.effective_to is not None and value.effective_to < value.effective_from:
            findings.append((ReconciliationStatus.CONFLICT_FOUND, subject, "NSE_MEMBERSHIP_EFFECTIVE_INTERVAL_INVALID"))
        grouped.setdefault((value.universe_id, value.instrument_id), []).append(value)
    for (universe_id, instrument_id), intervals in grouped.items():
        ordered = sorted(intervals, key=lambda item: (item.effective_from, item.membership_id))
        for prior, current in zip(ordered, ordered[1:]):
            if prior.effective_to is None or current.effective_from <= prior.effective_to:
                findings.append((
                    ReconciliationStatus.CONFLICT_FOUND,
                    f"{universe_id}:{instrument_id}",
                    "NSE_MEMBERSHIP_OVERLAPPING_INTERVAL",
                ))
                break
    return findings


def _paths_fingerprint(paths: Iterable[Path]) -> str:
    return sha256("|".join(sha256(path.read_bytes()).hexdigest() for path in paths).encode()).hexdigest()


def _same_official_corporate_action(existing: object, incoming: object) -> bool:
    """Compare an action's official event semantics across a local rerun.

    ``as_of`` is this system's first-observed timestamp and must remain on the
    original immutable record.  Mapping-method annotations are provenance for
    the canonical resolver, not a correction to the official event.  A later
    resolver improvement can therefore corroborate the same source row without
    fabricating a revised corporate action or overwriting its original record.
    """
    semantic_fields = (
        "action_id", "canonical_instrument_id", "kind", "announcement_date",
        "record_date", "ex_date", "effective_date", "ratio_numerator",
        "ratio_denominator", "source", "revision",
    )
    if any(getattr(existing, field, None) != getattr(incoming, field, None) for field in semantic_fields):
        return False
    return (
        _corporate_action_details_without_mapping(getattr(existing, "details", None))
        == _corporate_action_details_without_mapping(getattr(incoming, "details", None))
        and _corporate_action_reference_without_mapping(getattr(existing, "source_reference", None))
        == _corporate_action_reference_without_mapping(getattr(incoming, "source_reference", None))
        and _corporate_action_warnings_without_mapping(getattr(existing, "warnings", ()))
        == _corporate_action_warnings_without_mapping(getattr(incoming, "warnings", ()))
    )


def _corporate_action_details_without_mapping(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(decoded, dict):
        return decoded
    decoded.pop("mapping_method", None)
    return decoded


def _corporate_action_reference_without_mapping(value: object) -> object:
    return value.split(";mapping_method=", 1)[0] if isinstance(value, str) else value


def _corporate_action_warnings_without_mapping(value: object) -> tuple[object, ...]:
    return tuple(item for item in value if not isinstance(item, str) or not item.startswith("MAPPING_METHOD_"))


def _source_unavailable(code: str) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, NSE_OFFICIAL, error_summary=code, warnings=(code,))


def _invalid(code: str, detail: str) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(EvidenceRefreshStatus.INVALID_EVIDENCE, NSE_OFFICIAL, error_summary=code, warnings=tuple(sorted({code, detail[:160]})))


__all__ = (
    "NIFTY_500_UNIVERSE_ID", "NseCorporateActionsRefreshJob", "NseIndexMembershipRefreshJob",
    "NseTaxonomyReferenceRefreshJob",
)
