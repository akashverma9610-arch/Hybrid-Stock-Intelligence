"""Bounded, provider-free draft coverage over a supplied universe snapshot.

The caller supplies previously computed diagnostic results. This does not
inspect the live database, acquire data, run the brain or qualify securities.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

from app.diagnostics.models import EvaluatedDiagnostic
from app.lens_knowledge.assessment import LensAssessment, assess_lenses, catalog_fingerprint, load_catalog
from app.universe_analysis.models import UniverseSnapshot


@dataclass(frozen=True, slots=True)
class SecurityLensCoverage:
    instrument_id: str
    diagnostic_source_state: str
    diagnostics_fingerprint: str | None
    assessments: tuple[LensAssessment, ...]


@dataclass(frozen=True, slots=True)
class UniverseLensCoverageBatch:
    universe_snapshot_id: str
    universe_checksum: str
    catalog_fingerprint: str
    as_of: datetime
    universe_count: int
    start: int
    next_cursor: int
    completed: bool
    securities_with_results: int
    securities_without_results: int
    securities: tuple[SecurityLensCoverage, ...]
    input_basis: str = "SUPPLIED_UNVERIFIED"
    canonical_input_fingerprints: tuple[tuple[str, str], ...] = ()
    canonical_strategy_fingerprint: str | None = None
    canonical_limitations_fingerprint: str | None = None


def assess_universe_batch(*, universe: UniverseSnapshot, as_of: datetime,
                          diagnostics_by_instrument: Mapping[str, tuple[EvaluatedDiagnostic, ...]],
                          cursor: int = 0, batch_size: int = 100) -> UniverseLensCoverageBatch:
    """Assess a bounded page without fetching or recomputing diagnostics.

    The supplied snapshot is the population, not proof of complete NSE coverage.
    The mapping must contain only identities within the selected batch; absence
    and an empty result tuple are both visible as unavailable. Results can only
    be resumed against the same caller-retained snapshot and cutoff.
    """
    if (not universe.snapshot_id or not universe.checksum or as_of.tzinfo is None
            or as_of.utcoffset() is None or universe.as_of.tzinfo is None
            or universe.as_of.utcoffset() is None):
        raise ValueError("Snapshot identity and timezone-aware cutoffs are required")
    cutoff = as_of.astimezone(timezone.utc)
    if universe.as_of.astimezone(timezone.utc) > cutoff:
        raise ValueError("Universe snapshot is newer than the evaluation cutoff")
    ids = universe.instrument_ids
    if (len(set(ids)) != len(ids) or any(not item for item in ids)
            or universe.eligible_security_count != len(ids)
            or universe.total_records != universe.eligible_security_count + universe.excluded_count):
        raise ValueError("Universe population counts or identities are inconsistent")
    if type(cursor) is not int or type(batch_size) is not int or not 0 <= cursor <= len(ids) or not 1 <= batch_size <= 1000:
        raise ValueError("Invalid cursor or batch size")
    selected = ids[cursor:cursor + batch_size]
    if set(diagnostics_by_instrument) - set(selected):
        raise ValueError("Results contain a security outside the requested batch")
    # Bind the evaluated definitions to their bytes, even if files changed
    # after an earlier in-process catalog read.
    catalog_id = catalog_fingerprint()
    load_catalog.cache_clear()
    load_catalog()
    rows = []
    for instrument_id in selected:
        values = diagnostics_by_instrument.get(instrument_id, ())
        assessments = assess_lenses(instrument_id=instrument_id, as_of=cutoff, diagnostics=values)
        serialized = json.dumps([asdict(item) for item in sorted(values, key=lambda item: item.canonical_rule_id)],
                                sort_keys=True, separators=(",", ":"), default=str)
        fingerprint = sha256(serialized.encode("utf-8")).hexdigest() if values else None
        rows.append(SecurityLensCoverage(instrument_id, "SUPPLIED" if values else "UNAVAILABLE", fingerprint, assessments))
    next_cursor = cursor + len(selected)
    supplied = sum(row.diagnostic_source_state == "SUPPLIED" for row in rows)
    if catalog_id != catalog_fingerprint():
        raise ValueError("Lens catalog changed during assessment")
    return UniverseLensCoverageBatch(universe.snapshot_id, universe.checksum, catalog_id, cutoff, len(ids), cursor,
        next_cursor, next_cursor == len(ids), supplied, len(rows) - supplied, tuple(rows))
