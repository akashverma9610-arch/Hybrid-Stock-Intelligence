from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.concall.local_import import import_local_transcript

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def load(path: Path):
    return import_local_transcript(
        path, instrument_id="NSE:TEST", filing_id="filing-1",
        source_reference="official-export", published_at=NOW,
        received_at=NOW, fiscal_year=2027, fiscal_quarter=2,
    )


def test_local_import_is_deterministic(tmp_path):
    path = tmp_path / "concall.txt"
    path.write_text("Management: revenue guidance remains unchanged.", encoding="utf-8")
    a, b = load(path), load(path)
    assert a.document.document_id == b.document.document_id
    assert a.segments[0].speaker == "UNATTRIBUTED"
    assert a.segments[0].document_id == a.document.document_id


def test_reject_unsupported_or_empty_files(tmp_path):
    pdf = tmp_path / "call.pdf"
    pdf.write_bytes(b"%PDF")
    with pytest.raises(ValueError):
        load(pdf)
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    with pytest.raises(ValueError):
        load(empty)


def test_reject_invalid_utf8_and_oversize(tmp_path):
    path = tmp_path / "call.txt"
    path.write_bytes(b"\\xff")
    with pytest.raises(ValueError):
        load(path)
    path.write_text("some content")
    with pytest.raises(ValueError):
        import_local_transcript(
            path, instrument_id="NSE:TEST", filing_id="filing-1",
            source_reference="official-export", published_at=NOW,
            received_at=NOW, fiscal_year=2027, fiscal_quarter=2,
            max_bytes=2,
        )
