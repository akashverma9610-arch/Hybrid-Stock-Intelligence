from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import ast
from pathlib import Path

import pytest

from app.data_operations.source_dependency_ledger import (
    RetainedFreshness, RetainedSourceReference, SourceReadiness, SourceRequirement,
    build_source_dependency_ledger,
)

T = datetime(2026, 9, 22, 16, tzinfo=UTC)
REQ = SourceRequirement("benchmark", "INDEX_BARS", "NSE", "NIFTY500", True)
REF = RetainedSourceReference(REQ, "native:bar:1", "sha256:" + "a" * 64,
                              T - timedelta(hours=6), T - timedelta(hours=5), T - timedelta(hours=4),
                              True, RetainedFreshness.CURRENT, "native-policy:v1")


class Reader:
    def __init__(self, references=(REF,), *, verified=True, manifest=True):
        self.references, self.verified, self.manifest = references, verified, manifest

    def manifest_verified(self, consumer, run_id, requirements, *, as_of):
        return self.manifest

    def read(self, requirement, *, as_of):
        return tuple(x for x in self.references if x.requirement == requirement)

    def verify(self, reference, *, as_of):
        return self.verified


def build(reader=None, requirements=(REQ,), **kwargs):
    return build_source_dependency_ledger(consumer="P1_SOURCE_PREFLIGHT", run_id="evaluation:1",
        as_of=kwargs.get("as_of", T), requirements=requirements, reader=reader or Reader())


def test_exact_metadata_preserved_and_read_only_handoff():
    result = build()
    assert result.ready_to_evaluate
    assert result.rows[0].references == (REF,)
    assert len({REF.source_at, REF.known_at, REF.ingested_at}) == 3
    with pytest.raises(FrozenInstanceError):
        result.run_id = "changed"


@pytest.mark.parametrize("field,value,expected", [
    ("source_at", None, SourceReadiness.SOURCE_UNVERIFIED),
    ("source_at", T + timedelta(seconds=1), SourceReadiness.SOURCE_UNVERIFIED),
    ("known_at", None, SourceReadiness.KNOWN_AT_INSUFFICIENT),
    ("known_at", T + timedelta(seconds=1), SourceReadiness.KNOWN_AT_INSUFFICIENT),
    ("ingested_at", None, SourceReadiness.SOURCE_UNVERIFIED),
    ("ingested_at", T + timedelta(seconds=1), SourceReadiness.SOURCE_UNVERIFIED),
    ("identity_resolved", False, SourceReadiness.IDENTITY_UNRESOLVED),
    ("freshness", RetainedFreshness.STALE, SourceReadiness.SOURCE_STALE),
    ("freshness", RetainedFreshness.UNVERIFIED, SourceReadiness.SOURCE_UNVERIFIED),
    ("freshness_policy_reference", None, SourceReadiness.POLICY_UNAVAILABLE),
])
def test_unavailable_metadata_cannot_be_ready(field, value, expected):
    result = build(Reader((replace(REF, **{field: value}),)))
    assert not result.ready_to_evaluate and expected in result.rows[0].states


def test_missing_required_benchmark_blocks_regime_and_sector_consumers():
    for consumer in ("MARKET_REGIME", "SECTOR_ALIGNMENT", "P1_SOURCE_PREFLIGHT"):
        result = build_source_dependency_ledger(consumer=consumer, run_id="run", as_of=T,
            requirements=(REQ,), reader=Reader(()))
        assert not result.ready_to_evaluate and result.rows[0].states == (SourceReadiness.SOURCE_MISSING,)


def test_optional_missing_still_visible_but_not_required():
    optional = replace(REQ, dependency_id="optional-news", source_family="NEWS", required=False)
    result = build(requirements=(optional, REQ))
    assert result.ready_to_evaluate
    assert result.rows[1].states == (SourceReadiness.SOURCE_MISSING,)
    assert not build(requirements=(optional,)).ready_to_evaluate


def test_complete_manifest_and_native_verification_mandatory():
    for reader in (Reader(verified=False), Reader(manifest=False)):
        assert not build(reader).ready_to_evaluate
    with pytest.raises(ValueError, match="COMPLETE_MANIFEST"):
        build(requirements=())


def test_duplicates_idempotent_and_conflicts_never_collapsed():
    assert build(Reader((REF, REF)), (REQ, REQ)) == build()
    conflict = replace(REF, known_at=T)
    forward = build(Reader((REF, conflict)))
    reverse = build(Reader((conflict, REF)))
    assert forward.serialize() == reverse.serialize()
    assert len(forward.rows[0].references) == 2 and not forward.ready_to_evaluate
    with pytest.raises(ValueError, match="REQUIREMENT_CONFLICT"):
        build(requirements=(REQ, replace(REQ, required=False)))


def test_timezone_and_serialization_stability():
    offset = timezone(timedelta(hours=5, minutes=30))
    ref = replace(REF, source_at=REF.source_at.astimezone(offset), known_at=REF.known_at.astimezone(offset), ingested_at=REF.ingested_at.astimezone(offset))
    a = build()
    b = build(Reader((ref,)), as_of=T.astimezone(offset))
    assert a.serialize() == b.serialize() and a.fingerprint == b.fingerprint
    assert build(Reader((replace(REF, fingerprint="b" * 64),))).fingerprint != a.fingerprint


def test_malformed_identity_fingerprint_and_naive_times_rejected():
    with pytest.raises(ValueError):
        replace(REF, fingerprint="bad")
    with pytest.raises(ValueError):
        replace(REF, known_at=T.replace(tzinfo=None))
    with pytest.raises(ValueError):
        replace(REQ, dependency_id="")


def test_no_p1_persistence_or_authority_dependencies():
    path = Path(__file__).resolve().parents[2] / "app/data_operations/source_dependency_ledger.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(x and x.startswith("app.") for x in imports)
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert not {"save", "execute", "commit", "now", "utcnow", "request", "post"}.intersection(calls)
