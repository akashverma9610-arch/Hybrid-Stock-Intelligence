"""Immutable, versioned read snapshots for the core FastAPI data families."""
from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any, Protocol
from collections.abc import Mapping


class CoreApiSnapshotFamily(StrEnum):
    PORTFOLIO = "PORTFOLIO"
    SIGNAL = "SIGNAL"
    PAPER_TRADE = "PAPER_TRADE"
    PERFORMANCE_REPORT = "PERFORMANCE_REPORT"
    BENCHMARK_COMPARISON = "BENCHMARK_COMPARISON"
    MARKET_REGIME = "MARKET_REGIME"
    SECTOR_ANALYSIS = "SECTOR_ANALYSIS"
    STOCK_ANALYSIS = "STOCK_ANALYSIS"
    CAPITAL_ROTATION = "CAPITAL_ROTATION"
    PROMOTION_PROPOSAL = "PROMOTION_PROPOSAL"
    PROMOTION_ELIGIBILITY = "PROMOTION_ELIGIBILITY"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    STRATEGY_ACTIVATION = "STRATEGY_ACTIVATION"
    STRATEGY_ROLLBACK = "STRATEGY_ROLLBACK"
    APPROVED_STRATEGY_VERSION = "APPROVED_STRATEGY_VERSION"
    CRISIS_ASSESSMENT = "CRISIS_ASSESSMENT"
    CRISIS_EVENT = "CRISIS_EVENT"
    PAPER_TRADE_CRISIS_CONTEXT = "PAPER_TRADE_CRISIS_CONTEXT"
    UPSIDE_EXCESS_ASSESSMENT = "UPSIDE_EXCESS_ASSESSMENT"
    MARKET_EXTREME_EVENT = "MARKET_EXTREME_EVENT"
    PAPER_TRADE_UPSIDE_EXTREME_CONTEXT = "PAPER_TRADE_UPSIDE_EXTREME_CONTEXT"
    PORTFOLIO_ANALYSIS_JOB = "PORTFOLIO_ANALYSIS_JOB"
    NSE_UNIVERSE = "NSE_UNIVERSE"
    UNIVERSE_ANALYSIS_JOB = "UNIVERSE_ANALYSIS_JOB"
    UNIVERSE_OPPORTUNITY = "UNIVERSE_OPPORTUNITY"
    UNIVERSE_ANALYSIS_ITEM = "UNIVERSE_ANALYSIS_ITEM"
    UNIVERSE_SNAPSHOT = "UNIVERSE_SNAPSHOT"
    UNIVERSE_CANDIDATE = "UNIVERSE_CANDIDATE"
    PORTFOLIO_UNIVERSE_ROTATION = "PORTFOLIO_UNIVERSE_ROTATION"
    UNIVERSE_COVERAGE = "UNIVERSE_COVERAGE"
    PROVIDER_INSTRUMENT_MAPPING = "PROVIDER_INSTRUMENT_MAPPING"
    CANONICAL_QUOTE = "CANONICAL_QUOTE"
    # Daily official index levels are close-only evidence.  They deliberately
    # do not share the OHLCV bar family because the source can truthfully omit
    # open/high/low while still being suitable for relative-strength work.
    OFFICIAL_INDEX_CLOSE_ARTIFACT = "OFFICIAL_INDEX_CLOSE_ARTIFACT"
    CANONICAL_INDEX_CLOSE_OBSERVATION = "CANONICAL_INDEX_CLOSE_OBSERVATION"
    CURRENT_SECTOR_RANKING = "CURRENT_SECTOR_RANKING"
    TOP3_OPPORTUNITY_FINDER_RUN = "TOP3_OPPORTUNITY_FINDER_RUN"
    GOVERNANCE_DRIFT_OBSERVATION = "GOVERNANCE_DRIFT_OBSERVATION"
    GOVERNANCE_ASSESSMENT = "GOVERNANCE_ASSESSMENT"
    DECISION_AUDIT_RECORD = "DECISION_AUDIT_RECORD"
    DECISION_OUTCOME_LINK = "DECISION_OUTCOME_LINK"
    SELL_SIDE_DECISION = "SELL_SIDE_DECISION"
    RECONCILIATION_RESULT = "RECONCILIATION_RESULT"
    EVIDENCE_COVERAGE = "EVIDENCE_COVERAGE"
    EXECUTION_SIMULATION = "EXECUTION_SIMULATION"
    CALIBRATION_OBSERVATION = "CALIBRATION_OBSERVATION"
    ROTATION_HURDLE = "ROTATION_HURDLE"
    PORTFOLIO_FACTOR_EXPOSURE = "PORTFOLIO_FACTOR_EXPOSURE"
    REGIME_VALIDATION = "REGIME_VALIDATION"
    NEWS_EVENT_CLUSTER = "NEWS_EVENT_CLUSTER"
    AI_AUDIT_METADATA = "AI_AUDIT_METADATA"
    EMERGENCY_DEFENSIVE_MODE = "EMERGENCY_DEFENSIVE_MODE"
    MACRO_EVIDENCE = "MACRO_EVIDENCE"
    MACRO_STATE = "MACRO_STATE"
    ECONOMIC_REGIME = "ECONOMIC_REGIME"
    SECTOR_ECONOMIC_IMPACT = "SECTOR_ECONOMIC_IMPACT"
    COMPANY_SENSITIVITY_PROFILE = "COMPANY_SENSITIVITY_PROFILE"
    MACRO_EARNINGS_TRANSMISSION = "MACRO_EARNINGS_TRANSMISSION"
    CATALYST_EVENT = "CATALYST_EVENT"
    PRE_BREAKOUT_CONFIG = "PRE_BREAKOUT_CONFIG"
    PRE_BREAKOUT_SECTOR_SCAN = "PRE_BREAKOUT_SECTOR_SCAN"
    PRE_BREAKOUT_CANDIDATE = "PRE_BREAKOUT_CANDIDATE"
    INFLECTION_CONFIG = "INFLECTION_CONFIG"
    INFLECTION_CANDIDATE = "INFLECTION_CANDIDATE"
    STRATEGY_SETUP_QUALITY = "STRATEGY_SETUP_QUALITY"
    STRATEGY_OUTCOME_ATTRIBUTION = "STRATEGY_OUTCOME_ATTRIBUTION"
    TAXONOMY_CLASSIFICATION = "TAXONOMY_CLASSIFICATION"
    NSE_INDICES_TAXONOMY_SOURCE = "NSE_INDICES_TAXONOMY_SOURCE"
    NSE_SECTOR_INDEX_SOURCE = "NSE_SECTOR_INDEX_SOURCE"
    NSE_SECTOR_INDEX_REGISTRY = "NSE_SECTOR_INDEX_REGISTRY"
    NSE_SECTOR_INDEX_MAPPING = "NSE_SECTOR_INDEX_MAPPING"
    NSE_SECTOR_INDEX_CONSTITUENT = "NSE_SECTOR_INDEX_CONSTITUENT"
    NSE_DELIVERY_REPORT = "NSE_DELIVERY_REPORT"
    NSE_DELIVERY_OBSERVATION = "NSE_DELIVERY_OBSERVATION"
    THEME_MEMBERSHIP = "THEME_MEMBERSHIP"
    DATA_COVERAGE_RECORD = "DATA_COVERAGE_RECORD"
    DATA_COVERAGE_SUMMARY = "DATA_COVERAGE_SUMMARY"
    HISTORICAL_SECURITY_IDENTITY = "HISTORICAL_SECURITY_IDENTITY"
    # Primary exchange lifecycle documents are retained separately from the
    # identities they may (or may not) link.  An unlinked BSE notice is still
    # auditable evidence; it must never be promoted by a name match.
    HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE = "HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE"
    # Date-labelled NSE MII security-master artifacts are immutable snapshot
    # evidence.  They are deliberately separate from PIT-eligible identity
    # receipts: the public report supplies a session date, not a verifiable
    # publication timestamp.
    HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT = "HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT"
    # Human-approved, exact NSE session-point observations.  These are not
    # HistoricalSecurityIdentity intervals and cannot establish lifecycle.
    HISTORICAL_NSE_SESSION_IDENTITY = "HISTORICAL_NSE_SESSION_IDENTITY"
    # Exact, source-dated legal-entity evidence and its session-scoped
    # security bridges.  These are intentionally distinct from both the
    # NSE security receipt and a future issuer/company master.
    HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE = "HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE"
    # Non-active, immutable BRSR-to-exact-MII anchor readiness receipts. They
    # retain primary source lineage only and are not issuer bridges or forward
    # continuity observations.
    HISTORICAL_ISSUER_ANCHOR_EVIDENCE = "HISTORICAL_ISSUER_ANCHOR_EVIDENCE"
    HISTORICAL_ISSUER_SECURITY_BRIDGE = "HISTORICAL_ISSUER_SECURITY_BRIDGE"
    # Immutable primary regulator records used only to establish future
    # company-type evidence readiness.  This family is not a company-type
    # classification, issuer master, or policy-activation store.
    HISTORICAL_REGULATOR_ENTITY_EVIDENCE = "HISTORICAL_REGULATOR_ENTITY_EVIDENCE"
    HISTORICAL_UNIVERSE_MEMBERSHIP = "HISTORICAL_UNIVERSE_MEMBERSHIP"
    HISTORICAL_CORPORATE_ACTION = "HISTORICAL_CORPORATE_ACTION"
    HISTORICAL_PRICE_INTEGRITY = "HISTORICAL_PRICE_INTEGRITY"
    REAL_BRAIN_TRIAL = "REAL_BRAIN_TRIAL"
    REAL_BRAIN_STOCK_RESULT = "REAL_BRAIN_STOCK_RESULT"
    FUNDAMENTAL_BRAIN_PROBE = "FUNDAMENTAL_BRAIN_PROBE"
    YAHOO_SECONDARY_ENRICHMENT = "YAHOO_SECONDARY_ENRICHMENT"
    EVIDENCE_REFRESH_RUN = "EVIDENCE_REFRESH_RUN"
    EVIDENCE_REFRESH_WATERMARK = "EVIDENCE_REFRESH_WATERMARK"
    EVIDENCE_RECONCILIATION_FINDING = "EVIDENCE_RECONCILIATION_FINDING"
    FORWARD_PAPER_STUDY = "FORWARD_PAPER_STUDY"
    FORWARD_PAPER_EVENT = "FORWARD_PAPER_EVENT"
    FORWARD_PAPER_RUN = "FORWARD_PAPER_RUN"
    FORWARD_PAPER_PERFORMANCE_EVIDENCE = "FORWARD_PAPER_PERFORMANCE_EVIDENCE"
    FORWARD_PAPER_EXECUTABLE_SETUP = "FORWARD_PAPER_EXECUTABLE_SETUP"
    GOVERNED_EXECUTABLE_SETUP_SOURCE_RUN = "GOVERNED_EXECUTABLE_SETUP_SOURCE_RUN"
    CANONICAL_SETUP_OPPORTUNITY = "CANONICAL_SETUP_OPPORTUNITY"
    CANONICAL_PORTFOLIO_SETUP_RUN = "CANONICAL_PORTFOLIO_SETUP_RUN"
    PRODUCTION_V1_READINESS_REPORT = "PRODUCTION_V1_READINESS_REPORT"
    PRODUCTION_V1_CYCLE_RUN = "PRODUCTION_V1_CYCLE_RUN"
    SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT = "SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT"
    OWNERSHIP_RAW_FACT = "OWNERSHIP_RAW_FACT"
    OWNERSHIP_OBSERVATION = "OWNERSHIP_OBSERVATION"
    RELIABILITY_INTEGRITY_OBSERVATION = "RELIABILITY_INTEGRITY_OBSERVATION"
    MARKET_WIDE_QUALITY_INFLECTION_WATCH = "MARKET_WIDE_QUALITY_INFLECTION_WATCH"
    # Immutable operational receipts for the bounded official-BSE NIFTY 500
    # financial acquisition coordinator.  This is deliberately separate from
    # both canonical filings/facts and generic evidence-refresh records.
    BSE_FINANCIAL_ACQUISITION = "BSE_FINANCIAL_ACQUISITION"


@dataclass(frozen=True, slots=True)
class CoreApiSnapshot:
    snapshot_id: str
    family: CoreApiSnapshotFamily
    schema_version: str
    record_type: str
    fingerprint: str
    created_at: datetime
    payload: Any


class CoreApiSnapshotRepository(Protocol):
    def save_snapshot(self, value: CoreApiSnapshot) -> None: ...
    def get_snapshot(self, snapshot_id: str) -> CoreApiSnapshot | None: ...
    def list_snapshots(self, family: CoreApiSnapshotFamily, *, limit: int = 100, offset: int = 0) -> tuple[CoreApiSnapshot, ...]: ...


def snapshot_dump(value: CoreApiSnapshot) -> dict[str, Any]:
    return {
        "snapshot_id": value.snapshot_id, "family": value.family.value,
        "schema_version": value.schema_version, "record_type": value.record_type,
        "fingerprint": value.fingerprint, "created_at": _encode(value.created_at),
        "payload": _encode(value.payload),
    }


def snapshot_from(value: dict[str, Any]) -> CoreApiSnapshot:
    if value.get("schema_version") != "v1":
        raise ValueError("Unsupported core API snapshot schema version.")
    return CoreApiSnapshot(
        snapshot_id=value["snapshot_id"], family=CoreApiSnapshotFamily(value["family"]),
        schema_version=value["schema_version"], record_type=value["record_type"],
        fingerprint=value["fingerprint"], created_at=_decode(value["created_at"]), payload=_decode(value["payload"]),
    )


def snapshot_json(value: CoreApiSnapshot) -> str:
    return json.dumps(snapshot_dump(value), sort_keys=True, separators=(",", ":"))


def snapshot_json_from(value: str | dict[str, Any]) -> CoreApiSnapshot:
    return snapshot_from(json.loads(value) if isinstance(value, str) else value)


def _encode(value: Any) -> Any:
    if isinstance(value, datetime): return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, date): return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal): return {"$type": "decimal", "value": str(value)}
    if isinstance(value, Enum): return {"$type": "enum", "class": _path(type(value)), "value": value.value}
    if is_dataclass(value): return {"$type": "dataclass", "class": _path(type(value)), "fields": {item.name: _encode(getattr(value, item.name)) for item in fields(value)}}
    if isinstance(value, tuple): return {"$type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, list): return [_encode(item) for item in value]
    if isinstance(value, Mapping): return {"$type": "dict", "items": [[str(key), _encode(item)] for key, item in value.items()]}
    return value


def _decode(value: Any) -> Any:
    if not isinstance(value, dict): return [_decode(item) for item in value] if isinstance(value, list) else value
    kind = value.get("$type")
    if kind == "datetime": return datetime.fromisoformat(value["value"])
    if kind == "date": return date.fromisoformat(value["value"])
    if kind == "decimal": return Decimal(value["value"])
    if kind == "tuple": return tuple(_decode(item) for item in value["items"])
    if kind == "dict": return {key: _decode(item) for key, item in value["items"]}
    if kind == "enum": return _load(value["class"])(value["value"])
    if kind == "dataclass": return _load(value["class"])(**{key: _decode(item) for key, item in value["fields"].items()})
    return {key: _decode(item) for key, item in value.items()}


def _path(value: type) -> str: return f"{value.__module__}:{value.__qualname__}"
def _load(value: str) -> type:
    module_name, qualname = value.split(":", 1)
    if not module_name.startswith("app."):
        raise ValueError("Unsupported core API snapshot payload type.")
    target: Any = importlib.import_module(module_name)
    for part in qualname.split("."): target = getattr(target, part)
    return target
