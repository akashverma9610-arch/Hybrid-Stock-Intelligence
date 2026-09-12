"""Read-only gate authority, configured by application composition, not evidence.

An input receipt is never its own verifier. The scoring producer or an
independently configured canonical reader must reproduce the attestation.
This is an in-process trust boundary; it does not defend against replacement
of Python code, the configured reader, or the underlying canonical database.
No source label, caller-supplied receipt, or hash grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.domain.models import StrategyVersionReference
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.score_provenance import _card
from app.gates.version_compatibility import GateVersionBlocked, _utc, require_gate_source
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import DecisionScorecard, build_scorecard

VERSION = "six-gates-source-authority/v1"
CALENDAR_BLOCKER = "EARNINGS_CALENDAR_AUTHORITY_NOT_READY"


def _body(value):
    return {f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"}


@dataclass(frozen=True, slots=True)
class ScoreEvidenceAttestation:
    """Deterministic audit output of an authority, never admission input."""
    scorecard_id: str
    instrument_id: str
    score_value: Decimal | None
    registry_version: str
    scoring_configuration_version: str
    scoring_policy_version: str
    scoring_policy_fingerprint: str
    strategy_version: StrategyVersionReference | str
    as_of: datetime
    score_status: str
    score_eligible: bool
    execution_path_allowed: bool
    shadow_only: bool
    producer_id: str
    source_fingerprint: str
    diagnostic_fingerprints: tuple[str, ...]
    comparison_fingerprint: str | None
    fingerprint: str
    contract_version: str = VERSION

    def __post_init__(self):
        object.__setattr__(self, "as_of", _utc(self.as_of))
        if (self.contract_version != VERSION or self.registry_version != DIAGNOSTIC_REGISTRY_VERSION
                or self.shadow_only is not False or self.execution_path_allowed is not self.score_eligible
                or self.score_eligible is not (self.score_value is not None and self.score_status == "COMPLETE")
                or self.score_status not in {"COMPLETE", "SCORE_INCOMPLETE"}
                or (self.score_value is None) != (self.score_status == "SCORE_INCOMPLETE")
                or not self.scorecard_id or not self.instrument_id or not self.scoring_policy_version
                or not (type(self.strategy_version) is StrategyVersionReference
                        or (type(self.strategy_version) is str and bool(self.strategy_version)))
                or not self.producer_id or type(self.diagnostic_fingerprints) is not tuple or not self.diagnostic_fingerprints
                or (self.score_value is not None and (type(self.score_value) is not Decimal or not self.score_value.is_finite()))):
            raise GateVersionBlocked("GATE_SCORE_ATTESTATION_INVALID")
        from app.gates.version_compatibility import _fingerprint
        if (not _fingerprint(self.source_fingerprint)
                or type(self.scoring_policy_fingerprint) is not str
                or not _fingerprint("sha256:" + self.scoring_policy_fingerprint)
                or any(not _fingerprint(x) for x in self.diagnostic_fingerprints)
                or self.diagnostic_fingerprints != tuple(sorted(set(self.diagnostic_fingerprints)))
                or (self.comparison_fingerprint is not None and not _fingerprint(self.comparison_fingerprint))
                or self.fingerprint != content_fingerprint(_body(self))):
            raise GateVersionBlocked("GATE_SCORE_ATTESTATION_FINGERPRINT_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


class GateSourceAuthority(Protocol):
    """Trusted dependency at engine construction; never an evaluate/API field."""
    def attest_score(self, proof) -> ScoreEvidenceAttestation: ...
    def verify_domain(self, ref, value, *, instrument_id, as_of, gate_policy_version) -> None: ...


def _receipt(card, *, producer, diagnostic_fingerprints, comparison=None):
    _card(card)
    from app.registry.canonical import SCORING_POLICY
    from app.portfolio.canonical_decision_score import scoring_policy_fingerprint
    body = dict(scorecard_id=card.id, instrument_id=card.instrument_id, score_value=card.final_score,
        registry_version=card.registry_version, scoring_configuration_version=card.configuration_version,
        scoring_policy_version=SCORING_POLICY.version, scoring_policy_fingerprint=scoring_policy_fingerprint(SCORING_POLICY),
        strategy_version=card.strategy_version, as_of=_utc(card.as_of_timestamp), score_status=card.score_status,
        score_eligible=card.final_score is not None and card.score_status == "COMPLETE",
        execution_path_allowed=card.final_score is not None and card.score_status == "COMPLETE", shadow_only=False, producer_id=producer,
        source_fingerprint=content_fingerprint(card),
        diagnostic_fingerprints=tuple(sorted(set(diagnostic_fingerprints))),
        comparison_fingerprint=content_fingerprint(comparison) if comparison is not None else None,
        contract_version=VERSION)
    return ScoreEvidenceAttestation(**body, fingerprint=content_fingerprint(body))


class UnavailableGateAuthority:
    def attest_score(self, proof):
        raise GateVersionBlocked("GATE_SCORE_AUTHORITY_UNAVAILABLE")

    def verify_domain(self, ref, value, **context):
        if ref.evidence_family == "EARNINGS_CALENDAR":
            raise GateVersionBlocked(CALENDAR_BLOCKER)
        raise GateVersionBlocked("GATE_DOMAIN_AUTHORITY_UNAVAILABLE:" + ref.input_field)


@dataclass(frozen=True, slots=True)
class ScoringRunGateAuthority(UnavailableGateAuthority):
    """Adapter over the existing scoring calculation and canonical runner output.

    Constructed by the universe scoring boundary, before accepting GateInput.
    No score/receipt/claimed producer parameter is accepted. No new formula.
    """
    instrument_id: str
    strategy_version: StrategyVersionReference
    as_of: datetime
    diagnostics: tuple
    configuration_version: str = "decision-score-v1"
    source_run_fingerprint: str = field(init=False)

    def __post_init__(self):
        _utc(self.as_of)
        object.__setattr__(self, "source_run_fingerprint", self._source_fingerprint())

    def _source_fingerprint(self):
        return content_fingerprint(dict(instrument=self.instrument_id, strategy=self.strategy_version,
            as_of=self.as_of, diagnostics=self.diagnostics, configuration=self.configuration_version))

    def attest_score(self, proof):
        from app.diagnostics.models import EvaluatedDiagnostic
        if self.source_run_fingerprint != self._source_fingerprint():
            raise GateVersionBlocked("GATE_SCORE_PRODUCER_INPUT_TAMPERED")
        if self.configuration_version != "decision-score-v1":
            raise GateVersionBlocked("GATE_SCORING_POLICY_UNVERIFIED")
        if type(self.diagnostics) is not tuple or not self.diagnostics:
            raise GateVersionBlocked("GATE_SCORE_DIAGNOSTICS_UNVERIFIED")
        identities = set()
        for item in self.diagnostics:
            require_gate_source(item)
            if (type(item) is not EvaluatedDiagnostic or item.record.id in identities
                    or item.record.instrument_id != self.instrument_id
                    or item.record.strategy_version != self.strategy_version
                    or _utc(item.record.as_of_timestamp) > _utc(self.as_of)
                    or _utc(item.record.evaluated_at) > _utc(self.as_of)):
                raise GateVersionBlocked("GATE_SCORE_DIAGNOSTICS_UNVERIFIED")
            identities.add(item.record.id)
        card = build_scorecard(instrument_id=self.instrument_id, strategy_version=self.strategy_version,
            registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=self.as_of,
            evaluated_at=self.as_of, diagnostics=self.diagnostics, configuration_version=self.configuration_version)
        if proof.source_fingerprint != content_fingerprint(card) or proof.comparison_result is not None:
            raise GateVersionBlocked("GATE_SCORE_PRODUCER_MISMATCH")
        return _receipt(card, producer="app.scoring.engine.build_scorecard/v1",
                        diagnostic_fingerprints=tuple(content_fingerprint(x) for x in self.diagnostics))


@dataclass(frozen=True, slots=True)
class RepositoryGateAuthority(UnavailableGateAuthority):
    """Only read methods of the independently configured governance repository.

    A reopened immutable V1 record is authority; an unlinked historical number
    is not. No insertion, rehash repair, backfill or source-name allowlist.
    Neutral sources remain closed pending exact admitted producer adapters.
    """
    repository: object

    def verify_domain(self, ref, value, *, instrument_id, as_of, gate_policy_version):
        if ref.input_field != "holding_entry_date":
            return UnavailableGateAuthority.verify_domain(self, ref, value)
        # Existing canonical acquisition timestamp, not caller-declared days.
        # The source time here is the stored transaction cutoff, not an invented
        # receipt/publication timestamp. No holding or portfolio is changed.
        from app.portfolio.models import PortfolioSnapshot
        reader = getattr(self.repository, "get_portfolio_snapshot", None)
        snapshot = reader(ref.source_id) if reader is not None else None
        require_gate_source(snapshot)
        if type(snapshot) is not PortfolioSnapshot:
            raise GateVersionBlocked("GATE_HOLDING_CANONICAL_RECORD_UNVERIFIED")
        if (snapshot.snapshot_id != ref.source_id or ref.source_fingerprints != (content_fingerprint(snapshot),)
                or ref.source_version != snapshot.cost_basis_methodology_version
                or ref.policy_version != gate_policy_version or ref.as_of != _utc(snapshot.as_of_timestamp)
                or ref.known_at != _utc(snapshot.source_transaction_cutoff)
                or _utc(snapshot.source_transaction_cutoff) > _utc(snapshot.as_of_timestamp)
                or _utc(snapshot.as_of_timestamp) > _utc(as_of)):
            raise GateVersionBlocked("GATE_HOLDING_SOURCE_BINDING_MISMATCH")
        matches = tuple(x for x in snapshot.holdings if x.instrument_id == instrument_id and x.active)
        if (len(matches) != 1 or _utc(matches[0].acquisition_at) > ref.known_at
                or matches[0].acquisition_at.date() != value):
            raise GateVersionBlocked("GATE_HOLDING_ACQUISITION_UNVERIFIED")

    def attest_score(self, proof):
        from app.portfolio.canonical_decision_score import CanonicalDecisionScorecard
        card = _card(proof.source)
        method = "get_decision_scorecard" if type(card) is DecisionScorecard else "get_canonical_decision_scorecard"
        reader = getattr(self.repository, method, None)
        stored = reader(card.id) if reader is not None else None
        if stored is None or type(stored) is not type(card) or content_fingerprint(stored) != proof.source_fingerprint:
            raise GateVersionBlocked("GATE_SCORE_CANONICAL_RECORD_UNVERIFIED")
        _card(stored)
        from app.registry.canonical import SCORING_POLICY
        from app.portfolio.canonical_decision_score import scoring_policy_fingerprint
        if (stored.configuration_version != "decision-score-v1"
                or (type(stored) is CanonicalDecisionScorecard and (
                    stored.scoring_policy_version != SCORING_POLICY.version
                    or stored.scoring_policy_fingerprint != scoring_policy_fingerprint(SCORING_POLICY)))):
            raise GateVersionBlocked("GATE_SCORING_POLICY_UNVERIFIED")
        ids = {x for component in stored.components for x in component.diagnostic_ids}
        records = tuple(self.repository.list_diagnostic_results(stored.strategy_version, stored.as_of_timestamp))
        selected = tuple(x for x in records if x.id in ids)
        if not ids or len(selected) != len(ids) or {x.id for x in selected} != ids:
            raise GateVersionBlocked("GATE_SCORE_DIAGNOSTIC_LINK_UNVERIFIED")
        for item in selected:
            require_gate_source(item)
            if (item.instrument_id != stored.instrument_id or item.strategy_version != stored.strategy_version
                    or _utc(item.as_of_timestamp) > _utc(stored.as_of_timestamp)
                    or _utc(item.evaluated_at) > _utc(stored.as_of_timestamp)):
                raise GateVersionBlocked("GATE_SCORE_DIAGNOSTIC_LINK_UNVERIFIED")
            if type(stored) is CanonicalDecisionScorecard:
                from app.domain.models import canonical_diagnostic_result_fingerprint
                if item.diagnostic_fingerprint != canonical_diagnostic_result_fingerprint(item):
                    raise GateVersionBlocked("GATE_SCORE_DIAGNOSTIC_FINGERPRINT_MISMATCH")
        comparison = proof.comparison_result
        if comparison is not None:
            original = self.repository.get_execution_gate_evaluation(comparison.id)
            if original is None or content_fingerprint(original) != proof.comparison_fingerprint:
                raise GateVersionBlocked("GATE_COMPARISON_CANONICAL_RECORD_UNVERIFIED")
            require_gate_source(original)
        return _receipt(stored, producer="canonical-governance-reader/" + method,
                        diagnostic_fingerprints=tuple(content_fingerprint(x) for x in selected), comparison=comparison)


def require_source_authority(authority, *, inputs, candidate, incumbent, context, instrument_id, as_of, policy):
    """After nominal/value admission, before ANY of the six formula methods."""
    authority = authority if authority is not None else UnavailableGateAuthority()
    for proof in (candidate, incumbent):
        if proof is None or (proof.source.final_score is None and proof.comparison_result is None):
            # No numeric score is consumed. Existing missing-score semantics,
            # including non-rotation exemptions, are not rewritten here.
            continue
        attestation = authority.attest_score(proof)
        if type(attestation) is not ScoreEvidenceAttestation:
            raise GateVersionBlocked("GATE_SCORE_ATTESTATION_INVALID")
        attestation.__post_init__()
        card = proof.source
        if (attestation.source_fingerprint != proof.source_fingerprint
                or attestation.score_value != card.final_score or attestation.scorecard_id != card.id
                or attestation.instrument_id != card.instrument_id or attestation.registry_version != card.registry_version
                or attestation.scoring_configuration_version != card.configuration_version
                or attestation.strategy_version != card.strategy_version
                or attestation.as_of != _utc(card.as_of_timestamp) or attestation.as_of > _utc(as_of)
                or attestation.comparison_fingerprint != proof.comparison_fingerprint
                or attestation.score_status != card.score_status
                or attestation.score_eligible is not True or attestation.execution_path_allowed is not True):
            raise GateVersionBlocked("GATE_SCORE_ATTESTATION_BINDING_MISMATCH")
    if context is not None:
        from app.gates.version_compatibility import DOMAIN_FIELDS
        for ref in context.dependencies:
            value = getattr(inputs, ref.input_field)
            if ref.input_field in DOMAIN_FIELDS and value is not None:
                authority.verify_domain(ref, value, instrument_id=instrument_id, as_of=_utc(as_of),
                                        gate_policy_version=policy)
