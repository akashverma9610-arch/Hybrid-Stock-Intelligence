from datetime import datetime, timedelta, timezone
import unittest

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DiagnosticResult, StrategyVersionReference
from app.lens_knowledge.assessment import assess_lenses, load_catalog


AT = datetime(2026, 9, 10, tzinfo=timezone.utc)
INSTRUMENT = "NSE:INE002A01018"


def diagnostic(rule, *, instrument=INSTRUMENT, at=AT, eligibility=EvaluationEligibility.ELIGIBLE, result="HEALTHY"):
    record = DiagnosticResult(f"result-{rule}", instrument, str(rule), StrategyVersionReference("test", "v1"),
                              result, None, None, (), (), at, at)
    return EvaluatedDiagnostic(record, rule, "v1", eligibility, (), ())


class LensCoverageTests(unittest.TestCase):
    def test_all_35_drafts_are_visible_without_inventing_fit(self):
        catalog = load_catalog()
        self.assertEqual(35, len(catalog))
        self.assertEqual(35, len({item.lens_id for item in catalog}))
        rows = assess_lenses(instrument_id=INSTRUMENT, as_of=AT, diagnostics=())
        self.assertEqual({x.lens_id for x in catalog}, {x.lens_id for x in rows})
        self.assertTrue(all(x.status == "UNKNOWN" for x in rows))
        self.assertTrue(all(x.unavailable_primary_diagnostics for x in rows))

    def test_primary_coverage_reuses_results_and_does_not_claim_qualification(self):
        results = tuple(diagnostic(rule) for rule in range(1, 62))
        row = next(x for x in assess_lenses(instrument_id=INSTRUMENT, as_of=AT, diagnostics=results)
                   if x.lens_id == "FUNDAMENTAL_INFLECTION")
        self.assertEqual((15, 16, 24, 25, 26), row.available_primary_diagnostics)
        self.assertEqual((), row.unavailable_primary_diagnostics)
        self.assertEqual("UNKNOWN", row.status)
        self.assertIn("LENS_SPECIFIC_EVIDENCE_NOT_ASSESSED", row.reasons)
        self.assertIn("result-24", row.diagnostic_result_ids)

    def test_ineligible_and_missing_results_are_not_counted_as_available(self):
        rows = assess_lenses(instrument_id=INSTRUMENT, as_of=AT, diagnostics=(
            diagnostic(15, eligibility=EvaluationEligibility.INELIGIBLE_MISSING_DATA),
            diagnostic(16, result="INSUFFICIENT_DATA"), diagnostic(24),))
        row = next(x for x in rows if x.lens_id == "FUNDAMENTAL_INFLECTION")
        self.assertEqual((24,), row.available_primary_diagnostics)
        self.assertIn(15, row.unavailable_primary_diagnostics)
        self.assertIn(16, row.unavailable_primary_diagnostics)

    def test_rejects_mixed_instrument_cutoff_and_duplicate_rule(self):
        for values in ((diagnostic(24, instrument="NSE:OTHER"),),
                       (diagnostic(24, at=AT + timedelta(days=1)),),
                       (diagnostic(24), diagnostic(24))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                assess_lenses(instrument_id=INSTRUMENT, as_of=AT, diagnostics=values)


if __name__ == "__main__":
    unittest.main()
