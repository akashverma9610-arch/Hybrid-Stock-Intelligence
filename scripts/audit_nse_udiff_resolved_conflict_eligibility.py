"""Read-only retained-evidence reconciliation and exact 4/5/6-session reads.

No acquisition, migration or source rewrite. Explicit local report paths are
the only writes. Both the accepted collision audit and repair receipt are
checked against current SQLite observations and original archived rows.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from app.historical.nse_udiff_effective_identity_coverage import (
    NseUdiffEffectiveIdentityCoverageIndex, compose_action_window_coverage,
)
from app.market_data.historical import _bar_from_mapping, _conflict_artifact_from_payload
from app.market_data.nse_udiff_archive_verification import UdiffArchiveVerifier
from app.market_data.nse_udiff_conflict_resolution import reconcile_udiff_conflict
from app.market_data.nse_udiff_conflict_semantics import NseUdiffSourceRowEvidence
from app.market_data.nse_udiff_daily_integrity import audit_udiff_same_provider_conflicts
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalRequirement, DailyTechnicalRequirementProfile,
    certify_daily_technical_eligibility,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadRequest, NseUdiffDailyTechnicalReadEvidence,
    NseUdiffDailyTechnicalUseMode, read_certified_daily_technical_bars,
)
from app.market_data.nse_udiff_source_identity import source_fields
from app.storage.core_api_snapshot_repository import snapshot_json_from
from scripts.audit_nse_udiff_identity_boundary import open_readonly


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _snapshots(c, family):
    return tuple(snapshot_json_from(row[0]).payload for row in c.execute(
        "SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY snapshot_id", (family,)))


def _bars(c, instrument, start, end):
    # Source dates are NSE local dates, not the UTC date portion of start_time.
    return tuple(_bar_from_mapping(row) for row in c.execute(
        "SELECT * FROM historical_bars WHERE instrument_id=? AND provider_identity='nse_udiff_official' "
        "AND date(start_time,'+330 minutes') BETWEEN ? AND ? ORDER BY start_time,bar_id",
        (instrument, str(start), str(end))))


def _counts(c):
    tables = ("historical_bars", "historical_bar_conflicts", "core_api_snapshots",
              "portfolio_snapshots", "strategy_versions", "diagnostic_results")
    return {name: c.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0] for name in tables}


def audit(database: Path, accepted_audit: Path, repair_receipt: Path):
    import sqlite3
    historical = json.loads(accepted_audit.read_text(encoding="utf-8"))
    prior_resolved = json.loads(repair_receipt.read_text(encoding="utf-8"))
    prior = {item["conflict_fingerprint"]: item for item in prior_resolved}
    if len(prior) != len(prior_resolved):
        raise ValueError("UDIFF_REPAIR_RECEIPT_DUPLICATE")
    with closing(open_readonly(database)) as c:
        c.row_factory = sqlite3.Row
        before = _counts(c)
        raw_conflicts = tuple(row[0] for row in c.execute(
            "SELECT payload_json FROM historical_bar_conflicts ORDER BY conflict_fingerprint"))
        conflict_digest = sha256(_encoded(raw_conflicts).encode()).hexdigest()
        artifacts = tuple(_conflict_artifact_from_payload(raw) for raw in raw_conflicts)
        udiff = {item.conflict_fingerprint: item for item in artifacts
                 if item.stored_lineage.provider_identity == "nse_udiff_official"}
        def load(identifier):
            row = c.execute("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=?", (identifier,)).fetchone()
            if row is None:
                raise ValueError("UDIFF_RECONCILIATION_SOURCE_ARCHIVE_MISSING")
            return snapshot_json_from(row[0]).payload
        verifier = UdiffArchiveVerifier(load)
        resolutions, details = [], []
        for item in sorted(historical["conflicts"], key=lambda item: (item["trade_date"], item["conflict_fingerprint"])):
            conflict = udiff[item["conflict_fingerprint"]]
            sources = []
            for side in ("stored", "incoming"):
                evidence = item[side]
                archive, parsed = verifier._parsed(evidence["artifact_id"])
                row_index = evidence["row_index"]
                row = NseUdiffSourceRowEvidence(
                    archive.artifact_id, archive.fingerprint, archive.content_sha256,
                    archive.source_url, archive.observed_at, row_index,
                    tuple(tuple(pair) for pair in evidence["fields"]), evidence["fingerprint"])
                if dict(row.fields) != parsed.rows[row_index]:
                    raise ValueError("UDIFF_RECONCILIATION_ARCHIVED_ROW_CHANGED")
                sources.append(row)
            observations = _bars(c, conflict.canonical_instrument_id, item["trade_date"], item["trade_date"])
            identities = {s.source_row_id for s in sources}
            retained = tuple(bar for bar in observations if bar.source_observation_identity in identities)
            for bar in retained:
                verifier(bar)
            proof = reconcile_udiff_conflict(artifact=conflict, stored_row=sources[0], incoming_row=sources[1], retained_bars=retained)
            expected = prior[conflict.conflict_fingerprint]
            actual = sorted((bar.source_observation_identity, bar.bar_id, source_fields(bar)["SctySrs"]) for bar in retained)
            if (expected["status"] != "DISTINCT_SERIES/STRUCTURAL_COLLISION_RESOLVED"
                    or actual != sorted((x["source_identity"], x["bar_id"], x["series"]) for x in expected["observations"])):
                raise ValueError("UDIFF_RECONCILIATION_PRIOR_REPAIR_MISMATCH")
            resolutions.append(proof)
            details.append({"instrument": conflict.canonical_instrument_id, "date": item["trade_date"],
                "conflict_id": conflict.conflict_fingerprint, "classification": proof.classification.value,
                "state": proof.state.value, "resolution_fingerprint": proof.fingerprint,
                "observations": [{"id": bar.source_observation_identity, "bar_id": bar.bar_id,
                                  "fields": source_fields(bar)} for bar in retained]})
        if set(prior) != {item.artifact.conflict_fingerprint for item in resolutions}:
            raise ValueError("UDIFF_RECONCILIATION_REPAIR_POPULATION_MISMATCH")
        old = audit_udiff_same_provider_conflicts(artifacts)
        new = audit_udiff_same_provider_conflicts(artifacts, reconciliations=resolutions)
        print(_encoded({"reconciled": len(resolutions), "instruments": len({x["instrument"] for x in details}),
                        "states": dict(Counter(x["state"] for x in details))}), flush=True)
        identities = (*_snapshots(c, "NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL"),
                      *_snapshots(c, "NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL"))
        index = NseUdiffEffectiveIdentityCoverageIndex(identities)
        queries = _snapshots(c, "NSE_CORPORATE_ACTION_QUERY_RECEIPT")
        actions = _snapshots(c, "HISTORICAL_CORPORATE_ACTION")
        manifest, = _snapshots(c, "NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST")
        sessions = tuple(x.trade_date for x in manifest.entries if x.state.value == "ARTIFACT_VALID_SESSION")[-6:]
        universe = next(x for x in _snapshots(c, "UNIVERSE_SNAPSHOT") if x.snapshot_id == historical["universe_id"])
        instruments = tuple(sorted({x.instrument_id for x in _snapshots(c, "NSE_UNIVERSE")
                                    if x.instrument_id in universe.instrument_ids and x.isin}))
        current = {instrument: _bars(c, instrument, sessions[0], sessions[-1]) for instrument in instruments}
        at = max(*(q.observed_at for q in queries), *(bar.provenance.received_at for bars in current.values() for bar in bars))
        affected = {x["instrument"] for x in details}
        old_by, new_by = defaultdict(list), defaultdict(list)
        for item in old: old_by[item.canonical_instrument_id].append(item)
        for item in new: new_by[item.canonical_instrument_id].append(item)
        results, affected_results, holding_results = {}, {}, {}
        holding_ids = {"NSE:INE372A01015": "APARINDS", "NSE:INE0FHS01024": "DEEPINDS",
                       "NSE:INE955D01029": "GENUSPOWER", "NSE:INE068V01023": "GLAND", "NSE:INE090A01021": "ICICIBANK"}
        for count in (4, 5, 6):
            window = sessions[-count:]
            totals = Counter()
            changed, per_affected = [], []
            for instrument in instruments:
                bars = tuple(b for b in current[instrument] if date.fromisoformat(source_fields(b)["TradDt"]) in window)
                coverage = compose_action_window_coverage(canonical_instrument_id=instrument,
                    window_start=window[0], window_end=window[-1], identity_intervals=index,
                    query_receipts=queries, actions=actions, evaluation_as_of=at, required_sessions=window).assertion()
                request = NseUdiffDailyTechnicalReadRequest(instrument, window[0], window[-1],
                    DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME),
                    NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, at)
                readings = []
                for label, assessments in (("before", old_by[instrument]), ("after", new_by[instrument])):
                    conflicts = tuple(sorted(assessments, key=lambda x: (x.trade_date, x.conflict_fingerprint)))
                    evidence = NseUdiffDailyTechnicalReadEvidence(window, bars, index, coverage,
                        tuple(sorted(actions, key=lambda x: (x.effective_date, x.action_id))), conflicts)
                    reading = read_certified_daily_technical_bars(request=request, evidence=evidence)
                    cert = certify_daily_technical_eligibility(canonical_instrument_id=instrument,
                        start_session=window[0], end_session=window[-1], requirement=request.requirement,
                        evaluation_as_of=at, expected_sessions=window, observed_bars=bars,
                        identity_intervals=index, action_coverage=coverage, actions=actions, conflicts=conflicts)
                    if cert != reading.certification or (reading.state.value == "READY") != (cert.eligibility.value == "READY"):
                        raise ValueError("UDIFF_READER_CERTIFIER_MISMATCH")
                    totals[label + "_" + reading.state.value] += 1
                    blocking = tuple(x for x in conflicts if x.trade_date in window and x.blocks_window(bars, at))
                    for state in sorted({x.current_state.value for x in blocking}):
                        totals[label + "_blocking_state_" + state] += 1
                    for reason in cert.reasons:
                        if reading.state.value != "READY": totals[label + "_reason_" + reason.value] += 1
                    readings.append(reading)
                previous, latest = readings
                if previous.state != latest.state:
                    if previous.state.value != "NOT_READY" or "SAME_PROVIDER_CONFLICT" not in previous.reasons:
                        raise ValueError("UDIFF_UNEXPLAINED_ELIGIBILITY_CHANGE")
                    changed.append(instrument)
                if instrument in affected:
                    per_affected.append({"instrument": instrument, "selected_series": latest.certification.selected_series,
                        "before": previous.state.value, "after": latest.state.value,
                        "before_reasons": previous.reasons, "after_reasons": latest.reasons,
                        "resolved_artifacts_in_window": sum(x.trade_date in window and x.current_state.value == "RESOLVED_STRUCTURAL_CONFLICT" for x in new_by[instrument])})
                if count == 6 and instrument in holding_ids:
                    strict = read_certified_daily_technical_bars(request=NseUdiffDailyTechnicalReadRequest(
                        instrument, window[0], window[-1], request.requirement,
                        NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL, at), evidence=None)
                    holding_results[holding_ids[instrument]] = {"before": previous.state.value, "after": latest.state.value,
                        "reasons": latest.reasons, "strict": strict.reasons,
                        "source_observation_ids": latest.source_observation_ids,
                        "source_references": latest.source_references,
                        "raw_observations": [{"id": b.source_observation_identity, "bar_id": b.bar_id, "fields": source_fields(b)} for b in bars]}
            results[str(count)] = {"counts": dict(sorted(totals.items())), "improved_instruments": changed,
                "reader_certifier_mismatch": 0,
                "resolved_conflict_blockers_after": totals["after_blocking_state_RESOLVED_STRUCTURAL_CONFLICT"],
                "true_conflict_blockers_after": totals["after_blocking_state_CURRENT_TRUE_SOURCE_CONFLICT"],
                "unresolved_conflict_blockers_after": totals["after_blocking_state_CURRENT_UNRESOLVED_CONFLICT"]}
            affected_results[str(count)] = per_affected
            print(_encoded({"sessions": count, "before": totals["before_READY"], "after": totals["after_READY"], "improved": len(changed)}), flush=True)
        after = _counts(c)
        raw_after = tuple(row[0] for row in c.execute("SELECT payload_json FROM historical_bar_conflicts ORDER BY conflict_fingerprint"))
        if before != after or raw_conflicts != raw_after:
            raise ValueError("UDIFF_READ_ONLY_INVARIANT_CHANGED")
        return {"contract": "nse-udiff-resolved-conflict-eligibility-audit-v1", "evaluation_as_of": at.isoformat(),
            "sessions": [str(d) for d in sessions], "universe": universe.snapshot_id, "universe_count": len(instruments),
            "historical_artifacts": len(udiff), "artifact_payload_digest_before_after": conflict_digest,
            "accepted_audit_digest": sha256(accepted_audit.read_bytes()).hexdigest(),
            "repair_receipt_digest": sha256(repair_receipt.read_bytes()).hexdigest(),
            "reconciliation_states": dict(Counter(x.current_state.value for x in new)),
            "affected_instruments": len(affected), "conflicts": details, "coverage": results,
            "affected_windows": affected_results, "holdings": holding_results,
            "before_counts": before, "after_counts": after, "sqlite_mode": "mode=ro/query_only/transaction"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("database", "accepted-audit", "repair-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.database, args.accepted_audit, args.repair_receipt)
    encoded = _encoded(report)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / ("audit-" + sha256(encoded.encode()).hexdigest() + ".json")
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError("UDIFF_AUDIT_REPORT_IMMUTABILITY_CONFLICT")
    else:
        with path.open("x", encoding="utf-8") as file:
            file.write(encoded)
    print(_encoded({"report": str(path), "states": report["reconciliation_states"]}), flush=True)
