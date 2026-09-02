"""Deterministic, one-way projection from canonical intelligence to News evidence."""
from __future__ import annotations

import hashlib
import json

from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.intelligence.external_intelligence import EvidenceVersion, EventType, ExternalEvent
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.news.store import NewsEvidenceStore


EXTERNAL_INTELLIGENCE_NEWS_PROVIDER = "HSI_EXTERNAL_INTELLIGENCE"
EXTERNAL_INTELLIGENCE_NEWS_PROJECTION_VERSION = "hsi-external-intelligence-news-projection/v1"


class ExternalIntelligenceNewsProjector:
    """Projects persisted evidence only; it never fetches sources or invokes Brain flows."""

    def __init__(self, news_store: NewsEvidenceStore) -> None:
        self._news_store = news_store

    def projection_id(self, event: ExternalEvent, evidence: EvidenceVersion) -> str:
        self._validate_lineage(event, evidence)
        encoded = "|".join((event.canonical_event_id, evidence.evidence_version_id, EXTERNAL_INTELLIGENCE_NEWS_PROJECTION_VERSION))
        return "external-intelligence-news:" + hashlib.sha256(encoded.encode()).hexdigest()[:24]

    def project(self, event: ExternalEvent, evidence: EvidenceVersion) -> NewsArticleEvidence:
        self._validate_lineage(event, evidence)
        if evidence.received_at < evidence.published_at:
            raise ValueError("External-intelligence News projection cannot alter a received-at boundary.")
        projection_id = self.projection_id(event, evidence)
        verified = tuple(item for item in evidence.company_exposures if item.verification_status == "VERIFIED" and item.canonical_instrument_id is not None)
        unverified_present = any(item.verification_status != "VERIFIED" for item in evidence.company_exposures)
        warnings = {
            "EXTERNAL_INTELLIGENCE_DERIVED_NEWS_PROJECTION",
            "CANONICAL_EXTERNAL_INTELLIGENCE_RETAINS_FACT_DATA_INTERPRETATION_INFERENCE",
            "INFERENCES_NOT_PROMOTED_TO_NEWS_FACTS",
            f"EXTERNAL_INTELLIGENCE_EVENT_TYPE:{event.event_type.value}",
            f"EXTERNAL_INTELLIGENCE_MATERIALITY:{event.materiality.value}",
        }
        if event.policy_stage is not None:
            warnings.add(f"EXTERNAL_INTELLIGENCE_POLICY_STAGE:{event.policy_stage.value}")
        if unverified_present:
            warnings.add("UNVERIFIED_COMPANY_EXPOSURES_NOT_MAPPED")
        themes = [f"EVENT_TYPE:{event.event_type.value}", f"DOMAIN:{event.domain}", f"MATERIALITY:{event.materiality.value}"]
        if event.policy_stage is not None:
            themes.append(f"POLICY_STAGE:{event.policy_stage.value}")
        if evidence.time_horizon is not None:
            themes.append(f"TIME_HORIZON:{evidence.time_horizon}")
        themes.extend(f"INDUSTRY:{item}" for item in evidence.affected_industries)
        primary_url = evidence.primary_source.source_reference
        return NewsArticleEvidence(
            article_id=projection_id,
            source_provider=EXTERNAL_INTELLIGENCE_NEWS_PROVIDER,
            publisher=evidence.primary_source.source_name,
            publisher_url=primary_url if primary_url and primary_url.startswith(("https://", "http://")) else None,
            url=f"https://hsi.local/external-intelligence/{projection_id}",
            title=event.title,
            description=_description(evidence),
            published_at=evidence.published_at,
            received_at=evidence.received_at,
            language=None,
            country=event.country,
            instrument_ids=tuple(sorted({item.canonical_instrument_id for item in verified})),
            sectors=tuple(sorted(set(evidence.affected_sectors))),
            themes=tuple(sorted(set(themes))),
            source_quality=NewsSourceQuality.SECONDARY_RESEARCH,
            provenance=SourceRecordProvenance(
                source_id=projection_id,
                provider=EXTERNAL_INTELLIGENCE_NEWS_PROVIDER,
                source_reference=_provenance_reference(event, evidence),
                observed_at=evidence.discovered_at,
                published_at=evidence.published_at,
                received_at=evidence.received_at,
                effective_from=evidence.effective_at,
                effective_to=None,
                family=DataFamily.NEWS_RESEARCH,
                schema_version="hsi-external-intelligence-event/v1",
                normalization_version=EXTERNAL_INTELLIGENCE_NEWS_PROJECTION_VERSION,
            ),
            event_category=_news_category(event.event_type),
            match_warnings=(),
            warnings=tuple(sorted(warnings)),
            normalization_version=EXTERNAL_INTELLIGENCE_NEWS_PROJECTION_VERSION,
            company_name=verified[0].external_company_name if len(verified) == 1 else None,
        )

    def project_and_save(self, event: ExternalEvent, evidence: EvidenceVersion) -> NewsArticleEvidence:
        derived = self.project(event, evidence)
        existing = self._news_store.get(derived.article_id)
        if existing is not None:
            if existing != derived:
                raise ValueError("External-intelligence News projection identity is immutable and conflicted.")
            return existing
        if self._news_store.save(derived):
            return derived
        existing = self._news_store.get(derived.article_id)
        if existing != derived:
            raise ValueError("External-intelligence News projection identity is immutable and conflicted.")
        return existing

    @staticmethod
    def _validate_lineage(event: ExternalEvent, evidence: EvidenceVersion) -> None:
        if event.canonical_event_id != evidence.event.canonical_event_id or event != evidence.event:
            raise ValueError("News projection requires the exact canonical event retained by evidence.")


def _description(evidence: EvidenceVersion) -> str:
    return evidence.summary + "\n\nWhat changed: " + evidence.what_changed


def _provenance_reference(event: ExternalEvent, evidence: EvidenceVersion) -> str:
    """One canonical JSON provenance field for the News model's string boundary."""
    return json.dumps({
        "canonical_event_id": event.canonical_event_id,
        "evidence_version_id": evidence.evidence_version_id,
        "producer_id": event.producer_id,
        "event_type": event.event_type.value,
        "materiality": event.materiality.value,
        "policy_stage": event.policy_stage.value if event.policy_stage is not None else None,
        "primary_source": {
            "source_name": evidence.primary_source.source_name,
            "source_type": evidence.primary_source.source_type,
            "source_reference": evidence.primary_source.source_reference,
            "source_confidence": evidence.primary_source.source_confidence,
        },
        "supporting_source_references": tuple(item.source_reference for item in evidence.supporting_sources),
        "published_at": evidence.published_at.isoformat(),
        "discovered_at": evidence.discovered_at.isoformat(),
        "received_at": evidence.received_at.isoformat(),
        "event_fingerprint": event.fingerprint,
        "evidence_fingerprint": evidence.fingerprint,
        "projection_version": EXTERNAL_INTELLIGENCE_NEWS_PROJECTION_VERSION,
    }, sort_keys=True, separators=(",", ":"))


def _news_category(event_type: EventType) -> NewsEventCategory:
    return {
        EventType.EARNINGS: NewsEventCategory.EARNINGS_RESULTS,
        EventType.ORDER_WIN: NewsEventCategory.ORDER_CONTRACT,
        EventType.M_AND_A: NewsEventCategory.ACQUISITION_DIVESTMENT,
        EventType.REGULATORY: NewsEventCategory.REGULATORY_LEGAL,
        EventType.GOVERNMENT_POLICY: NewsEventCategory.REGULATORY_LEGAL,
        EventType.MONETARY_POLICY: NewsEventCategory.MACRO,
        EventType.MACRO_DATA: NewsEventCategory.MACRO,
        EventType.SECTOR: NewsEventCategory.SECTOR_REGULATORY,
    }.get(event_type, NewsEventCategory.UNCLASSIFIED)
