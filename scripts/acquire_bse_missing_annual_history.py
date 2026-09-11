"""Explicit bounded older-annual acquisition for existing financial-source companies.

No broad-plan resume or inventory rebuild. Uses the approved official archive,
hash-addressed staging and canonical context-aware importer. Per-document JSON
receipts are operational artifacts, not a second financial fact store.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityProjection
from app.filings.store import _filing, SQLiteCorporateFilingsStore
from app.fundamentals.bse_annual_history import select_missing_annual_history
from app.fundamentals.bse_collector import (BseOfficialHttpTransport, BseOfficialHttpResponse,
    BseOfficialArchiveSnapshotStore, BseOfficialXbrlStaging, BseSecurityMapping, BseMappingStatus)
from app.fundamentals.bse_official import BSE_RESULT_ARCHIVE, BSEOfficialFinancialResultsArchiveProvider, BSEOfficialLocalXbrlIngestionService
from app.fundamentals.diagnostic_comparability import assemble_financial_comparability, canonical_json, content_fingerprint
from app.fundamentals.store import _fact, SQLiteFinancialFactStore
from app.storage.core_api_snapshot_repository import snapshot_json_from
from scripts.audit_bse_annual_history import _Corrections


def _write_once(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _inputs(database, as_of):
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("BEGIN")
        facts = tuple(_fact(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM financial_facts ORDER BY fact_id"))
        filings = tuple(_filing(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM corporate_filings ORDER BY filing_id"))
        projection = FinancialPeriodIdentityProjection(_Corrections(connection))
        grouped, mappings = defaultdict(list), defaultdict(list)
        for fact in facts:
            grouped[fact.instrument.instrument_id].append(fact)
        if len(grouped) != 31:
            raise ValueError("APPROVED_31_COMPANY_SOURCE_SCOPE_CHANGED")
        for row in connection.execute("SELECT payload_json FROM core_api_snapshots WHERE family='PROVIDER_INSTRUMENT_MAPPING' ORDER BY created_at,snapshot_id"):
            item = snapshot_json_from(row[0]).payload
            if item.provider == "BSE_OFFICIAL" and item.effective_as_of <= as_of:
                mappings[item.canonical_instrument_id].append(item)
        result = []
        for identifier, own in sorted(grouped.items()):
            candidates = mappings[identifier]
            if not candidates or len({(v.isin, v.provider_instrument_reference) for v in candidates}) != 1:
                raise ValueError("EXACT_BSE_MAPPING_MISSING_OR_AMBIGUOUS:" + identifier)
            mapping = max(candidates, key=lambda v: (v.effective_as_of, v.mapping_id))
            current = assemble_financial_comparability(projection.project(tuple(own), as_of=as_of),
                tuple(f for f in filings if f.instrument.instrument_id == identifier),
                canonical_instrument_id=identifier, as_of=as_of)
            result.append((own[0].instrument, mapping, current))
    return tuple(result)


def acquire(*, database, source_root, report_root, max_documents):
    # Capture real receipt time at the acquisition boundary only; never pretend
    # these old accounts were present in HSI at their old publication dates.
    started = datetime.now(UTC)
    inputs = _inputs(database, started)
    transport = BseOfficialHttpTransport()
    archive_root = source_root / "annual_history_archives"
    archive_root.mkdir(parents=True, exist_ok=True)
    snapshot_store = BseOfficialArchiveSnapshotStore(archive_root)
    staging = BseOfficialXbrlStaging(source_root / "nifty500")
    importer = BSEOfficialLocalXbrlIngestionService(SQLiteCorporateFilingsStore(database), SQLiteFinancialFactStore(database))
    local = {}
    for path in sorted(source_root.rglob("*.json")):
        if path.name.endswith(".aliases.json"):
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        if "filename" in meta and str(meta["filename"]).endswith(".xml"):
            local.setdefault(meta["source_reference"], []).append((path.parent / meta["filename"], meta))
    attempted, unavailable_streak, rows = 0, 0, []
    for instrument, mapping, comparable in inputs:
        code = mapping.provider_instrument_reference
        exact = BseSecurityMapping(instrument.instrument_id, instrument.isin, BseMappingStatus.EXACT,
            code, instrument.symbol, instrument.name, mapping.source_reference,
            mapping.effective_as_of, content_fingerprint(mapping))
        try:
            # Reuse this slice's immutable archive snapshot in subsequent batches.
            cached = sorted(archive_root.glob(f"bse-archive-{code}-*.json"))
            if len(cached) > 1:
                raise ValueError("ANNUAL_ARCHIVE_SNAPSHOT_AMBIGUOUS")
            if cached:
                sidecar = json.loads(cached[0].read_text(encoding="utf-8"))
                csv_path = cached[0].with_suffix(".csv")
                raw = csv_path.read_bytes()
                if "sha256:" + sha256(raw).hexdigest() != sidecar["raw_sha256"]:
                    raise ValueError("ANNUAL_ARCHIVE_SNAPSHOT_HASH_MISMATCH")
            else:
                response = transport.fetch_results_archive_response(BSE_RESULT_ARCHIVE.format(security_code=code))
                snapshot_store.capture(mapping=exact, response=response)
                raw = response.body
                sleep(0.5)
            provider = BSEOfficialFinancialResultsArchiveProvider(fetch_csv=lambda _: raw.decode("utf-8-sig"))
            archives = provider.result_metadata_aliases(code)
            selection = select_missing_annual_history(comparable, mapping, archives)
            rows.append({"symbol": instrument.symbol, "selection": selection})
            for metadata in selection.selected:
                key = sha256(metadata.xbrl_url.encode()).hexdigest()
                receipt_path = report_root / (key + ".json")
                if receipt_path.exists():
                    continue  # immutable completed-document receipt, no blind retry
                if attempted >= max_documents:
                    break
                attempted += 1
                incoming = None
                try:
                    retained = local.get(metadata.xbrl_url, [])
                    if retained:
                        hashes = {m["sha256"] for _, m in retained}
                        if len(hashes) != 1:
                            raise ValueError("RETAINED_DOCUMENT_VERSIONS_CONFLICTED")
                        path, meta = retained[0]
                        body = path.read_bytes()
                        if sha256(body).hexdigest() != meta["sha256"]:
                            raise ValueError("RETAINED_DOCUMENT_HASH_MISMATCH")
                        response = BseOfficialHttpResponse(metadata.xbrl_url, meta["content_type"], body,
                                                         datetime.fromisoformat(meta["received_at"]))
                    else:
                        response = transport.fetch_xbrl(metadata.xbrl_url)
                    incoming = {"sha256": sha256(response.body).hexdigest(), "bytes": len(response.body),
                                "received_at": response.received_at}
                    staged = staging.stage(mapping=exact, metadata=metadata, response=response)
                    group = next(g for g in archives if g.document_url == metadata.xbrl_url)
                    staging.preserve_archive_aliases(staged=staged, mapping=exact, aliases=group)
                    imported = importer.ingest_official_staged(instrument, code, staged.path, metadata=metadata)
                    replay = importer.ingest_official_staged(instrument, code, staged.path, metadata=metadata)
                    if replay.facts_inserted or replay.facts_conflicted:
                        raise ValueError("ANNUAL_REPLAY_INVARIANT_FAILED")
                    receipt = {"symbol": instrument.symbol, "code": code, "metadata": metadata,
                        "status": "CONFLICTED" if imported.facts_conflicted else "ACCEPTED",
                        "staged_path": staged.path.relative_to(ROOT).as_posix(), "sha256": staged.sha256,
                        "imported": imported, "replay": replay, "received_at": response.received_at,
                        "retained_source_reused": bool(retained)}
                    unavailable_streak = 0
                except (ValueError, OSError) as error:
                    receipt = {"symbol": instrument.symbol, "code": code, "metadata": metadata,
                               "status": "REJECTED", "reason": str(error), "incoming": incoming,
                               "at": datetime.now(UTC)}
                    unavailable_streak = unavailable_streak + 1 if "SOURCE_UNAVAILABLE" in str(error) else 0
                    if "INVARIANT" in str(error):
                        _write_once(receipt_path, receipt)
                        raise
                _write_once(receipt_path, receipt)
                print(canonical_json({"attempted": attempted, "symbol": instrument.symbol,
                    "period": metadata.period_end, "status": receipt["status"], "reason": receipt.get("reason"),
                    "inserted": receipt.get("imported").facts_inserted if receipt.get("imported") else 0}), flush=True)
                if unavailable_streak >= 2:
                    _write_once(report_root / "PROVIDER_HALT.json", {"at": datetime.now(UTC), "receipt": receipt})
                    break
                sleep(0.5)
        except (ValueError, OSError) as error:
            if "INVARIANT" in str(error):
                _write_once(report_root / "INVARIANT_HALT.json", {"at": datetime.now(UTC), "reason": str(error)})
                raise
            rows.append({"symbol": instrument.symbol, "archive_error": str(error)})
            unavailable_streak += 1
            if unavailable_streak >= 2:
                _write_once(report_root / "PROVIDER_HALT.json", {"at": datetime.now(UTC), "reason": str(error)})
        if attempted >= max_documents or unavailable_streak >= 2:
            break
    _write_once(report_root / ("batch-" + started.strftime("%Y%m%dT%H%M%S%f") + ".json"),
                {"started": started, "attempted": attempted, "rows": rows, "halted": unavailable_streak >= 2})
    print(canonical_json({"batch_complete": True, "attempted": attempted, "halted": unavailable_streak >= 2}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--max-documents", type=int, default=5, choices=range(1, 26))
    args = parser.parse_args()
    report_root = ROOT / "reports" / "bse-annual-history-v1" / "acquisition"
    report_root.mkdir(parents=True, exist_ok=True)
    if any((report_root / name).exists() for name in ("PROVIDER_HALT.json", "INVARIANT_HALT.json")):
        parser.error("Saved provider/invariant halt requires explicit operator review; not automatically resumed")
    lock = report_root / "worker.lock"
    # Atomic ownership; never remove an existing worker's lock.
    with lock.open("x", encoding="ascii") as handle:
        handle.write(str(os.getpid()))
    try:
        acquire(database=ROOT / "data" / "nse_stock_manager.db",
                source_root=ROOT / "data" / "official_sources" / "bse_financial_results",
                report_root=report_root, max_documents=args.max_documents)
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
