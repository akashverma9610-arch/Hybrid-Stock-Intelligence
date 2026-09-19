"""Bounded, non-creating reader of the existing P1 journal, not a producer."""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from threading import RLock

from app.storage.sqlite_p1_signal_lifecycle import _P1LifecycleReads
from app.intelligence.p1_signal_lifecycle import LifecycleError, Reason


# Exact existing immutable payload vocabulary. A tampered class tag must not
# make the generic snapshot decoder import/construct a service or repository.
_PAYLOAD_TYPES = {
    "app.intelligence.p1_signal_lifecycle": "Batch Evaluation Qualification SourceReference State Transition",
    "app.historical.security_master": "HistoricalSecurityIdentity HistoricalSecurityStatus HistoricalCorporateAction CorporateActionKind",
    "app.intelligence.market_wide_watch": "MarketWideWatchRecord WatchEvidenceReference WatchClassification WatchStatus",
    "app.intelligence.opportunity_archetypes": "OpportunityArchetype ExternalEvidenceReference",
    "app.production_v1.canonical_setup_activation": "CanonicalSetupOpportunity",
    "app.strategies.common.models": "CandidateStatus StrategyFamily",
    "app.strategies.pre_breakout.candidate_assembly": "PreBreakoutCandidate PreBreakoutCandidateResearchStatus PreBreakoutCandidateRole",
    "app.strategies.pre_breakout.materialization": "GovernedPreBreakoutBaseWindow GovernedPreBreakoutPivot GovernedPreBreakoutResolvedInputs GovernedPreBreakoutStructuralResult PreBreakoutResolvedInputStatus PreBreakoutStructuralStatus",
    "app.strategies.pre_breakout.policy": "PreBreakoutPolicyApproval PreBreakoutPolicyApprovalDecision PreBreakoutPolicySelection PreBreakoutPolicySelectionContext",
    "app.strategies.pre_breakout.setup_assessment": "GovernedPreBreakoutSetupAssessment PreBreakoutSetupAssessmentStatus PreBreakoutSetupBlocker PreBreakoutSetupBlockerCategory",
}
_ALLOWED_TYPES = frozenset(f"{module}:{name}" for module, names in _PAYLOAD_TYPES.items() for name in names.split())


def _verify_payload_types(value, depth=0):
    if depth > 64:
        raise LifecycleError(Reason.CHAIN_CONFLICT)
    if isinstance(value, dict):
        if value.get("$type") in {"dataclass", "enum"} and value.get("class") not in _ALLOWED_TYPES:
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        for child in value.values():
            _verify_payload_types(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _verify_payload_types(child, depth + 1)


class P1ReadUnavailable(RuntimeError):
    """Finite safe error code; never a database path or SQLite error text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ReadOnlyP1SignalLifecycleReader(_P1LifecycleReads):
    # Infrastructure bounds, not investment policy. Never return partial history.
    MAX_BATCHES = 2000
    MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
    MAX_SQL_STEPS = 5_000_000

    def __init__(self, database_path: str | Path):
        self._lock = RLock()
        path = Path(database_path).resolve()
        if not path.is_file():
            raise P1ReadUnavailable("P1_LIFECYCLE_STORE_UNAVAILABLE")
        try:
            self._connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
        except sqlite3.Error:
            raise P1ReadUnavailable("P1_LIFECYCLE_STORE_UNAVAILABLE") from None
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA query_only=ON")
            self._connection.set_authorizer(self._authorize)
            self._steps = 0
            self._connection.set_progress_handler(self._progress, 1000)
        except Exception:
            self._connection.close()
            raise

    @staticmethod
    def _authorize(action, arg1, arg2, database, trigger):
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    def _progress(self):
        self._steps += 1000
        return int(self._steps > self.MAX_SQL_STEPS)

    def _snapshot_rows(self, query, args):
        # Inspect lengths before fetching/decoding potentially oversized bodies.
        metadata_query = query.replace("SELECT *", "SELECT length(CAST(payload_json AS BLOB)) AS size", 1)
        sizes = self._connection.execute(metadata_query + " LIMIT ?", (*args, self.MAX_BATCHES + 1)).fetchall()
        if len(sizes) > self.MAX_BATCHES or sum(row["size"] or 0 for row in sizes) > self.MAX_PAYLOAD_BYTES:
            raise P1ReadUnavailable("P1_LIFECYCLE_READ_LIMIT_EXCEEDED")
        rows = super()._snapshot_rows(query, args)
        for row in rows:
            try:
                _verify_payload_types(json.loads(row["payload_json"]))
            except (RecursionError, TypeError):
                raise LifecycleError(Reason.CHAIN_CONFLICT) from None
        return rows

    def read(self, instrument, *, as_of):
        self._steps = 0
        try:
            # Schema absence is unavailable, not an empty/healthy signal list.
            tables = {r[0] for r in self._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {"core_api_snapshots", "p1_signal_lifecycle_batch_index", "p1_signal_lifecycle_heads"}
            if not required <= tables:
                raise P1ReadUnavailable("P1_LIFECYCLE_SCHEMA_UNAVAILABLE")
            return super().read(instrument, as_of=as_of)
        except sqlite3.Error:
            code = "P1_LIFECYCLE_READ_LIMIT_EXCEEDED" if self._steps > self.MAX_SQL_STEPS else "P1_LIFECYCLE_STORE_UNAVAILABLE"
            raise P1ReadUnavailable(code) from None

    def close(self):
        self._connection.close()
