"""Isolated synthetic admission proofs, not production source availability."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from pathlib import Path

import pytest

from app.intelligence.p1_prospective_dry_run import dry_run
from app.intelligence.p1_signal_lifecycle import canonical_json, Outcome, evaluate
from app.storage.sqlite_p1_signal_lifecycle import SQLiteP1SignalLifecycleRepository
from tests.unit.test_p1_signal_lifecycle_runtime import governance, fixture, Ledger, T, I, TECHNICAL_FAILURES


START = T - timedelta(days=2)  # Hypothetical fixture boundary, never an activation.


def test_qualifying_fixture_dry_run_and_existing_writer_are_separate(governance, tmp_path):
    value = fixture(governance)
    repo = SQLiteP1SignalLifecycleRepository(tmp_path / 'isolated.sqlite')
    try:
        result = dry_run(value, Ledger(value), hypothetical_start=START)
        assert result.status == 'WOULD_ADMIT'
        assert result.reason is None and result.writes_performed == 0
        assert repo.read(I, as_of=T).last_transition is None
        accepted = repo.submit(value, Ledger(value))
        assert accepted.outcome is Outcome.ACCEPTED
        assert repo.submit(value, Ledger(value)).outcome is Outcome.NO_CHANGE
        assert repo.read(I, as_of=T).last_transition == accepted.batch.transitions[-1]
    finally:
        repo.close()


@pytest.mark.parametrize('predicate', tuple(TECHNICAL_FAILURES))
def test_verified_negative_is_healthy_zero_without_writing(governance, tmp_path, predicate):
    value = fixture(governance, negative=predicate)
    repo = SQLiteP1SignalLifecycleRepository(tmp_path / 'isolated.sqlite')
    try:
        result = dry_run(value, Ledger(value), hypothetical_start=START)
        assert result.status == 'EVALUATED_NO_CURRENT_VALID_SETUP'
        assert result.reason is None and result.writes_performed == 0
        assert repo.read(I, as_of=T).last_transition is None
    finally:
        repo.close()


@pytest.mark.parametrize('start,reason', [(None, 'PROSPECTIVE_START_UNSET'),
    (T + timedelta(seconds=1), 'EVALUATION_BEFORE_PROSPECTIVE_START'),
    (START + timedelta(microseconds=1), 'EVIDENCE_BEFORE_PROSPECTIVE_START')])
def test_no_relabeling_old_evidence(governance, start, reason):
    value = fixture(governance)
    before = canonical_json(value)
    result = dry_run(value, Ledger(value), hypothetical_start=start)
    assert (result.status, result.reason) == ('SOURCE_BLOCKED', reason)
    assert canonical_json(value) == before


@pytest.mark.parametrize('known,reason', [(None, 'EVIDENCE_KNOWN_AT_UNAVAILABLE'),
    (T + timedelta(seconds=1), 'SOURCE_NOT_ELIGIBLE')])
def test_missing_and_future_known_at_fail_closed(governance, known, reason):
    value = fixture(governance)
    ref = replace(value.references[0], evidence_known_at=known)
    value = replace(value, references=(ref, *value.references[1:]))
    result = dry_run(value, Ledger(value), hypothetical_start=START)
    assert result.status == 'SOURCE_BLOCKED' and result.reason == reason


@pytest.mark.parametrize('negative', [None, 'BBW_NOT_COMPRESSED'])
@pytest.mark.parametrize('fault', ['unverified', 'stale', 'closure', 'outage'])
def test_reader_failure_never_becomes_healthy_zero(governance, negative, fault):
    value = fixture(governance, negative=negative)
    class FailedReader(Ledger):
        def verify(self, reference, *, as_of):
            if fault == 'outage':
                raise OSError('secret must not be returned')
            return fault not in {'unverified', 'stale'}
        def dependencies(self, reference):
            return None if fault == 'closure' else super().dependencies(reference)
    result = dry_run(value, FailedReader(value), hypothetical_start=START)
    assert result.status == 'SOURCE_BLOCKED'
    assert 'secret' not in canonical_json(result)


@pytest.mark.parametrize('negative', [None, 'BBW_NOT_COMPRESSED'])
def test_policy_unavailable_is_not_a_zero_setup_result(governance, negative):
    value = replace(fixture(governance, negative=negative), approvals=(), selections=())
    native = evaluate(value, (), Ledger(value))
    result = dry_run(value, Ledger(value), hypothetical_start=START)
    # Retained positive projection contradicts absent policy; native conflict
    # priority must not be weakened to policy-only, or healthy zero.
    assert result.status == native.outcome.value
    assert result.status in {'POLICY_BLOCKED', 'CONFLICTED'}
    assert result.reason == native.reason.value


def test_reader_receives_exact_canonical_timestamps_without_redating(governance):
    value = fixture(governance)
    seen = []
    class ObservedReader(Ledger):
        def verify(self, reference, *, as_of):
            seen.append((reference, as_of))
            return super().verify(reference, as_of=as_of)
    assert dry_run(value, ObservedReader(value), hypothetical_start=START).status == 'WOULD_ADMIT'
    assert {ref for ref, _ in seen} == set(value.references)
    assert all(as_of == value.as_of for _, as_of in seen)
    assert min(ref.evidence_known_at for ref, _ in seen) == START


def test_tampered_native_evidence_rejected(governance):
    value = fixture(governance)
    value = replace(value, assessments=(replace(value.assessments[0], sector='TAMPERED'),))
    assert dry_run(value, Ledger(value), hypothetical_start=START).status == 'CONFLICTED'


def test_deterministic_serialization_utc_and_fixed_authority(governance):
    value = fixture(governance)
    first = dry_run(value, Ledger(value), hypothetical_start=START)
    second = dry_run(replace(value, references=tuple(reversed(value.references))), Ledger(value),
                     hypothetical_start=START.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert canonical_json(first) == canonical_json(second)
    assert first.mode == 'DRY_RUN_NOT_ACTIVE'
    assert first.actionability == 'WATCH_ONLY' and first.execution_status == 'NON_EXECUTABLE'
    with pytest.raises(FrozenInstanceError):
        first.status = 'ACTIVE'


def test_dry_run_has_no_io_clock_or_activation_dependencies():
    tree = ast.parse(Path('app/intelligence/p1_prospective_dry_run.py').read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert set(imports) <= {'dataclasses', 'datetime', 'hashlib', 'app.intelligence.p1_signal_lifecycle'}
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert not set(calls) & {'now', 'utcnow', 'submit', 'connect', 'execute', 'save', 'write', 'send'}
