"""Explicit offline authorization bootstrap/reconciliation; no provider calls.

Run from repository root with the same Python environment as HSI. No tokens or
passwords are accepted. Auth0 human account creation is an operator dashboard
step; issuer/subject below are identifiers, not authentication credentials.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.pilot_identity import PilotRole
from app.storage.pilot_identity_store import PilotIdentityStore, PrivateResourceKind


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="Separate HSI authorization SQLite path (not canonical DB).")
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--owner-subject", required=True, help="Exact verified Auth0 owner subject; never a token.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap-owner")
    bind = commands.add_parser("bind-snapshot")
    bind.add_argument("--canonical-db", required=True)
    bind.add_argument("--snapshot-id", required=True)
    bind.add_argument("--expected-fingerprint", required=True)
    bind.add_argument("--target-subject", required=True)
    bind.add_argument("--confirm-reviewed-ownership", action="store_true", required=True)
    args = parser.parse_args(argv)
    if args.command == "bootstrap-owner":
        # Refuse existing files, so an incorrect canonical DB path cannot be modified.
        store = PilotIdentityStore.initialize(args.store)
        store.bootstrap_owner(args.issuer, args.owner_subject, reason="EXPLICIT_OPERATOR_OWNER_BOOTSTRAP")
        print("PILOT_OWNER_BOOTSTRAPPED")
        return
    canonical = Path(args.canonical_db).resolve()
    if canonical == Path(args.store).resolve() or not canonical.is_file():
        raise ValueError("PILOT_CANONICAL_DATABASE_INVALID")
    store = PilotIdentityStore(args.store)
    actor = store.principal(args.issuer, args.owner_subject)
    if actor.role is not PilotRole.OWNER:
        raise ValueError("PILOT_OWNER_REQUIRED")
    target = store.principal(args.issuer, args.target_subject)
    connection = sqlite3.connect(canonical.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute("SELECT fingerprint FROM core_api_snapshots WHERE snapshot_id=?", (args.snapshot_id,)).fetchone()
        if row != (args.expected_fingerprint,):
            raise ValueError("PILOT_CANONICAL_REFERENCE_MISMATCH")
    finally:
        connection.close()
    store.bind(actor, PrivateResourceKind.CORE_SNAPSHOT, args.snapshot_id, args.expected_fingerprint,
               target.user_id, reason="EXPLICIT_OPERATOR_REVIEWED_LEGACY_BINDING")
    print("PILOT_SNAPSHOT_OWNERSHIP_BOUND")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never echo argv, identity configuration, database contents or exception args.
        print("PILOT_IDENTITY_ADMIN_FAILED", file=sys.stderr)
        raise SystemExit(1) from None
