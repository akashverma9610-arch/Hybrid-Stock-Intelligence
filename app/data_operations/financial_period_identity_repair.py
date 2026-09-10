"""Append-only, source-proven repair projection for legacy financial periods.

This is intentionally a narrow remediation for facts whose legacy BSE staged
ingestion retained a document-level duration in place of the XBRL context
duration.  It never changes a stored ``FinancialFact``.  Instead, it records
the exact retained-source proof in the existing immutable reconciliation
family and produces a comparability-only in-memory projection after the
repair itself became known.

No duration arithmetic determines a repaired period type.  Duration is used
only to locate a structurally suspect legacy fact; an explicit XBRL context
must then prove the replacement identity.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable, Protocol

from app.filings.models import CorporateFiling, FilingType
from app.filings.store import CorporateFilingsStore
from app.fundamentals.bse_official import BSE_OFFICIAL_PROVIDER, parse_bse_xbrl
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
    NumericScale,
    StatementScope,
)
from app.fundamentals.store import FinancialFactStore
from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


POLICY_ID = "canonical-financial-period-identity-repair"
POLICY_VERSION = "v1"
RECORD_TYPE = "canonical-financial-period-identity-repair-v1"
AUDIT_RECORD_TYPE = "canonical-financial-period-identity-repair-audit-v1"
CONFLICT_RECORD_TYPE = "canonical-financial-period-identity-repair-conflict-v1"
PROJECTION_PROVENANCE_PREFIX = "CANONICAL_FINANCIAL_PERIOD_IDENTITY_REPAIR:"
PIT_STATUS = "SOURCE_XBRL_EXPLICIT_RECONSTRUCTED_NO_STRICT_HISTORICAL_BACKPROJECTION"


class PeriodIdentityRepairDisposition(StrEnum):
    READY_CORRECTION = "READY_CORRECTION"
    ALREADY_CORRECT = "ALREADY_CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    SOURCE_EVIDENCE_INSUFFICIENT = "SOURCE_EVIDENCE_INSUFFICIENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PeriodIdentityRepairWriteStatus(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"
    CONFLICTED = "CONFLICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityCorrection:
    """Immutable correction proof; the original canonical fact remains intact."""

    correction_id: str
    target_fact_id: str
    canonical_instrument_id: str
    source_filing_id: str
    source_document_reference: str
    source_artifact_filename: str
    source_artifact_sha256: str
    source_context_ids: tuple[str, ...]
    metric: FinancialMetric
    value: Decimal
    currency: str
    unit: str
    scale: NumericScale
    statement_scope: StatementScope
    fiscal_year: int | None
    fiscal_quarter: int | None
    original_period_type: FinancialPeriodType
    original_value_basis: FinancialValueBasis
    original_period_start: datetime | None
    original_period_end: datetime
    corrected_period_type: FinancialPeriodType
    corrected_value_basis: FinancialValueBasis
    corrected_period_start: datetime | None
    corrected_period_end: datetime
    source_semantics_status: str
    projection_known_at: datetime
    policy_id: str
    policy_version: str
    source_evidence_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        required = (
            self.correction_id, self.target_fact_id, self.canonical_instrument_id,
            self.source_filing_id, self.source_document_reference,
            self.source_artifact_filename, self.source_artifact_sha256,
            self.source_context_ids, self.currency, self.unit,
            self.source_semantics_status, self.policy_id, self.policy_version,
            self.source_evidence_fingerprint, self.fingerprint,
        )
        if any(not value for value in required):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_IDENTITY_INCOMPLETE")
        if self.policy_id != POLICY_ID or self.policy_version != POLICY_VERSION:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_POLICY_MISMATCH")
        if self.source_semantics_status != PIT_STATUS:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_PIT_STATUS_INVALID")
        if len(self.source_artifact_sha256) != 64 or any(
            item != item.strip() or not item for item in self.source_context_ids
        ):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_SOURCE_INVALID")
        if self.source_context_ids != tuple(sorted(set(self.source_context_ids))):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_CONTEXTS_NONCANONICAL")
        _require_aware(self.original_period_end, "ORIGINAL_PERIOD_END")
        _require_aware(self.corrected_period_end, "CORRECTED_PERIOD_END")
        _require_aware(self.projection_known_at, "PROJECTION_KNOWN_AT")
        if self.original_period_start is not None:
            _require_aware(self.original_period_start, "ORIGINAL_PERIOD_START")
        if self.corrected_period_start is not None:
            _require_aware(self.corrected_period_start, "CORRECTED_PERIOD_START")
        if self.original_period_end != self.corrected_period_end:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_PERIOD_END_MUTATION")
        if (
            self.original_period_type is self.corrected_period_type
            and self.original_value_basis is self.corrected_value_basis
            and self.original_period_start == self.corrected_period_start
        ):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_NO_CHANGE")
        if self.fingerprint != financial_period_identity_correction_fingerprint(self):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityAuditObservation:
    """A deterministic, source-level audit row for one suspect stored fact."""

    fact_id: str
    canonical_instrument_id: str
    symbol: str
    filing_id: str | None
    metric: FinancialMetric
    statement_scope: StatementScope
    fiscal_year: int | None
    fiscal_quarter: int | None
    stored_period_type: FinancialPeriodType
    stored_value_basis: FinancialValueBasis
    stored_period_start: datetime | None
    stored_period_end: datetime
    disposition: PeriodIdentityRepairDisposition
    reason: str
    source_artifact_filename: str | None
    source_artifact_sha256: str | None
    source_context_ids: tuple[str, ...]
    source_period_type: FinancialPeriodType | None
    source_value_basis: FinancialValueBasis | None
    source_period_start: datetime | None
    source_period_end: datetime | None
    correction_id: str | None
    source_evidence_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.fact_id, self.canonical_instrument_id, self.symbol, self.reason, self.fingerprint)):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_OBSERVATION_IDENTITY_INCOMPLETE")
        _require_aware(self.stored_period_end, "STORED_PERIOD_END")
        for value in (self.stored_period_start, self.source_period_start, self.source_period_end):
            if value is not None:
                _require_aware(value, "PERIOD_BOUNDARY")
        if self.source_context_ids != tuple(sorted(set(self.source_context_ids))):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_CONTEXTS_NONCANONICAL")
        artifact_values = (self.source_artifact_filename, self.source_artifact_sha256)
        if any(value is not None for value in artifact_values) and any(value is None for value in artifact_values):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_SOURCE_ARTIFACT_PARTIAL")
        source_values = (
            self.source_period_type, self.source_value_basis,
            self.source_period_end, self.source_evidence_fingerprint,
        )
        if any(value is not None for value in source_values) and any(value is None for value in source_values):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_SOURCE_SEMANTICS_PARTIAL")
        if self.disposition is PeriodIdentityRepairDisposition.READY_CORRECTION:
            if not self.correction_id or not all(value is not None for value in source_values):
                raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_READY_PROOF_REQUIRED")
        elif self.correction_id is not None:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_UNEXPECTED_CORRECTION")
        if self.fingerprint != financial_period_identity_audit_observation_fingerprint(self):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_OBSERVATION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityRepairAudit:
    """Repository-equivalent machine-readable audit artifact, stored immutably."""

    audit_id: str
    canonical_instrument_ids: tuple[str, ...]
    observations: tuple[FinancialPeriodIdentityAuditObservation, ...]
    created_at: datetime
    policy_id: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.audit_id or not self.canonical_instrument_ids or not self.fingerprint:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_IDENTITY_INCOMPLETE")
        if self.canonical_instrument_ids != tuple(sorted(set(self.canonical_instrument_ids))):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_INSTRUMENTS_NONCANONICAL")
        if tuple(item.fact_id for item in self.observations) != tuple(sorted(item.fact_id for item in self.observations)):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_OBSERVATIONS_NONCANONICAL")
        if len({item.fact_id for item in self.observations}) != len(self.observations):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_FACT_DUPLICATE")
        _require_aware(self.created_at, "AUDIT_CREATED_AT")
        if self.policy_id != POLICY_ID or self.policy_version != POLICY_VERSION:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_POLICY_MISMATCH")
        if self.fingerprint != financial_period_identity_audit_fingerprint(self):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_FINGERPRINT_MISMATCH")

    @property
    def disposition_counts(self) -> tuple[tuple[PeriodIdentityRepairDisposition, int], ...]:
        return tuple(
            (disposition, sum(item.disposition is disposition for item in self.observations))
            for disposition in PeriodIdentityRepairDisposition
            if any(item.disposition is disposition for item in self.observations)
        )


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityRepairConflict:
    """Append-only evidence that a later proof disagreed with an existing repair."""

    conflict_id: str
    target_fact_id: str
    existing_correction_ids: tuple[str, ...]
    incoming_correction_id: str
    incoming_fingerprint: str
    created_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.conflict_id, self.target_fact_id, self.existing_correction_ids,
                    self.incoming_correction_id, self.incoming_fingerprint, self.fingerprint)):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CONFLICT_IDENTITY_INCOMPLETE")
        if self.existing_correction_ids != tuple(sorted(set(self.existing_correction_ids))):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CONFLICT_IDS_NONCANONICAL")
        _require_aware(self.created_at, "CONFLICT_CREATED_AT")
        if self.fingerprint != financial_period_identity_conflict_fingerprint(self):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CONFLICT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityRepairOutcome:
    fact_id: str
    correction_id: str | None
    status: PeriodIdentityRepairWriteStatus


@dataclass(frozen=True, slots=True)
class FinancialPeriodIdentityRepairRun:
    audit: FinancialPeriodIdentityRepairAudit
    audit_written: bool
    outcomes: tuple[FinancialPeriodIdentityRepairOutcome, ...]

    @property
    def new_corrections(self) -> int:
        return sum(item.status is PeriodIdentityRepairWriteStatus.INSERTED for item in self.outcomes)

    @property
    def existing_corrections(self) -> int:
        return sum(item.status is PeriodIdentityRepairWriteStatus.IDENTICAL for item in self.outcomes)


class FinancialPeriodIdentityCorrectionStore:
    """Small immutable store over the pre-existing reconciliation family."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def get(self, correction_id: str) -> FinancialPeriodIdentityCorrection | None:
        snapshot = self._repository.get_snapshot(correction_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, FinancialPeriodIdentityCorrection) else None

    def corrections(self) -> tuple[FinancialPeriodIdentityCorrection, ...]:
        return tuple(sorted(
            (snapshot.payload for snapshot in _all_reconciliation_snapshots(self._repository)
             if snapshot.record_type == RECORD_TYPE and isinstance(snapshot.payload, FinancialPeriodIdentityCorrection)),
            key=lambda item: item.correction_id,
        ))

    def corrections_for_fact(self, fact_id: str) -> tuple[FinancialPeriodIdentityCorrection, ...]:
        return tuple(item for item in self.corrections() if item.target_fact_id == fact_id)

    def save(self, value: FinancialPeriodIdentityCorrection) -> bool:
        existing = self.get(value.correction_id)
        if existing is not None:
            if existing.fingerprint == value.fingerprint:
                return False
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_IMMUTABLE_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.correction_id, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            RECORD_TYPE, value.fingerprint, value.projection_known_at, value,
        ))
        return True

    def save_audit(self, value: FinancialPeriodIdentityRepairAudit) -> bool:
        existing = self.get_audit(value.audit_id)
        if existing is not None:
            if existing.fingerprint == value.fingerprint:
                return False
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_IMMUTABLE_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.audit_id, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            AUDIT_RECORD_TYPE, value.fingerprint, value.created_at, value,
        ))
        return True

    def get_audit(self, audit_id: str) -> FinancialPeriodIdentityRepairAudit | None:
        snapshot = self._repository.get_snapshot(audit_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, FinancialPeriodIdentityRepairAudit) else None

    def save_conflict(self, value: FinancialPeriodIdentityRepairConflict) -> bool:
        existing = self._repository.get_snapshot(value.conflict_id)
        if existing is not None:
            if isinstance(existing.payload, FinancialPeriodIdentityRepairConflict) and existing.payload.fingerprint == value.fingerprint:
                return False
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CONFLICT_IMMUTABLE_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.conflict_id, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            CONFLICT_RECORD_TYPE, value.fingerprint, value.created_at, value,
        ))
        return True


class FinancialPeriodIdentityProjection:
    """Apply only PIT-eligible immutable corrections to a diagnostic input tuple."""

    def __init__(self, corrections: FinancialPeriodIdentityCorrectionStore) -> None:
        self._corrections = corrections
        self._corrections_by_fact: dict[str, FinancialPeriodIdentityCorrection] | None = None

    def project(self, facts: tuple[FinancialFact, ...], *, as_of: datetime) -> tuple[FinancialFact, ...]:
        _require_aware(as_of, "PROJECTION_AS_OF")
        by_fact_id = {item.fact_id: item for item in facts}
        if len(by_fact_id) != len(facts):
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_PROJECTION_DUPLICATE_FACT")
        corrections_by_fact = self._corrections_by_fact
        if corrections_by_fact is None:
            corrections_by_fact = {}
            for correction in self._corrections.corrections():
                existing = corrections_by_fact.get(correction.target_fact_id)
                if existing is not None and existing != correction:
                    raise ValueError("FINANCIAL_PERIOD_IDENTITY_PROJECTION_CONFLICTED")
                corrections_by_fact[correction.target_fact_id] = correction
            self._corrections_by_fact = corrections_by_fact
        values: list[FinancialFact] = []
        for fact in facts:
            correction = corrections_by_fact.get(fact.fact_id)
            if correction is None:
                values.append(fact)
                continue
            if correction.projection_known_at > as_of.astimezone(UTC):
                values.append(fact)
                continue
            _validate_projection_source(fact, correction)
            values.append(replace(
                fact,
                period_type=correction.corrected_period_type,
                value_basis=correction.corrected_value_basis,
                period_start=correction.corrected_period_start,
                period_end=correction.corrected_period_end,
                provenance=tuple(sorted(set((*fact.provenance, PROJECTION_PROVENANCE_PREFIX + correction.correction_id))),),
            ))
        return tuple(values)


class FinancialPeriodIdentityRepairService:
    """Audit, prove, and append source-backed period corrections without fetching."""

    def __init__(
        self,
        *,
        facts: FinancialFactStore,
        filings: CorporateFilingsStore,
        corrections: FinancialPeriodIdentityCorrectionStore,
        source_directory: Path,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._facts = facts
        self._filings = filings
        self._corrections = corrections
        self._source_directory = source_directory
        self._clock = clock

    def audit_and_apply(self, instrument_ids: Iterable[str]) -> FinancialPeriodIdentityRepairRun:
        ids = tuple(sorted(set(instrument_ids)))
        if not ids:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_REPAIR_POPULATION_REQUIRED")
        created_at = _utc(self._clock())
        raw_by_checksum = _raw_artifacts(self._source_directory)
        observations = tuple(sorted(
            (self._inspect(fact, raw_by_checksum, created_at)
             for instrument_id in ids
             for fact in self._facts.facts(instrument_id, limit=500)
             if _structurally_suspect(fact)),
            key=lambda item: item.fact_id,
        ))
        audit_values = dict(
            canonical_instrument_ids=ids,
            observations=observations,
            created_at=created_at,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
        )
        fingerprint = _audit_fingerprint_values(audit_values)
        proposed_audit = FinancialPeriodIdentityRepairAudit(
            audit_id="canonical-financial-period-identity-repair-audit:" + fingerprint[:24],
            **audit_values,
            fingerprint=fingerprint,
        )
        existing_audit = self._corrections.get_audit(proposed_audit.audit_id)
        if existing_audit is not None and existing_audit.fingerprint != proposed_audit.fingerprint:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_AUDIT_IMMUTABLE_CONFLICT")
        audit = existing_audit or proposed_audit
        audit_written = existing_audit is None and self._corrections.save_audit(audit)
        outcomes: list[FinancialPeriodIdentityRepairOutcome] = []
        for observation in observations:
            if observation.disposition is not PeriodIdentityRepairDisposition.READY_CORRECTION:
                outcomes.append(FinancialPeriodIdentityRepairOutcome(
                    observation.fact_id, observation.correction_id, PeriodIdentityRepairWriteStatus.NOT_APPLICABLE,
                ))
                continue
            correction = self._correction_from_observation(observation, created_at)
            existing = self._corrections.corrections_for_fact(correction.target_fact_id)
            if existing and (len(existing) != 1 or existing[0].fingerprint != correction.fingerprint):
                conflict = _conflict_for(existing, correction, created_at)
                self._corrections.save_conflict(conflict)
                outcomes.append(FinancialPeriodIdentityRepairOutcome(
                    correction.target_fact_id, correction.correction_id, PeriodIdentityRepairWriteStatus.CONFLICTED,
                ))
                continue
            outcomes.append(FinancialPeriodIdentityRepairOutcome(
                correction.target_fact_id,
                correction.correction_id,
                PeriodIdentityRepairWriteStatus.INSERTED if self._corrections.save(correction)
                else PeriodIdentityRepairWriteStatus.IDENTICAL,
            ))
        return FinancialPeriodIdentityRepairRun(audit, audit_written, tuple(outcomes))

    def _inspect(
        self,
        fact: FinancialFact,
        raw_by_checksum: dict[str, Path],
        projection_known_at: datetime,
    ) -> FinancialPeriodIdentityAuditObservation:
        filing = self._filings.get(fact.filing_id) if fact.filing_id else None
        if not _filing_matches_fact(filing, fact):
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "EXACT_FINANCIAL_FILING_REQUIRED")
        assert filing is not None
        raw_paths = tuple(sorted(
            (raw_by_checksum[item.checksum] for item in filing.attachments
             if item.checksum and item.checksum in raw_by_checksum),
            key=lambda item: item.name,
        ))
        if len(raw_paths) != 1:
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "RETAINED_RAW_XBRL_UNIQUE_ATTACHMENT_REQUIRED")
        raw_path = raw_paths[0]
        raw_bytes = raw_path.read_bytes()
        raw_sha256 = sha256(raw_bytes).hexdigest()
        try:
            document = parse_bse_xbrl(
                raw_bytes.decode("utf-8"), filing.document_reference or filing.source_reference or raw_path.name,
                period_end=fact.period_end,
            )
        except (UnicodeDecodeError, ValueError):
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "RETAINED_RAW_XBRL_PARSE_REQUIRED", source_artifact_filename=raw_path.name,
                source_artifact_sha256=raw_sha256)
        if document.checksum != raw_sha256 or document.scope is not fact.statement_scope:
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "RETAINED_RAW_XBRL_IDENTITY_OR_SCOPE_MISMATCH", source_artifact_filename=raw_path.name,
                source_artifact_sha256=raw_sha256)
        if (fact.fiscal_year, fact.fiscal_quarter) != _bse_fiscal_identity(fact.period_end):
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "EXACT_BSE_FISCAL_IDENTITY_REQUIRED", source_artifact_filename=raw_path.name,
                source_artifact_sha256=raw_sha256)
        matches = tuple(item for item in document.context_facts if (
            item.metric is fact.metric and item.value == fact.value and item.context.period_end == fact.period_end
        ))
        semantic_values = tuple(sorted({
            (item.context.period_start, item.context.period_end, item.period_type, item.value_basis)
            for item in matches
        }, key=lambda item: (_time_key(item[0]), _time_key(item[1]), item[2].value, item[3].value)))
        if not semantic_values:
            return _audit_observation(fact, PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT,
                "EXACT_XBRL_CONTEXT_VALUE_MATCH_REQUIRED", source_artifact_filename=raw_path.name,
                source_artifact_sha256=raw_sha256)
        if len(semantic_values) != 1:
            return _audit_observation(fact, PeriodIdentityRepairDisposition.AMBIGUOUS,
                "MULTIPLE_XBRL_CONTEXT_SEMANTICS", source_artifact_filename=raw_path.name,
                source_artifact_sha256=raw_sha256)
        start, end, period_type, value_basis = semantic_values[0]
        matching_context_ids = tuple(sorted({
            item.context.context_id for item in matches
            if (item.context.period_start, item.context.period_end, item.period_type, item.value_basis) == semantic_values[0]
        }))
        evidence_values = dict(
            target_fact_id=fact.fact_id,
            source_filing_id=filing.filing_id,
            source_artifact_sha256=raw_sha256,
            source_document_reference=filing.document_reference or filing.source_reference or raw_path.name,
            metric=fact.metric.value,
            value=str(fact.value),
            scope=fact.statement_scope.value,
            contexts=matching_context_ids,
            period_start=start,
            period_end=end,
            period_type=period_type.value,
            value_basis=value_basis.value,
        )
        evidence_fingerprint = "sha256:" + content_fingerprint(evidence_values).removeprefix("sha256:")
        if (
            fact.period_start == start and fact.period_end == end
            and fact.period_type is period_type and fact.value_basis is value_basis
        ):
            return _audit_observation(
                fact, PeriodIdentityRepairDisposition.ALREADY_CORRECT, "EXPLICIT_XBRL_CONTEXT_CONFIRMED",
                source_artifact_filename=raw_path.name, source_artifact_sha256=raw_sha256, source_context_ids=matching_context_ids,
                source_period_type=period_type, source_value_basis=value_basis,
                source_period_start=start, source_period_end=end,
                source_evidence_fingerprint=evidence_fingerprint,
            )
        correction_values = dict(
            target_fact_id=fact.fact_id,
            canonical_instrument_id=fact.instrument.instrument_id,
            source_filing_id=filing.filing_id,
            source_document_reference=filing.document_reference or filing.source_reference or raw_path.name,
            source_artifact_filename=raw_path.name,
            source_artifact_sha256=raw_sha256,
            source_context_ids=matching_context_ids,
            metric=fact.metric,
            value=fact.value,
            currency=fact.currency,
            unit=fact.unit,
            scale=fact.scale,
            statement_scope=fact.statement_scope,
            fiscal_year=fact.fiscal_year,
            fiscal_quarter=fact.fiscal_quarter,
            original_period_type=fact.period_type,
            original_value_basis=fact.value_basis,
            original_period_start=fact.period_start,
            original_period_end=fact.period_end,
            corrected_period_type=period_type,
            corrected_value_basis=value_basis,
            corrected_period_start=start,
            corrected_period_end=end,
            source_semantics_status=PIT_STATUS,
            projection_known_at=projection_known_at,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            source_evidence_fingerprint=evidence_fingerprint,
        )
        correction_fingerprint = _correction_fingerprint_values(correction_values)
        correction_id = "financial-period-identity-correction:" + correction_fingerprint[:24]
        return _audit_observation(
            fact, PeriodIdentityRepairDisposition.READY_CORRECTION, "EXPLICIT_XBRL_CONTEXT_PROVES_PERIOD_IDENTITY",
            source_artifact_filename=raw_path.name, source_artifact_sha256=raw_sha256, source_context_ids=matching_context_ids,
            source_period_type=period_type, source_value_basis=value_basis,
            source_period_start=start, source_period_end=end,
            correction_id=correction_id, source_evidence_fingerprint=evidence_fingerprint,
        )

    def _correction_from_observation(
        self, observation: FinancialPeriodIdentityAuditObservation, projection_known_at: datetime,
    ) -> FinancialPeriodIdentityCorrection:
        fact = self._facts.get(observation.fact_id)
        if fact is None:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_TARGET_FACT_MISSING")
        if observation.source_period_type is None or observation.source_value_basis is None or observation.source_period_end is None:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_SOURCE_SEMANTICS_MISSING")
        filing = self._filings.get(observation.filing_id) if observation.filing_id else None
        if filing is None or observation.source_artifact_sha256 is None or observation.source_evidence_fingerprint is None:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_CORRECTION_SOURCE_LINEAGE_MISSING")
        values = dict(
            target_fact_id=fact.fact_id,
            canonical_instrument_id=fact.instrument.instrument_id,
            source_filing_id=filing.filing_id,
            source_document_reference=filing.document_reference or filing.source_reference or "RETAINED_XBRL",
            source_artifact_filename=observation.source_artifact_filename or "RETAINED_XBRL",
            source_artifact_sha256=observation.source_artifact_sha256,
            source_context_ids=observation.source_context_ids,
            metric=fact.metric,
            value=fact.value,
            currency=fact.currency,
            unit=fact.unit,
            scale=fact.scale,
            statement_scope=fact.statement_scope,
            fiscal_year=fact.fiscal_year,
            fiscal_quarter=fact.fiscal_quarter,
            original_period_type=fact.period_type,
            original_value_basis=fact.value_basis,
            original_period_start=fact.period_start,
            original_period_end=fact.period_end,
            corrected_period_type=observation.source_period_type,
            corrected_value_basis=observation.source_value_basis,
            corrected_period_start=observation.source_period_start,
            corrected_period_end=observation.source_period_end,
            source_semantics_status=PIT_STATUS,
            projection_known_at=projection_known_at,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            source_evidence_fingerprint=observation.source_evidence_fingerprint,
        )
        fingerprint = _correction_fingerprint_values(values)
        return FinancialPeriodIdentityCorrection(
            correction_id="financial-period-identity-correction:" + fingerprint[:24],
            **values,
            fingerprint=fingerprint,
        )


def financial_period_identity_correction_fingerprint(value: FinancialPeriodIdentityCorrection) -> str:
    return _correction_fingerprint_values({
        field.name: getattr(value, field.name)
        for field in fields(value) if field.name not in {"correction_id", "fingerprint", "projection_known_at"}
    })


def financial_period_identity_audit_observation_fingerprint(value: FinancialPeriodIdentityAuditObservation) -> str:
    return content_fingerprint({field.name: getattr(value, field.name) for field in fields(value) if field.name != "fingerprint"})


def financial_period_identity_audit_fingerprint(value: FinancialPeriodIdentityRepairAudit) -> str:
    return _audit_fingerprint_values({
        field.name: getattr(value, field.name)
        for field in fields(value) if field.name not in {"audit_id", "created_at", "fingerprint"}
    })


def financial_period_identity_conflict_fingerprint(value: FinancialPeriodIdentityRepairConflict) -> str:
    return content_fingerprint({field.name: getattr(value, field.name) for field in fields(value) if field.name not in {"conflict_id", "created_at", "fingerprint"}})


def audit_json(value: FinancialPeriodIdentityRepairAudit) -> str:
    """Stable machine-readable artifact representation (without write side effects)."""
    return canonical_json({field.name: getattr(value, field.name) for field in fields(value)})


def _correction_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**{
        key: _fingerprint_value(value)
        for key, value in sorted(values.items())
        if key not in {"correction_id", "fingerprint", "projection_known_at"}
    })


def _audit_fingerprint_values(values: dict) -> str:
    return content_fingerprint({
        key: _fingerprint_value(value)
        for key, value in sorted(values.items())
        if key not in {"audit_id", "created_at", "fingerprint"}
    })


def _fingerprint_value(value):
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_fingerprint_value(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field.name: _fingerprint_value(getattr(value, field.name)) for field in fields(value)}
    return value


def _all_reconciliation_snapshots(repository: CoreApiSnapshotRepository) -> tuple[CoreApiSnapshot, ...]:
    values: list[CoreApiSnapshot] = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.RECONCILIATION_RESULT, limit=100, offset=offset)
        values.extend(page)
        if len(page) < 100:
            return tuple(values)
        offset += len(page)


def _raw_artifacts(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise ValueError("FINANCIAL_PERIOD_IDENTITY_REPAIR_RETAINED_SOURCE_DIRECTORY_REQUIRED")
    values: dict[str, Path] = {}
    for path in sorted(directory.rglob("*.xml")):
        checksum = sha256(path.read_bytes()).hexdigest()
        if checksum in values:
            raise ValueError("FINANCIAL_PERIOD_IDENTITY_REPAIR_DUPLICATE_RAW_CHECKSUM")
        values[checksum] = path
    return values


def _structurally_suspect(fact: FinancialFact) -> bool:
    if fact.period_type is FinancialPeriodType.POINT_IN_TIME:
        return fact.period_start is not None
    if fact.period_start is None:
        return fact.period_type in {FinancialPeriodType.QUARTERLY, FinancialPeriodType.ANNUAL}
    duration = (fact.period_end.astimezone(UTC).date() - fact.period_start.astimezone(UTC).date()).days + 1
    return (
        fact.period_type is FinancialPeriodType.QUARTERLY
        and fact.value_basis is FinancialValueBasis.QUARTER_ONLY and duration > 100
    ) or (
        fact.period_type is FinancialPeriodType.QUARTERLY
        and fact.value_basis is FinancialValueBasis.YEAR_TO_DATE and duration <= 100
    ) or (
        fact.period_type is FinancialPeriodType.ANNUAL and not 360 <= duration <= 367
    )


def _filing_matches_fact(filing: CorporateFiling | None, fact: FinancialFact) -> bool:
    return bool(
        filing is not None
        and fact.source == BSE_OFFICIAL_PROVIDER == filing.source
        and filing.filing_type is FilingType.FINANCIAL_RESULTS
        and filing.instrument.instrument_id == fact.instrument.instrument_id
        and filing.announced_at == fact.published_at
        and filing.received_at == fact.received_at
    )


def _audit_observation(
    fact: FinancialFact,
    disposition: PeriodIdentityRepairDisposition,
    reason: str,
    *,
    source_artifact_filename: str | None = None,
    source_artifact_sha256: str | None = None,
    source_context_ids: tuple[str, ...] = (),
    source_period_type: FinancialPeriodType | None = None,
    source_value_basis: FinancialValueBasis | None = None,
    source_period_start: datetime | None = None,
    source_period_end: datetime | None = None,
    correction_id: str | None = None,
    source_evidence_fingerprint: str | None = None,
) -> FinancialPeriodIdentityAuditObservation:
    values = dict(
        fact_id=fact.fact_id,
        canonical_instrument_id=fact.instrument.instrument_id,
        symbol=fact.instrument.symbol,
        filing_id=fact.filing_id,
        metric=fact.metric,
        statement_scope=fact.statement_scope,
        fiscal_year=fact.fiscal_year,
        fiscal_quarter=fact.fiscal_quarter,
        stored_period_type=fact.period_type,
        stored_value_basis=fact.value_basis,
        stored_period_start=fact.period_start,
        stored_period_end=fact.period_end,
        disposition=disposition,
        reason=reason,
        source_artifact_filename=source_artifact_filename,
        source_artifact_sha256=source_artifact_sha256,
        source_context_ids=tuple(sorted(set(source_context_ids))),
        source_period_type=source_period_type,
        source_value_basis=source_value_basis,
        source_period_start=source_period_start,
        source_period_end=source_period_end,
        correction_id=correction_id,
        source_evidence_fingerprint=source_evidence_fingerprint,
    )
    return FinancialPeriodIdentityAuditObservation(
        **values,
        fingerprint=content_fingerprint(values),
    )


def _validate_projection_source(fact: FinancialFact, correction: FinancialPeriodIdentityCorrection) -> None:
    if not (
        fact.fact_id == correction.target_fact_id
        and fact.instrument.instrument_id == correction.canonical_instrument_id
        and fact.filing_id == correction.source_filing_id
        and fact.metric is correction.metric
        and fact.value == correction.value
        and fact.currency == correction.currency
        and fact.unit == correction.unit
        and fact.scale is correction.scale
        and fact.statement_scope is correction.statement_scope
        and fact.fiscal_year == correction.fiscal_year
        and fact.fiscal_quarter == correction.fiscal_quarter
        and fact.period_type is correction.original_period_type
        and fact.value_basis is correction.original_value_basis
        and fact.period_start == correction.original_period_start
        and fact.period_end == correction.original_period_end
    ):
        raise ValueError("FINANCIAL_PERIOD_IDENTITY_PROJECTION_SOURCE_TAMPERED")


def _conflict_for(
    existing: tuple[FinancialPeriodIdentityCorrection, ...],
    incoming: FinancialPeriodIdentityCorrection,
    created_at: datetime,
) -> FinancialPeriodIdentityRepairConflict:
    existing_ids = tuple(sorted(item.correction_id for item in existing))
    values = dict(
        target_fact_id=incoming.target_fact_id,
        existing_correction_ids=existing_ids,
        incoming_correction_id=incoming.correction_id,
        incoming_fingerprint=incoming.fingerprint,
    )
    fingerprint = content_fingerprint(values)
    return FinancialPeriodIdentityRepairConflict(
        conflict_id="financial-period-identity-correction-conflict:" + fingerprint.removeprefix("sha256:")[:24],
        **values,
        created_at=created_at,
        fingerprint=fingerprint,
    )


def _utc(value: datetime) -> datetime:
    _require_aware(value, "TIME")
    return value.astimezone(UTC)


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FINANCIAL_PERIOD_IDENTITY_" + field + "_TIMEZONE_REQUIRED")


def _time_key(value: datetime | None) -> str:
    return _utc(value).isoformat() if value is not None else ""


def _bse_fiscal_identity(period_end: datetime) -> tuple[int, int | None]:
    """The existing BSE adapter's April--March fiscal key, repeated exactly."""
    end = _utc(period_end)
    return end.year if end.month == 3 else end.year + 1, {6: 1, 9: 2, 12: 3, 3: 4}.get(end.month)


__all__ = (
    "AUDIT_RECORD_TYPE", "CONFLICT_RECORD_TYPE", "FinancialPeriodIdentityAuditObservation",
    "FinancialPeriodIdentityCorrection", "FinancialPeriodIdentityCorrectionStore",
    "FinancialPeriodIdentityProjection", "FinancialPeriodIdentityRepairAudit",
    "FinancialPeriodIdentityRepairConflict", "PeriodIdentityRepairDisposition",
    "FinancialPeriodIdentityRepairOutcome", "FinancialPeriodIdentityRepairRun",
    "FinancialPeriodIdentityRepairService", "PeriodIdentityRepairWriteStatus",
    "PIT_STATUS", "POLICY_ID", "POLICY_VERSION", "RECORD_TYPE", "audit_json",
    "financial_period_identity_audit_fingerprint", "financial_period_identity_correction_fingerprint",
)
