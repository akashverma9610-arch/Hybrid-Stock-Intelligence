import os
import pytest
from app.news.live_validation import validate_live_gnews

def test_gnews_live_validation_is_explicit_and_bounded():
    if not (os.environ.get("GNEWS_LIVE_VALIDATION", "").lower() in {"1","true","yes"} and os.environ.get("GNEWS_API_KEY") and os.environ.get("GNEWS_TEST_QUERY")):
        pytest.skip("GNews live validation is opt-in and requires GNEWS_API_KEY, GNEWS_TEST_QUERY plus GNEWS_LIVE_VALIDATION=true.")
    assert validate_live_gnews() >= 0
