"""Read-only official-source feasibility audit for company-level EBITDA/EBIT.

The audit deliberately records source metadata, semantic classifications and
definition fingerprints only.  It never stores values in SQLite, derives a
metric, or changes the canonical financial model.  NSE documents are fetched
only from documented exchange endpoints and are bounded before parsing.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Callable, Iterable, Mapping
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.fundamentals.store import _fact


NSE_HOME_URL = "https://www.nseindia.com/"
NSE_INTEGRATED_FILING_ENDPOINT = "https://www.nseindia.com/api/integrated-filing-results"
NSE_ANNUAL_REPORT_XBRL_ENDPOINT = "https://www.nseindia.com/api/annual-reports-xbrl"
NSE_ANNUAL_REPORT_ENDPOINT = "https://www.nseindia.com/api/annual-reports"
NSE_ALLOWED_HOSTS = frozenset({"www.nseindia.com", "nsearchives.nseindia.com"})
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
POLICY_VERSION = "official-company-level-ebitda-ebit-source-feasibility-v1"

_EBITDA_LABEL = re.compile(
    r"(?:^|[^A-Za-z])EBITDA(?:$|[^A-Za-z])|EarningsBeforeInterest(?:And)?Tax(?:es)?DepreciationAndAmorti[sz]ation",
    re.I,
)
_EBIT_LABEL = re.compile(
    r"^EBIT$|EarningsBeforeInterestAndTax|EarningsBeforeFinance(?:Costs?)?AndTax",
    re.I,
)
_TEXT_EBITDA = re.compile(r"\bEBITDA\b|Earnings Before Interest,? Tax(?:es)?,? Depreciation", re.I)
_TEXT_EBIT = re.compile(r"\bEBIT\b|Earnings Before Interest and Tax|Earnings Before Finance Costs? and Tax", re.I)
_FORMULA = re.compile(r"(?:is|are)\s+(?:derived|calculated|computed|defined)|(?:EBITDA|EBIT)\s*=", re.I)
_HTML = re.compile(r"<[^>]+>")


class OfficialSourceProbeError(ValueError):
    """A bounded, non-secret official-source probe failure."""


@dataclass(frozen=True, slots=True)
class Target:
    instrument_id: str
    symbol: str
    isin: str


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_family: str
    authority: str
    role: str
    url: str
    publication_at: datetime | None
    reporting_period: str | None
    scope: str | None
    expected_isin: str
    received_at: datetime
    local_path: Path | None = None


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    raise TypeError(f"Unsupported audit value: {type(value).__name__}")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required.")
    return value.astimezone(UTC)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_text(value: str) -> str:
    return " ".join(_HTML.sub(" ", value).split())


def _metric_tag_matches(metric: str, name: str) -> bool:
    """Recognise a metric token in a tag without treating ``Debit`` as EBIT."""
    tokenized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name).lower()
    tokens = frozenset(re.findall(r"[a-z]+", tokenized))
    if metric == "EBITDA":
        return bool(_EBITDA_LABEL.search(name)) or "ebitda" in tokens
    return bool(_EBIT_LABEL.search(name)) or ("ebit" in tokens and "ebitda" not in tokens)


def _official_nse_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname in NSE_ALLOWED_HOSTS
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _nse_headers(*, accept: str) -> dict[str, str]:
    return {
        "User-Agent": "HSI official-source feasibility audit/1.0",
        "Accept": accept,
        "Referer": NSE_HOME_URL,
    }


def _nse_time(value: object) -> datetime | None:
    """NSE dates are published in IST; convert with a fixed, documented zone."""
    from zoneinfo import ZoneInfo

    text = str(value or "").strip()
    if not text:
        return None
    for form in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(text, form).replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _numeric(value: str) -> bool:
    try:
        from decimal import Decimal

        Decimal(value.strip())
        return True
    except Exception:
        return False


def _context_levels(root: ET.Element) -> dict[str, str]:
    levels: dict[str, str] = {}
    for node in root.iter():
        if _local_name(node.tag) != "context" or not node.get("id"):
            continue
        names = {_local_name(item.tag).lower() for item in node.iter()}
        text = " ".join((item.text or "") for item in node.iter()).lower()
        levels[node.get("id", "")] = "SEGMENT" if "segment" in text or any("segment" in name for name in names) else "COMPANY"
    return levels


def formula_semantics(text: str, metric: str) -> dict[str, str] | None:
    """Fingerprint only source-declared treatment; never calculate a value."""
    clean = _clean_text(text).lower()
    if not _FORMULA.search(clean):
        return None
    if metric == "EBITDA" and "ebitda" not in clean:
        return None
    if metric == "EBIT" and "ebit" not in clean and "earnings before interest" not in clean:
        return None
    return {
        "metric": metric,
        "anchor": (
            "PROFIT_BEFORE_EXCEPTIONAL_ITEMS_AND_TAX"
            if "profit" in clean and "before exceptional" in clean and "tax" in clean
            else "NOT_STATED"
        ),
        "other_income": "SUBTRACTED" if re.search(r"(?:less|subtract(?:ed)?)\s+other income", clean) else "NOT_STATED",
        "exceptional_items": "EXCLUDED" if "before exceptional" in clean or "excluding exceptional" in clean else "NOT_STATED",
        "finance_costs": "ADDED_BACK" if re.search(r"add(?:ing)? back\s+(?:finance|interest)", clean) else "NOT_STATED",
        "tax": "ANCHOR_BEFORE_TAX" if "before" in clean and "tax" in clean else "NOT_STATED",
        "depreciation_amortisation": "ADDED_BACK" if re.search(r"add(?:ing)? back.*(?:depreciation|amorti)", clean) else "NOT_STATED",
        "joint_venture_associates": "NOT_STATED",
        "other_adjustments": "NOT_STATED",
    }


def parse_official_xbrl(document: SourceDocument, body: bytes) -> dict[str, object]:
    """Extract classifications, never monetary values, from one official XML."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise OfficialSourceProbeError("SOURCE_XML_MALFORMED") from error
    contexts = _context_levels(root)
    isins = sorted({(node.text or "").strip().upper() for node in root.iter() if _local_name(node.tag) == "ISIN" and (node.text or "").strip()})
    identity = "EXACT" if isins == [document.expected_isin] else "MISSING" if not isins else "MISMATCH_OR_AMBIGUOUS"
    observations: dict[str, list[dict[str, object]]] = {"EBITDA": [], "EBIT": []}
    formulae: dict[str, list[dict[str, object]]] = {"EBITDA": [], "EBIT": []}
    for node in root.iter():
        name, text = _local_name(node.tag), (node.text or "").strip()
        context_level = contexts.get(node.get("contextRef", ""), "COMPANY")
        tag_segment = name.lower().startswith("segment") or context_level == "SEGMENT"
        for metric, text_pattern in (("EBITDA", _TEXT_EBITDA), ("EBIT", _TEXT_EBIT)):
            tag_matches = _metric_tag_matches(metric, name)
            if tag_matches:
                if "adjusted" in name.lower():
                    classification = "ADJUSTED_EBITDA_ONLY" if metric == "EBITDA" else "AMBIGUOUS"
                elif "margin" in name.lower() or "percent" in name.lower():
                    classification = "EBITDA_MARGIN_ONLY" if metric == "EBITDA" else "AMBIGUOUS"
                elif tag_segment:
                    classification = "SEGMENT_LEVEL_ONLY" if metric == "EBITDA" else "SEGMENT_EBIT_ONLY"
                elif _numeric(text):
                    classification = "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA" if metric == "EBITDA" else "COMPANY_LEVEL_DIRECT_EBIT_VALUE"
                else:
                    classification = "AMBIGUOUS_TEXT" if metric == "EBITDA" else "AMBIGUOUS"
                observations[metric].append({
                    "classification": classification,
                    "concept": name,
                    "context_level": context_level,
                    "machine_readability": "STRUCTURED_NUMERIC_FIELD" if _numeric(text) else "STRUCTURED_TEXT_BLOCK",
                    "source_url": document.url,
                    "reporting_period": document.reporting_period,
                })
            if text_pattern.search(text):
                semantics = formula_semantics(text, metric)
                if semantics is not None:
                    formulae[metric].append({
                        "fingerprint": _fingerprint(semantics),
                        "semantics": semantics,
                        "source_url": document.url,
                        "reporting_period": document.reporting_period,
                        "machine_readability": "STRUCTURED_TEXT_BLOCK",
                    })
                elif not tag_matches:
                    observations[metric].append({
                        "classification": "AMBIGUOUS_TEXT" if metric == "EBITDA" else "AMBIGUOUS",
                        "concept": name,
                        "context_level": context_level,
                        "machine_readability": "STRUCTURED_TEXT_BLOCK",
                        "source_url": document.url,
                        "reporting_period": document.reporting_period,
                    })
        if name == "OperatingProfitBeforeProvisionAndContingencies":
            observations["EBITDA"].append({
                "classification": "OPERATING_PROFIT_ONLY", "concept": name, "context_level": context_level,
                "machine_readability": "STRUCTURED_NUMERIC_FIELD" if _numeric(text) else "STRUCTURED_TEXT_BLOCK",
                "source_url": document.url, "reporting_period": document.reporting_period,
            })
        if name.startswith("ProfitBefore") and "Tax" in name:
            observations["EBIT"].append({
                "classification": "PBT_LIKE_NOT_EBIT", "concept": name, "context_level": context_level,
                "machine_readability": "STRUCTURED_NUMERIC_FIELD" if _numeric(text) else "STRUCTURED_TEXT_BLOCK",
                "source_url": document.url, "reporting_period": document.reporting_period,
            })
    return {"identity": identity, "source_isins": isins, "observations": observations, "formulae": formulae}


def aggregate_metric(metric: str, parsed: Iterable[dict[str, object]], source_failures: Iterable[str]) -> dict[str, object]:
    observations = [item for result in parsed for item in result["observations"][metric]]
    formulae = [item for result in parsed for item in result["formulae"][metric]]
    priorities = (
        "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_WITH_FORMULA", "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA",
        "COMPANY_LEVEL_DIRECT_EBIT_VALUE", "COMPANY_LEVEL_DISCLOSED_FORMULA_ONLY", "COMPANY_LEVEL_EBIT_FORMULA",
        "SEGMENT_LEVEL_ONLY", "SEGMENT_EBIT_ONLY", "EBITDA_MARGIN_ONLY", "ADJUSTED_EBITDA_ONLY",
        "OPERATING_PROFIT_ONLY", "OPERATING_PROFIT_BUT_SEMANTICS_DIFFER", "PBT_LIKE_NOT_EBIT", "AMBIGUOUS_TEXT", "AMBIGUOUS",
    )
    classes = {str(item["classification"]) for item in observations}
    formula_only = "COMPANY_LEVEL_DISCLOSED_FORMULA_ONLY" if metric == "EBITDA" else "COMPANY_LEVEL_EBIT_FORMULA"
    if formulae:
        classes.add(formula_only)
    if metric == "EBITDA":
        direct_sources = {
            str(item["source_url"])
            for item in observations
            if item["classification"] == "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA"
        }
        formula_sources = {str(item["source_url"]) for item in formulae}
        if direct_sources & formula_sources:
            classes.discard("COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA")
            classes.add("COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_WITH_FORMULA")
    chosen = next((item for item in priorities if item in classes), None)
    if chosen is None:
        chosen = "SOURCE_UNAVAILABLE" if tuple(source_failures) and not tuple(parsed) else "NOT_DISCLOSED"
    fingerprints = tuple(sorted({str(item["fingerprint"]) for item in formulae}))
    return {
        "classification": chosen,
        "all_observed_classifications": tuple(sorted(classes)),
        "direct_company_level_value": chosen in {
            "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_WITH_FORMULA",
            "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA",
            "COMPANY_LEVEL_DIRECT_EBIT_VALUE",
        },
        "formula_fingerprints": fingerprints,
        "definition_stability": (
            "UNDEFINED" if not fingerprints else "STABLE_DEFINITION" if len(fingerprints) == 1 and len(formulae) >= 2
            else "CHANGED_DEFINITION" if len(fingerprints) > 1 else "INSUFFICIENT_HISTORY"
        ),
        "machine_readability": tuple(sorted({str(item["machine_readability"]) for item in observations + formulae})),
        "occurrences": tuple(sorted(observations, key=lambda item: (str(item["source_url"]), str(item["concept"])))),
    }


def select_bounded_documents(rows: Iterable[Mapping[str, object]], *, family: str, target: Target, received_at: datetime) -> tuple[SourceDocument, ...]:
    values = [
        row for row in rows
        if not str(row.get("symbol") or "").strip() or str(row.get("symbol")).upper() == target.symbol
    ]
    values.sort(key=lambda row: (_nse_time(row.get("broadcast_Date")) or datetime.min.replace(tzinfo=UTC), str(row.get("xbrl") or row.get("fileName") or "")), reverse=True)
    if family == "NSE_INTEGRATED_FILING_FINANCIAL":
        latest = values[:1]
        audited = [row for row in values if str(row.get("audited", "")).upper() == "AUDITED"]
        selected = latest + audited[:2]
        url_key, period_key = "xbrl", "qe_Date"
        roles = ("LATEST_RELEVANT_FINANCIAL_RESULT", "LATEST_AUDITED_RESULT", "HISTORICAL_AUDITED_RESULT")
    else:
        selected = values[:2]
        url_key, period_key = "fileName", "toYr"
        roles = ("LATEST_ANNUAL_REPORT_XBRL", "HISTORICAL_ANNUAL_REPORT_XBRL")
    unique: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for row in selected:
        url = str(row.get(url_key) or "")
        if url and url not in seen:
            unique.append(row); seen.add(url)
    result = []
    for index, row in enumerate(unique):
        url = str(row.get(url_key) or "")
        if not _official_nse_url(url):
            continue
        result.append(SourceDocument(
            source_family=family, authority="PRIMARY_EXCHANGE", role=roles[min(index, len(roles) - 1)], url=url,
            publication_at=_nse_time(row.get("broadcast_Date")), reporting_period=str(row.get(period_key) or "") or None,
            scope=str(row.get("consolidated") or row.get("submission_type") or "") or None,
            expected_isin=target.isin, received_at=received_at,
        ))
    return tuple(result)


class NseOfficialSourceClient:
    """Small allowlisted reader for the public NSE listing endpoints."""

    def __init__(self, *, timeout_seconds: float, fetch: Callable[[str, int], bytes] | None = None) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout, self._fetch = timeout_seconds, fetch
        self._session = requests.Session() if fetch is None else None

    def metadata(self, endpoint: str, symbol: str) -> tuple[Mapping[str, object], ...]:
        query = urlencode({"index": "equities", "symbol": symbol, "page": "1", "size": "50", "type": "Integrated Filing- Financials"} if endpoint == NSE_INTEGRATED_FILING_ENDPOINT else {"index": "equities", "symbol": symbol})
        raw = self._read(endpoint + "?" + query, MAX_METADATA_BYTES, "application/json")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OfficialSourceProbeError("NSE_METADATA_INVALID_JSON") from error
        rows = value.get("data") if isinstance(value, dict) else None
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise OfficialSourceProbeError("NSE_METADATA_SHAPE_INVALID")
        return tuple(rows)

    def document(self, url: str) -> bytes:
        return self._read(url, MAX_DOCUMENT_BYTES, "application/xml,text/xml,*/*")

    def _read(self, url: str, maximum: int, accept: str) -> bytes:
        if not _official_nse_url(url):
            raise OfficialSourceProbeError("NSE_SOURCE_URL_REJECTED")
        if self._fetch is not None:
            return self._fetch(url, maximum)
        assert self._session is not None
        try:
            self._session.get(NSE_HOME_URL, headers={"User-Agent": _nse_headers(accept="*/*")["User-Agent"]}, timeout=self._timeout)
            with self._session.get(url, headers=_nse_headers(accept=accept), timeout=self._timeout, stream=True) as response:
                if response.status_code != 200:
                    raise OfficialSourceProbeError(f"NSE_HTTP_{response.status_code}")
                chunks, seen = [], 0
                for chunk in response.iter_content(64 * 1024):
                    seen += len(chunk)
                    if seen > maximum:
                        raise OfficialSourceProbeError("NSE_SOURCE_RESPONSE_TOO_LARGE")
                    chunks.append(chunk)
                return b"".join(chunks)
        except requests.RequestException as error:
            raise OfficialSourceProbeError("NSE_SOURCE_UNAVAILABLE") from error


def _targets(database: Path) -> tuple[Target, ...]:
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        values = tuple(_fact(json.loads(row[0])) for row in connection.execute("SELECT payload_json FROM financial_facts ORDER BY fact_id"))
    grouped: dict[str, object] = {}
    for value in values:
        grouped.setdefault(value.instrument.instrument_id, value.instrument)
    result = tuple(Target(item.instrument_id, item.symbol, item.isin or "") for item in sorted(grouped.values(), key=lambda item: item.instrument_id))
    if len(result) != 31 or any(not item.isin for item in result):
        raise ValueError("APPROVED_31_COMPANY_SOURCE_SCOPE_CHANGED")
    return result


def _local_bse_documents(source_root: Path, targets: Iterable[Target], received_at: datetime) -> dict[str, list[SourceDocument]]:
    target_by_isin = {target.isin: target for target in targets}
    sidecars: dict[Path, Mapping[str, object]] = {}
    for path in source_root.rglob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        filename = value.get("filename") if isinstance(value, dict) else None
        if isinstance(filename, str) and filename.endswith(".xml"):
            sidecars[path.parent / filename] = value
    result: dict[str, list[SourceDocument]] = defaultdict(list)
    for path in sorted(source_root.rglob("*.xml")):
        try:
            root = ET.fromstring(path.read_bytes())
        except (OSError, ET.ParseError):
            continue
        isins = {(node.text or "").strip().upper() for node in root.iter() if _local_name(node.tag) == "ISIN"}
        matches = isins & target_by_isin.keys()
        if len(matches) != 1:
            continue
        target = target_by_isin[next(iter(matches))]
        meta = sidecars.get(path, {})
        published = meta.get("published_at") if isinstance(meta, Mapping) else None
        result[target.instrument_id].append(SourceDocument(
            source_family="BSE_FINANCIAL_RESULT_XBRL", authority="PRIMARY_EXCHANGE", role="RETAINED_OFFICIAL_FINANCIAL_RESULT",
            url=str(meta.get("source_reference") or meta.get("document_identifier") or path.resolve().relative_to(ROOT).as_posix()),
            publication_at=datetime.fromisoformat(published) if isinstance(published, str) else None,
            reporting_period=str(meta.get("period_end") or "") or None,
            scope=str(meta.get("statement_scope") or "") or None,
            expected_isin=target.isin, received_at=received_at, local_path=path,
        ))
    return result


def audit(*, database: Path, source_root: Path, received_at: datetime, client: NseOfficialSourceClient) -> dict[str, object]:
    received = _utc(received_at)
    targets = _targets(database)
    bse = _local_bse_documents(source_root, targets, received)
    rows = []
    for target in targets:
        parsed, failures, documents = [], [], list(bse.get(target.instrument_id, ()))
        for document in documents:
            try:
                if document.local_path is None:
                    raise OfficialSourceProbeError("BSE_RETAINED_SOURCE_PATH_MISSING")
                parsed.append(parse_official_xbrl(document, document.local_path.read_bytes()))
            except (OfficialSourceProbeError, OSError, StopIteration):
                failures.append("BSE_RETAINED_SOURCE_UNREADABLE")
        source_families = {
            "BSE_FINANCIAL_RESULT_XBRL": "PRIMARY_EXCHANGE_AVAILABLE" if documents else "SOURCE_UNAVAILABLE",
            "NSE_INTEGRATED_FILING_FINANCIAL": "SOURCE_UNAVAILABLE",
            "NSE_ANNUAL_REPORT_XBRL": "SOURCE_UNAVAILABLE",
            "NSE_ANNUAL_REPORT_PDF": "SOURCE_UNAVAILABLE",
            "ISSUER_ANNUAL_REPORT_WITH_EXCHANGE_LINKAGE": "SOURCE_UNAVAILABLE",
            "EXCHANGE_HOSTED_INVESTOR_PRESENTATION": "SOURCE_UNAVAILABLE",
        }
        for endpoint, family in ((NSE_INTEGRATED_FILING_ENDPOINT, "NSE_INTEGRATED_FILING_FINANCIAL"), (NSE_ANNUAL_REPORT_XBRL_ENDPOINT, "NSE_ANNUAL_REPORT_XBRL")):
            try:
                metadata = client.metadata(endpoint, target.symbol)
                selected = select_bounded_documents(metadata, family=family, target=target, received_at=received)
                if selected:
                    source_families[family] = "PRIMARY_EXCHANGE_AVAILABLE"
                for document in selected:
                    documents.append(document)
                    try:
                        parsed.append(parse_official_xbrl(document, client.document(document.url)))
                    except OfficialSourceProbeError as error:
                        failures.append(str(error))
            except OfficialSourceProbeError as error:
                failures.append(str(error))
        try:
            annual_metadata = client.metadata(NSE_ANNUAL_REPORT_ENDPOINT, target.symbol)
            if annual_metadata:
                source_families["NSE_ANNUAL_REPORT_PDF"] = "PRIMARY_EXCHANGE_METADATA_AVAILABLE"
        except OfficialSourceProbeError as error:
            failures.append(str(error))
        eligible = [item for item in parsed if item["identity"] == "EXACT"]
        rows.append({
            "symbol": target.symbol, "canonical_instrument_id": target.instrument_id,
            "source_families": source_families,
            "documents_examined": tuple(sorted({item.url for item in documents})),
            "publication_semantics": "SOURCE_PUBLICATION_TIMESTAMP_PRESERVED_WHEN_EXCHANGE_METADATA_PROVIDES_IT",
            "ebitda": aggregate_metric("EBITDA", eligible, failures),
            "ebit": aggregate_metric("EBIT", eligible, failures),
            "identity_failures": len(parsed) - len(eligible), "source_failures": tuple(sorted(set(failures))),
        })
    return {
        "policy_version": POLICY_VERSION, "research_received_at": received, "target_population": rows,
        "source_families": {
            "BSE_FINANCIAL_RESULT_XBRL": "PRIMARY_EXCHANGE",
            "NSE_INTEGRATED_FILING_FINANCIAL": "PRIMARY_EXCHANGE",
            "NSE_ANNUAL_REPORT_XBRL": "PRIMARY_EXCHANGE",
            "NSE_ANNUAL_REPORT_PDF": "PRIMARY_EXCHANGE",
            "ISSUER_ANNUAL_REPORT_WITH_EXCHANGE_LINKAGE": "PRIMARY_ISSUER_IF_EXCHANGE_LINKED",
            "EXCHANGE_HOSTED_INVESTOR_PRESENTATION": "PRIMARY_COMPANY_FILED_WITH_EXCHANGE_IF_IDENTITY_LINKED",
        },
        "historical_pit": "EXTERNAL_DOCUMENT_PUBLICATION_TIME_DOES_NOT_BACKDATE_HSI_RECEIPT_OR_HISTORICAL_AVAILABILITY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT / "data" / "official_sources" / "bse_financial_results")
    parser.add_argument("--received-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new immutable research receipt")
    result = audit(database=args.database, source_root=args.source_root, received_at=args.received_at, client=NseOfficialSourceClient(timeout_seconds=args.timeout_seconds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(result) + "\n", encoding="utf-8")
    print(canonical_json({"companies": len(result["target_population"]), "output": str(args.output), "fingerprint": _fingerprint(result)}))


if __name__ == "__main__":
    main()
