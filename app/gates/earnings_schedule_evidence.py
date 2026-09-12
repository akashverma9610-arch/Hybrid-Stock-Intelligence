"""Candidate future-calendar evidence contract; NOT an admitted producer.

The approved source declaration is official-nse-earnings-calendar-v1. There
is no admitted acquisition/verification/revision adapter in this slice. Even
a valid instance cannot clear Gate 6. Financial filing timestamps are not
scheduled future events. No acquisition, activation or absence-as-clearance.
"""
from dataclasses import dataclass, fields
from datetime import datetime

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.version_compatibility import GateVersionBlocked, _utc, _text, _fingerprint

VERSION = "verified-earnings-schedule-evidence/candidate-v1"


@dataclass(frozen=True, slots=True)
class VerifiedEarningsScheduleEvidence:
    instrument_id: str
    scheduled_at: datetime
    event_type: str
    source_authority: str
    source_reference: str
    received_at: datetime
    known_at: datetime
    verification_state: str
    source_contract_version: str
    policy_version: str
    revision_id: str | None
    supersedes_id: str | None
    source_fingerprint: str
    fingerprint: str
    contract_version: str = VERSION

    def __post_init__(self):
        for name in ("scheduled_at", "received_at", "known_at"):
            object.__setattr__(self, name, _utc(getattr(self, name)))
        if (self.contract_version != VERSION or self.event_type not in {"BOARD_MEETING", "FINANCIAL_RESULTS"}
                or self.source_authority != "NSE" or self.source_contract_version != "official-nse-earnings-calendar-v1"
                or self.verification_state != "UNVERIFIED_SOURCE_AUTHORITY"
                or self.received_at > self.known_at or self.scheduled_at <= self.known_at
                or any(not _text(x) for x in (self.instrument_id, self.source_reference, self.policy_version))
                or any(x is not None and not _text(x) for x in (self.revision_id, self.supersedes_id))
                or (self.supersedes_id is not None and (self.revision_id is None or self.revision_id == self.supersedes_id))
                or not _fingerprint(self.source_fingerprint)):
            raise GateVersionBlocked("EARNINGS_CALENDAR_CANDIDATE_INVALID")
        if self.fingerprint != content_fingerprint({f.name: getattr(self, f.name) for f in fields(self) if f.name != "fingerprint"}):
            raise GateVersionBlocked("EARNINGS_CALENDAR_CANDIDATE_FINGERPRINT_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)
