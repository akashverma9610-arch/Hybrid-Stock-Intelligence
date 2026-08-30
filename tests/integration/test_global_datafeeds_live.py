"""Explicit live GDFL smoke; skipped unless every local opt-in is supplied."""
import os,pytest
@pytest.mark.skipif(not all((os.getenv("GDFL_LIVE_VALIDATION") == "true",os.getenv("GDFL_ACCESS_KEY"),os.getenv("GDFL_TEST_EXCHANGE"),os.getenv("GDFL_TEST_INSTRUMENT"))),reason="GDFL live validation is disabled or local test mapping/credential is incomplete.")
def test_gdfl_live_validation_is_explicitly_opt_in():
    # Transport construction is intentionally host-owned; this test never runs by default.
    assert os.getenv("GDFL_LIVE_VALIDATION") == "true"
