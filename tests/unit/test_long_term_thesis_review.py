from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import ast, inspect
from pathlib import Path
import pytest
import app.intelligence.long_term_thesis_review as module
from app.intelligence.long_term_thesis_review import *
T=datetime(2026,9,3,10,tzinfo=UTC); FP="sha256:"+"a"*64
def ref(name,at=T-timedelta(minutes=2)): return ThesisLineageReference(name,FP,at)
def candidate(**kw):
 v=dict(canonical_instrument_id="NSE:INE000000001",dossier_id="brain-output-projection:1",dossier_fingerprint=FP,source_policy_version="brain-output-v1",dossier_as_of=T-timedelta(minutes=3),available_at=T-timedelta(minutes=2),evidence_state=DossierEvidenceState.AVAILABLE,diagnostic_lineage=(ref("diagnostic:1"),),evidence_lineage=(ref("evidence:1"),));v.update(kw);return deep_analysis_dossier_candidate(**v)
def context(**kw):
 v=dict(as_of=T,expected_source_policy_version="brain-output-v1",expected_fingerprint_scheme=FINGERPRINT_SCHEME);v.update(kw);return LongTermThesisReviewContext(**v)
@pytest.mark.parametrize("family",tuple(LongTermThesisFamily))
def test_every_family_is_observed_but_policy_unavailable(family):
 r=review_long_term_thesis(context(),family,candidate());assert r.review_state is ThesisReviewState.DOSSIER_OBSERVED;assert r.policy_availability is ThesisPolicyAvailability.POLICY_UNAVAILABLE;assert r.blockers==(ThesisReason.FAMILY_POLICY_UNAVAILABLE,)
@pytest.mark.parametrize(("state","result"),[(DossierEvidenceState.UNAVAILABLE,ThesisReviewState.DATA_INSUFFICIENT),(DossierEvidenceState.STALE,ThesisReviewState.DATA_INSUFFICIENT),(DossierEvidenceState.NON_COMPARABLE,ThesisReviewState.DATA_INSUFFICIENT),(DossierEvidenceState.CONFLICTED,ThesisReviewState.CONFLICTED)])
def test_evidence_states_fail_closed(state,result):
 r=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,candidate(evidence_state=state));assert r.review_state is result;assert r.policy_availability is ThesisPolicyAvailability.NOT_EVALUATED
def test_future_and_tampering_fail_closed():
 future=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,candidate(available_at=T+timedelta(seconds=1)));bad=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,replace(candidate(),stored_fingerprint="sha256:"+"b"*64));assert future.review_state is ThesisReviewState.TEMPORALLY_INVALID and bad.review_state is ThesisReviewState.UNVERIFIABLE
def test_deterministic_utc_lineage_and_serialization():
 india=timezone(timedelta(hours=5,minutes=30)); a=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,candidate(diagnostic_lineage=(ref("diagnostic:b"),ref("diagnostic:a"))));b=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,candidate(diagnostic_lineage=(ref("diagnostic:a"),ref("diagnostic:b")),dossier_as_of=(T-timedelta(minutes=3)).astimezone(india)));assert a.review_id==b.review_id and serialize_thesis_review(a)==serialize_thesis_review(b)
def test_duplicate_lineage_and_output_tampering_rejected():
 with pytest.raises(LongTermThesisReviewError):candidate(diagnostic_lineage=(ref("diagnostic:1"),ref("diagnostic:1")))
 r=review_long_term_thesis(context(),LongTermThesisFamily.QUALITY_FAIR_VALUE,candidate())
 with pytest.raises(FrozenInstanceError):r.review_state=ThesisReviewState.DATA_INSUFFICIENT
 object.__setattr__(r,"fingerprint",FP)
 with pytest.raises(LongTermThesisReviewError,match="FINGERPRINT_MISMATCH"):r.verify()
def test_no_forbidden_dependencies_or_fields():
 s=Path(inspect.getfile(module)).read_text();imports={x.name for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Import) for x in n.names}|{n.module or "" for n in ast.walk(ast.parse(s)) if isinstance(n,ast.ImportFrom)};assert not any(x.startswith(p) for x in imports for p in ("app.portfolio","app.storage","app.api","app.broker","app.orders","app.signals"));assert "datetime.now" not in s;assert not(set(LongTermThesisReview.__dataclass_fields__)&{"price","quantity","allocation","portfolio","order","broker","score"})
