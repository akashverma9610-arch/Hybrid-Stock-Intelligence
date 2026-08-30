"""Stored-only bridge from current Top-3 membership to official NSE delivery.

This deliberately composes the existing PreBreakoutEngine; it does not alter
strategy rules or initiate market-data access.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.market_data.nse_delivery import NseDeliveryStore
from app.market_data.models import Timeframe
from app.market_data.bridge import price_bar_observation
from app.domain.models import AsOfSnapshot, StrategyVersionReference
from app.analysis.models import AnalysisStatus
from app.analysis.technical import TechnicalAnalysisEngine
from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from app.strategies.pre_breakout.service import PreBreakoutConfig, PreBreakoutEngine, PreBreakoutInput
from app.market_data.current_sector_rotation import CurrentSectorRelativeStrength


@dataclass(frozen=True, slots=True)
class CurrentPreBreakoutDelivery:
    instrument_id: str
    symbol: str
    sector: str
    ohlcv_ready: bool
    delivery_status: str
    delivery_pct: Decimal | None
    trade_date: datetime | None
    availability_at: datetime | None
    source_artifact_id: str | None
    canonical_sessions: int
    latest_close: Decimal | None
    bbw_percentile: Decimal | None
    atr: Decimal | None
    rsi14: Decimal | None
    setup_status: str
    missing_inputs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurrentPreBreakoutReport:
    as_of: datetime
    top3: tuple[str, ...]
    rows: tuple[CurrentPreBreakoutDelivery, ...]
    canonical_sector_count: int
    excluded_sectors: tuple[CurrentSectorRelativeStrength, ...]

    @property
    def distinct_top3_stocks(self) -> int: return len(self.rows)
    @property
    def ohlcv_ready(self) -> int: return sum(item.ohlcv_ready for item in self.rows)
    @property
    def delivery_ready(self) -> int: return sum(item.delivery_pct is not None for item in self.rows)
    @property
    def delivery_pass(self) -> int: return sum(item.delivery_status == "PASS" for item in self.rows)


class CurrentPreBreakoutService:
    def __init__(self, *, rotation_service, delivery_store: NseDeliveryStore, historical_store, clock) -> None:
        self._rotation, self._delivery, self._historical, self._clock = rotation_service, delivery_store, historical_store, clock

    def assess(self) -> CurrentPreBreakoutReport:
        as_of = self._clock()
        rotation = self._rotation.assess()
        top3 = set(rotation.top3)
        coverage = {item.instrument_id: item for item in rotation.coverage if item.instrument_id}
        values = [item for item in rotation.constituents if item.sector in top3 and item.instrument_id]
        unique = {item.instrument_id: item for item in values}
        rows = []
        for instrument_id, item in sorted(unique.items(), key=lambda pair: (pair[1].sector, pair[1].symbol)):
            conflicted = self._historical.has_conflict_artifact(instrument_id)
            observation = self._delivery.latest_official_delivery(instrument_id, as_of=as_of)
            status = "OHLCV_CONFLICTED" if conflicted else ("MISSING" if observation is None else ("PASS" if observation.delivery_percentage > PreBreakoutConfig().delivery_pct_min else "FAIL"))
            features = self._features(instrument_id, as_of) if status == "PASS" else (0, None, None, None, None)
            candidate = PreBreakoutEngine().evaluate(PreBreakoutInput(
                candidate_id=f"current-prebreakout:{instrument_id}:{as_of.date().isoformat()}", instrument_id=instrument_id,
                sector=item.sector, scan_as_of=as_of, universe_snapshot_id="CURRENT_FORWARD_MEMBERSHIP",
                evidence_ids=(observation.observation_id,) if observation else (), bbw_percentile=None, atr_recent=(), atr_prior=(),
                consolidation_volumes=(), volume_sma20=None, delivery_pct=observation.delivery_percentage if observation else None,
                price=None, high_52_week=None, rsi14=None, structural_resistance=None, structural_invalidation=None, realistic_target=None,
            ), config=PreBreakoutConfig())
            missing = tuple(sorted(set((*candidate.warnings, *(("OHLCV_CONFLICTED",) if conflicted else ())))))
            rows.append(CurrentPreBreakoutDelivery(instrument_id, item.symbol, item.sector, bool(coverage.get(instrument_id) and coverage[instrument_id].at_least_320 and not conflicted), status,
                observation.delivery_percentage if observation else None, observation.trade_date if observation else None,
                observation.available_at if observation else None, observation.report_id if observation else None, *features, candidate.status.value, missing))
        return CurrentPreBreakoutReport(
            as_of, tuple(rotation.top3), tuple(rows), len(rotation.relative_strength),
            tuple(item for item in rotation.relative_strength if item.exclusion_reason is not None),
        )

    def _features(self, instrument_id: str, as_of: datetime):
        bars = self._historical.range(instrument_id, Timeframe.DAILY, datetime(1970, 1, 1, tzinfo=as_of.tzinfo), as_of, as_of=as_of)
        if not bars: return (0, None, None, None, None)
        validator = ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: __import__('datetime').timedelta(days=3650)}, __import__('datetime').timedelta(days=3650))))
        observations = tuple(price_bar_observation(bar).with_validation(validator.validate(price_bar_observation(bar), evaluated_timestamp=bar.provenance.received_at)) for bar in bars)
        snapshot = AsOfSnapshot(f"current-prebreakout:{instrument_id}:{as_of.isoformat()}", as_of, as_of, "CURRENT_STORED_ONLY", observations)
        engine = TechnicalAnalysisEngine(); ref = StrategyVersionReference("pre-breakout", PreBreakoutConfig().version)
        bbw = engine.bollinger_band_width_percentile(snapshot, instrument_id=instrument_id, strategy_version=ref, evaluated_at=as_of, history_sessions=PreBreakoutConfig().bbw_history_sessions)
        atr = engine.atr(snapshot, instrument_id=instrument_id, strategy_version=ref, evaluated_at=as_of, period=14)
        rsi = engine.rsi(snapshot, instrument_id=instrument_id, strategy_version=ref, evaluated_at=as_of, period=14)
        value = lambda result: Decimal(str(result.value)) if result.status is AnalysisStatus.VALID and result.value is not None else None
        return (len(bars), bars[-1].close, value(bbw), value(atr), value(rsi))

    @staticmethod
    def write_reports(report: CurrentPreBreakoutReport, directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        json_path, csv_path = directory / "current_prebreakout_scan.json", directory / "current_prebreakout_scan.csv"
        json_path.write_text(json.dumps(asdict(report), default=str, indent=2, sort_keys=True), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=tuple(asdict(report.rows[0])) if report.rows else ("instrument_id", "symbol", "sector", "ohlcv_ready", "delivery_status", "delivery_pct", "trade_date", "availability_at", "source_artifact_id", "setup_status", "missing_inputs"))
            writer.writeheader(); writer.writerows(asdict(item) for item in report.rows)
        # Keep U09's delivery-gate artifact as an exact compatibility copy.
        (directory / "top3_delivery_gate_status.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        (directory / "top3_delivery_gate_status.csv").write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
        return json_path, csv_path
