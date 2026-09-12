"""Synthetic governed inputs: no network, production writes or clearance."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.filings.earnings_schedule_identity import (
    EarningsScheduleCanonicalIdentityBridge as Bridge, EarningsScheduleIdentityResolution,
    IdentityState as S, IdentityAuthority as A, VERSION,
)
from app.filings.earnings_schedule_ingestion import normalize_schedule
from app.filings.earnings_schedule_discovery import inspect_nse_join
from app.filings.earnings_schedule_source import Fetch, SourceState, parse_bse_detail
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as F
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord, ProviderMappingStatus
from app.historical.security_master import HistoricalSecurityStatus
from test_earnings_schedule_adapters import T, INSTRUMENT, BSE_URL, nse_row, bse_html, identity, xbrl
from test_earnings_schedule_discovery import inventory

ISIN = "INE372A01015"


def master(**changes):
    return NseEquityInstrument(**(dict(instrument_id=INSTRUMENT, symbol="APARINDS", isin=ISIN,
        sector=None, industry=None, listing_status="UNKNOWN", listing_date=None, tradable=None,
        data_as_of=T-timedelta(days=1), source="NSE_OFFICIAL_EXPORT") | changes))


def mapping(**changes):
    body = dict(mapping_id="", canonical_instrument_id=INSTRUMENT, provider="BSE_OFFICIAL",
        provider_exchange_segment="BSE_EQ", provider_instrument_reference="532259", provider_symbol=None,
        isin=ISIN, status=ProviderMappingStatus.ACTIVE, effective_as_of=T-timedelta(hours=1),
        source_reference="https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/synthetic.xml",
        source_checksum="a"*64, mapping_version="bse-xbrl-v1") | changes
    key = sha256("|".join((body['provider'], body['canonical_instrument_id'], body['provider_exchange_segment'],
        body['provider_instrument_reference'], body['mapping_version'], body['effective_as_of'].isoformat(), body['source_checksum'] or '')).encode()).hexdigest()[:24]
    body['mapping_id'] = "mapping:" + body['provider'].lower() + ":" + key
    return ProviderInstrumentMappingRecord(**body)


def snap(p):
    if isinstance(p, NseEquityInstrument):
        f, key, at = F.NSE_UNIVERSE, f"nse-equity:{p.instrument_id}:{p.data_as_of.isoformat()}", p.data_as_of
    elif isinstance(p, ProviderInstrumentMappingRecord):
        f, key, at = F.PROVIDER_INSTRUMENT_MAPPING, f"provider-mapping:{p.mapping_id}", p.effective_as_of
    else:
        f, key, at = F.HISTORICAL_SECURITY_IDENTITY, f"historical-security:{p.identity_id}", p.as_of
    return CoreApiSnapshot(key, f, "v1", "historical-security-master-v1" if f == F.HISTORICAL_SECURITY_IDENTITY else "universe-analysis-v1",
                           sha256(repr(p).encode()).hexdigest(), at, p)


def resolve(*records, symbol="APARINDS", isin=ISIN, at=T, bse=False):
    b = Bridge(tuple(snap(p) for p in records))
    return b.resolve_bse(symbol, isin, at) if bse else b.resolve_nse(symbol, isin, at)


@pytest.mark.parametrize("at", [T-timedelta(days=1), T, T+timedelta(days=2)])
def test_current_master_exact_effective_and_forward_identity_only(at):
    r = resolve(master(), at=at)
    assert r.resolution_state == S.RESOLVED and r.identity_authority == A.NSE_CURRENT_UNIVERSE
    assert r.canonical_instrument_id == INSTRUMENT and r.canonical_isin == ISIN
    assert r.canonical_nse_symbol == "APARINDS" and r.canonical_bse_code is None
    assert r.effective_from == T-timedelta(days=1) and r.effective_to is None
    assert r.version == VERSION and r.evidence


@pytest.mark.parametrize("at", [T-timedelta(days=2), datetime(2025,7,16,tzinfo=UTC)])
def test_no_current_master_backdating(at):
    assert resolve(master(), at=at).resolution_state == S.IDENTITY_NOT_EFFECTIVE


@pytest.mark.parametrize("symbol,isin", [(None,ISIN), ("",ISIN), ("Apar Industries",None), ("aparinds",ISIN),
    ("APARINDS","bad"), ("APARINDS","ine372a01015"), ("APARINDS","")])
def test_no_name_normalization_or_unsupported_isin_only(symbol, isin):
    assert resolve(master(),symbol=symbol,isin=isin).resolution_state == S.SOURCE_IDENTITY_INCOMPLETE


def test_missing_authority_and_unknown_source_fail_closed():
    assert resolve().resolution_state == S.IDENTITY_UNAVAILABLE
    assert resolve(master(),symbol="UNKNOWN",isin=None).resolution_state == S.IDENTITY_UNAVAILABLE


def test_incomplete_legacy_symbol_key_is_not_another_canonical_identity():
    legacy=master(instrument_id="NSE:APARINDS",isin=None)
    assert resolve(legacy).resolution_state==S.IDENTITY_UNAVAILABLE
    assert resolve(master(),legacy)==resolve(master())
    assert resolve(master(),master(instrument_id="NSE:APARINDS")).resolution_state==S.IDENTITY_CONFLICTED


def test_original_mapping_fingerprint_verified_without_dropping_populated_extensions():
    p=mapping()
    legacy_names=('mapping_id','canonical_instrument_id','provider','provider_exchange_segment',
        'provider_instrument_reference','provider_symbol','isin','status','effective_as_of',
        'source_reference','source_checksum','mapping_version')
    legacy="ProviderInstrumentMappingRecord("+", ".join(f"{k}={getattr(p,k)!r}" for k in legacy_names)+")"
    s=replace(snap(p),fingerprint=sha256(legacy.encode()).hexdigest())
    assert Bridge((s,)).resolve_bse('532259',ISIN,T).resolution_state==S.RESOLVED
    tampered=replace(s,payload=replace(p,provider_name='new evidence'))
    assert Bridge((tampered,)).resolve_bse('532259',ISIN,T).resolution_state==S.IDENTITY_CONFLICTED
    assert s.fingerprint==sha256(legacy.encode()).hexdigest()


def test_existing_direct_xbrl_content_address_must_match_checksum_exactly():
    p=mapping(source_reference='BSE_OFFICIAL_XBRL_SHA256:'+'a'*64)
    assert resolve(p,symbol='532259',bse=True).resolution_state==S.RESOLVED
    p=replace(p,source_reference='BSE_OFFICIAL_XBRL_SHA256:'+'b'*64)
    assert resolve(p,symbol='532259',bse=True).resolution_state==S.IDENTITY_CONFLICTED


@pytest.mark.parametrize("provider", ["DHAN","UPSTOX","YAHOO"])
def test_provider_only_cannot_resolve_or_override_canonical(provider):
    p = mapping(provider=provider,provider_symbol="APARINDS")
    assert resolve(p).resolution_state == S.IDENTITY_UNAVAILABLE
    assert resolve(master(symbol="OTHER"),p).resolution_state == S.IDENTITY_CONFLICTED
    assert resolve(master(),p) == resolve(master())


@pytest.mark.parametrize("changed", [{"isin":"INE090A01021"}, {"symbol":"OTHER"}, {"instrument_id":"NSE:INE090A01021"}])
def test_symbol_and_isin_conflicts_have_no_preference(changed):
    assert resolve(master(**changed)).resolution_state == S.IDENTITY_CONFLICTED


def test_symbol_without_isin_requires_one_exact_canonical_match():
    assert resolve(master(),isin=None).resolution_state == S.RESOLVED
    other = master(instrument_id="NSE:INE090A01021",isin="INE090A01021")
    assert resolve(master(),other,isin=None).resolution_state == S.AMBIGUOUS
    assert resolve(master(),other).resolution_state == S.IDENTITY_CONFLICTED


@pytest.mark.parametrize("isin", [ISIN,None])
def test_bse_official_code_resolves_with_optional_consistent_isin(isin):
    r=resolve(master(),mapping(),symbol="532259",isin=isin,bse=True)
    assert r.resolution_state == S.RESOLVED and r.canonical_bse_code == "532259"
    assert r.canonical_nse_symbol == "APARINDS" and r.identity_authority == A.BSE_OFFICIAL_XBRL_MAPPING


@pytest.mark.parametrize("code,isin", [("532174",ISIN),("532259","INE090A01021")])
def test_bse_code_isin_conflicts(code,isin):
    assert resolve(mapping(),symbol=code,isin=isin,bse=True).resolution_state == S.IDENTITY_CONFLICTED


@pytest.mark.parametrize("change", [{"mapping_version":"guess"},{"provider_exchange_segment":"NSE_EQ"},
    {"source_reference":"https://www.bseindia.com.evil.test/XBRLFILES/a"},{"source_checksum":None}])
def test_bse_provenance_required(change):
    assert resolve(mapping(**change),symbol="532259",bse=True).resolution_state == S.IDENTITY_CONFLICTED


@pytest.mark.parametrize('url',['https://[bad','https://www.bseindia.com:8443/XBRLFILES/synthetic.xml'])
def test_malformed_or_noncanonical_bse_origin_fails_closed(url):
    assert resolve(mapping(source_reference=url),symbol='532259',bse=True).resolution_state==S.IDENTITY_CONFLICTED


def test_bse_future_and_retired_no_older_active_fallback():
    assert resolve(mapping(effective_as_of=T+timedelta(seconds=1)),symbol="532259",bse=True).resolution_state == S.IDENTITY_NOT_EFFECTIVE
    assert resolve(mapping(),mapping(effective_as_of=T,status=ProviderMappingStatus.RETIRED),symbol="532259",bse=True).resolution_state == S.IDENTITY_NOT_EFFECTIVE


def test_historical_interval_reuses_selector_inclusive_endpoints():
    p=identity(as_of=T-timedelta(days=101))
    for at in (p.symbol_effective_from,T):
        r=resolve(p,at=at)
        assert r.resolution_state == S.RESOLVED and r.identity_authority == A.HISTORICAL_SECURITY_IDENTITY
    assert resolve(replace(p,symbol_effective_to=T)).resolution_state == S.RESOLVED
    assert resolve(replace(p,symbol_effective_to=T),at=T+timedelta(microseconds=1)).resolution_state == S.IDENTITY_NOT_EFFECTIVE


@pytest.mark.parametrize("changes", [{"as_of":T+timedelta(seconds=1)}, {"symbol_effective_from":T+timedelta(seconds=1)},
    {"symbol_effective_to":T-timedelta(seconds=1)}])
def test_historical_future_observation_future_effective_and_expiry(changes):
    assert resolve(identity(**changes)).resolution_state == S.IDENTITY_NOT_EFFECTIVE


def test_current_and_effective_historical_disagreement_blocks():
    assert resolve(master(),identity(symbol="OLD")).resolution_state == S.IDENTITY_CONFLICTED


def test_acutaas_does_not_extend_expired_amiorg_interval():
    at=datetime(2025,5,1,tzinfo=UTC)
    old=identity(canonical_instrument_id="NSE:INE00FF01025",isin="INE00FF01025",symbol="AMIORG",
        as_of=T-timedelta(days=2),symbol_effective_from=at,symbol_effective_to=at+timedelta(days=30))
    current=master(instrument_id=old.canonical_instrument_id,isin=old.isin,symbol="ACUTAAS")
    assert resolve(old,symbol="ACUTAAS",isin=old.isin).resolution_state == S.IDENTITY_NOT_EFFECTIVE
    assert resolve(old,current,symbol="ACUTAAS",isin=old.isin).resolution_state == S.RESOLVED
    assert resolve(old,current,symbol="AMIORG",isin=old.isin,at=at).resolution_state == S.IDENTITY_NOT_EFFECTIVE
    assert old.symbol_effective_to == at+timedelta(days=30)


@pytest.mark.parametrize("status", ["DELISTED","INACTIVE","SUSPENDED","MERGED"])
def test_explicit_current_negative_lifecycle_is_not_active_fallback(status):
    assert resolve(master(),master(data_as_of=T,listing_status=status)).resolution_state == S.IDENTITY_NOT_EFFECTIVE


def test_equal_time_conflicts_and_identical_duplicates_are_order_independent():
    a,b=master(),master(symbol="OTHER")
    assert resolve(a,b)==resolve(b,a)
    assert resolve(a,b).resolution_state == S.AMBIGUOUS
    assert resolve(a,a)==resolve(a)
    a,b=mapping(),mapping(provider_instrument_reference="532174")
    assert resolve(a,b,bse=True,symbol="532259")==resolve(b,a,bse=True,symbol="532259")
    assert resolve(a,b,bse=True,symbol="532259").resolution_state == S.AMBIGUOUS


@pytest.mark.parametrize("change", [{"fingerprint":"a"*64},{"snapshot_id":"fake"},{"schema_version":"v2"},
    {"record_type":"fake"},{"created_at":T},{"payload":master(symbol="OTHER")}])
def test_tampered_snapshot_is_not_rehashed_and_repaired(change):
    r=Bridge((replace(snap(master()),**change),)).resolve_nse("APARINDS",ISIN,T)
    assert r.resolution_state == S.IDENTITY_CONFLICTED


def test_missing_or_tampered_history_lineage_and_mapping_identity():
    assert resolve(identity(source_fingerprint=None)).resolution_state == S.IDENTITY_CONFLICTED
    assert resolve(identity(source_reference=None)).resolution_state == S.IDENTITY_CONFLICTED
    assert resolve(replace(mapping(),mapping_id="mapping:bse_official:fake"),symbol="532259",bse=True).resolution_state == S.IDENTITY_CONFLICTED


def test_utc_request_order_and_serialization_stability():
    a,b=master(),mapping()
    r=resolve(a,b)
    assert resolve(b,a,at=T.astimezone(timezone(timedelta(hours=5,minutes=30))))==r
    j=json.loads(r.to_json()); j['as_of']=datetime.fromisoformat(j['as_of'])
    j['effective_from']=datetime.fromisoformat(j['effective_from'])
    from app.filings.earnings_schedule_identity import IdentityEvidence
    j['evidence']=tuple(IdentityEvidence(**x) for x in j['evidence']);j['reasons']=tuple(j['reasons'])
    j['resolution_state']=S(j['resolution_state']);j['identity_authority']=A(j['identity_authority'])
    assert EarningsScheduleIdentityResolution(**j).to_json()==r.to_json()
    with pytest.raises(FrozenInstanceError): r.as_of=T
    with pytest.raises(ValueError,match="FINGERPRINT"): replace(r,fingerprint="sha256:"+"0"*64)
    with pytest.raises(ValueError): replace(r,canonical_instrument_id=None)
    with pytest.raises(ValueError): Bridge(snapshots=[])
    with pytest.raises(ValueError): resolve(a,isin=[])
    with pytest.raises(ValueError): resolve(a,at=T.replace(tzinfo=None))


def test_reader_pages_only_existing_families_and_never_writes():
    a=snap(master())
    class Reader:
        def list_snapshots(self,family,*,limit,offset):
            assert limit==100 and offset==0
            return (a,) if family==F.NSE_UNIVERSE else ()
        def save_snapshot(self,*args): raise AssertionError('write forbidden')
        def get_snapshot(self,*args): raise AssertionError('unnecessary read')
    assert Bridge.from_reader(Reader()).resolve_nse("APARINDS",ISIN,T)==resolve(master())


@pytest.mark.parametrize("exchange", ["NSE","BSE"])
def test_both_adapters_share_bridge_no_gate6_authority(exchange):
    row=nse_row() if exchange=='NSE' else parse_bse_detail(bse_html(),BSE_URL)[0]
    b=Bridge((snap(master()),snap(mapping())))
    before=b.snapshots
    r=normalize_schedule(row,canonical_instrument_id=INSTRUMENT,identity_bridge=b,retrieved_at=T)
    assert r.candidate is not None and r.candidate.known_at==T
    assert 'UNVERIFIED_SOURCE_AUTHORITY' in r.candidate.to_json()
    assert b.snapshots==before
    bad=normalize_schedule(row,canonical_instrument_id=INSTRUMENT,identity_bridge=Bridge(),retrieved_at=T)
    assert bad.candidate is None and bad.state==SourceState.IDENTITY_UNRESOLVED


def test_identity_does_not_invent_timestamp_or_parent_and_descriptive_join_stays_separate():
    b=Bridge((snap(master()),))
    r=normalize_schedule(nse_row(disseminated='12-Sep-2026 10:00:00'),canonical_instrument_id=INSTRUMENT,identity_bridge=b,retrieved_at=T)
    assert r.candidate is None and r.state==SourceState.TIMESTAMP_UNAVAILABLE
    inv=inventory()
    inspected=inspect_nse_join(inv,Fetch(inv.field('link'),200,xbrl()),canonical_instrument_id=INSTRUMENT,identity_bridge=b,observed_at=T)
    assert inspected.current_descriptive_ready and not inspected.strict_pit_ready
    assert json.loads(inspected.to_json())['gate6_clearance'] is False


def test_historical_apar_source_pair_is_not_backdated_or_gate_evidence():
    # Exact pair from the already discovered official 2025-07-16 Prior Intimation;
    # fixture only, not a new download or a governed source timezone assertion.
    at=datetime(2025,7,16,14,27,57,tzinfo=UTC)
    b=Bridge((snap(master()),))
    assert b.resolve_nse('APARINDS',ISIN,at).resolution_state==S.IDENTITY_NOT_EFFECTIVE
    assert b.resolve_nse('APARINDS',ISIN,T).resolution_state==S.RESOLVED


def test_static_boundary_and_source_parsers_unchanged():
    path=Path('app/filings/earnings_schedule_identity.py')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(x.startswith(('app.gates','app.ai','app.portfolio','app.broker','app.orders')) for x in imports)
    calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    assert not calls & {'now','utcnow','execute','save_snapshot','capture_provider_mapping','save_instrument','getenv'}
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'open','eval','exec'} for n in ast.walk(tree))
    assert set(Bridge.__dataclass_fields__)=={'snapshots','identities'}
