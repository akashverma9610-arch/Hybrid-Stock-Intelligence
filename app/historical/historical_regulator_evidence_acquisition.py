"""Strict adapters for source-dated RBI and IRDAI regulator evidence.

This companion to :mod:`regulator_company_type_evidence` extracts only rows
whose enclosing primary-regulator table explicitly establishes the regulated
population.  It does not classify an issuer or manufacture an entity link.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO
import re
from typing import Iterable

from app.historical import regulator_company_type_evidence as regulator


RBI_TREND_PROGRESS_2022_23_URL = (
    "https://rbidocs.rbi.org.in/rdocs/Publications/PDFs/"
    "0RTP27122023D9394304B3D149428EB730022B3BB232.PDF"
)
IRDAI_ANNUAL_REPORT_2022_23_URL = (
    "https://irdai.gov.in/documents/37343/366637/"
    "%E0%A4%B5%E0%A4%BE%E0%A4%B7%E0%A4%BF%E0%A4%95%2B%E0%A4%B0%E0%A4%BF%E0%A4%AA%E0%A5%8B%E0%A4%B0%E0%A5%8D%E0%A4%9F%2B_"
    "%2BAnnual%2BReport%2B2022-23.pdf/c3ecf83d-ddc1-3d13-da8c-c64364baf20f"
    "?download=true&t=1703656400415&version=1.0"
)
RBI_NBFC_CANCELLATION_2024_02_09_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=57298"

RBI_TREND_PROGRESS_2022_23_RELEASED_ON = date(2023, 12, 27)
IRDAI_ANNUAL_REPORT_2022_23_PUBLISHED_ON = date(2023, 12, 27)
IRDAI_ANNUAL_REPORT_2022_23_AS_OF = date(2023, 3, 31)
RBI_NBFC_CANCELLATION_2024_02_09_PUBLISHED_ON = date(2024, 2, 9)


class HistoricalRegulatorEvidenceAcquisitionError(ValueError):
    """Stable, fail-closed extraction error for historical regulator sources."""


def rbi_trend_progress_bank_batch(*, payload: bytes, observed_at: datetime, source_as_of_date: date,
                                  source_known_on: date, source_reference: str = RBI_TREND_PROGRESS_2022_23_URL) -> regulator.RegulatorEvidenceBatch:
    """Use a structured RBI bank-category table without accepting prose rows."""
    return regulator.rbi_scheduled_bank_batch(
        payload=payload, observed_at=observed_at, source_as_of_date=source_as_of_date,
        source_known_on=source_known_on, source_reference=source_reference,
    )


def rbi_nbfc_cancellation_press_release_batch(*, payload: bytes, observed_at: datetime, published_on: date,
                                              source_reference: str) -> regulator.RegulatorEvidenceBatch:
    """Extract exact cancellation-event rows; CoR issuance is not an interval."""
    if not _aware(observed_at) or not _is_date(published_on) or not source_reference:
        raise HistoricalRegulatorEvidenceAcquisitionError("RBI_CANCELLATION_SOURCE_METADATA_INVALID")
    rows = regulator._html_rows(payload, keep_empty=True)
    index, header = _cancellation_header(rows)
    artifact = regulator.source_artifact_from_payload(
        source=regulator.RegulatorEvidenceSource.RBI_CANCELLED_NBFC_ARC,
        source_reference=source_reference, payload=payload, content_type="text/html",
        observed_at=observed_at, source_as_of_date=published_on, source_known_on=published_on,
        temporal_status=regulator.RegulatorTemporalStatus.CANCELLATION_DATE_PRESENT, schema=header,
    )
    columns = {_header_key(value): number for number, value in enumerate(header)}
    name_at, cor_at, issued_at, cancelled_at = (
        _required_column(columns, "NAME OF THE COMPANY"), _required_column(columns, "COR NO"),
        _required_column(columns, "COR ISSUED ON"), _required_column(columns, "CANCELLATION ORDER DATE"),
    )
    address_at = columns.get("REGISTERED OFFICE ADDRESS")
    values: list[regulator.RegulatorEntityEvidence] = []
    seen: set[tuple[str, str, date, date, str | None]] = set()
    for ordinal, raw in enumerate(rows[index + 1:], start=index + 2):
        row = _trim_repeated_tail(raw, len(header), cancelled_at)
        if len(row) != len(header) or not _serial(row[0]):
            continue
        name, cor, issued, cancelled = (_at(row, name_at), _at(row, cor_at), _date(_at(row, issued_at)), _date(_at(row, cancelled_at)))
        if not name or not cor or issued is None or cancelled is None:
            continue
        key = (name, cor, issued, cancelled, _at(row, address_at))
        if key in seen:
            continue
        seen.add(key)
        values.append(regulator._entity(
            artifact=artifact, source_record_id=f"rbi-nbfc-cancellation-row:{ordinal}",
            entity_kind=regulator.RegulatorEntityEvidenceKind.RBI_CANCELLED_NBFC,
            entity_status=regulator.RegulatorEntityStatus.CANCELLED, legal_name=name,
            regulator_registration_id=cor, address=_at(row, address_at), cancellation_on=cancelled,
            cor_issued_on=issued, temporal_status=regulator.RegulatorTemporalStatus.CANCELLATION_DATE_PRESENT,
        ))
    return regulator._batch(artifact, values)


def irdai_annual_report_2022_23_insurer_batches(*, payload: bytes, observed_at: datetime,
                                                source_reference: str = IRDAI_ANNUAL_REPORT_2022_23_URL) -> tuple[regulator.RegulatorEvidenceBatch, ...]:
    """Extract Annexure 1 insurer populations, excluding specialists/reinsurers.

    The report's Annexure 1 labels Life, Non-Life and Standalone Health.  Only
    rows in the Life or the public/private Non-Life subsections become the
    Life/General families; specialised insurers, reinsurers and intermediaries
    are intentionally absent from this adapter.
    """
    if not _aware(observed_at) or not payload or not source_reference:
        raise HistoricalRegulatorEvidenceAcquisitionError("IRDAI_ANNUAL_REPORT_SOURCE_METADATA_INVALID")
    page_number, lines = _irdai_annexure_one_lines(payload)
    rows = _irdai_insurer_rows(lines)
    by_source = {
        regulator.RegulatorEvidenceSource.IRDAI_LIFE_INSURERS: (
            regulator.RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER, "LIFE"),
        regulator.RegulatorEvidenceSource.IRDAI_GENERAL_INSURERS: (
            regulator.RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER, "GENERAL"),
        regulator.RegulatorEvidenceSource.IRDAI_HEALTH_INSURERS: (
            regulator.RegulatorEntityEvidenceKind.IRDAI_HEALTH_INSURER, "HEALTH"),
    }
    batches: list[regulator.RegulatorEvidenceBatch] = []
    for source, (kind, category) in by_source.items():
        selected = tuple(item for item in rows if item[0] == category)
        artifact = regulator.source_artifact_from_payload(
            source=source, source_reference=source_reference, payload=payload, content_type="application/pdf",
            observed_at=observed_at, source_as_of_date=IRDAI_ANNUAL_REPORT_2022_23_AS_OF,
            source_known_on=IRDAI_ANNUAL_REPORT_2022_23_PUBLISHED_ON,
            temporal_status=regulator.RegulatorTemporalStatus.SOURCE_DATE_PRESENT,
            schema=("annexure", "category", "serial_number", "legal_name"),
        )
        evidence = tuple(
            regulator._entity(
                artifact=artifact, source_record_id=f"irdai-annual-2022-23:page-{page_number}:{section.lower()}:{ordinal}",
                entity_kind=kind, entity_status=regulator.RegulatorEntityStatus.LISTED,
                legal_name=name, regulator_subtype=category,
            )
            for _category, section, ordinal, name in selected
        )
        batches.append(regulator._batch(artifact, evidence))
    return tuple(batches)


def _irdai_annexure_one_lines(payload: bytes) -> tuple[int, tuple[tuple[float, str, str], ...]]:
    try:
        import pdfplumber
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - packaging error is explicit.
        raise HistoricalRegulatorEvidenceAcquisitionError("PDFPLUMBER_REQUIRED_FOR_IRDAI_ANNUAL_REPORT") from error
    try:
        # pypdf's text layer efficiently locates the annexure.  pdfplumber is
        # then used only for that page's layout/character geometry, avoiding
        # an expensive all-page layout traversal.
        reader = PdfReader(BytesIO(payload))
        target_index = next((index for index, page in enumerate(reader.pages) if all(
            marker in _compact(page.extract_text() or "")
            for marker in (
                "LISTOFREGISTEREDINSURERSREINSURERSOPERATINGININDIA",
                "LIFEINSURERS", "STANDALONEHEALTHINSURERS",
            )
        )), None)
        if target_index is None:
            raise HistoricalRegulatorEvidenceAcquisitionError("IRDAI_ANNUAL_REPORT_INSURER_ANNEXURE_UNAVAILABLE")
        with pdfplumber.open(BytesIO(payload)) as document:
            page = document.pages[target_index]
            return target_index + 1, _pdf_column_lines(page.chars)
    except HistoricalRegulatorEvidenceAcquisitionError:
        raise
    except Exception as error:
        raise HistoricalRegulatorEvidenceAcquisitionError("IRDAI_ANNUAL_REPORT_PDF_INVALID") from error
    raise HistoricalRegulatorEvidenceAcquisitionError("IRDAI_ANNUAL_REPORT_INSURER_ANNEXURE_UNAVAILABLE")


def _irdai_insurer_rows(lines: Iterable[tuple[float, str, str]]) -> tuple[tuple[str, str, str, str], ...]:
    family = {"LEFT": None, "RIGHT": None}
    section = {"LEFT": None, "RIGHT": None}
    values: list[tuple[str, str, str, str]] = []
    for _top, column, text in lines:
        compact = _compact(text)
        if column == "LEFT":
            if compact == "LIFEINSURERS":
                family[column] = "LIFE"; section[column] = None; continue
            if compact in {"PUBLICSECTOR", "PRIVATESECTOR"}:
                if family[column] is not None:
                    section[column] = f"{family[column]}_{compact}"
                continue
        else:
            if compact == "NONLIFEINSURERS":
                family[column] = "GENERAL"; section[column] = None; continue
            if compact.startswith("SPECIALIZEDINSURERS"):
                family[column] = "IGNORE"; section[column] = None; continue
            if compact.startswith("STANDALONEHEALTHINSURERS"):
                family[column] = "HEALTH"; section[column] = "HEALTH_PRIVATE"; continue
            if compact in {"PUBLICSECTOR", "PRIVATESECTOR"}:
                if family[column] is not None and family[column] != "IGNORE":
                    section[column] = f"{family[column]}_{compact}"
                continue
        match = re.fullmatch(r"(\d+)\.?\s+(.+)", text)
        if match is None or family[column] in {None, "IGNORE"} or section[column] is None:
            continue
        name = match.group(2).rstrip("$").strip()
        if not name or _compact(name).startswith("ANNUALREPORT"):
            continue
        values.append((family[column], section[column], match.group(1), name))
    ordered = tuple(sorted(set(values), key=lambda item: (item[0], item[1], int(item[2]), item[3])))
    if not ordered or not {item[0] for item in ordered}.issuperset({"LIFE", "GENERAL", "HEALTH"}):
        raise HistoricalRegulatorEvidenceAcquisitionError("IRDAI_ANNUAL_REPORT_INSURER_ROWS_UNAVAILABLE")
    return ordered


def _pdf_column_lines(chars: Iterable[dict[str, object]]) -> tuple[tuple[float, str, str], ...]:
    buckets: dict[tuple[str, int], list[dict[str, object]]] = {}
    for value in chars:
        x0, top = float(value["x0"]), float(value["top"])
        if top < 100 or top > 700:
            continue
        column = "LEFT" if x0 < 300 else "RIGHT"
        buckets.setdefault((column, round(top)), []).append(value)
    lines: list[tuple[float, str, str]] = []
    for (column, top), values in buckets.items():
        ordered = sorted(values, key=lambda item: float(item["x0"]))
        chunks: list[str] = []
        previous_right: float | None = None
        for item in ordered:
            left, right, character = float(item["x0"]), float(item["x1"]), str(item["text"])
            if previous_right is not None and left - previous_right >= 0.65:
                chunks.append(" ")
            chunks.append(character); previous_right = right
        text = "".join(chunks).strip()
        if text:
            lines.append((float(top), column, text))
    return tuple(sorted(lines, key=lambda item: (item[0], item[1])))


def _cancellation_header(rows: tuple[tuple[str, ...], ...]) -> tuple[int, tuple[str, ...]]:
    needed = {"NAME OF THE COMPANY", "COR NO", "COR ISSUED ON", "CANCELLATION ORDER DATE"}
    for index, row in enumerate(rows[:80]):
        header = tuple(_header_key(value) for value in row)
        if needed.issubset(set(header)):
            return index, header
    raise HistoricalRegulatorEvidenceAcquisitionError("RBI_CANCELLATION_HEADERS_UNAVAILABLE")


def _trim_repeated_tail(row: tuple[str, ...], width: int, cancellation_at: int) -> tuple[str, ...]:
    if len(row) == width:
        return row
    if len(row) > width and all(value == row[cancellation_at] for value in row[width:]):
        return row[:width]
    return row


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    for layout in ("%B %d, %Y", "%d %B %Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, layout).date()
        except ValueError:
            pass
    return None


def _required_column(columns: dict[str, int], value: str) -> int:
    if value not in columns:
        raise HistoricalRegulatorEvidenceAcquisitionError("RBI_CANCELLATION_HEADERS_UNAVAILABLE")
    return columns[value]


def _header_key(value: str) -> str:
    return " ".join(value.upper().replace(".", " ").split())


def _at(row: tuple[str, ...], index: int | None) -> str | None:
    return row[index].strip() if index is not None and index < len(row) and row[index].strip() else None


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _serial(value: str) -> bool:
    return re.fullmatch(r"\d+\.?", value.strip()) is not None


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _is_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


__all__ = (
    "HistoricalRegulatorEvidenceAcquisitionError", "IRDAI_ANNUAL_REPORT_2022_23_AS_OF",
    "IRDAI_ANNUAL_REPORT_2022_23_PUBLISHED_ON", "IRDAI_ANNUAL_REPORT_2022_23_URL",
    "RBI_NBFC_CANCELLATION_2024_02_09_PUBLISHED_ON", "RBI_NBFC_CANCELLATION_2024_02_09_URL",
    "RBI_TREND_PROGRESS_2022_23_RELEASED_ON", "RBI_TREND_PROGRESS_2022_23_URL",
    "irdai_annual_report_2022_23_insurer_batches", "rbi_nbfc_cancellation_press_release_batch",
    "rbi_trend_progress_bank_batch",
)
