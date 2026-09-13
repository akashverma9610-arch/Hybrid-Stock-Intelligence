"""Pure source parsing and non-active evidence projection; no gate decisions.

ASM/GSM report-API/export equivalence is UNPROVEN. The exact full price-band
CSV can prove capture completeness, not current effective applicability.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
import json
import re

from app.filings.earnings_schedule_identity import (
    EarningsScheduleCanonicalIdentityBridge, EarningsScheduleIdentityResolution,
    IdentityEvidence, IdentityState,
)
from app.filings.earnings_schedule_source import utc
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.historical.nse_mii_security_master import NseMiiSecurityMasterRow, NseMiiSecurityMasterSnapshot
from app.market_data.surveillance_prospective import (
    CaptureState, SurveillanceEvidenceStore, SurveillanceFamily, SurveillancePollReceipt, VERSION,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_dump


PARSER_VERSION = "nse-surveillance-source-parse/v1"
_ROMAN = {"0": 0, "I": 1, "II": 2, "III": 3, "IV": 4}
_BAND_HEADER = ("Symbol", "Series", "Security Name", "Band", "Remarks")


@dataclass(frozen=True, slots=True)
class SurveillanceSourceRow:
    family: SurveillanceFamily
    section: str
    row_number: int
    raw_fields: tuple[tuple[str, str | None], ...]
    symbol: str | None
    isin: str | None
    series: str | None
    stage: int | None
    static_band: Decimal | None
    value_state: str

    def __post_init__(self):
        if (not isinstance(self.family, SurveillanceFamily) or self.row_number < 1
                or type(self.raw_fields) is not tuple or not self.raw_fields
                or self.raw_fields != tuple(sorted(self.raw_fields))
                or len({k for k, _ in self.raw_fields}) != len(self.raw_fields)
                or any(not isinstance(k, str) or (v is not None and not isinstance(v, str)) for k, v in self.raw_fields)
                or self.value_state not in {"EXPLICIT", "UNKNOWN", "UNSUPPORTED", "CONFLICTED"}
                or (self.stage is not None and (type(self.stage) is not int or self.stage not in range(5)))
                or (self.static_band is not None and (not isinstance(self.static_band, Decimal)
                    or not self.static_band.is_finite() or not 0 < self.static_band <= 1))
                or (self.family is SurveillanceFamily.PRICE_BAND and self.stage is not None)
                or (self.family is not SurveillanceFamily.PRICE_BAND and self.static_band is not None)
                or ((self.value_state == "EXPLICIT") != (self.stage is not None or self.static_band is not None))):
            raise ValueError("SURVEILLANCE_ROW_INVALID")

    @property
    def fingerprint(self):
        return content_fingerprint(self)


@dataclass(frozen=True, slots=True)
class SurveillanceObservation:
    row: SurveillanceSourceRow
    identity: EarningsScheduleIdentityResolution
    mapping_state: str
    master_lineage: tuple[IdentityEvidence, ...] = ()
    master_report_date: str | None = None
    nse_security_token: str | None = None
    descriptive_status: str | None = None

    def __post_init__(self):
        self.row.__post_init__()
        self.identity.__post_init__()
        if (self.mapping_state not in {"RESOLVED", "OUTSIDE_HSI_SCOPE", "UNRESOLVED", "CONFLICTED"}
                or type(self.master_lineage) is not tuple
                or self.master_lineage != tuple(sorted(set(self.master_lineage)))
                or len({v.evidence_id for v in self.master_lineage}) != len(self.master_lineage)
                or (self.mapping_state == "RESOLVED" and self.identity.resolution_state is not IdentityState.RESOLVED)
                or (self.row.family is SurveillanceFamily.PRICE_BAND and self.mapping_state == "RESOLVED"
                    and (len(self.master_lineage) != 2 or not self.row.series or not self.master_report_date or not self.nse_security_token))
                or (self.row.family is not SurveillanceFamily.PRICE_BAND and self.master_lineage)):
            raise ValueError("SURVEILLANCE_OBSERVATION_INVALID")


@dataclass(frozen=True, slots=True)
class SurveillanceEvidenceReceipt:
    poll_id: str
    poll_fingerprint: str
    family: SurveillanceFamily
    raw_id: str | None
    first_observed_at: datetime | None
    capture_known_at: datetime
    processed_at: datetime
    capture_state: CaptureState
    capture_proofs: tuple[str, ...]
    rows_seen: int
    rejected_rows: int
    observations: tuple[SurveillanceObservation, ...]
    scope_fingerprint: str
    reasons: tuple[str, ...]
    previous_complete_receipts: tuple[IdentityEvidence, ...]
    replacement_state: str
    parser_version: str = PARSER_VERSION
    source_version: str = VERSION
    official_product_completeness: str = "PRODUCT_DOCUMENTED_COMPLETE"
    source_publication: None = None
    effective_from: None = None
    effective_to: None = None
    effective_state: str = "UNRESOLVED"
    evidence_only: bool = True
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self):
        for name in ("first_observed_at", "capture_known_at", "processed_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, utc(getattr(self, name)))
        for values in (self.capture_proofs, self.reasons):
            if type(values) is not tuple or values != tuple(sorted(set(values))):
                raise ValueError("SURVEILLANCE_RECEIPT_ORDER_INVALID")
        for row in self.observations:
            row.__post_init__()
        if (not isinstance(self.capture_state, CaptureState) or not isinstance(self.family, SurveillanceFamily)
                or not self.poll_id.startswith("surveillance-poll:")
                or self.poll_fingerprint != "sha256:" + self.poll_id.split(":", 1)[1]
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.scope_fingerprint)
                or self.processed_at < self.capture_known_at
                or (self.first_observed_at is not None and self.first_observed_at > self.capture_known_at)
                or ((self.raw_id is None) != (self.first_observed_at is None))
                or min(self.rows_seen, self.rejected_rows) < 0
                or self.rows_seen != len(self.observations) + self.rejected_rows
                or type(self.observations) is not tuple
                or tuple((x.row.section, x.row.row_number) for x in self.observations)
                    != tuple(sorted({(x.row.section, x.row.row_number) for x in self.observations}))
                or any(x.row.family is not self.family or x.identity.as_of != self.capture_known_at for x in self.observations)
                or self.previous_complete_receipts != tuple(sorted(set(self.previous_complete_receipts)))
                or self.replacement_state not in {"NONE", "COMPLETE_REPLACEMENT_CANDIDATE_EFFECTIVITY_UNRESOLVED"}
                or bool(self.previous_complete_receipts) != (self.replacement_state != "NONE")
                or (self.previous_complete_receipts and self.capture_state is not CaptureState.COMPLETE)
                or (self.capture_state is CaptureState.COMPLETE and (self.family is not SurveillanceFamily.PRICE_BAND
                    or self.rejected_rows or not self.observations or "EXACT_COMPLETE_CSV_EXPORT" not in self.capture_proofs))
                or any(x is not None for x in (self.source_publication, self.effective_from, self.effective_to))
                or self.effective_state != "UNRESOLVED" or self.evidence_only is not True
                or self.execution_status != "NON_EXECUTABLE" or self.parser_version != PARSER_VERSION
                or self.source_version != VERSION or self.official_product_completeness != "PRODUCT_DOCUMENTED_COMPLETE"):
            raise ValueError("SURVEILLANCE_EVIDENCE_RECEIPT_INVALID")

    @property
    def record_id(self):
        return "surveillance-evidence:" + content_fingerprint((self.poll_id, self.parser_version, self.scope_fingerprint))[7:]

    @property
    def fingerprint(self):
        return content_fingerprint(self)


def _object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_SOURCE_KEY")
        result[k] = v
    return result


def _fields(row):
    if not isinstance(row, dict) or any(v is not None and not isinstance(v, (str, int)) for v in row.values()):
        raise ValueError("SOURCE_ROW_SHAPE")
    return tuple(sorted((k, None if v is None else str(v)) for k, v in row.items()))


def _source_row(family, section, number, raw):
    fields = _fields(raw)
    band, stage, state = None, None, "UNSUPPORTED"
    if family is SurveillanceFamily.PRICE_BAND:
        symbol, isin, series = raw.get("Symbol"), None, raw.get("Series")
        if not symbol or not series:
            raise ValueError("SOURCE_IDENTITY_FIELDS_MISSING")
        text = raw.get("Band", "").strip()
        if not text:
            state = "UNKNOWN"
        elif re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
            try:
                candidate = Decimal(text) / Decimal(100)
                if 0 < candidate <= 1:
                    band, state = candidate, "EXPLICIT"
            except InvalidOperation:
                pass
    else:
        symbol, isin, series = raw.get("symbol"), raw.get("isin"), raw.get("series")
        if family is SurveillanceFamily.ASM:
            labels = {"Stage " + k: v for k, v in _ROMAN.items() if v}
            stage = labels.get(raw.get("asmSurvIndicator"))
            prefix = "LTASM" if section == "longterm" else "STASM"
            match = re.fullmatch(prefix + r" - (I|II|III|IV) \([0-9]+\)", str(raw.get("survCode", "")))
            if stage is not None and (not match or _ROMAN[match[1]] != stage):
                stage, state = None, "CONFLICTED"
            elif stage is not None:
                state = "EXPLICIT"
        else:
            # gsmStage is often a *composite surveillance indicator*, not a
            # GSM stage. Only corroborated single-GSM labels are decoded here.
            match = re.fullmatch(r"GSM - (0|I|II|III|IV) \([0-9]+\)", str(raw.get("survCode", "")))
            if match and raw.get("gsmStage") == match[1]:
                stage, state = _ROMAN[match[1]], "EXPLICIT"
            elif match:
                state = "CONFLICTED"
    return SurveillanceSourceRow(family, section, number, fields, symbol, isin, series, stage, band, state)


def parse_source(poll: SurveillancePollReceipt):
    """Return parsed rows plus independent capture proof; never clearance.

    Raw asmTime/gsmTime remain source-labelled strings. Their publication and
    effectiveness meaning is not invented from a display/report timestamp.
    """
    poll.__post_init__()
    if poll.raw is None or poll.http_status != 200:
        return (), 0, CaptureState.FAILED, (), (poll.reason or "NO_SOURCE_PAYLOAD",)
    rows, rejected, seen = [], 0, 0
    proofs = ["FIXED_OFFICIAL_PRODUCT_PATH"]
    reason = []
    try:
        text = poll.raw.raw_payload().decode("utf-8-sig")
        if poll.family is SurveillanceFamily.PRICE_BAND:
            reader = csv.reader(StringIO(text), strict=True)
            if tuple(next(reader, ())) != _BAND_HEADER:
                raise ValueError("SOURCE_SCHEMA")
            for number, fields in enumerate(reader, 1):
                if not fields:
                    continue
                seen += 1
                if len(fields) != len(_BAND_HEADER):
                    rejected += 1
                else:
                    try:
                        rows.append(_source_row(poll.family, "complete_csv", number, dict(zip(_BAND_HEADER, fields, strict=True))))
                    except ValueError:
                        rejected += 1
            proofs.extend(("EXACT_COMPLETE_CSV_EXPORT", "EXPECTED_SCHEMA", "ALL_CSV_ROWS_CONSUMED_NO_PAGINATION"))
            state = CaptureState.COMPLETE if rows and not rejected else CaptureState.PARTIAL
        else:
            data = json.loads(text, object_pairs_hook=_object)
            sections = data if poll.family is SurveillanceFamily.ASM else {"gsm": {"data": data}}
            if not isinstance(sections, dict) or set(sections) != ({"longterm", "shortterm"} if poll.family is SurveillanceFamily.ASM else {"gsm"}):
                raise ValueError("SOURCE_SECTIONS")
            for name, section in sorted(sections.items()):
                if not isinstance(section, dict) or set(section) != {"data"} or not isinstance(section["data"], list):
                    raise ValueError("SOURCE_SECTION_SHAPE")
                for number, raw in enumerate(section["data"], 1):
                    seen += 1
                    try:
                        rows.append(_source_row(poll.family, name, number, raw))
                    except (ValueError, TypeError):
                        rejected += 1
            state = CaptureState.UNPROVEN if not rejected else CaptureState.PARTIAL
            proofs.append("ALL_RETURNED_API_SECTIONS_PARSED")
            reason.append("API_TO_COMPLETE_PRODUCT_EQUIVALENCE_UNPROVEN")
        if poll.transfer_complete:
            proofs.append("TRANSPORT_EOF_OBSERVED")
        else:
            state = CaptureState.PARTIAL
            reason.append(poll.reason or "TRANSFER_INCOMPLETE")
        if poll.declared_length is not None:
            if poll.declared_length == poll.bytes_received:
                proofs.append("DECLARED_LENGTH_MATCH")
            else:
                state = CaptureState.PARTIAL
                reason.append("LENGTH_MISMATCH")
    except (UnicodeError, ValueError, TypeError, csv.Error):
        return (), max(seen, 1), CaptureState.PARTIAL, (), ("SOURCE_PARSE_INCOMPLETE",)
    keys = {}
    for row in rows:
        key = (row.section, row.symbol, row.series if poll.family is SurveillanceFamily.PRICE_BAND else None)
        semantic = (row.isin, row.stage, row.static_band, row.value_state)
        if key in keys:
            reason.append("DUPLICATE_SOURCE_ROW" if keys[key] == semantic else "CONFLICTING_SOURCE_ROWS")
        keys[key] = semantic
    if "CONFLICTING_SOURCE_ROWS" in reason or any(r.value_state == "CONFLICTED" for r in rows):
        state = CaptureState.CONFLICTED
        reason.append("SOURCE_VALUE_CONFLICT")
    elif "DUPLICATE_SOURCE_ROW" in reason:
        state = CaptureState.PARTIAL
    if rejected:
        reason.append("REJECTED_SOURCE_ROWS")
    return tuple(rows), rejected, state, tuple(sorted(set(proofs))), tuple(sorted(set(reason)))


def _master_rows(snapshots: tuple[CoreApiSnapshot, ...], as_of: datetime):
    """Validate existing master snapshots; do not create a master or continuity."""
    masters, rows = {}, []
    for s in snapshots:
        if s.created_at > as_of:
            continue
        p = s.payload
        if not isinstance(p, (NseMiiSecurityMasterRow, NseMiiSecurityMasterSnapshot)):
            raise ValueError("SURVEILLANCE_MASTER_TYPE_INVALID")
        p.__post_init__()
        if (s.family is not CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT
                or s.fingerprint != p.fingerprint or s.snapshot_id != (p.row_id if isinstance(p, NseMiiSecurityMasterRow) else p.snapshot_id)
                or s.created_at != p.document_observed_at or p.report_date > as_of.date()):
            raise ValueError("SURVEILLANCE_MASTER_LINEAGE_INVALID")
        if isinstance(p, NseMiiSecurityMasterSnapshot):
            masters[p.snapshot_id] = p
        else:
            rows.append(p)
    result = {}
    for row in rows:
        master = masters.get(row.snapshot_id)
        if master is None or master.report_date != row.report_date:
            raise ValueError("SURVEILLANCE_MASTER_PARENT_MISSING")
        result.setdefault((row.symbol, row.series), []).append((row, master))
    return result


def project_poll(store: SurveillanceEvidenceStore, poll_id: str, *,
                 identity_bridge: EarningsScheduleCanonicalIdentityBridge,
                 master_snapshots: tuple[CoreApiSnapshot, ...] = (),
                 clock=None) -> SurveillanceEvidenceReceipt:
    """Replay the original poll with PIT-visible canonical identity only.

    Any receipt is later adapter INPUT, not an admitted GateEvidenceContext.
    Existing MII date rows can prove an exact join but not current tradability
    or effective continuity. Those limitations remain explicit.
    """
    from app.filings.earnings_schedule_prospective_receipt_collector import SystemUtcClock
    poll = store.get(poll_id)
    if not isinstance(poll, SurveillancePollReceipt):
        raise ValueError("SURVEILLANCE_POLL_REQUIRED")
    if poll.raw is not None and store.get(poll.raw.record_id) != poll.raw:
        raise ValueError("SURVEILLANCE_RAW_PARENT_UNVERIFIED")
    # Hash only PIT-visible identity inputs: future identities cannot even
    # perturb a historical projection's identity or provenance.
    known = tuple(sorted((s for s in identity_bridge.snapshots if s.created_at <= poll.completed_at), key=lambda s: s.snapshot_id))
    masters = (tuple(sorted((s for s in master_snapshots if s.created_at <= poll.completed_at), key=lambda s: s.snapshot_id))
        if poll.family is SurveillanceFamily.PRICE_BAND else ())
    if identity_bridge.identities or len({s.snapshot_id for s in known}) != len(known) or len({s.snapshot_id for s in masters}) != len(masters):
        raise ValueError("SURVEILLANCE_DUPLICATE_OR_UNBOUND_IDENTITY")
    bridge = EarningsScheduleCanonicalIdentityBridge(known)
    scope_fp = content_fingerprint(tuple(snapshot_dump(s) for s in known + masters))
    record_id = "surveillance-evidence:" + content_fingerprint((poll_id, PARSER_VERSION, scope_fp))[7:]
    existing = store.get(record_id)
    if existing is not None:
        if not isinstance(existing, SurveillanceEvidenceReceipt):
            raise ValueError("SURVEILLANCE_RECEIPT_COLLISION")
        return existing
    rows, rejected, state, proofs, reasons = parse_source(poll)
    master_index = _master_rows(masters, poll.completed_at) if poll.family is SurveillanceFamily.PRICE_BAND else {}
    observations = []
    for row in rows:
        identity = bridge.resolve_nse(row.symbol, row.isin, poll.completed_at)
        mapping = ("RESOLVED" if identity.resolution_state is IdentityState.RESOLVED else
            "CONFLICTED" if identity.resolution_state in {IdentityState.AMBIGUOUS, IdentityState.IDENTITY_CONFLICTED} else
            "OUTSIDE_HSI_SCOPE" if identity.resolution_state is IdentityState.IDENTITY_UNAVAILABLE else "UNRESOLVED")
        refs, report_date, token, status = (), None, None, None
        if row.family is SurveillanceFamily.PRICE_BAND and mapping == "RESOLVED":
            matches = master_index.get((row.symbol, row.series), ())
            if len(matches) != 1 or not row.series:
                mapping = "CONFLICTED" if len(matches) > 1 else "UNRESOLVED"
            else:
                m, parent = matches[0]
                if m.isin != identity.canonical_isin:
                    mapping = "CONFLICTED"
                else:
                    refs = tuple(sorted((IdentityEvidence(m.row_id, m.fingerprint), IdentityEvidence(parent.snapshot_id, parent.fingerprint))))
                    report_date, token, status = m.report_date.isoformat(), m.security_code, m.normal_market_status_raw
        observations.append(SurveillanceObservation(row, identity, mapping, refs, report_date, token, status))
    if any(o.mapping_state == "CONFLICTED" for o in observations):
        state, reasons = CaptureState.CONFLICTED, tuple(sorted(set(reasons + ("IDENTITY_CONFLICT",))))
    # Keep complete replacement lineage, never timestamp-vote among unresolved
    # sources or turn a partial poll into removal. Effective admission deferred.
    prior = []
    if state is CaptureState.COMPLETE:
        offset = 0
        while True:
            page = store.repository.list_snapshots(store.family, limit=100, offset=offset)
            for s in page:
                if isinstance(s.payload, SurveillanceEvidenceReceipt):
                    p = store.get(s.snapshot_id)
                    if (p.family is poll.family and p.capture_state is CaptureState.COMPLETE
                            and p.capture_known_at < poll.completed_at and p.raw_id != (poll.raw.record_id if poll.raw else None)):
                        prior.append(IdentityEvidence(p.record_id, p.fingerprint))
            if len(page) < 100:
                break
            offset += len(page)
    receipt = SurveillanceEvidenceReceipt(poll.record_id, poll.fingerprint, poll.family,
        poll.raw.record_id if poll.raw else None, poll.raw.first_observed_at if poll.raw else None,
        poll.completed_at, utc((clock or SystemUtcClock()).now()), state, proofs,
        len(rows) + rejected, rejected, tuple(observations), scope_fp,
        tuple(sorted(set(reasons + ("SOURCE_TIME_SEMANTICS_AND_EFFECTIVE_INTERVAL_UNRESOLVED",)
            + (("MASTER_DATE_ROW_IS_NOT_CURRENT_EXECUTION_CONTINUITY",) if poll.family is SurveillanceFamily.PRICE_BAND else ())))),
        tuple(sorted(set(prior))), "COMPLETE_REPLACEMENT_CANDIDATE_EFFECTIVITY_UNRESOLVED" if prior else "NONE")
    return store.save(receipt, receipt.processed_at)


def summary(receipt: SurveillanceEvidenceReceipt) -> dict:
    receipt.__post_init__()
    return dict(receipt_id=receipt.record_id, fingerprint=receipt.fingerprint, family=receipt.family,
        product_completeness=receipt.official_product_completeness, capture=receipt.capture_state,
        rows=receipt.rows_seen, rejected=receipt.rejected_rows,
        mapping={k: sum(x.mapping_state == k for x in receipt.observations)
            for k in ("RESOLVED", "OUTSIDE_HSI_SCOPE", "UNRESOLVED", "CONFLICTED")},
        unsupported_values=sum(x.row.value_state == "UNSUPPORTED" for x in receipt.observations),
        explicit_values=sum(x.row.value_state == "EXPLICIT" for x in receipt.observations),
        first_observed_at=receipt.first_observed_at.isoformat() if receipt.first_observed_at else None,
        capture_known_at=receipt.capture_known_at.isoformat(), processed_at=receipt.processed_at.isoformat(),
        effective_state=receipt.effective_state, capture_proofs=receipt.capture_proofs, reasons=receipt.reasons,
        execution_status=receipt.execution_status)
