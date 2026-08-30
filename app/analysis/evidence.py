from __future__ import annotations

import hashlib
from datetime import datetime

from app.domain.models import DataQuality, Evidence, EvidenceType, Provenance


def analysis_evidence(
    *, analysis_id: str, evidence_type: EvidenceType, source: str, timestamp: datetime,
    observation_ids: tuple[str, ...], content_reference: str, confidence: float | None,
    data_quality: DataQuality,
) -> Evidence:
    identifier = hashlib.sha256(f"{analysis_id}|{evidence_type.value}|{content_reference}".encode()).hexdigest()[:16]
    return Evidence(
        id=f"evidence-{identifier}", source=source, source_identifier=analysis_id, timestamp=timestamp,
        observation_ids=observation_ids, evidence_type=evidence_type,
        factual_content_reference=content_reference, confidence=confidence,
        provenance=Provenance(source, analysis_id, timestamp, timestamp, data_quality),
    )
