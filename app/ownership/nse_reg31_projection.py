"""Bounded V1 ownership projection from the five corrected official Reg31 XBRLs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from app.data_operations.nse_reg31_pit_correction import TARGETS, is_pit_timestamp_correction
from app.filings.models import FilingType
from app.filings.store import CorporateFilingsStore
from app.historical.guard import manifest_fingerprint
from app.ownership.models import (
    OwnershipCategory, OwnershipCategoryRelationship, OwnershipEvidenceSufficiency,
    OwnershipNormalizedUnit, OwnershipObservation, OwnershipRawFact,
)
from app.ownership.store import OwnershipObservationStore, OwnershipWriteOutcome


NSE_REG31_OWNERSHIP_PROVIDER = "NSE_OFFICIAL_REG31_XBRL"
NORMALIZATION_RULE_ID = "NSE_REG31_XBRL_PURE_RATIO_TO_PERCENTAGE_POINTS_V1"
PERCENTAGE_CONCEPT = "ShareholdingAsAPercentageOfTotalNumberOfShares"
ENCUMBRANCE_CONCEPT = "EncumberedSharesHeldAsPercentageOfTotalNumberOfShares"
_SUPPORTED_CONCEPTS = frozenset((PERCENTAGE_CONCEPT, ENCUMBRANCE_CONCEPT))
_PERCENTAGE_SCOPE = "EQUITY_SHARE_CAPITAL_TOTAL_NUMBER_OF_SHARES"
_ENCUMBRANCE_SCOPE = "PROMOTER_GROUP_ENCUMBRANCE_TOTAL_NUMBER_OF_SHARES"


@dataclass(frozen=True, slots=True)
class OwnershipMaterializationOutcome:
    canonical_instrument_id: str
    filing_id: str
    reporting_period: datetime
    published_at: datetime
    raw_fact_inserted: int
    raw_fact_identical: int
    observation_inserted: int
    observation_identical: int
    normalized_percentage_count: int
    unsupported_concepts: tuple[str, ...]
    conflict_count: int


@dataclass(frozen=True, slots=True)
class _ProjectionPlan:
    canonical_instrument_id: str
    filing_id: str
    reporting_period: datetime
    published_at: datetime
    raw_facts: tuple[OwnershipRawFact, ...]
    observations: tuple[OwnershipObservation, ...]
    unsupported_concepts: tuple[str, ...]


class NseReg31OwnershipProjectionService:
    """Extract direct top-level Reg31 facts without any provider or thesis logic."""

    def __init__(
        self, *, filings: CorporateFilingsStore, observations: OwnershipObservationStore,
        source_directory: Path, targets=TARGETS, clock=lambda: datetime.now(UTC),
    ) -> None:
        self._filings = filings
        self._observations = observations
        self._source_directory = source_directory
        self._targets = tuple(targets)
        self._clock = clock

    def materialize(self) -> tuple[OwnershipMaterializationOutcome, ...]:
        if len(self._targets) != 5 or len({item.canonical_instrument_id for item in self._targets}) != 5:
            raise ValueError("NSE_REG31_OWNERSHIP_EXACT_FIVE_REQUIRED")
        plans = tuple(self._plan(target) for target in self._targets)  # preflight all targets before writes
        outcomes: list[OwnershipMaterializationOutcome] = []
        for plan in plans:
            raw_inserted = raw_identical = observation_inserted = observation_identical = 0
            for item in plan.raw_facts:
                result = self._observations.save_raw_fact(item)
                raw_inserted += result is OwnershipWriteOutcome.INSERTED
                raw_identical += result is OwnershipWriteOutcome.IDENTICAL
            for item in plan.observations:
                result = self._observations.save_observation(item)
                observation_inserted += result is OwnershipWriteOutcome.INSERTED
                observation_identical += result is OwnershipWriteOutcome.IDENTICAL
            outcomes.append(OwnershipMaterializationOutcome(
                plan.canonical_instrument_id, plan.filing_id, plan.reporting_period, plan.published_at,
                raw_inserted, raw_identical, observation_inserted, observation_identical,
                len(plan.observations), plan.unsupported_concepts, 0,
            ))
        return tuple(outcomes)

    def _plan(self, target) -> _ProjectionPlan:
        cutoff = self._clock().astimezone(UTC)
        candidates = tuple(item for item in self._filings.list(
            instrument_id=target.canonical_instrument_id, filing_type=FilingType.SHAREHOLDING_PATTERN,
            as_of=cutoff, limit=100,
        ) if item.period_end is not None and item.period_end.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() == target.reporting_period_end
                  and _filing_artifact_hash(item) == target.raw_sha256)
        if len(candidates) != 1:
            raise ValueError("NSE_REG31_OWNERSHIP_EFFECTIVE_FILING_NOT_UNIQUE")
        filing = candidates[0]
        if not is_pit_timestamp_correction(filing) or filing.revision_of_filing_id != target.filing_id:
            raise ValueError("NSE_REG31_OWNERSHIP_PIT_CORRECTION_REQUIRED")
        if (filing.source != "NSE" or filing.document_reference is None
                or not filing.document_reference.startswith("https://nsearchives.nseindia.com/corporate/xbrl/SHP_")):
            raise ValueError("NSE_REG31_OWNERSHIP_OFFICIAL_XBRL_REQUIRED")
        raw_path = self._source_directory / target.artifact_filename
        try:
            raw = raw_path.read_bytes()
            root = ET.fromstring(raw)
        except (OSError, ET.ParseError) as error:
            raise ValueError("NSE_REG31_OWNERSHIP_ARTIFACT_REQUIRED") from error
        if sha256(raw).hexdigest() != target.raw_sha256:
            raise ValueError("NSE_REG31_OWNERSHIP_ARTIFACT_HASH_MISMATCH")
        facts: list[OwnershipRawFact] = []
        observations: list[OwnershipObservation] = []
        unsupported: set[str] = set()
        for element in root.iter():
            concept = _local(element.tag)
            context = element.attrib.get("contextRef")
            unit = element.attrib.get("unitRef")
            text = (element.text or "").strip()
            if concept not in _SUPPORTED_CONCEPTS or not context or not unit or not text:
                continue
            # ``ContextI`` is the issuer's explicitly disclosed top-level row.
            # Detail contexts (Context15 etc.) are constituents, not another total.
            if not context.endswith("_ContextI"):
                continue
            try:
                raw_value = Decimal(text)
            except Exception as error:
                raise ValueError("NSE_REG31_OWNERSHIP_NON_NUMERIC_EXPLICIT_VALUE") from error
            scope = _scope(concept)
            raw_fact = _raw_fact(
                canonical_instrument_id=target.canonical_instrument_id, filing_id=filing.filing_id,
                artifact_sha256=target.raw_sha256, reporting_period=filing.period_end,
                published_at=filing.announced_at, received_at=filing.received_at,
                raw_concept=concept, raw_value=raw_value, raw_unit=unit, scope=scope,
                source_context_reference=context, source_reference=filing.document_reference,
            )
            facts.append(raw_fact)
            mapping = _mapping(concept, context)
            if mapping is None:
                unsupported.add(f"{concept}@{context}")
                continue
            category, relationship = mapping
            observation = _observation(raw_fact, category, relationship)
            if observation.normalized_value is None:
                unsupported.add(f"{concept}@{context}:UNIT={unit}")
                continue
            observations.append(observation)
        if not facts:
            raise ValueError("NSE_REG31_OWNERSHIP_EXPLICIT_PERCENTAGE_FACTS_REQUIRED")
        return _ProjectionPlan(
            target.canonical_instrument_id, filing.filing_id, filing.period_end, filing.announced_at,
            tuple(sorted(facts, key=lambda item: item.fact_id)),
            tuple(sorted(observations, key=lambda item: item.observation_id)), tuple(sorted(unsupported)),
        )


def _raw_fact(**values) -> OwnershipRawFact:
    semantic = dict(values)
    fingerprint = manifest_fingerprint(**semantic)
    return OwnershipRawFact(
        fact_id="nse-reg31-ownership-raw:" + fingerprint[:24], fingerprint=fingerprint, **values,
    )


def _observation(
    raw: OwnershipRawFact, category: OwnershipCategory, relationship: OwnershipCategoryRelationship,
) -> OwnershipObservation:
    normalized_value = raw.raw_value * Decimal("100") if raw.raw_unit == "pure" else None
    normalized_unit = OwnershipNormalizedUnit.PERCENTAGE_POINTS if normalized_value is not None else None
    normalization_rule_id = NORMALIZATION_RULE_ID if normalized_value is not None else None
    values = dict(
        raw_fact_id=raw.fact_id, canonical_instrument_id=raw.canonical_instrument_id, filing_id=raw.filing_id,
        category=category, category_relationship=relationship, reporting_period=raw.reporting_period,
        published_at=raw.published_at, received_at=raw.received_at, raw_concept=raw.raw_concept,
        raw_value=raw.raw_value, raw_unit=raw.raw_unit, normalized_value=normalized_value,
        normalized_unit=normalized_unit, normalization_rule_id=normalization_rule_id, scope=raw.scope,
        artifact_sha256=raw.artifact_sha256, source_context_reference=raw.source_context_reference,
        source_reference=raw.source_reference, evidence_sufficiency=OwnershipEvidenceSufficiency.DIRECT_OFFICIAL,
    )
    fingerprint = manifest_fingerprint(**values)
    return OwnershipObservation(
        observation_id="nse-reg31-ownership-observation:" + fingerprint[:24], fingerprint=fingerprint, **values,
    )


def _scope(concept: str) -> str:
    return _PERCENTAGE_SCOPE if concept == PERCENTAGE_CONCEPT else _ENCUMBRANCE_SCOPE


def _mapping(concept: str, context: str) -> tuple[OwnershipCategory, OwnershipCategoryRelationship] | None:
    mappings = {
        (PERCENTAGE_CONCEPT, "ShareholdingOfPromoterAndPromoterGroup_ContextI"):
            (OwnershipCategory.PROMOTER_AND_PROMOTER_GROUP, OwnershipCategoryRelationship.TOTAL),
        (PERCENTAGE_CONCEPT, "PublicShareholding_ContextI"):
            (OwnershipCategory.PUBLIC, OwnershipCategoryRelationship.TOTAL),
        (PERCENTAGE_CONCEPT, "InstitutionsDomestic_ContextI"):
            (OwnershipCategory.DII, OwnershipCategoryRelationship.TOTAL),
        (PERCENTAGE_CONCEPT, "MutualFundsOrUTI_ContextI"):
            (OwnershipCategory.MUTUAL_FUNDS, OwnershipCategoryRelationship.SUBCATEGORY),
        (PERCENTAGE_CONCEPT, "Governments_ContextI"):
            (OwnershipCategory.GOVERNMENT, OwnershipCategoryRelationship.SUBCATEGORY),
        (PERCENTAGE_CONCEPT, "InsuranceCompanies_ContextI"):
            (OwnershipCategory.INSURANCE, OwnershipCategoryRelationship.SUBCATEGORY),
        (PERCENTAGE_CONCEPT, "Banks_ContextI"):
            (OwnershipCategory.BANKS_FINANCIAL_INSTITUTIONS, OwnershipCategoryRelationship.SUBCATEGORY),
        (ENCUMBRANCE_CONCEPT, "ShareholdingOfPromoterAndPromoterGroup_ContextI"):
            (OwnershipCategory.PROMOTER_PLEDGE_OR_ENCUMBRANCE, OwnershipCategoryRelationship.SUBCATEGORY),
    }
    return mappings.get((concept, context))


def _filing_artifact_hash(filing) -> str | None:
    prefix = "NSE_REG31_ARTIFACT_SHA256:"
    return next((item[len(prefix):] for item in filing.warnings if item.startswith(prefix)), None)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


__all__ = (
    "ENCUMBRANCE_CONCEPT", "NORMALIZATION_RULE_ID", "NSE_REG31_OWNERSHIP_PROVIDER",
    "NseReg31OwnershipProjectionService", "OwnershipMaterializationOutcome", "PERCENTAGE_CONCEPT",
)
