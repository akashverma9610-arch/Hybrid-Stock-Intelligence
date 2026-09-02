"""Read-only, fail-closed strategy-policy provenance for Watch-only HSISignal."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable, Protocol

from app.historical.guard import manifest_fingerprint
from app.intelligence.hsi_signal import StrategyResolutionReference, StrategyResolutionStatus
from app.intelligence.opportunity_archetypes import OpportunityArchetype, SetupPolicyRoute
from app.strategies.pre_breakout.governance import (
    PreBreakoutPolicyGovernanceError,
    PreBreakoutPolicyGovernanceService,
    PreBreakoutPolicyGovernanceState,
)
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApproval,
    PreBreakoutPolicyDraft,
    PreBreakoutPolicySelection,
    PreBreakoutPolicySelectionContext,
    PreBreakoutMultiStageEntrySuccessorDraft,
    PreBreakoutVolumeResolvedSuccessorDraft,
    prebreakout_policy_governance_drafts,
)

HSI_SIGNAL_STRATEGY_REGISTRY_ID = "hsi-signal-strategy-registry"
HSI_SIGNAL_STRATEGY_REGISTRY_VERSION = "v1"
HSI_SIGNAL_STRATEGY_REGISTRY_CONTRACT = f"{HSI_SIGNAL_STRATEGY_REGISTRY_ID}/{HSI_SIGNAL_STRATEGY_REGISTRY_VERSION}"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+")
_FINGERPRINT = re.compile(r"(?:sha256:)?[0-9a-f]{64}")


class HSISignalStrategyRegistryError(ValueError):
    """Raised only for malformed immutable registry input/result contracts."""


class StrategyRegistryReasonCode(StrEnum):
    UNKNOWN_ARCHETYPE = "UNKNOWN_ARCHETYPE"
    WATCH_ARCHETYPE_NOT_ROUTED = "WATCH_ARCHETYPE_NOT_ROUTED"
    WATCH_ROUTING_PRECONDITION_MISSING = "WATCH_ROUTING_PRECONDITION_MISSING"
    CURRENT_VALID_SETUP_REQUIRED = "CURRENT_VALID_SETUP_REQUIRED"
    STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE = "STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE"
    PREBREAKOUT_POLICY_MISSING = "PREBREAKOUT_POLICY_MISSING"
    PREBREAKOUT_POLICY_SELECTION_MISSING = "PREBREAKOUT_POLICY_SELECTION_MISSING"
    PREBREAKOUT_POLICY_SELECTION_NOT_EFFECTIVE_AT_WATCH_AS_OF = "PREBREAKOUT_POLICY_SELECTION_NOT_EFFECTIVE_AT_WATCH_AS_OF"
    PREBREAKOUT_POLICY_APPROVAL_NOT_EFFECTIVE_AT_WATCH_AS_OF = "PREBREAKOUT_POLICY_APPROVAL_NOT_EFFECTIVE_AT_WATCH_AS_OF"
    PREBREAKOUT_POLICY_UNAPPROVED = "PREBREAKOUT_POLICY_UNAPPROVED"
    PREBREAKOUT_POLICY_SELECTION_INACTIVE = "PREBREAKOUT_POLICY_SELECTION_INACTIVE"
    PREBREAKOUT_POLICY_PROVENANCE_INVALID = "PREBREAKOUT_POLICY_PROVENANCE_INVALID"
    PREBREAKOUT_POLICY_SELECTION_AMBIGUOUS = "PREBREAKOUT_POLICY_SELECTION_AMBIGUOUS"
    PREBREAKOUT_POLICY_SELECTION_DUPLICATE = "PREBREAKOUT_POLICY_SELECTION_DUPLICATE"
    PREBREAKOUT_POLICY_PROVENANCE_UNVERIFIABLE = "PREBREAKOUT_POLICY_PROVENANCE_UNVERIFIABLE"


class PreBreakoutPolicyProvenanceReader(Protocol):
    """Narrow read-only view of the existing governance repository contract."""

    def get_prebreakout_policy_approval(self, approval_id: str) -> PreBreakoutPolicyApproval | None: ...
    def list_prebreakout_policy_approvals(self, policy_id: str | None = None) -> tuple[PreBreakoutPolicyApproval, ...]: ...
    def list_prebreakout_policy_selections(
        self, policy_id: str | None = None,
        context: PreBreakoutPolicySelectionContext | None = None,
    ) -> tuple[PreBreakoutPolicySelection, ...]: ...


@dataclass(frozen=True, slots=True)
class WatchStrategyRoutingContext:
    """PIT-bound Watch routing facts supplied by a future verified Watch reader."""

    canonical_instrument_id: str
    watch_id: str
    watch_fingerprint: str
    watch_as_of: datetime
    archetype: OpportunityArchetype | str
    watch_archetypes: tuple[OpportunityArchetype | str, ...]
    setup_state: str
    setup_policy_routes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "watch_as_of", _canonical_timestamp(
            self.watch_as_of, "HSI_SIGNAL_STRATEGY_REGISTRY_WATCH_AS_OF_INVALID",
        ))
        _validate_context(self)

    def verify(self) -> None:
        _validate_context(self)


@dataclass(frozen=True, slots=True)
class StrategyRegistryResolution:
    """Stable read result. Unavailable results contain no policy references."""

    canonical_instrument_id: str
    watch_id: str
    watch_fingerprint: str
    watch_as_of: datetime
    archetype: str
    resolution: StrategyResolutionReference
    reason_code: StrategyRegistryReasonCode | None
    registry_id: str = HSI_SIGNAL_STRATEGY_REGISTRY_ID
    registry_version: str = HSI_SIGNAL_STRATEGY_REGISTRY_VERSION
    resolution_id: str = field(init=False)
    provenance_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "watch_as_of", _canonical_timestamp(
            self.watch_as_of, "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLUTION_WATCH_AS_OF_INVALID",
        ))
        _validate_resolution_contract(self)
        object.__setattr__(self, "resolution_id", "hsi-signal-strategy-resolution:" + manifest_fingerprint(**_identity_payload(self))[:32])
        object.__setattr__(self, "provenance_fingerprint", manifest_fingerprint(**_payload(self)))

    def verify(self) -> None:
        _validate_resolution_contract(self)
        expected_id = "hsi-signal-strategy-resolution:" + manifest_fingerprint(**_identity_payload(self))[:32]
        if self.resolution_id != expected_id:
            raise HSISignalStrategyRegistryError("HSI_SIGNAL_STRATEGY_REGISTRY_IDENTITY_MISMATCH")
        if self.provenance_fingerprint != manifest_fingerprint(**_payload(self)):
            raise HSISignalStrategyRegistryError("HSI_SIGNAL_STRATEGY_REGISTRY_FINGERPRINT_MISMATCH")


class HSISignalStrategyRegistry:
    """Read-only P1B policy-provenance resolver; it creates no strategy or signal."""

    def __init__(
        self, reader: PreBreakoutPolicyProvenanceReader, *,
        drafts: Iterable[PreBreakoutPolicyDraft | PreBreakoutVolumeResolvedSuccessorDraft | PreBreakoutMultiStageEntrySuccessorDraft] = prebreakout_policy_governance_drafts(),
    ) -> None:
        self._reader = reader
        self._governance = PreBreakoutPolicyGovernanceService(reader, drafts=tuple(drafts))

    @property
    def registry_identity(self) -> tuple[str, str]:
        return HSI_SIGNAL_STRATEGY_REGISTRY_ID, HSI_SIGNAL_STRATEGY_REGISTRY_VERSION

    def resolve(self, context: WatchStrategyRoutingContext) -> StrategyRegistryResolution:
        """Resolve only policy provenance at the supplied canonical Watch as-of."""
        if not isinstance(context, WatchStrategyRoutingContext):
            raise HSISignalStrategyRegistryError("HSI_SIGNAL_STRATEGY_REGISTRY_CONTEXT_REQUIRED")
        context.verify()
        archetype = _known_archetype(context.archetype)
        if archetype is None:
            return self._unavailable(context, _archetype_value(context.archetype), StrategyRegistryReasonCode.UNKNOWN_ARCHETYPE)
        if archetype.value not in {_archetype_value(item) for item in context.watch_archetypes}:
            return self._unavailable(context, archetype.value, StrategyRegistryReasonCode.WATCH_ARCHETYPE_NOT_ROUTED)
        if archetype is not OpportunityArchetype.PRE_BREAKOUT:
            return self._unavailable(context, archetype.value, StrategyRegistryReasonCode.STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE)
        if context.setup_state != "CURRENT_VALID_SETUP":
            return self._unavailable(context, archetype.value, StrategyRegistryReasonCode.CURRENT_VALID_SETUP_REQUIRED)
        if (OpportunityArchetype.PRE_BREAKOUT.value, SetupPolicyRoute.PRE_BREAKOUT_POLICY.value) not in context.setup_policy_routes:
            return self._unavailable(context, archetype.value, StrategyRegistryReasonCode.WATCH_ROUTING_PRECONDITION_MISSING)
        return self._resolve_prebreakout(context, archetype.value)

    def _resolve_prebreakout(self, context: WatchStrategyRoutingContext, archetype: str) -> StrategyRegistryResolution:
        try:
            approvals = tuple(self._reader.list_prebreakout_policy_approvals())
            selections = tuple(self._reader.list_prebreakout_policy_selections(
                context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
            ))
        except Exception:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_UNVERIFIABLE)
        if not approvals and not selections:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_MISSING)
        if not selections:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_MISSING)
        if len({item.selection_id for item in selections}) != len(selections):
            return self._unavailable(
                context, archetype,
                StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_DUPLICATE,
            )
        eligible = tuple(item for item in selections if item.effective_from <= context.watch_as_of and item.selected_at <= context.watch_as_of)
        if not eligible:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_NOT_EFFECTIVE_AT_WATCH_AS_OF)
        latest_effective = max(item.effective_from for item in eligible)
        latest = tuple(item for item in eligible if item.effective_from == latest_effective)
        if _conflicting_selection_provenance(latest):
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_AMBIGUOUS)
        selected = max(latest, key=lambda item: (item.selected_at, item.selection_id))
        try:
            approval = self._reader.get_prebreakout_policy_approval(selected.approval_id)
        except Exception:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_UNVERIFIABLE)
        if approval is None:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID)
        approval_records = tuple(
            item for item in approvals if item.approval_id == selected.approval_id
        )
        if len(approval_records) != 1 or approval_records[0] != approval:
            return self._unavailable(
                context, archetype,
                StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID,
            )
        if approval.reviewed_at > context.watch_as_of or approval.created_at > context.watch_as_of:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_APPROVAL_NOT_EFFECTIVE_AT_WATCH_AS_OF)
        try:
            view = self._governance.validate_selection(selected)
        except PreBreakoutPolicyGovernanceError as error:
            return self._unavailable(context, archetype, _governance_reason(error))
        except Exception:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_UNVERIFIABLE)
        if view.state is not PreBreakoutPolicyGovernanceState.SELECTED_FOR_SCAN:
            return self._unavailable(context, archetype, StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_INACTIVE)
        return StrategyRegistryResolution(
            canonical_instrument_id=context.canonical_instrument_id, watch_id=context.watch_id,
            watch_fingerprint=context.watch_fingerprint, watch_as_of=context.watch_as_of,
            archetype=archetype,
            resolution=StrategyResolutionReference(
                StrategyResolutionStatus.RESOLVED, policy_id=view.policy.policy_id,
                policy_version=view.policy.version, approval_id=view.approval.approval_id,
                selection_id=view.selection.selection_id, policy_fingerprint=view.policy_fingerprint,
            ),
            reason_code=None,
        )

    @staticmethod
    def _unavailable(
        context: WatchStrategyRoutingContext, archetype: str, reason: StrategyRegistryReasonCode,
    ) -> StrategyRegistryResolution:
        return StrategyRegistryResolution(
            canonical_instrument_id=context.canonical_instrument_id, watch_id=context.watch_id,
            watch_fingerprint=context.watch_fingerprint, watch_as_of=context.watch_as_of,
            archetype=archetype,
            resolution=StrategyResolutionReference(StrategyResolutionStatus.STRATEGY_UNAVAILABLE),
            reason_code=reason,
        )


def strategy_registry_resolution_payload(value: StrategyRegistryResolution) -> dict[str, object]:
    value.verify()
    return _payload(value)


def serialize_strategy_registry_resolution(value: StrategyRegistryResolution) -> str:
    return json.dumps(strategy_registry_resolution_payload(value), sort_keys=True, separators=(",", ":"))


def _known_archetype(value: OpportunityArchetype | str) -> OpportunityArchetype | None:
    return value if isinstance(value, OpportunityArchetype) else None


def _archetype_value(value: OpportunityArchetype | str) -> str:
    if isinstance(value, OpportunityArchetype):
        return value.value
    if isinstance(value, str) and _IDENTIFIER.fullmatch(value):
        return value
    raise HSISignalStrategyRegistryError("HSI_SIGNAL_STRATEGY_REGISTRY_ARCHETYPE_IDENTIFIER_INVALID")


def _conflicting_selection_provenance(values: tuple[PreBreakoutPolicySelection, ...]) -> bool:
    return len({(
        item.approval_id, item.policy_id, item.policy_version, item.policy_fingerprint,
        item.selection_context.value,
    ) for item in values}) > 1


def _governance_reason(error: PreBreakoutPolicyGovernanceError) -> StrategyRegistryReasonCode:
    if str(error) == "PREBREAKOUT_POLICY_APPROVAL_NOT_APPROVED":
        return StrategyRegistryReasonCode.PREBREAKOUT_POLICY_UNAPPROVED
    if str(error) == "PREBREAKOUT_POLICY_SELECTION_CONTEXT_INVALID":
        return StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_INACTIVE
    return StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID


def _validate_context(value: WatchStrategyRoutingContext) -> None:
    for item in (
        value.canonical_instrument_id, value.watch_id, value.setup_state,
    ):
        _require_identifier(item, "HSI_SIGNAL_STRATEGY_REGISTRY_CONTEXT_IDENTITY_INVALID")
    _require_fingerprint(
        value.watch_fingerprint,
        "HSI_SIGNAL_STRATEGY_REGISTRY_WATCH_FINGERPRINT_INVALID",
    )
    _canonical_timestamp(
        value.watch_as_of, "HSI_SIGNAL_STRATEGY_REGISTRY_WATCH_AS_OF_INVALID"
    )
    archetypes = tuple(_archetype_value(item) for item in value.watch_archetypes)
    if not archetypes or len(set(archetypes)) != len(archetypes):
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_WATCH_ARCHETYPES_INVALID"
        )
    if archetypes != tuple(sorted(archetypes)):
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_WATCH_ARCHETYPES_NONCANONICAL"
        )
    _archetype_value(value.archetype)
    routes = tuple(value.setup_policy_routes)
    if not routes:
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_SETUP_ROUTES_REQUIRED"
        )
    for route in routes:
        if not isinstance(route, tuple) or len(route) != 2:
            raise HSISignalStrategyRegistryError(
                "HSI_SIGNAL_STRATEGY_REGISTRY_SETUP_ROUTE_INVALID"
            )
        for item in route:
            _require_identifier(item, "HSI_SIGNAL_STRATEGY_REGISTRY_SETUP_ROUTE_INVALID")
    if len(set(routes)) != len(routes) or routes != tuple(sorted(routes)):
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_SETUP_ROUTES_NONCANONICAL"
        )


def _validate_resolution_contract(value: StrategyRegistryResolution) -> None:
    for item in (
        value.canonical_instrument_id, value.watch_id, value.archetype,
        value.registry_id, value.registry_version,
    ):
        _require_identifier(
            item, "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLUTION_IDENTITY_INVALID"
        )
    _require_fingerprint(
        value.watch_fingerprint,
        "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLUTION_WATCH_FINGERPRINT_INVALID",
    )
    _canonical_timestamp(
        value.watch_as_of,
        "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLUTION_WATCH_AS_OF_INVALID",
    )
    if (
        value.registry_id != HSI_SIGNAL_STRATEGY_REGISTRY_ID
        or value.registry_version != HSI_SIGNAL_STRATEGY_REGISTRY_VERSION
    ):
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_VERSION_OR_ID_INVALID"
        )
    if not isinstance(value.resolution, StrategyResolutionReference):
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLUTION_INVALID"
        )
    if value.resolution.status is StrategyResolutionStatus.RESOLVED:
        if value.reason_code is not None:
            raise HSISignalStrategyRegistryError(
                "HSI_SIGNAL_STRATEGY_REGISTRY_RESOLVED_REASON_FORBIDDEN"
            )
    elif value.resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE:
        if not isinstance(value.reason_code, StrategyRegistryReasonCode):
            raise HSISignalStrategyRegistryError(
                "HSI_SIGNAL_STRATEGY_REGISTRY_UNAVAILABLE_REASON_REQUIRED"
            )
    else:
        raise HSISignalStrategyRegistryError(
            "HSI_SIGNAL_STRATEGY_REGISTRY_STATUS_INVALID"
        )


def _canonical_timestamp(value: datetime, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise HSISignalStrategyRegistryError(code)
    return value.astimezone(UTC)


def _require_identifier(value: str, code: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise HSISignalStrategyRegistryError(code)


def _require_fingerprint(value: str, code: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise HSISignalStrategyRegistryError(code)


def _identity_payload(value: StrategyRegistryResolution) -> dict[str, object]:
    return {
        "registry_contract": HSI_SIGNAL_STRATEGY_REGISTRY_CONTRACT,
        "canonical_instrument_id": value.canonical_instrument_id,
        "watch_id": value.watch_id,
        "watch_fingerprint": value.watch_fingerprint,
        "watch_as_of": value.watch_as_of.isoformat(),
        "archetype": value.archetype,
    }


def _payload(value: StrategyRegistryResolution) -> dict[str, object]:
    return {
        **_identity_payload(value), "registry_id": value.registry_id,
        "registry_version": value.registry_version, "resolution_id": value.resolution_id,
        "resolution_status": value.resolution.status.value,
        "reason_code": None if value.reason_code is None else value.reason_code.value,
        "policy_id": value.resolution.policy_id, "policy_version": value.resolution.policy_version,
        "approval_id": value.resolution.approval_id, "selection_id": value.resolution.selection_id,
        "policy_fingerprint": value.resolution.policy_fingerprint,
    }


__all__ = (
    "HSI_SIGNAL_STRATEGY_REGISTRY_CONTRACT", "HSI_SIGNAL_STRATEGY_REGISTRY_ID",
    "HSI_SIGNAL_STRATEGY_REGISTRY_VERSION", "HSISignalStrategyRegistry",
    "HSISignalStrategyRegistryError", "PreBreakoutPolicyProvenanceReader",
    "StrategyRegistryReasonCode", "StrategyRegistryResolution",
    "WatchStrategyRoutingContext", "serialize_strategy_registry_resolution",
    "strategy_registry_resolution_payload",
)
