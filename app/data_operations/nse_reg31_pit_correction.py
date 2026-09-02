"""Append-only correction of five known NSE Reg31 XBRL PIT timestamps.

This is deliberately a one-purpose remediation, not a generic filing repair
framework.  It preserves the original filing and raw XBRL, appends a corrected
filing revision, and records immutable reconciliation lineage.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from app.filings.models import CorporateFiling, FilingType
from app.filings.store import CorporateFilingsStore, FilingWriteOutcome
from app.historical.guard import manifest_fingerprint
from app.market_data.models import MarketDataProvenance
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


POLICY_ID = "nse-reg31-pit-timestamp-correction"
POLICY_VERSION = "v1"
CORRECTION_REASON = "NSE_NAIVE_PUBLICATION_TIMESTAMP_INTERPRETED_AS_UTC"
TIMEZONE_INTERPRETATION = "Asia/Kolkata"
_CORRECTION_WARNING = "NSE_REG31_PIT_TIMESTAMP_CORRECTED_V1:"


@dataclass(frozen=True, slots=True)
class _Target:
    canonical_instrument_id: str
    filing_id: str
    raw_sha256: str
    reporting_period_end: str
    artifact_filename: str


TARGETS = (
    _Target("NSE:INE372A01015", "nse:NSE:reg31-xbrl:213063", "52546ef73e634451d55681d333f656f9ad16dcd56a1d44a4b6e4fed652304f1b", "2026-08-13", "SHP-Reg31-equities-APARINDS-2026-08-13-213063.xml"),
    _Target("NSE:INE0FHS01024", "nse:NSE:reg31-xbrl:211379", "6e9df650d623c158fd2289085937d8e9263754cb5da51fa3d57af649ce6c908a", "2026-06-30", "SHP-Reg31-equities-DEEPINDS-2026-06-30-211379.xml"),
    _Target("NSE:INE955D01029", "nse:NSE:reg31-xbrl:211611", "ce7d1f82aba7074df5659cfd7d6a721b4f9044fb14eeeb0a43d7d0ac598c0a1d", "2026-06-30", "SHP-Reg31-equities-GENUSPOWER-2026-06-30-211611.xml"),
    _Target("NSE:INE068V01023", "nse:NSE:reg31-xbrl:212361", "4bf5a51f6aba23ea5a30e8092ab2b8e5226858fbcd069573b9e17324a3953c15", "2026-06-30", "SHP-Reg31-equities-GLAND-2026-06-30-212361.xml"),
    _Target("NSE:INE090A01021", "nse:NSE:reg31-xbrl:211654", "1f4be8c6d2cbc1676d29a727051f42c9031e158abb649f5969056c01a25bec61", "2026-06-30", "SHP-Reg31-equities-ICICIBANK-2026-06-30-211654.xml"),
)


@dataclass(frozen=True, slots=True)
class NseReg31PitTimestampCorrection:
    correction_id: str
    target_filing_id: str
    corrected_filing_id: str
    canonical_instrument_id: str
    raw_sha256: str
    original_manifest_filename: str
    original_manifest_sha256: str
    corrected_manifest_filename: str
    original_source_timestamp_text: str
    timezone_interpretation: str
    erroneous_published_at: datetime
    corrected_published_at: datetime
    reporting_period_end: datetime
    correction_reason: str
    policy_id: str
    policy_version: str
    created_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.correction_id, self.target_filing_id, self.corrected_filing_id, self.canonical_instrument_id, self.raw_sha256, self.original_manifest_filename, self.original_manifest_sha256, self.corrected_manifest_filename, self.original_source_timestamp_text, self.correction_reason, self.policy_id, self.policy_version, self.fingerprint)):
            raise ValueError("NSE Reg31 PIT correction identity is incomplete.")
        if self.timezone_interpretation != TIMEZONE_INTERPRETATION or len(self.raw_sha256) != 64 or len(self.original_manifest_sha256) != 64:
            raise ValueError("NSE Reg31 PIT correction provenance is invalid.")
        if any(value.tzinfo is None or value.utcoffset() is None for value in (self.erroneous_published_at, self.corrected_published_at, self.reporting_period_end, self.created_at)):
            raise ValueError("NSE Reg31 PIT correction timestamps must be timezone-aware.")
        if self.corrected_published_at >= self.erroneous_published_at:
            raise ValueError("NSE Reg31 PIT correction must move publication earlier.")
        if self.fingerprint != correction_fingerprint(self):
            raise ValueError("NSE Reg31 PIT correction fingerprint is invalid.")


@dataclass(frozen=True, slots=True)
class NseReg31PitCorrectionOutcome:
    canonical_instrument_id: str
    correction_id: str
    corrected_filing_id: str
    status: str


def correction_fingerprint(value: NseReg31PitTimestampCorrection) -> str:
    return _correction_fingerprint(
        value.target_filing_id, value.canonical_instrument_id, value.raw_sha256,
        value.original_manifest_filename, value.original_manifest_sha256,
        value.corrected_manifest_filename, value.original_source_timestamp_text,
        value.timezone_interpretation, value.erroneous_published_at, value.corrected_published_at,
        value.reporting_period_end, value.correction_reason, value.policy_id, value.policy_version,
    )


class NseReg31PitTimestampCorrectionStore:
    """Stores this correction lineage in existing immutable reconciliation snapshots."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def get(self, correction_id: str) -> NseReg31PitTimestampCorrection | None:
        snapshot = self._repository.get_snapshot(correction_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, NseReg31PitTimestampCorrection) else None

    def save(self, value: NseReg31PitTimestampCorrection) -> bool:
        existing = self.get(value.correction_id)
        if existing is not None:
            if existing.fingerprint == value.fingerprint:
                return False
            raise ValueError("NSE Reg31 PIT corrections are immutable and conflict-free.")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.correction_id, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            "nse-reg31-pit-timestamp-correction-v1", value.fingerprint, value.created_at, value,
        ))
        return True


class NseReg31PitTimestampCorrectionService:
    def __init__(self, *, filings: CorporateFilingsStore, corrections: NseReg31PitTimestampCorrectionStore, source_directory: Path, targets: tuple[_Target, ...] = TARGETS, clock=lambda: datetime.now(UTC)) -> None:
        self._filings, self._corrections, self._source_directory, self._targets, self._clock = filings, corrections, source_directory, targets, clock

    def apply(self) -> tuple[NseReg31PitCorrectionOutcome, ...]:
        if len(self._targets) != 5 or len({target.filing_id for target in self._targets}) != 5:
            raise ValueError("NSE_REG31_PIT_CORRECTION_EXACT_FIVE_REQUIRED")
        planned = tuple(self._plan(target) for target in self._targets)  # validate the exact five before writing one record
        outcomes: list[NseReg31PitCorrectionOutcome] = []
        for correction, original, corrected, manifest in planned:
            existed = self._corrections.get(correction.correction_id)
            if existed is not None:
                if existed.fingerprint != correction.fingerprint or self._filings.get(correction.corrected_filing_id) != corrected:
                    raise ValueError("NSE_REG31_PIT_CORRECTION_CONFLICT")
                outcomes.append(NseReg31PitCorrectionOutcome(correction.canonical_instrument_id, correction.correction_id, correction.corrected_filing_id, "IDENTICAL"))
                continue
            outcome = self._filings.save(corrected)
            if outcome is not FilingWriteOutcome.INSERTED:
                raise ValueError("NSE_REG31_PIT_CORRECTION_CONFLICT")
            self._write_corrected_manifest(correction, manifest)
            self._corrections.save(correction)
            outcomes.append(NseReg31PitCorrectionOutcome(correction.canonical_instrument_id, correction.correction_id, correction.corrected_filing_id, "INSERTED"))
        return tuple(outcomes)

    def _plan(self, target: _Target) -> tuple[NseReg31PitTimestampCorrection, CorporateFiling, CorporateFiling, dict[str, object]]:
        original = self._filings.get(target.filing_id)
        if original is None or original.instrument.instrument_id != target.canonical_instrument_id or original.filing_type is not FilingType.SHAREHOLDING_PATTERN or original.source != "NSE" or original.period_end is None or original.period_end.astimezone(ZoneInfo(TIMEZONE_INTERPRETATION)).date().isoformat() != target.reporting_period_end:
            raise ValueError("NSE_REG31_PIT_CORRECTION_TARGET_NOT_UNIQUE")
        if _warning_hash(original) != target.raw_sha256:
            raise ValueError("NSE_REG31_PIT_CORRECTION_RAW_HASH_MISMATCH")
        source = original.document_reference
        if not isinstance(source, str) or not source.startswith("https://nsearchives.nseindia.com/corporate/xbrl/SHP_"):
            raise ValueError("NSE_REG31_PIT_CORRECTION_OFFICIAL_SOURCE_REQUIRED")
        raw_path = self._source_directory / target.artifact_filename
        manifest_path = raw_path.with_suffix(raw_path.suffix + ".provenance.json")
        try:
            raw = raw_path.read_bytes(); manifest_bytes = manifest_path.read_bytes(); manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("NSE_REG31_PIT_CORRECTION_ARTIFACT_REQUIRED") from error
        if not isinstance(manifest, dict) or sha256(raw).hexdigest() != target.raw_sha256 or manifest.get("sha256") != target.raw_sha256 or manifest.get("source_url") != source:
            raise ValueError("NSE_REG31_PIT_CORRECTION_RAW_HASH_MISMATCH")
        original_text = _reconstruct_original_local_timestamp(original.announced_at)
        corrected_at = _nse_local_timestamp_to_utc(original_text)
        if original.announced_at != _nse_naive_timestamp_as_utc(original_text):
            raise ValueError("NSE_REG31_PIT_CORRECTION_TIMESTAMP_NOT_PRE_FIX")
        corrected_manifest_filename = raw_path.name + ".metadata-correction-v1.json"
        fingerprint = _correction_fingerprint(
            target.filing_id, target.canonical_instrument_id, target.raw_sha256, manifest_path.name,
            sha256(manifest_bytes).hexdigest(), corrected_manifest_filename, original_text,
            TIMEZONE_INTERPRETATION, original.announced_at, corrected_at, original.period_end,
            CORRECTION_REASON, POLICY_ID, POLICY_VERSION,
        )
        correction_id = "nse-reg31-pit-correction:" + fingerprint[:24]
        corrected_id = "nse:NSE:reg31-xbrl-pit-v1:" + fingerprint[:24]
        correction = NseReg31PitTimestampCorrection(
            correction_id, target.filing_id, corrected_id, target.canonical_instrument_id, target.raw_sha256,
            manifest_path.name, sha256(manifest_bytes).hexdigest(), corrected_manifest_filename, original_text,
            TIMEZONE_INTERPRETATION, original.announced_at, corrected_at, original.period_end,
            CORRECTION_REASON, POLICY_ID, POLICY_VERSION, self._clock().astimezone(UTC), fingerprint,
        )
        corrected = replace(
            original, filing_id=corrected_id, announced_at=corrected_at, received_at=corrected_at,
            revision_of_filing_id=original.filing_id,
            provenance=MarketDataProvenance("NSE", original.provenance.provider_instrument_reference, corrected_at, corrected_at, original.provenance.received_at, "nse-reg31-pit-correction-v1", correction_id, original.document_reference),
            normalization_version="nse-reg31-pit-correction-v1",
            warnings=(*original.warnings, _CORRECTION_WARNING + correction_id, "NSE_REG31_ORIGINAL_HSI_RECEIVED_AT:" + original.received_at.isoformat()),
        )
        return correction, original, corrected, manifest

    def _write_corrected_manifest(self, correction: NseReg31PitTimestampCorrection, original_manifest: dict[str, object]) -> None:
        path = self._source_directory / correction.corrected_manifest_filename
        payload = {
            "correction_id": correction.correction_id, "correction_reason": correction.correction_reason,
            "corrected_published_at": correction.corrected_published_at.isoformat(),
            "created_at": correction.created_at.isoformat(), "original_manifest_filename": correction.original_manifest_filename,
            "original_manifest_sha256": correction.original_manifest_sha256,
            "original_source_timestamp_text": correction.original_source_timestamp_text,
            "policy": f"{correction.policy_id} / {correction.policy_version}", "raw_sha256": correction.raw_sha256,
            "source_timezone_interpretation": correction.timezone_interpretation,
            "supersedes_filing_id": correction.target_filing_id, "corrected_filing_id": correction.corrected_filing_id,
            "previous_erroneous_published_at": correction.erroneous_published_at.isoformat(),
            "source_url": original_manifest.get("source_url"), "fingerprint": correction.fingerprint,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8") + b"\n"
        if path.exists():
            if path.read_bytes() != encoded:
                raise ValueError("NSE_REG31_PIT_CORRECTED_MANIFEST_CONFLICT")
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_bytes(encoded); temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()


def is_pit_timestamp_correction(value: CorporateFiling) -> bool:
    return any(item.startswith(_CORRECTION_WARNING) for item in value.warnings)


def _warning_hash(value: CorporateFiling) -> str | None:
    prefix = "NSE_REG31_ARTIFACT_SHA256:"
    return next((item[len(prefix):] for item in value.warnings if item.startswith(prefix)), None)


def _reconstruct_original_local_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%d-%b-%Y %H:%M:%S").upper()


def _nse_naive_timestamp_as_utc(value: str) -> datetime:
    return datetime.strptime(value, "%d-%b-%Y %H:%M:%S").replace(tzinfo=UTC)


def _nse_local_timestamp_to_utc(value: str) -> datetime:
    return datetime.strptime(value, "%d-%b-%Y %H:%M:%S").replace(tzinfo=ZoneInfo(TIMEZONE_INTERPRETATION)).astimezone(UTC)


def _correction_fingerprint(target_filing_id: str, canonical_instrument_id: str, raw_sha256: str, original_manifest_filename: str, original_manifest_sha256: str, corrected_manifest_filename: str, original_source_timestamp_text: str, timezone: str, erroneous: datetime, corrected: datetime, period: datetime, reason: str, policy_id: str, policy_version: str) -> str:
    return manifest_fingerprint(
        target_filing_id=target_filing_id, canonical_instrument_id=canonical_instrument_id, raw_sha256=raw_sha256,
        original_manifest_filename=original_manifest_filename, original_manifest_sha256=original_manifest_sha256,
        corrected_manifest_filename=corrected_manifest_filename, original_source_timestamp_text=original_source_timestamp_text,
        timezone=timezone, erroneous=erroneous, corrected=corrected, period=period, reason=reason,
        policy=(policy_id, policy_version),
    )


__all__ = (
    "NseReg31PitCorrectionOutcome", "NseReg31PitTimestampCorrection", "NseReg31PitTimestampCorrectionService",
    "NseReg31PitTimestampCorrectionStore", "POLICY_ID", "POLICY_VERSION", "TARGETS", "correction_fingerprint", "is_pit_timestamp_correction",
)
