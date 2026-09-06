"""Bounded archived-row verification shared by explicit database migrations."""
from functools import lru_cache
from typing import Callable

from app.market_data.models import CanonicalOHLCVBar
from app.market_data.nse_udiff_daily_history import (
    NseUdiffDailySourceArtifact, NseUdiffDailyTarget, _bar_from_row, _parse_valid_archive,
)
from app.market_data.nse_udiff_source_identity import observation_key, source_row_id


class UdiffArchiveVerifier:
    def __init__(self, load: Callable[[str], NseUdiffDailySourceArtifact]) -> None:
        @lru_cache(maxsize=4)
        def parsed(identifier: str):
            artifact = load(identifier)
            artifact.__post_init__()
            if artifact.artifact_id != identifier:
                raise ValueError("UDIFF_ARCHIVE_IDENTITY_MISMATCH")
            return artifact, _parse_valid_archive(artifact)
        self._parsed = parsed

    def __call__(self, bar: CanonicalOHLCVBar) -> None:
        reference = bar.provenance.request_reference or ""
        try:
            identifier, suffix = reference.rsplit(":row:", 1)
            index = int(suffix.split(":", 1)[0])
        except (ValueError, IndexError):
            raise ValueError("UDIFF_ARCHIVED_ROW_REFERENCE_REQUIRED") from None
        artifact, parsed = self._parsed(identifier)
        if index < 0 or index >= len(parsed.rows):
            raise ValueError("UDIFF_ARCHIVED_ROW_INDEX_INVALID")
        row = parsed.rows[index]
        if row["TckrSymb"] != bar.instrument.symbol or row["ISIN"] != bar.instrument.isin:
            raise ValueError("UDIFF_ARCHIVED_SOURCE_IDENTITY_MISMATCH")
        target = NseUdiffDailyTarget(bar.instrument.instrument_id, bar.instrument.isin, bar.instrument.symbol, bar.instrument)
        expected, _ = _bar_from_row(artifact, parsed, index, row, target)
        if expected != bar or observation_key(bar) != source_row_id(row):
            raise ValueError("UDIFF_ARCHIVED_OBSERVATION_MISMATCH")
