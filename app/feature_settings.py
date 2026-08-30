"""Typed capability boundary for future application runtime orchestration.

This module intentionally does not guard reusable library services. A future
scheduler or API runtime must opt in explicitly before it automatically starts
the experimental Phase 9B research cycle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class FeatureName(str, Enum):
    AUTOMATED_SELF_IMPROVEMENT_RESEARCH = "AUTOMATED_SELF_IMPROVEMENT_RESEARCH"


class FeatureMaturity(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"


class FeatureLifecycleStatus(str, Enum):
    DEFERRED = "DEFERRED"


class RuntimeFeatureDisabledError(RuntimeError):
    """Raised when a future runtime tries to use a disabled capability."""

    code = "AUTOMATED_RESEARCH_DISABLED"


@dataclass(frozen=True, slots=True)
class FeatureCapabilityStatus:
    """Immutable, API-ready description of a runtime capability."""

    name: FeatureName
    enabled: bool
    maturity: FeatureMaturity
    lifecycle_status: FeatureLifecycleStatus
    production_blocking: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name.value,
            "enabled": self.enabled,
            "maturity": self.maturity.value,
            "status": self.lifecycle_status.value,
            "production_blocking": self.production_blocking,
        }


@dataclass(frozen=True, slots=True)
class FeatureSettings:
    """Minimal typed settings for future runtime orchestration.

    The default fails closed. It has no repository dependency and checking it
    has no side effects.
    """

    automated_self_improvement_research_enabled: bool = False

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "FeatureSettings":
        source = os.environ if environ is None else environ
        raw = source.get("ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH", "false")
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return cls(automated_self_improvement_research_enabled=True)
        if normalized in {"0", "false", "no", "off", ""}:
            return cls()
        raise ValueError("ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH must be a boolean value.")

    @property
    def automated_self_improvement_research(self) -> FeatureCapabilityStatus:
        return FeatureCapabilityStatus(
            name=FeatureName.AUTOMATED_SELF_IMPROVEMENT_RESEARCH,
            enabled=self.automated_self_improvement_research_enabled,
            maturity=FeatureMaturity.EXPERIMENTAL,
            lifecycle_status=FeatureLifecycleStatus.DEFERRED,
            production_blocking=False,
        )

    def capability_statuses(self) -> dict[str, FeatureCapabilityStatus]:
        """Return future status-endpoint data without importing Phase 9B services."""
        status = self.automated_self_improvement_research
        return {"automated_self_improvement_research": status}

    def require_automated_self_improvement_research_enabled(self) -> FeatureCapabilityStatus:
        """Future runtime gate; intentionally not used by direct library services."""
        status = self.automated_self_improvement_research
        if not status.enabled:
            raise RuntimeFeatureDisabledError(
                "AUTOMATED_RESEARCH_DISABLED: automatic self-improvement research "
                "runtime orchestration is disabled."
            )
        return status
