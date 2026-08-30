"""Explicit source priority and readiness composition; no network activity."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import os
from typing import Mapping

from app.data_sources.models import (
    AdjustmentCapability, DataFamily, DataFreshnessPolicy, DataRequirement,
    DataSourceDefinition, DataSourceReadiness, DataSourceReadinessReport,
    FreshnessBasis, FundamentalFactKind, PointInTimeCapability,
    RuntimeSourceReadiness, SourceCapability, SourceReadinessStatus,
    SourceRecordProvenance, SourceValidationState,
)
from app.runtime.cycle import RuntimeMode


FRESHNESS_POLICIES = {
    DataFamily.CURRENT_QUOTES: DataFreshnessPolicy(DataFamily.CURRENT_QUOTES, FreshnessBasis.WALL_CLOCK, timedelta(minutes=1)),
    DataFamily.STREAMING_QUOTES: DataFreshnessPolicy(DataFamily.STREAMING_QUOTES, FreshnessBasis.WALL_CLOCK, timedelta(seconds=30)),
    DataFamily.HISTORICAL_OHLCV: DataFreshnessPolicy(DataFamily.HISTORICAL_OHLCV, FreshnessBasis.COMPLETED_SESSION, None),
    DataFamily.INDEX_DATA: DataFreshnessPolicy(DataFamily.INDEX_DATA, FreshnessBasis.WALL_CLOCK, timedelta(minutes=1)),
    DataFamily.VIX: DataFreshnessPolicy(DataFamily.VIX, FreshnessBasis.WALL_CLOCK, timedelta(minutes=1)),
    DataFamily.UNIVERSE_MEMBERSHIP: DataFreshnessPolicy(DataFamily.UNIVERSE_MEMBERSHIP, FreshnessBasis.EFFECTIVE_EVENT, None),
    DataFamily.FUNDAMENTALS: DataFreshnessPolicy(DataFamily.FUNDAMENTALS, FreshnessBasis.PUBLICATION_EVENT, None),
    DataFamily.CORPORATE_FILINGS: DataFreshnessPolicy(DataFamily.CORPORATE_FILINGS, FreshnessBasis.PUBLICATION_EVENT, None),
    DataFamily.CORPORATE_ACTIONS: DataFreshnessPolicy(DataFamily.CORPORATE_ACTIONS, FreshnessBasis.EFFECTIVE_EVENT, None),
    DataFamily.NEWS_RESEARCH: DataFreshnessPolicy(DataFamily.NEWS_RESEARCH, FreshnessBasis.PUBLICATION_EVENT, None),
    DataFamily.IPO_PRIMARY_MARKET: DataFreshnessPolicy(DataFamily.IPO_PRIMARY_MARKET, FreshnessBasis.PUBLICATION_EVENT, None),
}


def _provenance(source_id: str, provider: str, family: DataFamily) -> SourceRecordProvenance:
    return SourceRecordProvenance(source_id, provider, None, None, None, datetime(1970, 1, 1, tzinfo=UTC), None, None, family, "data-source-v1", "not-applicable")


def _capability(family: DataFamily, pit=PointInTimeCapability.UNKNOWN, adjustment=AdjustmentCapability.NOT_APPLICABLE, *warnings: str) -> SourceCapability:
    return SourceCapability(family, pit, adjustment, FRESHNESS_POLICIES[family], tuple(warnings))


def standard_source_definitions() -> tuple[DataSourceDefinition, ...]:
    """Declared slots reflect implementation, not aspirational provider claims."""
    return (
        DataSourceDefinition(
            "kotak_neo", "kotak_neo", "Kotak Neo",
            (
                _capability(DataFamily.CURRENT_QUOTES, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, "LIVE_QUOTE_VALIDATION_PENDING"),
                _capability(DataFamily.STREAMING_QUOTES, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, "STREAMING_EXTERNAL_VALIDATION_PENDING"),
                _capability(DataFamily.HISTORICAL_OHLCV, PointInTimeCapability.UNSUPPORTED, AdjustmentCapability.UNSUPPORTED, "NO_DOCUMENTED_KOTAK_HISTORICAL_CONTRACT"),
                _capability(DataFamily.INDEX_DATA, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, "LIVE_QUOTE_VALIDATION_PENDING"),
                _capability(DataFamily.VIX, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, "LIVE_QUOTE_VALIDATION_PENDING"),
            ), _provenance("kotak_neo", "kotak_neo", DataFamily.CURRENT_QUOTES),
        ),
        DataSourceDefinition(
            "stored_data", "local_store", "Stored canonical data",
            (
                _capability(DataFamily.CURRENT_QUOTES, PointInTimeCapability.LIMITED),
                _capability(DataFamily.HISTORICAL_OHLCV, PointInTimeCapability.SUPPORTED, AdjustmentCapability.UNKNOWN),
                _capability(DataFamily.INDEX_DATA, PointInTimeCapability.LIMITED),
                _capability(DataFamily.VIX, PointInTimeCapability.LIMITED),
                _capability(DataFamily.UNIVERSE_MEMBERSHIP, PointInTimeCapability.SUPPORTED),
                _capability(DataFamily.FUNDAMENTALS, PointInTimeCapability.SUPPORTED, AdjustmentCapability.NOT_APPLICABLE, "STORED_DATA_ONLY_NO_LIVE_FUNDAMENTALS_PROVIDER"),
                _capability(DataFamily.IPO_PRIMARY_MARKET, PointInTimeCapability.SUPPORTED, AdjustmentCapability.NOT_APPLICABLE, "OFFICIAL_EXPORT_STORE_ONLY_NO_LIVE_IPO_PROVIDER"),
            ), _provenance("stored_data", "local_store", DataFamily.HISTORICAL_OHLCV),
        ),
        DataSourceDefinition(
            "mock", "mock", "Explicit deterministic mock",
            tuple(_capability(family, PointInTimeCapability.SUPPORTED, AdjustmentCapability.UNKNOWN, "EXPLICIT_MOCK_SOURCE") for family in (DataFamily.CURRENT_QUOTES, DataFamily.HISTORICAL_OHLCV, DataFamily.INDEX_DATA, DataFamily.VIX, DataFamily.UNIVERSE_MEMBERSHIP)),
            _provenance("mock", "mock", DataFamily.CURRENT_QUOTES),
        ),
        DataSourceDefinition("nse_filings", "nse", "NSE primary filings boundary", tuple(_capability(family, PointInTimeCapability.SUPPORTED, AdjustmentCapability.NOT_APPLICABLE, "LIVE_NSE_VALIDATION_PENDING") for family in (DataFamily.CORPORATE_FILINGS, DataFamily.CORPORATE_ACTIONS)), _provenance("nse_filings", "nse", DataFamily.CORPORATE_FILINGS)),
        DataSourceDefinition("bse_filings", "bse", "BSE primary filings boundary", tuple(_capability(family, PointInTimeCapability.SUPPORTED, AdjustmentCapability.NOT_APPLICABLE, "LIVE_BSE_VALIDATION_PENDING") for family in (DataFamily.CORPORATE_FILINGS, DataFamily.CORPORATE_ACTIONS, DataFamily.FUNDAMENTALS)), _provenance("bse_filings", "bse", DataFamily.CORPORATE_FILINGS)),
        DataSourceDefinition("future_fundamentals", "unconfigured", "Future fundamentals slot", (_capability(DataFamily.FUNDAMENTALS, PointInTimeCapability.UNKNOWN, AdjustmentCapability.NOT_APPLICABLE, "NO_FUNDAMENTAL_SOURCE_CONFIGURED"),), _provenance("future_fundamentals", "unconfigured", DataFamily.FUNDAMENTALS)),
        DataSourceDefinition("global_datafeeds", "global_datafeeds", "Global Datafeeds historical", (_capability(DataFamily.HISTORICAL_OHLCV, PointInTimeCapability.LIMITED, AdjustmentCapability.UNKNOWN, "HISTORICAL_ONLY_LIVE_VALIDATION_REQUIRED"),), _provenance("global_datafeeds", "global_datafeeds", DataFamily.HISTORICAL_OHLCV)),
        DataSourceDefinition("upstox", "upstox", "Upstox Historical Candle V3", (_capability(DataFamily.HISTORICAL_OHLCV, PointInTimeCapability.LIMITED, AdjustmentCapability.UNKNOWN, "HISTORICAL_ONLY_LIVE_VALIDATION_REQUIRED", "ADJUSTMENT_SEMANTICS_UNDOCUMENTED"),), _provenance("upstox", "upstox", DataFamily.HISTORICAL_OHLCV)),
        DataSourceDefinition("yfinance", "yfinance", "yfinance secondary research history", (_capability(DataFamily.HISTORICAL_OHLCV, PointInTimeCapability.LIMITED, AdjustmentCapability.UNKNOWN, "SECONDARY_RESEARCH_NON_AUTHORITATIVE", "CORPORATE_ACTION_INTEGRITY_PARTIAL", "LIVE_VALIDATION_REQUIRED"),), _provenance("yfinance", "yfinance", DataFamily.HISTORICAL_OHLCV)),
        DataSourceDefinition("gnews", "gnews", "GNews secondary research", (_capability(DataFamily.NEWS_RESEARCH, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, "OPTIONAL_SECONDARY_EVIDENCE", "DELAYED_SOURCE_PLAN_DEPENDENT", "DEVELOPMENT_PLAN_LIMITATIONS_POSSIBLE"),), _provenance("gnews", "gnews", DataFamily.NEWS_RESEARCH)),
        DataSourceDefinition("future_filings", "unconfigured", "Future filings slot", tuple(_capability(family, PointInTimeCapability.UNKNOWN, AdjustmentCapability.NOT_APPLICABLE, "NO_FILING_SOURCE_CONFIGURED") for family in (DataFamily.CORPORATE_FILINGS, DataFamily.CORPORATE_ACTIONS)), _provenance("future_filings", "unconfigured", DataFamily.CORPORATE_FILINGS)),
        DataSourceDefinition("future_research", "unconfigured", "Future research slot", (_capability(DataFamily.NEWS_RESEARCH, PointInTimeCapability.UNKNOWN, AdjustmentCapability.NOT_APPLICABLE, "NO_RESEARCH_SOURCE_CONFIGURED"),), _provenance("future_research", "unconfigured", DataFamily.NEWS_RESEARCH)),
        DataSourceDefinition("future_ipo", "unconfigured", "Future IPO slot", (_capability(DataFamily.IPO_PRIMARY_MARKET, PointInTimeCapability.UNKNOWN, AdjustmentCapability.NOT_APPLICABLE, "NO_IPO_SOURCE_CONFIGURED"),), _provenance("future_ipo", "unconfigured", DataFamily.IPO_PRIMARY_MARKET)),
    )


class DataSourceRegistry:
    def __init__(self, definitions: tuple[DataSourceDefinition, ...] = ()) -> None:
        self._definitions: dict[str, DataSourceDefinition] = {}
        self._priorities: dict[DataFamily, tuple[str, ...]] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: DataSourceDefinition) -> None:
        if not definition.source_id or definition.source_id in self._definitions:
            raise ValueError("Data source IDs must be non-empty and unique.")
        self._definitions[definition.source_id] = definition

    def set_priority(self, family: DataFamily, source_ids: tuple[str, ...]) -> None:
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source priority cannot repeat a source.")
        if any(source_id not in self._definitions for source_id in source_ids):
            raise ValueError("Source priority references an unknown source.")
        self._priorities[family] = source_ids

    def priority_for(self, family: DataFamily) -> tuple[str, ...]:
        return self._priorities.get(family, ())

    def definition(self, source_id: str) -> DataSourceDefinition:
        return self._definitions[source_id]


@dataclass(frozen=True, slots=True)
class SourceCompositionSettings:
    priorities: Mapping[DataFamily, tuple[str, ...]]
    provider: str = "mock"
    configured_source_ids: frozenset[str] = frozenset()

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SourceCompositionSettings":
        values = os.environ if environ is None else environ
        provider = values.get("MARKET_DATA_PROVIDER", "mock").strip().lower()
        priorities: dict[DataFamily, tuple[str, ...]] = {}
        configured: set[str] = set()
        for family in DataFamily:
            value = values.get(f"DATA_SOURCE_{family.value}_PRIORITY")
            if value is not None:
                priorities[family] = tuple(item.strip().lower() for item in value.split(",") if item.strip())
                configured.update(priorities[family])
        for family in (DataFamily.CURRENT_QUOTES, DataFamily.STREAMING_QUOTES, DataFamily.HISTORICAL_OHLCV, DataFamily.INDEX_DATA, DataFamily.VIX):
            priorities.setdefault(family, (provider,))
        historical = values.get("HISTORICAL_DATA_PROVIDER")
        if historical:
            priorities[DataFamily.HISTORICAL_OHLCV] = (historical.strip().lower(),); configured.add(historical.strip().lower())
        priorities.setdefault(DataFamily.CORPORATE_FILINGS, ("nse_filings", "bse_filings"))
        priorities.setdefault(DataFamily.CORPORATE_ACTIONS, ("nse_filings", "bse_filings"))
        priorities.setdefault(DataFamily.NEWS_RESEARCH, ("future_research",))
        if values.get("PRIMARY_MARKET_DATA_AVAILABLE", "").strip().lower() in {"1","true","yes"}:
            priorities[DataFamily.IPO_PRIMARY_MARKET] = ("stored_data", "future_ipo"); configured.add("stored_data")
        return cls(priorities, provider, frozenset(configured))


class DataSourceCompositionService:
    """Computes source readiness from supplied state without validating/fetching."""

    def __init__(self, registry: DataSourceRegistry, states: Mapping[str, SourceValidationState], *, clock=lambda: datetime.now(UTC)) -> None:
        self._registry, self._states, self._clock = registry, dict(states), clock

    @classmethod
    def from_settings(cls, settings: SourceCompositionSettings, *, states: Mapping[str, SourceValidationState] | None = None, clock=lambda: datetime.now(UTC)) -> "DataSourceCompositionService":
        registry = DataSourceRegistry(standard_source_definitions())
        for family, priority in settings.priorities.items():
            registry.set_priority(family, priority)
        default_states = {source_id: SourceValidationState(configured=source_id == settings.provider or source_id in settings.configured_source_ids, validated=source_id == "mock" and settings.provider == "mock") for source_id in ("kotak_neo", "mock", "nse_filings", "bse_filings", "global_datafeeds", "upstox", "yfinance", "gnews")}
        # Local canonical stores need no provider credential or network validation.
        default_states["stored_data"] = SourceValidationState(configured="stored_data" in settings.configured_source_ids, validated="stored_data" in settings.configured_source_ids)
        default_states.update(states or {})
        return cls(registry, default_states, clock=clock)

    def readiness(self, *, mode: RuntimeMode = RuntimeMode.STORED_DATA, requirements: Mapping[DataFamily, DataRequirement] | None = None) -> DataSourceReadinessReport:
        required = dict(requirements or {})
        items: list[DataSourceReadiness] = []
        for family in DataFamily:
            priorities = self._registry.priority_for(family)
            if not priorities:
                items.append(self._missing(family, required.get(family, DataRequirement.OPTIONAL)))
                continue
            for priority, source_id in enumerate(priorities, start=1):
                definition = self._registry.definition(source_id)
                capability = definition.capability_for(family)
                items.append(self._item(definition, capability, family, required.get(family, DataRequirement.OPTIONAL), priority, mode))
        warnings = ("MOCK_MODE_IS_EXPLICIT",) if mode is RuntimeMode.MOCK else ()
        return DataSourceReadinessReport(self._clock(), mode.value, tuple(items), warnings)

    def runtime_readiness(self, *, mode: RuntimeMode, requirements: Mapping[DataFamily, DataRequirement] | None = None) -> RuntimeSourceReadiness:
        effective = dict(requirements or {DataFamily.CURRENT_QUOTES: DataRequirement.CRITICAL, DataFamily.UNIVERSE_MEMBERSHIP: DataRequirement.CRITICAL, DataFamily.HISTORICAL_OHLCV: DataRequirement.OPTIONAL, DataFamily.FUNDAMENTALS: DataRequirement.OPTIONAL, DataFamily.CORPORATE_FILINGS: DataRequirement.OPTIONAL, DataFamily.NEWS_RESEARCH: DataRequirement.OPTIONAL, DataFamily.IPO_PRIMARY_MARKET: DataRequirement.OPTIONAL})
        report = self.readiness(mode=mode, requirements=effective)
        unavailable: list[DataFamily] = []
        optional: list[DataFamily] = []
        for family, requirement in effective.items():
            primary = report.primary(family)
            ready = primary is not None and primary.status in {SourceReadinessStatus.READY, SourceReadinessStatus.DEGRADED}
            if not ready:
                (unavailable if requirement is DataRequirement.CRITICAL else optional).append(family)
        return RuntimeSourceReadiness(mode.value, not unavailable, tuple(unavailable), tuple(optional), report, ("RUNTIME_SOURCE_REQUIREMENTS_UNMET",) if unavailable else ())

    def _item(self, definition: DataSourceDefinition, capability: SourceCapability | None, family: DataFamily, requirement: DataRequirement, priority: int, mode: RuntimeMode) -> DataSourceReadiness:
        state = self._states.get(definition.source_id, SourceValidationState(False))
        if definition.source_id == "mock" and mode is not RuntimeMode.MOCK:
            status = SourceReadinessStatus.UNAVAILABLE
        elif capability is None or capability.point_in_time is PointInTimeCapability.UNSUPPORTED:
            status = SourceReadinessStatus.UNSUPPORTED
        elif state.unavailable:
            status = SourceReadinessStatus.UNAVAILABLE
        elif state.degraded:
            status = SourceReadinessStatus.DEGRADED
        elif not state.configured:
            status = SourceReadinessStatus.MISSING_CONFIGURATION
        elif not state.validated:
            status = SourceReadinessStatus.CONFIGURED_NOT_VALIDATED
        else:
            status = SourceReadinessStatus.READY
        active = capability or _capability(family, PointInTimeCapability.UNSUPPORTED, AdjustmentCapability.UNSUPPORTED, "CAPABILITY_NOT_DECLARED")
        mock_warning = ("MOCK_SOURCE_REQUIRES_MOCK_MODE",) if definition.source_id == "mock" and mode is not RuntimeMode.MOCK else ()
        return DataSourceReadiness(definition.source_id, definition.provider, family, requirement, priority, status, state.configured, state.validated, state.last_success_at, state.last_failure_classification, active.freshness_policy, active.point_in_time, active.adjustment, tuple((*active.warnings, *state.warnings, *mock_warning)), replace(definition.provenance, family=family))

    def _missing(self, family: DataFamily, requirement: DataRequirement) -> DataSourceReadiness:
        return DataSourceReadiness(None, None, family, requirement, None, SourceReadinessStatus.MISSING_CONFIGURATION, False, False, None, None, FRESHNESS_POLICIES[family], PointInTimeCapability.UNKNOWN, AdjustmentCapability.UNKNOWN, ("NO_SOURCE_PRIORITY_CONFIGURED",), None)


__all__ = ("DataFamily", "DataSourceCompositionService", "DataSourceRegistry", "FundamentalFactKind", "SourceCompositionSettings", "SourceReadinessStatus", "SourceValidationState", "standard_source_definitions")
