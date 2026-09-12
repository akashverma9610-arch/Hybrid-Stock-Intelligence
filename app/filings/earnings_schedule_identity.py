"""Read-only exact identity admission; not listing, trading or schedule authority.

Consumes the existing append-only NSE universe, historical security identities
and official BSE mappings. Current observations are never historical intervals.
UDiFF/MII session evidence and broker transport mappings are not promoted here.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import re
from urllib.parse import urlsplit

from app.filings.earnings_schedule_source import utc
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.security_identity_selector import (
    HistoricalSecurityIdentityResolutionStatus as H, resolve_historical_security_identity,
)
from app.historical.security_master import HistoricalSecurityIdentity
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily as F, CoreApiSnapshotRepository,
)
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord, ProviderMappingStatus

VERSION = "earnings-schedule-canonical-identity/v1"
FAMILIES = (F.NSE_UNIVERSE, F.HISTORICAL_SECURITY_IDENTITY, F.PROVIDER_INSTRUMENT_MAPPING)
_ISIN = re.compile(r"IN[A-Z0-9]{9}[0-9]\Z")
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9&_.-]*\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
# The committed pre-extension mapping contract (d64bb98) had exactly these
# fields. Snapshot decoding fills later optional metadata with None. Verify
# that original representation only when every extension is absent; never
# drop populated fields to make a mismatched fingerprint pass.
_LEGACY_MAPPING_FIELDS = ("mapping_id", "canonical_instrument_id", "provider", "provider_exchange_segment",
    "provider_instrument_reference", "provider_symbol", "isin", "status", "effective_as_of",
    "source_reference", "source_checksum", "mapping_version")


class IdentityState(StrEnum):
    RESOLVED = "RESOLVED"
    IDENTITY_UNAVAILABLE = "IDENTITY_UNAVAILABLE"
    IDENTITY_NOT_EFFECTIVE = "IDENTITY_NOT_EFFECTIVE"
    IDENTITY_CONFLICTED = "IDENTITY_CONFLICTED"
    SOURCE_IDENTITY_INCOMPLETE = "SOURCE_IDENTITY_INCOMPLETE"
    AMBIGUOUS = "AMBIGUOUS"


class IdentityAuthority(StrEnum):
    NSE_CURRENT_UNIVERSE = "NSE_CURRENT_UNIVERSE"
    HISTORICAL_SECURITY_IDENTITY = "HISTORICAL_SECURITY_IDENTITY"
    BSE_OFFICIAL_XBRL_MAPPING = "BSE_OFFICIAL_XBRL_MAPPING"


@dataclass(frozen=True, slots=True, order=True)
class IdentityEvidence:
    evidence_id: str
    fingerprint: str

    def __post_init__(self):
        if not self.evidence_id or not _FP.fullmatch(self.fingerprint):
            raise ValueError("EARNINGS_IDENTITY_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class EarningsScheduleIdentityResolution:
    source_exchange: str
    source_identifier: str | None
    source_isin: str | None
    as_of: datetime
    resolution_state: IdentityState
    reasons: tuple[str, ...]
    canonical_instrument_id: str | None
    canonical_isin: str | None
    canonical_nse_symbol: str | None
    canonical_bse_code: str | None
    identity_authority: IdentityAuthority | None
    effective_from: datetime | None
    effective_to: datetime | None
    evidence: tuple[IdentityEvidence, ...]
    fingerprint: str
    version: str = VERSION

    def __post_init__(self):
        object.__setattr__(self, "as_of", utc(self.as_of))
        for name in ("effective_from", "effective_to"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, utc(getattr(self, name)))
        if (self.version != VERSION or self.source_exchange not in {"NSE", "BSE"}
                or (self.source_identifier is not None and not isinstance(self.source_identifier, str))
                or (self.source_isin is not None and not isinstance(self.source_isin, str))
                or not isinstance(self.resolution_state, IdentityState)
                or self.reasons != tuple(sorted(set(self.reasons)))
                or self.evidence != tuple(sorted(set(self.evidence)))):
            raise ValueError("EARNINGS_IDENTITY_RESOLUTION_INVALID")
        for item in self.evidence:
            item.__post_init__()
        resolved = self.resolution_state is IdentityState.RESOLVED
        if resolved:
            if (self.reasons or not self.evidence or len({e.evidence_id for e in self.evidence}) != len(self.evidence)
                    or not _ISIN.fullmatch(self.canonical_isin or "")
                    or self.canonical_instrument_id != "NSE:" + self.canonical_isin
                    or (self.canonical_nse_symbol is not None and not _SYMBOL.fullmatch(self.canonical_nse_symbol))
                    or (self.canonical_bse_code is not None and not re.fullmatch(r"[0-9]{6}", self.canonical_bse_code))
                    or not isinstance(self.identity_authority, IdentityAuthority)
                    or self.effective_from is None or self.effective_from > self.as_of
                    or (self.effective_to is not None and self.effective_to < self.as_of)
                    or (self.source_isin is not None and self.source_isin != self.canonical_isin)
                    or self.source_identifier != (self.canonical_nse_symbol if self.source_exchange == "NSE" else self.canonical_bse_code)):
                raise ValueError("EARNINGS_IDENTITY_RESOLVED_FIELDS_INVALID")
        elif not self.reasons or any(x is not None for x in (
                self.canonical_instrument_id, self.canonical_isin, self.canonical_nse_symbol,
                self.canonical_bse_code, self.identity_authority, self.effective_from, self.effective_to)):
            raise ValueError("EARNINGS_IDENTITY_UNAVAILABLE_FIELDS_INVALID")
        if self.fingerprint != content_fingerprint(self._body()):
            raise ValueError("EARNINGS_IDENTITY_FINGERPRINT_MISMATCH")

    def _body(self):
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "fingerprint"}

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(self)


@dataclass(frozen=True, slots=True)
class _Claim:
    instrument: str
    isin: str
    symbol: str | None
    code: str | None
    authority: IdentityAuthority
    start: datetime
    end: datetime | None
    evidence: tuple[IdentityEvidence, ...]


def _snapshot_valid(s: CoreApiSnapshot) -> bool:
    """Verify, never repair, the two existing stores' repr-based fingerprints."""
    p = s.payload
    expected_type = "historical-security-master-v1" if isinstance(p, HistoricalSecurityIdentity) else "universe-analysis-v1"
    if isinstance(p, NseEquityInstrument):
        family, key, at = F.NSE_UNIVERSE, f"nse-equity:{p.instrument_id}:{p.data_as_of.isoformat()}", p.data_as_of
    elif isinstance(p, ProviderInstrumentMappingRecord):
        family, key, at = F.PROVIDER_INSTRUMENT_MAPPING, f"provider-mapping:{p.mapping_id}", p.effective_as_of
    elif isinstance(p, HistoricalSecurityIdentity):
        family, key, at = F.HISTORICAL_SECURITY_IDENTITY, f"historical-security:{p.identity_id}", p.as_of
    else:
        return False
    utc(at)
    hashes = {sha256(repr(p).encode()).hexdigest()}
    if isinstance(p, ProviderInstrumentMappingRecord) and all(
            getattr(p, f.name) is None for f in fields(p) if f.name not in _LEGACY_MAPPING_FIELDS):
        legacy = "ProviderInstrumentMappingRecord(" + ", ".join(f"{name}={getattr(p, name)!r}" for name in _LEGACY_MAPPING_FIELDS) + ")"
        hashes.add(sha256(legacy.encode()).hexdigest())
    return (s.family == family and s.snapshot_id == key and s.created_at == at
            and s.schema_version == "v1" and s.record_type == expected_type
            and s.fingerprint in hashes)


def _ref(s: CoreApiSnapshot) -> IdentityEvidence:
    return IdentityEvidence(s.snapshot_id, "sha256:" + s.fingerprint)


def _bse_reference_valid(reference: str | None, checksum: str | None) -> bool:
    if reference == "BSE_OFFICIAL_XBRL_SHA256:" + (checksum or ""):
        return True
    try:
        u = urlsplit(reference or "")
        return (u.scheme == "https" and u.hostname == "www.bseindia.com" and u.port in (None, 443)
                and u.path.startswith("/XBRLFILES/") and not (u.username or u.password or u.query or u.fragment))
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class EarningsScheduleCanonicalIdentityBridge:
    """A frozen view of existing receipts. No independent master or write API.

    The legacy tuple preserves the existing callers' typed historical inputs;
    production readers should pass verified core snapshots via ``from_reader``.
    """
    snapshots: tuple[CoreApiSnapshot, ...] = ()
    identities: tuple[HistoricalSecurityIdentity, ...] = ()

    def __post_init__(self):
        if (type(self.snapshots) is not tuple or type(self.identities) is not tuple
                or any(not isinstance(s, CoreApiSnapshot) for s in self.snapshots)
                or any(not isinstance(p, HistoricalSecurityIdentity) for p in self.identities)):
            raise ValueError("EARNINGS_IDENTITY_INPUT_INVALID")

    @classmethod
    def from_reader(cls, reader: CoreApiSnapshotRepository):
        values = []
        for family in FAMILIES:
            offset = 0
            while True:
                page = reader.list_snapshots(family, limit=100, offset=offset)
                values.extend(page)
                if len(page) < 100:
                    break
                offset += len(page)
        return cls(tuple(values))

    def resolve_nse(self, source_symbol: str | None, source_isin: str | None, as_of: datetime) -> EarningsScheduleIdentityResolution:
        return self._resolve("NSE", source_symbol, source_isin, as_of)

    def resolve_bse(self, source_security_code: str | None, source_isin: str | None, as_of: datetime) -> EarningsScheduleIdentityResolution:
        return self._resolve("BSE", source_security_code, source_isin, as_of)

    def _resolve(self, exchange, key, isin, as_of):
        point = utc(as_of)
        if (key is not None and not isinstance(key, str)) or (isin is not None and not isinstance(isin, str)):
            raise ValueError("EARNINGS_IDENTITY_SOURCE_TYPE_INVALID")
        refs: set[IdentityEvidence] = set()

        def result(state, reason=None, claim=None, symbol=None):
            body = dict(source_exchange=exchange, source_identifier=key, source_isin=isin, as_of=point,
                        resolution_state=state, reasons=() if reason is None else (reason,),
                        canonical_instrument_id=claim.instrument if claim else None,
                        canonical_isin=claim.isin if claim else None,
                        canonical_nse_symbol=(claim.symbol or symbol) if claim else None,
                        canonical_bse_code=claim.code if claim else None,
                        identity_authority=claim.authority if claim else None,
                        effective_from=utc(claim.start) if claim else None,
                        effective_to=utc(claim.end) if claim and claim.end else None,
                        evidence=tuple(sorted(refs)), version=VERSION)
            return EarningsScheduleIdentityResolution(**body, fingerprint=content_fingerprint(body))

        if (not isinstance(key, str) or not (_SYMBOL.fullmatch(key) if exchange == "NSE" else re.fullmatch(r"[0-9]{6}", key))
                or (isin is not None and (not isinstance(isin, str) or not _ISIN.fullmatch(isin)))):
            return result(IdentityState.SOURCE_IDENTITY_INCOMPLETE, "EXACT_SOURCE_IDENTIFIER_REQUIRED")

        # Broker mappings deliberately do not participate, even as a fallback.
        source = [s for s in self.snapshots if isinstance(s.payload, (NseEquityInstrument, HistoricalSecurityIdentity))
                  or isinstance(s.payload, ProviderInstrumentMappingRecord) and s.payload.provider == "BSE_OFFICIAL"]
        # OfficialNseUniverseImporter explicitly retains NSE:<symbol> when ISIN
        # is absent. That incomplete key is not a competing canonical ISIN.
        # No other malformed or contradictory record is silently suppressed.
        source = [s for s in source if not (isinstance(s.payload, NseEquityInstrument)
                  and s.payload.isin is None and s.payload.instrument_id == "NSE:" + s.payload.symbol)]
        candidates = []
        for s in source:
            p = s.payload
            identifier = p.instrument_id if isinstance(p, NseEquityInstrument) else p.canonical_instrument_id
            source_key = (getattr(p, "symbol", None) if exchange == "NSE" else
                          p.provider_instrument_reference if isinstance(p, ProviderInstrumentMappingRecord) else getattr(p, "exchange_security_code", None))
            if source_key == key or (isin is not None and (p.isin == isin or identifier == "NSE:" + isin)):
                candidates.append(identifier)
        for p in self.identities:
            if (p.symbol if exchange == "NSE" else p.exchange_security_code) == key or p.isin == isin:
                candidates.append(p.canonical_instrument_id)
        if not candidates:
            return result(IdentityState.IDENTITY_UNAVAILABLE, "CANONICAL_AUTHORITY_REQUIRED")

        claims, errors = [], []
        for identifier in sorted(set(candidates)):
            relevant = [s for s in source if (s.payload.instrument_id if isinstance(s.payload, NseEquityInstrument) else s.payload.canonical_instrument_id) == identifier]
            known = []
            for s in relevant:
                try:
                    if utc(s.created_at) > point:
                        continue
                    if not _snapshot_valid(s):
                        errors.append("IDENTITY_PROVENANCE_INVALID")
                        continue
                    known.append(s)
                    refs.add(_ref(s))
                except (ValueError, AttributeError, TypeError):
                    errors.append("IDENTITY_PROVENANCE_INVALID")
            if errors:
                continue
            # Latest effective snapshot, no input-order tie break or inactive fallback.
            for kind in (NseEquityInstrument, ProviderInstrumentMappingRecord):
                rows = [s for s in known if isinstance(s.payload, kind)]
                if not rows or (kind is ProviderInstrumentMappingRecord and exchange == "NSE"):
                    continue
                at = max(s.created_at for s in rows)
                latest = [s for s in rows if s.created_at == at]
                semantic = {canonical_json(s.payload) for s in latest}
                if len(semantic) != 1:
                    errors.append("LATEST_IDENTITY_AMBIGUOUS")
                    continue
                p = latest[0].payload
                if not _ISIN.fullmatch(p.isin or "") or identifier != "NSE:" + p.isin:
                    errors.append("CANONICAL_ISIN_CONFLICT")
                    continue
                if kind is NseEquityInstrument:
                    if (p.source != "NSE_OFFICIAL_EXPORT" or p.exchange != "NSE" or not _SYMBOL.fullmatch(p.symbol)
                            or p.security_type != "EQUITY"):
                        errors.append("CANONICAL_SOURCE_UNVERIFIED")
                    elif p.listing_status in {"DELISTED", "INACTIVE", "SUSPENDED", "MERGED"}:
                        errors.append("IDENTITY_LIFECYCLE_NOT_EFFECTIVE")
                    else:
                        # UNKNOWN listing/tradability is not invented as ACTIVE.
                        claims.append(_Claim(identifier, p.isin, p.symbol, None, IdentityAuthority.NSE_CURRENT_UNIVERSE,
                                             at, None, tuple(sorted({_ref(s) for s in latest}))))
                else:
                    # Existing direct-XBRL ingestion used a content-addressed
                    # reference before the staging importer retained URLs.
                    reference_valid = _bse_reference_valid(p.source_reference, p.source_checksum)
                    mapping_key = sha256("|".join((p.provider, identifier, p.provider_exchange_segment,
                        p.provider_instrument_reference, p.mapping_version, p.effective_as_of.isoformat(),
                        p.source_checksum or "")).encode()).hexdigest()[:24]
                    if (p.provider_exchange_segment != "BSE_EQ" or p.mapping_version != "bse-xbrl-v1"
                            or not re.fullmatch(r"[0-9]{6}", p.provider_instrument_reference)
                            or not re.fullmatch(r"[0-9a-f]{64}", p.source_checksum or "")
                            or p.mapping_id != "mapping:bse_official:" + mapping_key
                            or not reference_valid):
                        errors.append("OFFICIAL_BSE_PROVENANCE_UNVERIFIED")
                    elif p.status is not ProviderMappingStatus.ACTIVE:
                        errors.append("IDENTITY_LIFECYCLE_NOT_EFFECTIVE")
                    else:
                        claims.append(_Claim(identifier, p.isin, None, p.provider_instrument_reference,
                                             IdentityAuthority.BSE_OFFICIAL_XBRL_MAPPING, at, None,
                                             tuple(sorted({_ref(s) for s in latest}))))
            history = tuple(s.payload for s in known if isinstance(s.payload, HistoricalSecurityIdentity)) + tuple(
                p for p in self.identities if p.canonical_instrument_id == identifier)
            history = tuple(p for p in history if p.exchange == exchange)
            if history:
                try:
                    if any(not p.identity_id or not p.source or not p.version or not p.source_reference
                           or not _FP.fullmatch(p.source_fingerprint or "") or not _SYMBOL.fullmatch(p.symbol)
                           or not _ISIN.fullmatch(p.isin or "") or p.canonical_instrument_id != "NSE:" + p.isin
                           or (exchange == "BSE" and not re.fullmatch(r"[0-9]{6}", p.exchange_security_code or "")) for p in history):
                        raise ValueError
                    selected = resolve_historical_security_identity(history, canonical_instrument_id=identifier, as_of=point)
                    if selected.status is H.EVIDENCE_CONFLICTED:
                        errors.append("HISTORICAL_IDENTITY_CONFLICT")
                    elif selected.status is H.NOT_LISTED:
                        errors.append("IDENTITY_LIFECYCLE_NOT_EFFECTIVE")
                    elif selected.status is H.RESOLVED:
                        matched = [p for p in history if p.identity_id == selected.identity_id]
                        if len({canonical_json(p) for p in matched}) != 1:
                            raise ValueError
                        p = matched[0]
                        evidence = (IdentityEvidence(p.identity_id, content_fingerprint(p)),
                                    IdentityEvidence(p.source_reference, p.source_fingerprint),
                                    IdentityEvidence("historical-selector:" + p.identity_id, selected.fingerprint))
                        refs.update(evidence)
                        claims.append(_Claim(identifier, p.isin, p.symbol if exchange == "NSE" else None,
                            p.exchange_security_code if exchange == "BSE" else None,
                            IdentityAuthority.HISTORICAL_SECURITY_IDENTITY,
                            max(p.as_of, p.symbol_effective_from, p.listed_from or p.as_of, p.tradable_from or p.as_of),
                            min((t for t in (p.symbol_effective_to, p.listed_until, p.tradable_until) if t), default=None), evidence))
                except (ValueError, TypeError, AttributeError):
                    errors.append("HISTORICAL_IDENTITY_PROVENANCE_INVALID")
        if errors:
            reason = sorted(set(errors))[0]
            state = (IdentityState.AMBIGUOUS if reason == "LATEST_IDENTITY_AMBIGUOUS" else
                     IdentityState.IDENTITY_NOT_EFFECTIVE if reason == "IDENTITY_LIFECYCLE_NOT_EFFECTIVE" else IdentityState.IDENTITY_CONFLICTED)
            return result(state, reason)
        relevant_claims = [c for c in claims if (c.symbol if exchange == "NSE" else c.code) is not None]
        if not relevant_claims:
            return result(IdentityState.IDENTITY_NOT_EFFECTIVE, "NO_EFFECTIVE_AUTHORITY_AT_AS_OF")
        if any((c.symbol if exchange == "NSE" else c.code) != key or (isin is not None and c.isin != isin) for c in relevant_claims):
            return result(IdentityState.IDENTITY_CONFLICTED, "SOURCE_CANONICAL_IDENTITY_CONFLICT")
        if len({c.instrument for c in relevant_claims}) != 1:
            return result(IdentityState.AMBIGUOUS, "MULTIPLE_CANONICAL_IDENTITIES")
        chosen = sorted(relevant_claims, key=lambda c: (c.authority != IdentityAuthority.HISTORICAL_SECURITY_IDENTITY, c.authority.value))[0]
        symbols = {c.symbol for c in claims if c.instrument == chosen.instrument and c.symbol}
        if len(symbols) > 1:
            return result(IdentityState.IDENTITY_CONFLICTED, "CANONICAL_SYMBOL_CONFLICT")
        return result(IdentityState.RESOLVED, claim=chosen, symbol=next(iter(symbols), None))
