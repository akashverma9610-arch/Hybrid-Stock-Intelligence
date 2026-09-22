"""Read-only binding of native source stores to the existing Daily certifier.

No indicators, source acquisition, clock, persistence or alternate price basis.
The caller supplies owning read-only stores and one explicit canonical cutoff.
Shared identity/action facts are read once per binding instance/cutoff.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.nse_udiff_effective_identity_coverage import (
    NseUdiffEffectiveIdentityCoverageIndex, compose_action_window_coverage,
)
from app.market_data.models import Timeframe
from app.market_data.nse_udiff_daily_technical_eligibility import (
    expected_nse_daily_sessions, expected_udiff_daily_sessions,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence, NseUdiffDailyTechnicalReadRequest,
    NseUdiffDailyTechnicalReadState, NseUdiffDailyTechnicalUseMode,
    NseUdiffCertifiedDailyTechnicalRead, read_certified_daily_technical_bars,
)
from app.market_data.nse_udiff_source_identity import is_udiff, source_fields
from app.market_data.nse_udiff_daily_integrity import audit_udiff_same_provider_conflicts
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.universe_analysis.technical_diagnostic_input import CanonicalTechnicalDiagnosticInput, assemble_current_descriptive_technical_input


class NativeSourceBindingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NativeDailyBinding:
    certified_read: NseUdiffCertifiedDailyTechnicalRead
    technical_input: CanonicalTechnicalDiagnosticInput | None
    action_window_fingerprint: str | None


class NativeDailyTechnicalBinding:
    """Native owner records, never a caller-authored completeness assertion.

    This class cannot promote current-descriptive certification to strict PIT.
    Missing identity/action coverage is handed to the existing certifier. It
    deliberately cannot repair or extend a retained historical source window.
    """

    def __init__(self, *, repository, historical_store, as_of: datetime):
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise NativeSourceBindingError("NATIVE_BINDING_AWARE_CUTOFF_REQUIRED")
        self._repository, self._bars = repository, historical_store
        self._as_of = as_of.astimezone(UTC)
        self._cache = {}

    def _family(self, family):
        if family not in self._cache:
            values = []
            offset = 0
            while True:
                page = self._repository.list_snapshots(family, limit=100, offset=offset)
                if len(page) > 100:
                    raise NativeSourceBindingError("NATIVE_BINDING_PAGE_INVALID")
                for item in page:
                    if item.family is not family:
                        raise NativeSourceBindingError("NATIVE_BINDING_FAMILY_MISMATCH")
                    if item.created_at <= self._as_of:
                        if hasattr(item.payload, "__post_init__"):
                            item.payload.__post_init__()
                        # Retention time is not a substitute for the native
                        # coverage artifact's own evidence cutoff.
                        native_as_of = getattr(item.payload, "as_of", None)
                        if native_as_of is not None and native_as_of > self._as_of:
                            continue
                        values.append(item.payload)
                if len(page) < 100:
                    break
                offset += 100
                if offset >= 100_000:
                    raise NativeSourceBindingError("NATIVE_BINDING_READ_LIMIT_EXCEEDED")
            self._cache[family] = tuple(values)
        return self._cache[family]

    def _sessions(self, start, end):
        calendar = nse_capital_market_calendar_2022_2026()
        # Exact historical source coverage is used only inside its retained
        # endpoints. Never extend it to a current date by a weekday heuristic.
        manifests = self._family(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST)
        # Native historical manifests enumerate requested exchange sessions,
        # not every calendar date. Reuse their owner-reader inside a fully
        # retained window instead of asking the forward calendar to backfill it.
        states = {}
        for manifest in manifests:
            for entry in manifest.entries:
                if start <= entry.trade_date <= end:
                    entry.__post_init__()
                    previous = states.setdefault(entry.trade_date, entry.state)
                    if previous != entry.state:
                        raise NativeSourceBindingError("NATIVE_BINDING_SESSION_CONFLICT")
        historical = tuple(manifest for manifest in manifests
            if manifest.entries and manifest.entries[0].trade_date <= start
            and manifest.entries[-1].trade_date >= end)
        if historical:
            windows = tuple(expected_udiff_daily_sessions(coverage=manifest,
                start_session=start, end_session=end) for manifest in historical)
            if any(window != windows[0] for window in windows):
                raise NativeSourceBindingError("NATIVE_BINDING_SESSION_CONFLICT")
            return windows[0]
        sessions = []
        cursor = start
        while cursor <= end:
            candidates = []
            for manifest in manifests:
                entries = tuple(x for x in manifest.entries if x.trade_date == cursor)
                if entries:
                    for entry in entries:
                        entry.__post_init__()
                    candidates.extend(entries)
            if candidates:
                if len(set((x.state, x.trade_date) for x in candidates)) != 1:
                    raise NativeSourceBindingError("NATIVE_BINDING_SESSION_CONFLICT")
                state = candidates[0].state.value
                if state == "ARTIFACT_VALID_SESSION":
                    sessions.append(cursor)
                elif state != "CONFIRMED_NON_TRADING_DAY":
                    raise NativeSourceBindingError("EXPECTED_SESSION_UNRESOLVED")
            else:
                resolved = calendar.resolve_trading_day(cursor, as_of=self._as_of)
                if resolved.state.value == "UNKNOWN":
                    raise NativeSourceBindingError("EXPECTED_SESSION_UNRESOLVED")
                if resolved.state.value not in {"HOLIDAY", "WEEKEND_NON_TRADING"}:
                    sessions.extend(expected_nse_daily_sessions(calendar=calendar, start_session=cursor,
                        end_session=cursor, as_of=self._as_of))
            cursor += timedelta(days=1)
        if not sessions:
            raise NativeSourceBindingError("EXPECTED_SESSION_REQUIRED")
        return tuple(sessions)

    def read(self, request: NseUdiffDailyTechnicalReadRequest) -> NativeDailyBinding:
        request.__post_init__()
        if request.evaluation_as_of.astimezone(UTC) != self._as_of:
            raise NativeSourceBindingError("NATIVE_BINDING_CUTOFF_MISMATCH")
        if request.use_mode is NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL:
            return NativeDailyBinding(read_certified_daily_technical_bars(request=request, evidence=None), None, None)
        sessions = self._sessions(request.start_session, request.end_session)
        identities = self._family(CoreApiSnapshotFamily.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL)
        identities = tuple(x for x in identities if x.known_at <= self._as_of)
        for identity in identities:
            identity.__post_init__()
        identity_index = NseUdiffEffectiveIdentityCoverageIndex(identities)
        queries = self._family(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_QUERY_RECEIPT)
        queries = tuple(x for x in queries if x.observed_at <= self._as_of)
        actions = self._family(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION)
        actions = tuple(sorted((x for x in actions if x.canonical_instrument_id == request.canonical_instrument_id
            and x.eligible_as_of(self._as_of)), key=lambda x: (x.effective_date, x.action_id)))
        coverage = compose_action_window_coverage(canonical_instrument_id=request.canonical_instrument_id,
            window_start=request.start_session, window_end=request.end_session,
            identity_intervals=identity_index, query_receipts=queries, actions=actions,
            evaluation_as_of=self._as_of, required_sessions=sessions)
        start = datetime.combine(request.start_session, time.min, tzinfo=UTC) - timedelta(days=1)
        end = datetime.combine(request.end_session, time.max, tzinfo=UTC)
        values = self._bars.raw_range(request.canonical_instrument_id, Timeframe.DAILY, start, end, as_of=self._as_of)
        # Preserve the owning store's conservative labelled-bar end boundary.
        # The calendar close must not silently rewrite it. Also enforce PIT
        # explicitly for injected readers; no future receipt can enter a read.
        # Provider filtering is explicit; never substitute Upstox to fill gaps.
        selected = tuple(sorted((x for x in values if is_udiff(x) and
            x.end_time <= self._as_of and x.provenance.received_at <= self._as_of and
            request.start_session.isoformat() <= source_fields(x)["TradDt"] <= request.end_session.isoformat()),
            key=lambda x: (x.start_time, x.bar_id)))
        conflicts = audit_udiff_same_provider_conflicts(tuple(x for x in
            self._bars.list_conflict_artifacts(instrument_id=request.canonical_instrument_id)
            if x.detected_at <= self._as_of))
        conflicts = tuple(sorted(conflicts, key=lambda x: (x.trade_date, x.conflict_fingerprint)))
        evidence = NseUdiffDailyTechnicalReadEvidence(sessions, selected, identity_index, coverage.assertion(), actions, conflicts)
        certified = read_certified_daily_technical_bars(request=request, evidence=evidence)
        technical = None
        if certified.state is NseUdiffDailyTechnicalReadState.READY:
            technical = assemble_current_descriptive_technical_input(canonical_instrument_id=request.canonical_instrument_id,
                as_of=self._as_of, daily_reads=(certified,), weekly_bars=())
        return NativeDailyBinding(certified, technical, coverage.fingerprint)
