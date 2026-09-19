"""Explicit opt-in P1 journal in the existing Core API snapshot database.

No production factory/runtime wiring. Every accepted write is one transaction;
the two indexes are disposable and never substitute for verified batch history.
"""
from __future__ import annotations

from threading import RLock

from app.intelligence.p1_signal_lifecycle import (
    Batch, CanonicalSourceReader, Evaluation, LifecycleError, Outcome, Reason,
    Result, State, evaluate, replay, slot_key, utc, verify_chain,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_json, snapshot_json_from,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS p1_signal_lifecycle_batch_index (
        batch_id TEXT PRIMARY KEY REFERENCES core_api_snapshots(snapshot_id),
        slot_key TEXT NOT NULL, input_key TEXT NOT NULL, accepted_cutoff TEXT NOT NULL,
        UNIQUE(slot_key,input_key), UNIQUE(slot_key,accepted_cutoff))""",
    """CREATE TABLE IF NOT EXISTS p1_signal_lifecycle_heads (
        slot_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES core_api_snapshots(snapshot_id),
        fingerprint TEXT NOT NULL, accepted_cutoff TEXT NOT NULL, current_lifetime_id TEXT)""",
)


class _P1LifecycleReads:
    """Shared journal verification; contains no schema or write operation."""

    def _snapshot_rows(self, query, args):
        return self._connection.execute(query, tuple(args)).fetchall()

    def _chain(self, instrument: str, as_of=None) -> tuple[Batch, ...]:
        slot = slot_key(instrument)
        # Do not trust head or batch-index contents to hide a fork/orphan.
        query = "SELECT * FROM core_api_snapshots WHERE family=?"
        args = [CoreApiSnapshotFamily.P1_SIGNAL_LIFECYCLE_BATCH.value]
        if as_of is not None:
            query += " AND created_at<=?"
            args.append(utc(as_of).isoformat())
        rows = self._snapshot_rows(query, args)
        found = []
        for row in rows:
            snapshot = snapshot_json_from(row["payload_json"])
            b = snapshot.payload
            if not isinstance(b, Batch) or (
                snapshot.snapshot_id != b.batch_id or snapshot.fingerprint != b.fingerprint
                or snapshot.family is not CoreApiSnapshotFamily.P1_SIGNAL_LIFECYCLE_BATCH
                or snapshot.created_at != b.evaluation.as_of
                or row["created_at"] != b.evaluation.as_of.isoformat()
                or row["snapshot_id"] != b.batch_id or row["fingerprint"] != b.fingerprint
                or row["record_type"] != "P1SignalLifecycleBatch" or row["schema_version"] != "v1"
            ):
                raise LifecycleError(Reason.CHAIN_CONFLICT)
            if b.slot_key == slot:
                found.append(b)
        by_prior = {}
        for b in found:
            if b.prior_batch_id in by_prior:
                raise LifecycleError(Reason.CHAIN_CONFLICT)
            by_prior[b.prior_batch_id] = b
        chain, prior = [], None
        while prior in by_prior:
            b = by_prior.pop(prior)
            chain.append(b)
            prior = b.batch_id
        if by_prior:
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        verify_chain(tuple(chain))
        return tuple(chain)

    @staticmethod
    def _head_values(chain):
        if not chain:
            return None
        b, t = chain[-1], chain[-1].transitions[-1]
        return (b.slot_key, b.batch_id, b.fingerprint, b.evaluation.as_of.isoformat(),
                t.lifetime_id if t.next_state is State.CURRENT else None)

    def _verify_indexes(self, chain, slot, as_of=None):
        row = self._connection.execute("SELECT * FROM p1_signal_lifecycle_heads WHERE slot_key=?", (slot,)).fetchone()
        future_head = row is not None and as_of is not None and row["accepted_cutoff"] > utc(as_of).isoformat()
        if not future_head and (tuple(row) if row else None) != self._head_values(chain):
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        query = "SELECT * FROM p1_signal_lifecycle_batch_index WHERE slot_key=?"
        args = [slot]
        if as_of is not None:
            query += " AND accepted_cutoff<=?"
            args.append(utc(as_of).isoformat())
        actual = {tuple(r) for r in self._connection.execute(query, tuple(args)).fetchall()}
        expected = {(b.batch_id, b.slot_key, b.input_key, b.evaluation.as_of.isoformat()) for b in chain}
        if actual != expected:
            raise LifecycleError(Reason.CHAIN_CONFLICT)

    def read(self, instrument, *, as_of):
        with self._lock, self._connection:
            self._connection.execute("BEGIN")
            try:
                chain = self._chain(instrument, as_of=as_of)
                self._verify_indexes(chain, slot_key(instrument), as_of=as_of)
                return replay(chain, as_of=as_of)
            except (ValueError, TypeError, AttributeError, KeyError):
                from app.intelligence.p1_signal_lifecycle import View, utc
                return View(utc(as_of), None, (), Outcome.CONFLICTED, Reason.CHAIN_CONFLICT)


class SQLiteP1SignalLifecycleRepository(_P1LifecycleReads, SQLiteCoreApiSnapshotRepository):
    def __init__(self, database_path=":memory:"):
        super().__init__(database_path)
        self._lock = RLock()
        self._connection.execute("PRAGMA foreign_keys=ON")
        with self._connection:
            for statement in SCHEMA:
                self._connection.execute(statement)

    def submit(self, value: Evaluation, reader: CanonicalSourceReader) -> Result:
        # BEGIN IMMEDIATE obtains the writer lock BEFORE reading the head. A
        # racing caller therefore recomputes against the newly committed head,
        # never blindly retries a stale proposed transition.
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                chain = self._chain(value.canonical_instrument_id)
                self._verify_indexes(chain, slot_key(value.canonical_instrument_id))
            except (ValueError, TypeError, AttributeError, KeyError):
                return Result(Outcome.CONFLICTED, Reason.CHAIN_CONFLICT, None)
            result = evaluate(value, chain, reader)
            if result.outcome is not Outcome.ACCEPTED:
                return result
            b = result.batch
            snapshot = CoreApiSnapshot(b.batch_id, CoreApiSnapshotFamily.P1_SIGNAL_LIFECYCLE_BATCH,
                                       "v1", "P1SignalLifecycleBatch", b.fingerprint, value.as_of, b)
            self._connection.execute("INSERT INTO core_api_snapshots VALUES (?,?,?,?,?,?,?)", (
                b.batch_id, snapshot.family.value, "v1", snapshot.record_type, b.fingerprint,
                value.as_of.isoformat(), snapshot_json(snapshot)))
            self._connection.execute("INSERT INTO p1_signal_lifecycle_batch_index VALUES (?,?,?,?)",
                                     (b.batch_id, b.slot_key, b.input_key, value.as_of.isoformat()))
            old = self._head_values(chain)
            new = self._head_values((*chain, b))
            if old is None:
                self._connection.execute("INSERT INTO p1_signal_lifecycle_heads VALUES (?,?,?,?,?)", new)
            else:
                changed = self._connection.execute(
                    "UPDATE p1_signal_lifecycle_heads SET batch_id=?,fingerprint=?,accepted_cutoff=?,current_lifetime_id=? "
                    "WHERE slot_key=? AND batch_id=? AND fingerprint=?", (*new[1:], new[0], old[1], old[2]))
                if changed.rowcount != 1:
                    raise LifecycleError(Reason.CHAIN_CONFLICT)
            return result

    def rebuild_indexes(self, instrument):
        """Explicit recovery: derive disposable indexes from the intact chain."""
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            chain = self._chain(instrument)
            slot = slot_key(instrument)
            self._connection.execute("DELETE FROM p1_signal_lifecycle_heads WHERE slot_key=?", (slot,))
            self._connection.execute("DELETE FROM p1_signal_lifecycle_batch_index WHERE slot_key=?", (slot,))
            for b in chain:
                self._connection.execute("INSERT INTO p1_signal_lifecycle_batch_index VALUES (?,?,?,?)",
                                         (b.batch_id, b.slot_key, b.input_key, b.evaluation.as_of.isoformat()))
            head = self._head_values(chain)
            if head:
                self._connection.execute("INSERT INTO p1_signal_lifecycle_heads VALUES (?,?,?,?,?)", head)
            return head
