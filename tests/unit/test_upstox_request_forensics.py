from datetime import UTC, datetime

import pytest

from app.market_data.upstox_forensics import (
    CallResult,
    execute_forensics,
    execute_production_probe,
    prepare_forensics,
    write_support_report,
)


T = datetime(2026, 8, 27, 12, tzinfo=UTC)


def test_prepared_v3_forensics_redacts_token_and_matches_the_documented_headers() -> None:
    forensic = prepare_forensics("  Bearer Bearer synthetic-secret\n", now=T)

    assert forensic.token_audit.present is True
    assert forensic.token_audit.leading_whitespace_present is True
    assert forensic.token_audit.trailing_whitespace_present is True
    assert forensic.token_audit.embedded_newline_present is True
    assert forensic.token_audit.already_has_bearer_prefix is True
    assert forensic.raw_instrument_key == "NSE_EQ|INE437A01024"
    assert forensic.encoded_instrument_key == "NSE_EQ%7CINE437A01024"
    assert "%257C" not in forensic.production.url
    assert "synthetic-secret" not in forensic.production.url
    assert forensic.production.headers["Authorization"] == "Bearer <ANALYTICS_TOKEN_MASKED>"
    assert forensic.direct.headers["Authorization"] == "Bearer <ANALYTICS_TOKEN_MASKED>"
    assert forensic.direct.headers["Content-Type"] == "application/json"
    assert forensic.production.headers["Content-Type"] == "application/json"
    assert forensic.differences == ("MATCH",)


def test_forensics_uses_exactly_one_redacted_direct_and_production_request_and_scans_report(tmp_path) -> None:
    sent = []

    def sender(prepared):
        sent.append(prepared)
        return CallResult(403, "application/json", {"content-type": "application/json", "x-request-id": "safe-id"}, {"code": "UDAPI403", "message": "forbidden"})

    forensic = execute_forensics(
        "synthetic-secret",
        now=T,
        direct_sender=sender,
        production_sender=sender,
    )

    assert len(sent) == 2
    assert all(item.headers["Authorization"] == "Bearer synthetic-secret" for item in sent)
    assert forensic.direct_result is not None and forensic.direct_result.status_code == 403
    assert forensic.production_result is not None and forensic.production_result.status_code == 403
    report = tmp_path / "upstox_analytics_request_diagnostic.md"
    write_support_report(forensic, report, access_token="synthetic-secret")
    contents = report.read_text(encoding="utf-8")
    assert "Authorization: Bearer <ANALYTICS_TOKEN_MASKED>" in contents
    assert "synthetic-secret" not in contents
    assert "Bearer Bearer" not in contents


def test_forensics_redacts_provider_body_or_exception_that_echoes_a_token_before_report_generation(tmp_path) -> None:
    secret = "synthetic-secret"

    def echoing_sender(_):
        return CallResult(403, "application/json", {}, {"provider_message": f"Bearer {secret}"}, f"request failed for {secret}")

    forensic = execute_forensics(secret, now=T, direct_sender=echoing_sender, production_sender=echoing_sender)
    assert forensic.direct_result is not None
    # Injected test senders are trusted only for status mechanics; the report's
    # final secret scan prevents a rogue sender from exposing this value.
    report = tmp_path / "upstox_analytics_request_diagnostic.md"
    with pytest.raises(ValueError, match="secret-safety"):
        write_support_report(forensic, report, access_token=secret)
    assert report.exists() is False


def test_production_probe_makes_one_request_without_triggering_the_direct_documented_call() -> None:
    calls = []

    result = execute_production_probe(
        "synthetic-secret",
        now=T,
        production_sender=lambda prepared: calls.append(prepared) or CallResult(200, "application/json", {}, {"status": "success"}),
    )

    assert len(calls) == 1
    assert result.direct_result is None
    assert result.production_result is not None and result.production_result.status_code == 200
    assert calls[0].headers == {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer synthetic-secret",
    }
