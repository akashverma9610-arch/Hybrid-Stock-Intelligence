"""Narrow persistence boundary for immutable tick-reference evidence."""
from __future__ import annotations

from typing import Protocol

from .tick_size import NseTickSizeObservation, TickSizeSourceClass


class TickSizeObservationRepository(Protocol):
    """Insert-only storage boundary; it deliberately has no as-of resolver."""

    def save_tick_size_observation(self, value: NseTickSizeObservation) -> None: ...

    def get_tick_size_observation(self, record_id: str) -> NseTickSizeObservation | None: ...

    def list_tick_size_observations(
        self,
        canonical_instrument_id: str | None = None,
        source_class: TickSizeSourceClass | None = None,
    ) -> tuple[NseTickSizeObservation, ...]: ...
