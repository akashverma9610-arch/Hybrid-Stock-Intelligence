"""Small HSI authorization sidecar; never changes canonical financial records.

    Explicit initialization/owner bootstrap is an operator operation, not login.
    No automatic owner selection, email matching, self-signup or legacy adoption.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.api.pilot_identity import PilotPrincipal, PilotRole, denied


class PrivateResourceKind(StrEnum):
    CORE_SNAPSHOT = "CORE_SNAPSHOT"
    IMPORT_DRAFT = "IMPORT_DRAFT"
    PORTFOLIO = "PORTFOLIO"
    BROKER_ACCOUNT = "BROKER_ACCOUNT"
    WATCHLIST = "WATCHLIST"
    PREFERENCES = "PREFERENCES"
    ALERT = "ALERT"
    PAPER_TRADE = "PAPER_TRADE"
    FEEDBACK = "FEEDBACK"
    PERSONAL_DECISION = "PERSONAL_DECISION"


_SCHEMA = """
CREATE TABLE pilot_identity_schema(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT INTO pilot_identity_schema VALUES(1);
CREATE TABLE pilot_users(
 user_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('OWNER','ADMIN','TESTER')),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), UNIQUE(issuer,subject));
CREATE UNIQUE INDEX pilot_one_owner ON pilot_users(role) WHERE role='OWNER';
CREATE TABLE pilot_ownership(
 kind TEXT NOT NULL, resource_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 owner_user_id TEXT NOT NULL REFERENCES pilot_users(user_id),
 PRIMARY KEY(kind,resource_id));
CREATE TABLE pilot_auth_audit(
 sequence INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL,
 actor_user_id TEXT NOT NULL REFERENCES pilot_users(user_id),
 action TEXT NOT NULL, target_id TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TRIGGER pilot_audit_no_update BEFORE UPDATE ON pilot_auth_audit
 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_AUDIT'); END;
CREATE TRIGGER pilot_audit_no_delete BEFORE DELETE ON pilot_auth_audit
 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_AUDIT'); END;
CREATE TRIGGER pilot_binding_no_update BEFORE UPDATE ON pilot_ownership
 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_OWNERSHIP'); END;
CREATE TRIGGER pilot_binding_no_delete BEFORE DELETE ON pilot_ownership
 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_OWNERSHIP'); END;
"""


def _text(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or value.strip() != value or any(ord(c) < 32 for c in value):
        raise ValueError("PILOT_IDENTITY_VALUE_INVALID")
    return value


class PilotIdentityStore:
    def __init__(self, path: str):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise ValueError("PILOT_IDENTITY_STORE_NOT_INITIALIZED")
        with self._connection() as connection:
            if connection.execute("SELECT version FROM pilot_identity_schema").fetchall() != [(1,)]:
                raise ValueError("PILOT_IDENTITY_SCHEMA_UNSUPPORTED")

    @classmethod
    def initialize(cls, path: str):
        """Create a NEW authorization DB exclusively; refuse all existing files."""
        target = Path(path).resolve()
        with target.open("xb"):
            pass
        connection = sqlite3.connect(target)
        try:
            connection.executescript(_SCHEMA)
            connection.commit()
        finally:
            connection.close()
        return cls(str(target))

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _audit(connection, actor, action, target, reason):
        connection.execute("INSERT INTO pilot_auth_audit(occurred_at,actor_user_id,action,target_id,reason) VALUES(?,?,?,?,?)",
                           (datetime.now(UTC).isoformat(), actor, action, target, _text(reason)))

    @staticmethod
    def _admin(connection, actor: PilotPrincipal):
        row = connection.execute("SELECT role,enabled FROM pilot_users WHERE user_id=?", (actor.user_id,)).fetchone()
        if not row or row[1] != 1 or row[0] not in ("OWNER", "ADMIN") or row[0] != actor.role.value:
            raise denied()

    def bootstrap_owner(self, issuer: str, subject: str, *, reason: str) -> PilotPrincipal:
        """Offline-only, one-time explicit owner; intentionally no HTTP endpoint."""
        _text(issuer); _text(subject)
        user_id = str(uuid5(NAMESPACE_URL, issuer + "\n" + subject))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM pilot_users").fetchone():
                raise ValueError("PILOT_OWNER_ALREADY_BOOTSTRAPPED")
            connection.execute("INSERT INTO pilot_users VALUES(?,?,?,?,1)", (user_id, issuer, subject, "OWNER"))
            self._audit(connection, user_id, "OWNER_BOOTSTRAP", user_id, reason)
        return PilotPrincipal(user_id, PilotRole.OWNER)

    def principal(self, issuer: str, subject: str) -> PilotPrincipal:
        with self._connection() as connection:
            row = connection.execute("SELECT user_id,role FROM pilot_users WHERE issuer=? AND subject=? AND enabled=1",
                                     (issuer, subject)).fetchone()
        if row is None:
            raise denied("PILOT_INVITATION_REQUIRED")
        return PilotPrincipal(row[0], PilotRole(row[1]))

    def invite_tester(self, actor: PilotPrincipal, issuer: str, subject: str, *, reason: str) -> PilotPrincipal:
        _text(issuer); _text(subject)
        user_id = str(uuid5(NAMESPACE_URL, issuer + "\n" + subject))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._admin(connection, actor)
            existing = connection.execute("SELECT 1 FROM pilot_users WHERE user_id=?", (user_id,)).fetchone()
            if existing:
                raise denied("PILOT_USER_ALREADY_REGISTERED", 409)
            connection.execute("INSERT INTO pilot_users VALUES(?,?,?,?,1)", (user_id, issuer, subject, "TESTER"))
            self._audit(connection, actor.user_id, "TESTER_INVITED", user_id, reason)
        return PilotPrincipal(user_id, PilotRole.TESTER)

    def set_tester_enabled(self, actor: PilotPrincipal, user_id: str, *, enabled: bool, reason: str):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._admin(connection, actor)
            cursor = connection.execute("UPDATE pilot_users SET enabled=? WHERE user_id=? AND role='TESTER'",
                                        (int(enabled), user_id))
            if cursor.rowcount != 1:
                raise denied("PILOT_USER_NOT_FOUND", 404)
            self._audit(connection, actor.user_id, "TESTER_ENABLED" if enabled else "TESTER_REVOKED", user_id, reason)

    def bind(self, actor: PilotPrincipal, kind: PrivateResourceKind, resource_id: str, fingerprint: str,
             owner_user_id: str, *, reason: str):
        """Explicit operator reconciliation only, never called on first login.

        Bind immutable canonical record ID AND fingerprint without editing it.
        Changing owner/fingerprint requires a separately audited recovery design.
        """
        _text(resource_id); _text(fingerprint)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._admin(connection, actor)
            existing = connection.execute("SELECT fingerprint,owner_user_id FROM pilot_ownership WHERE kind=? AND resource_id=?",
                                          (kind.value, resource_id)).fetchone()
            if existing:
                if existing != (fingerprint, owner_user_id):
                    raise denied("PILOT_OWNERSHIP_CONFLICT", 409)
                return
            connection.execute("INSERT INTO pilot_ownership VALUES(?,?,?,?)", (kind.value, resource_id, fingerprint, owner_user_id))
            self._audit(connection, actor.user_id, "OWNERSHIP_BOUND", resource_id, reason)

    def owned(self, principal: PilotPrincipal, kind: PrivateResourceKind) -> tuple[tuple[str, str], ...]:
        with self._connection() as connection:
            rows = connection.execute("SELECT o.resource_id,o.fingerprint FROM pilot_ownership o JOIN pilot_users u ON u.user_id=o.owner_user_id WHERE o.kind=? AND o.owner_user_id=? AND u.enabled=1 ORDER BY o.resource_id",
                                      (kind.value, principal.user_id)).fetchall()
        return tuple(rows)

    def require_owner(self, principal: PilotPrincipal, kind: PrivateResourceKind, resource_id: str):
        if resource_id not in dict(self.owned(principal, kind)):
            raise denied("PILOT_RESOURCE_NOT_FOUND", 404)

    def audit(self, actor: PilotPrincipal):
        with self._connection() as connection:
            self._admin(connection, actor)
            return tuple(connection.execute("SELECT sequence,occurred_at,actor_user_id,action,target_id,reason FROM pilot_auth_audit ORDER BY sequence DESC LIMIT 100"))
