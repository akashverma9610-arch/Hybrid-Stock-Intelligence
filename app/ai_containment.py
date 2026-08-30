"""Schema-bound AI assistance: deterministic code remains numerical authority."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AIAnalysisAuditMetadata:
    audit_id: str
    model_identifier: str
    prompt_template_version: str
    input_evidence_ids: tuple[str, ...]
    retrieval_snapshot_id: str
    structured_output_reference: str
    parser_schema_version: str
    created_at: datetime


class StructuredAIOutputValidator:
    """Reject malformed output; never substitutes a best guess."""
    def parse(self, raw: str, *, required_keys: tuple[str, ...]) -> dict:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("AI_STRUCTURED_OUTPUT_REJECTED") from error
        if not isinstance(value, dict) or any(key not in value for key in required_keys):
            raise ValueError("AI_STRUCTURED_OUTPUT_REJECTED")
        return value
