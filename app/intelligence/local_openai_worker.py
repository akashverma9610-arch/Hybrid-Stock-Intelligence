"""Opt-in local OpenAI monitoring worker for the existing intelligence intake.

The worker owns only a small delivery ledger.  HSI's authenticated V1C intake
remains the sole canonical store for events and evidence.  It intentionally has
no application-startup hook, trading capability, or general HTTP client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from time import sleep
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.api.schemas.intelligence import ExternalIntelligenceEventRequest
from app.intelligence.external_intelligence_live_connector import (
    DeliveryStatus,
    DeskDeliveryReceipt,
    ExternalIntelligenceLiveConnector,
    INGEST_TOKEN_ENVIRONMENT_KEY,
)


OPENAI_API_KEY_ENVIRONMENT_KEY = "OPENAI_API_KEY"
OPENAI_MODEL_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_OPENAI_MODEL"
WORKER_ENABLED_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_LOCAL_WORKER_ENABLED"
LOCAL_HSI_ORIGIN = "http://127.0.0.1:8000"
DEFAULT_MODEL = "gpt-5.4-mini"
MINIMUM_INTERVAL_SECONDS = 60 * 60
MAX_QUALIFIED_EVENTS_PER_RUN = 1
NO_NEW_MATERIAL_INTELLIGENCE = "NO_NEW_MATERIAL_INTELLIGENCE"


HSI_EXTERNAL_INTELLIGENCE_DESK_MASTER_DIRECTIVE = """\
You are the HSI External Intelligence Desk. Apply the existing HSI policy, not
a new policy: be change-first and primary-source-first; use Web Search for
discovery and verification; deduplicate; filter for materiality; preserve the
distinction between FACT, DATA, INTERPRETATION, and INFERENCE; retain policy
maturity and causal transmission; and never make a BUY, SELL, broker, cash, or
portfolio instruction. Monitor Government/PIB/Gazette, RBI/SEBI, policy and
regulation, global central banks, geopolitics, commodities, sectors,
NSE/BSE/company announcements, orders, capex, M&A, guidance, and material
earnings/news.

Return at most one qualified material event. If nothing qualifies, return an
object with outcome NO_NEW_MATERIAL_INTELLIGENCE and event null. Otherwise
return outcome QUALIFIED_EVENT and a complete event that conforms exactly to
the HSI External Intelligence V1C request schema. Use a stable
producer_event_id for the same primary-source event. Do not include secrets.
"""


class LocalWorkerConfigurationError(ValueError):
    """Safe configuration failure that never contains a credential."""


class OpenAIResponsesError(RuntimeError):
    """A safe upstream failure; the worker never persists raw model responses."""


class LocalWorkerRunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    NO_MATERIAL = NO_NEW_MATERIAL_INTELLIGENCE
    OPENAI_FAILURE = "OPENAI_FAILURE"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class LocalOpenAIWorkerSettings:
    enabled: bool = False
    interval_seconds: int = MINIMUM_INTERVAL_SECONDS
    model: str = DEFAULT_MODEL
    maximum_qualified_events: int = MAX_QUALIFIED_EVENTS_PER_RUN

    def __post_init__(self) -> None:
        if self.interval_seconds < MINIMUM_INTERVAL_SECONDS:
            raise LocalWorkerConfigurationError("Local intelligence worker interval must be at least one hour.")
        if self.maximum_qualified_events != MAX_QUALIFIED_EVENTS_PER_RUN:
            raise LocalWorkerConfigurationError("Local intelligence worker permits exactly one qualified event per run.")
        if not self.model.strip():
            raise LocalWorkerConfigurationError("OpenAI intelligence model is not configured.")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "LocalOpenAIWorkerSettings":
        source = os.environ if environ is None else environ
        enabled = _environment_bool(source.get(WORKER_ENABLED_ENVIRONMENT_KEY, "false"))
        raw_interval = source.get("HSI_EXTERNAL_INTELLIGENCE_LOCAL_WORKER_INTERVAL_SECONDS", str(MINIMUM_INTERVAL_SECONDS))
        try:
            interval = int(raw_interval)
        except ValueError as error:
            raise LocalWorkerConfigurationError("Local intelligence worker interval must be an integer.") from error
        return cls(enabled=enabled, interval_seconds=interval, model=source.get(OPENAI_MODEL_ENVIRONMENT_KEY, DEFAULT_MODEL))


@dataclass(frozen=True, slots=True)
class ResponsesResult:
    output_text: str
    sources_searched_count: int


class ResponsesClient(Protocol):
    def discover(self, *, model: str, instructions: str, input_text: str, response_schema: Mapping[str, object]) -> ResponsesResult: ...


class IntelligenceDeliveryConnector(Protocol):
    def ingest_intelligence_event(self, event: Mapping[str, object]) -> DeskDeliveryReceipt: ...


class OpenAIResponsesWebSearchClient:
    """Minimal, fixed-purpose Responses API client with built-in Web Search only."""

    _endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str, timeout_seconds: float = 30.0) -> None:
        if not api_key.strip():
            raise LocalWorkerConfigurationError("OpenAI API credential is not configured.")
        if not 0 < timeout_seconds <= 60:
            raise LocalWorkerConfigurationError("OpenAI response timeout must be between 0 and 60 seconds.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "OpenAIResponsesWebSearchClient":
        source = os.environ if environ is None else environ
        api_key = source.get(OPENAI_API_KEY_ENVIRONMENT_KEY)
        if not api_key:
            raise LocalWorkerConfigurationError("OpenAI API credential is not configured.")
        return cls(api_key=api_key)

    def discover(self, *, model: str, instructions: str, input_text: str, response_schema: Mapping[str, object]) -> ResponsesResult:
        body = json.dumps({
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "tools": [{"type": "web_search"}],
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
            "max_tool_calls": 8,
            "max_output_tokens": 8_000,
            "store": False,
            "text": {"format": {
                "type": "json_schema", "name": "hsi_external_intelligence_worker_result",
                "strict": False, "schema": response_schema,
            }},
        }, separators=(",", ":")).encode("utf-8")
        request = Request(self._endpoint, data=body, method="POST", headers={
            "Authorization": "Bearer " + self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310: constant OpenAI endpoint
                document = _json_object(response.read())
        except HTTPError as error:
            raise OpenAIResponsesError("OpenAI Responses request was rejected.") from error
        except (OSError, URLError) as error:
            raise OpenAIResponsesError("OpenAI Responses service is unavailable.") from error
        output_text = _response_output_text(document)
        if output_text is None:
            raise OpenAIResponsesError("OpenAI Responses result did not contain structured output text.")
        return ResponsesResult(output_text, _web_search_source_count(document))


class _WorkerResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str
    event: dict[str, object] | None

    @model_validator(mode="after")
    def validate_outcome(self) -> "_WorkerResultModel":
        if self.outcome == NO_NEW_MATERIAL_INTELLIGENCE and self.event is None:
            return self
        if self.outcome == "QUALIFIED_EVENT" and self.event is not None:
            return self
        raise ValueError("Worker result must be a no-material result or one qualified V1C event.")


@dataclass(frozen=True, slots=True)
class WorkerDiscovery:
    no_material: bool
    event: dict[str, object] | None
    sources_searched_count: int


@dataclass(frozen=True, slots=True)
class LocalWorkerRunReport:
    run_id: str
    status: LocalWorkerRunStatus
    started_at: datetime
    completed_at: datetime
    sources_searched_count: int
    candidates_considered: int
    qualified_events: int
    delivered: int
    pending: int
    duplicates: int
    rejected: int
    failure_code: str | None


class LocalOpenAIWorkerStateStore:
    """Delivery metadata only: run receipt, semantic fingerprints, and pending payloads."""

    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(Path(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS local_openai_worker_runs (
                run_id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL, sources_searched_count INTEGER NOT NULL,
                candidates_considered INTEGER NOT NULL, qualified_events INTEGER NOT NULL,
                delivered INTEGER NOT NULL, pending INTEGER NOT NULL, duplicates INTEGER NOT NULL,
                rejected INTEGER NOT NULL, failure_code TEXT
            );
            CREATE TABLE IF NOT EXISTS local_openai_worker_seen_events (
                event_fingerprint TEXT PRIMARY KEY, producer_event_id TEXT NOT NULL,
                delivered_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS local_openai_worker_seen_sources (
                source_fingerprint TEXT PRIMARY KEY, event_fingerprint TEXT NOT NULL,
                FOREIGN KEY(event_fingerprint) REFERENCES local_openai_worker_seen_events(event_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS local_openai_worker_pending_delivery (
                event_fingerprint TEXT PRIMARY KEY, producer_event_id TEXT NOT NULL,
                payload_json TEXT NOT NULL, failure_code TEXT NOT NULL, attempts INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def has_seen_event(self, fingerprint: str) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM local_openai_worker_seen_events WHERE event_fingerprint = ?", (fingerprint,),
        ).fetchone() is not None

    def pending_events(self) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            "SELECT payload_json FROM local_openai_worker_pending_delivery ORDER BY updated_at, event_fingerprint LIMIT ?",
            (MAX_QUALIFIED_EVENTS_PER_RUN,),
        ).fetchall()
        return tuple(json.loads(row["payload_json"]) for row in rows)

    def remember_delivered(self, event: Mapping[str, object], *, delivered_at: datetime) -> None:
        fingerprint = event_fingerprint(event)
        producer_event_id = _producer_event_id(event)
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO local_openai_worker_seen_events(event_fingerprint, producer_event_id, delivered_at) VALUES (?, ?, ?)",
                (fingerprint, producer_event_id, delivered_at.isoformat()),
            )
            self._connection.execute("DELETE FROM local_openai_worker_pending_delivery WHERE event_fingerprint = ?", (fingerprint,))
            for source_fingerprint in source_fingerprints(event):
                self._connection.execute(
                    "INSERT OR IGNORE INTO local_openai_worker_seen_sources(source_fingerprint, event_fingerprint) VALUES (?, ?)",
                    (source_fingerprint, fingerprint),
                )

    def remember_pending(self, event: Mapping[str, object], *, failure_code: str, updated_at: datetime) -> None:
        fingerprint = event_fingerprint(event)
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
        with self._connection:
            self._connection.execute("""
                INSERT INTO local_openai_worker_pending_delivery(event_fingerprint, producer_event_id, payload_json, failure_code, attempts, updated_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(event_fingerprint) DO UPDATE SET
                    failure_code = excluded.failure_code, attempts = attempts + 1, updated_at = excluded.updated_at
            """, (fingerprint, _producer_event_id(event), payload, failure_code, updated_at.isoformat()))

    def record_run(self, value: LocalWorkerRunReport) -> None:
        with self._connection:
            self._connection.execute("""
                INSERT INTO local_openai_worker_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                value.run_id, value.status.value, value.started_at.isoformat(), value.completed_at.isoformat(),
                value.sources_searched_count, value.candidates_considered, value.qualified_events,
                value.delivered, value.pending, value.duplicates, value.rejected, value.failure_code,
            ))

    def previous_successful_run(self) -> LocalWorkerRunReport | None:
        row = self._connection.execute("""
            SELECT * FROM local_openai_worker_runs WHERE status IN (?, ?) ORDER BY completed_at DESC LIMIT 1
        """, (LocalWorkerRunStatus.COMPLETED.value, LocalWorkerRunStatus.NO_MATERIAL.value)).fetchone()
        return _report_from_row(row) if row else None


class LocalOpenAIIntelligenceWorker:
    """Foreground-only worker. A caller must explicitly opt in to every cadence."""

    def __init__(
        self, *, state: LocalOpenAIWorkerStateStore, responses: ResponsesClient,
        connector: IntelligenceDeliveryConnector, settings: LocalOpenAIWorkerSettings | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._state = state
        self._responses = responses
        self._connector = connector
        self._settings = settings or LocalOpenAIWorkerSettings()
        self._clock = clock or (lambda: datetime.now(UTC))

    def run_once(self) -> LocalWorkerRunReport:
        started_at = _aware_utc(self._clock())
        run_id = "local-openai-" + started_at.strftime("%Y%m%dT%H%M%S%fZ")
        if not self._settings.enabled:
            return self._finish(run_id, LocalWorkerRunStatus.DISABLED, started_at, failure_code="WORKER_DISABLED")

        delivered = pending = duplicates = rejected = 0
        for pending_event in self._state.pending_events():
            receipt = self._connector.ingest_intelligence_event(pending_event)
            if receipt.delivery_status is DeliveryStatus.DELIVERED:
                self._state.remember_delivered(pending_event, delivered_at=_aware_utc(self._clock()))
                delivered += 1
            else:
                self._state.remember_pending(pending_event, failure_code=receipt.failure_code or "HSI_DELIVERY_FAILED", updated_at=_aware_utc(self._clock()))
                pending += 1
            return self._finish(run_id, LocalWorkerRunStatus.COMPLETED, started_at, delivered=delivered, pending=pending)

        try:
            result = self._responses.discover(
                model=self._settings.model, instructions=HSI_EXTERNAL_INTELLIGENCE_DESK_MASTER_DIRECTIVE,
                input_text=_worker_input(self._state.previous_successful_run()), response_schema=worker_response_schema(),
            )
        except OpenAIResponsesError:
            return self._finish(run_id, LocalWorkerRunStatus.OPENAI_FAILURE, started_at, rejected=1, failure_code="OPENAI_RESPONSES_UNAVAILABLE")

        try:
            discovery = parse_worker_discovery(result)
        except ValidationError:
            return self._finish(run_id, LocalWorkerRunStatus.INVALID_MODEL_OUTPUT, started_at, sources=result.sources_searched_count, rejected=1, failure_code="INVALID_MODEL_OUTPUT")
        if discovery.no_material:
            return self._finish(run_id, LocalWorkerRunStatus.NO_MATERIAL, started_at, sources=discovery.sources_searched_count)

        assert discovery.event is not None
        fingerprint = event_fingerprint(discovery.event)
        if self._state.has_seen_event(fingerprint):
            return self._finish(run_id, LocalWorkerRunStatus.COMPLETED, started_at, sources=discovery.sources_searched_count, candidates=1, duplicates=1)
        receipt = self._connector.ingest_intelligence_event(discovery.event)
        if receipt.delivery_status is DeliveryStatus.DELIVERED:
            self._state.remember_delivered(discovery.event, delivered_at=_aware_utc(self._clock()))
            delivered = 1
        else:
            self._state.remember_pending(discovery.event, failure_code=receipt.failure_code or "HSI_DELIVERY_FAILED", updated_at=_aware_utc(self._clock()))
            pending = 1
        return self._finish(
            run_id, LocalWorkerRunStatus.COMPLETED, started_at, sources=discovery.sources_searched_count,
            candidates=1, qualified=1, delivered=delivered, pending=pending,
        )

    def run_forever(self, *, stop_event: Event | None = None, max_cycles: int | None = None, wait: Callable[[float], None] = sleep) -> int:
        if not self._settings.enabled:
            return 0
        cycles = 0
        stopper = stop_event or Event()
        while not stopper.is_set() and (max_cycles is None or cycles < max_cycles):
            self.run_once()
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                wait(self._settings.interval_seconds)
        return cycles

    def _finish(self, run_id: str, status: LocalWorkerRunStatus, started_at: datetime, *, sources: int = 0, candidates: int = 0, qualified: int = 0, delivered: int = 0, pending: int = 0, duplicates: int = 0, rejected: int = 0, failure_code: str | None = None) -> LocalWorkerRunReport:
        report = LocalWorkerRunReport(run_id, status, started_at, _aware_utc(self._clock()), sources, candidates, qualified, delivered, pending, duplicates, rejected, failure_code)
        self._state.record_run(report)
        return report


def build_local_openai_worker(*, state_path: str | Path | None = None, environ: Mapping[str, str] | None = None) -> tuple[LocalOpenAIIntelligenceWorker, LocalOpenAIWorkerStateStore]:
    """Compose the one permitted local delivery path after explicit opt-in."""
    source = os.environ if environ is None else environ
    settings = LocalOpenAIWorkerSettings.from_environment(source)
    if not settings.enabled:
        raise LocalWorkerConfigurationError("Local intelligence worker is disabled; explicit opt-in is required.")
    token = source.get(INGEST_TOKEN_ENVIRONMENT_KEY)
    if not token:
        raise LocalWorkerConfigurationError("External-intelligence intake credential is not configured.")
    state = LocalOpenAIWorkerStateStore(state_path or Path("data") / "external_intelligence_local_worker_state.sqlite")
    try:
        worker = LocalOpenAIIntelligenceWorker(
            state=state, responses=OpenAIResponsesWebSearchClient.from_environment(source),
            connector=ExternalIntelligenceLiveConnector(backend_url=LOCAL_HSI_ORIGIN, ingest_token=token), settings=settings,
        )
    except Exception:
        state.close()
        raise
    return worker, state


def worker_response_schema() -> dict[str, object]:
    """Responses JSON schema containing the existing V1C event schema verbatim."""
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "outcome": {"type": "string", "enum": [NO_NEW_MATERIAL_INTELLIGENCE, "QUALIFIED_EVENT"]},
            "event": {"anyOf": [ExternalIntelligenceEventRequest.model_json_schema(), {"type": "null"}]},
        },
        "required": ["outcome", "event"],
    }


def parse_worker_discovery(result: ResponsesResult) -> WorkerDiscovery:
    value = _WorkerResultModel.model_validate_json(result.output_text)
    if value.outcome == NO_NEW_MATERIAL_INTELLIGENCE:
        return WorkerDiscovery(True, None, result.sources_searched_count)
    assert value.event is not None
    event = ExternalIntelligenceEventRequest.model_validate(value.event).model_dump(mode="json")
    return WorkerDiscovery(False, event, result.sources_searched_count)


def event_fingerprint(event: Mapping[str, object]) -> str:
    """Deduplicate semantically, independent of a model accidentally changing an ID."""
    value = dict(event)
    value.pop("producer_event_id", None)
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_fingerprints(event: Mapping[str, object]) -> tuple[str, ...]:
    sources: list[Mapping[str, object]] = []
    primary = event.get("primary_source")
    if isinstance(primary, Mapping):
        sources.append(primary)
    supporting = event.get("supporting_sources", ())
    if isinstance(supporting, (list, tuple)):
        sources.extend(item for item in supporting if isinstance(item, Mapping))
    return tuple("sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() for value in sources)


def _worker_input(previous: LocalWorkerRunReport | None) -> str:
    if previous is None:
        return "Start the bounded current intelligence monitoring cycle. Return no more than one qualified event."
    return f"Continue the bounded monitoring cycle after successful run {previous.run_id}; return no more than one new qualified event."


def _environment_bool(value: str) -> bool:
    if value.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if value.strip().lower() in {"0", "false", "no", "off", ""}:
        return False
    raise LocalWorkerConfigurationError("Local intelligence worker enabled flag must be a boolean.")


def _response_output_text(document: Mapping[str, object]) -> str | None:
    direct = document.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    output = document.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                return part["text"]
    return None


def _web_search_source_count(document: Mapping[str, object]) -> int:
    count = 0
    def visit(value: object) -> None:
        nonlocal count
        if isinstance(value, Mapping):
            sources = value.get("sources")
            if isinstance(sources, list):
                count += len(sources)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
    visit(document.get("output", ()))
    return count


def _json_object(value: bytes) -> Mapping[str, object]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _producer_event_id(event: Mapping[str, object]) -> str:
    value = event.get("producer_event_id")
    return value if isinstance(value, str) else ""


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Local intelligence worker clock must be timezone-aware.")
    return value.astimezone(UTC)


def _report_from_row(row: sqlite3.Row) -> LocalWorkerRunReport:
    return LocalWorkerRunReport(
        row["run_id"], LocalWorkerRunStatus(row["status"]), datetime.fromisoformat(row["started_at"]),
        datetime.fromisoformat(row["completed_at"]), row["sources_searched_count"], row["candidates_considered"],
        row["qualified_events"], row["delivered"], row["pending"], row["duplicates"], row["rejected"], row["failure_code"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit local HSI External Intelligence worker")
    parser.add_argument("--once", action="store_true", help="Run one opted-in bounded cycle (default: foreground hourly worker).")
    arguments = parser.parse_args(argv)
    worker, state = build_local_openai_worker()
    try:
        if arguments.once:
            report = worker.run_once()
            print(f"run_id={report.run_id} status={report.status.value} delivered={report.delivered} pending={report.pending}")
            return 0 if report.status not in {LocalWorkerRunStatus.OPENAI_FAILURE, LocalWorkerRunStatus.INVALID_MODEL_OUTPUT} else 2
        worker.run_forever()
        return 0
    finally:
        state.close()


if __name__ == "__main__":  # pragma: no cover - explicit operator entry point
    raise SystemExit(main())


__all__ = (
    "DEFAULT_MODEL", "HSI_EXTERNAL_INTELLIGENCE_DESK_MASTER_DIRECTIVE", "LOCAL_HSI_ORIGIN",
    "LocalOpenAIIntelligenceWorker", "LocalOpenAIWorkerSettings", "LocalOpenAIWorkerStateStore",
    "LocalWorkerConfigurationError", "LocalWorkerRunReport", "LocalWorkerRunStatus", "NO_NEW_MATERIAL_INTELLIGENCE",
    "OPENAI_API_KEY_ENVIRONMENT_KEY", "OPENAI_MODEL_ENVIRONMENT_KEY", "OpenAIResponsesError",
    "OpenAIResponsesWebSearchClient", "ResponsesResult", "WORKER_ENABLED_ENVIRONMENT_KEY",
    "build_local_openai_worker", "event_fingerprint", "parse_worker_discovery", "source_fingerprints", "worker_response_schema",
)
