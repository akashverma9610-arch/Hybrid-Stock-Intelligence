"""Explicit local text importer; no network, PDF parser or automatic claims."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from .models import ConcallDocument, ConcallSegment


@dataclass(frozen=True, slots=True)
class LocalConcallImport:
    document: ConcallDocument
    segments: tuple[ConcallSegment, ...]


def import_local_transcript(
    path: Path,
    *,
    instrument_id: str,
    filing_id: str,
    source_reference: str,
    published_at: datetime,
    received_at: datetime,
    fiscal_year: int,
    fiscal_quarter: int,
    max_bytes: int = 2_000_000,
) -> LocalConcallImport:
    """Import only explicitly supplied UTF-8 .txt files.

    Caller is responsible for validating source rights and linking the filing ID
    to an existing immutable filing. Nothing is persisted or downloaded here.
    """
    if not isinstance(path, Path) or path.suffix.lower() != ".txt" or not path.is_file() or path.is_symlink():
        raise ValueError("CONCALL_LOCAL_TXT_FILE_REQUIRED")
    if max_bytes <= 0 or path.stat().st_size > max_bytes:
        raise ValueError("CONCALL_FILE_SIZE_INVALID")
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise ValueError("CONCALL_FILE_SIZE_INVALID")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("CONCALL_UTF8_REQUIRED") from exc
    if not content.strip():
        raise ValueError("CONCALL_EMPTY_TRANSCRIPT")
    document = ConcallDocument(
        instrument_id=instrument_id,
        filing_id=filing_id,
        source_reference=source_reference,
        checksum=sha256(raw).hexdigest(),
        published_at=published_at,
        received_at=received_at,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
    )
    # Speaker attribution is deliberately unknown until evidence is verified.
    segments = (ConcallSegment(document.document_id, 0, "UNATTRIBUTED", content),)
    return LocalConcallImport(document, segments)
