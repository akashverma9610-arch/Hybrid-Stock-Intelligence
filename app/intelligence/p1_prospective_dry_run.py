"""Non-writing prospective admission rehearsal, never an activation authority.

The boundary is explicitly hypothetical. A production caller still requires a
durable verified start and an owning-store CanonicalSourceReader. No test ledger
or supplied timestamp is registered as a production source by this module.
"""
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256

from app.intelligence.p1_signal_lifecycle import (
    CanonicalSourceReader, Evaluation, LifecycleError, Outcome,
    canonical_json, evaluate, qualify, utc, verify_source_closure,
)


@dataclass(frozen=True, slots=True)
class ProspectiveDryRun:
    evaluation_fingerprint: str
    hypothetical_start: datetime | None
    status: str
    reason: str | None
    mode: str = field(default="DRY_RUN_NOT_ACTIVE", init=False)
    actionability: str = field(default="WATCH_ONLY", init=False)
    execution_status: str = field(default="NON_EXECUTABLE", init=False)
    writes_performed: int = field(default=0, init=False)


def dry_run(value: Evaluation, reader: CanonicalSourceReader, *,
            hypothetical_start: datetime | None) -> ProspectiveDryRun:
    """Rehearse initial admission only; not current-lifetime reevaluation.

    Enforce the requested strict known-at boundary without re-dating historical
    context. In particular, earlier policy/security/history evidence is not
    made newly known simply because it was fetched or projected again.
    """
    fingerprint = "sha256:" + sha256(canonical_json(value).encode()).hexdigest()
    start = None if hypothetical_start is None else utc(hypothetical_start)

    def result(status, reason=None):
        return ProspectiveDryRun(fingerprint, start, status, reason)

    if start is None:
        return result("SOURCE_BLOCKED", "PROSPECTIVE_START_UNSET")
    if value.as_of < start:
        return result("SOURCE_BLOCKED", "EVALUATION_BEFORE_PROSPECTIVE_START")
    if any(r.evidence_known_at is None for r in value.references):
        return result("SOURCE_BLOCKED", "EVIDENCE_KNOWN_AT_UNAVAILABLE")
    if any(r.evidence_known_at < start for r in value.references):
        return result("SOURCE_BLOCKED", "EVIDENCE_BEFORE_PROSPECTIVE_START")
    # Keep existing native validation, registry and source checks authoritative.
    native = evaluate(value, (), reader)
    if native.outcome is Outcome.ACCEPTED:
        return result("WOULD_ADMIT")
    if native.outcome is Outcome.SOURCE_BLOCKED:
        # The lifecycle reducer correctly refuses invalidation without a prior
        # lifetime. A fully verified negative assessment can still be a healthy
        # zero-signal initial evaluation, not a reason to fabricate a lifetime.
        try:
            qualification = qualify(value)
            verify_source_closure(value, reader)
            if qualification.request_kind == "NEGATIVE_ASSESSMENT":
                return result("EVALUATED_NO_CURRENT_VALID_SETUP")
        except (LifecycleError, ValueError, TypeError, AttributeError, KeyError, OSError):
            pass
    return result(native.outcome.value, native.reason.value if native.reason else None)
