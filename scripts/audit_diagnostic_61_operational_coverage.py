"""Read-only coverage projection of the sole canonical 61-rule registry.

No evaluator, policy, score, authority or persistence is defined here. Audit
annotations describe existing code, not new inputs to that code. The explicit
cutoff is an audit visibility boundary, not a claim of live market freshness.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_fact_vintage_selection_policy import CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY
from app.fundamentals.store import _fact, _filter
from app.filings.store import _filing
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.scoring.engine import COMPONENTS
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.taxonomy.security_sector_index_mapping_coverage import SecuritySectorIndexCoverageInput, audit_current_security_sector_index_coverage
from app.universe_analysis.benchmark_sector_technical_input import assemble_current_descriptive_benchmark_sector_input
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler

CONTRACT = "diagnostic-61-operational-coverage"
VERSION = "v1"
POLICY_PATH = "docs/architecture/RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json"
POLICY_FP = "sha256:bc1f7548b372738d69b72c2e54afdc34c9f10929aee9a10d834ce99cb8d43d8a"

# One annotation per existing wrapper, in canonical registry order. Names,
# purpose, category, missing behavior and horizon cells are NEVER redefined.
ANNOTATIONS = (
    ("market_regime", "market", "NIFTY_50 daily OHLC; 4+ aligned observations; breadth optional", "CANONICAL_INDEX_OHLC_OBSERVATION", "Benchmark retrieval known-at; breadth missing remains a limitation"),
    ("sector_health", "sector", "Exact sector index + NIFTY_50; 4 aligned daily sessions", "NSE_SECTOR_INDEX_MAPPING + CANONICAL_INDEX_OHLC_OBSERVATION", "No close-only/ETF/TRI or broad-sector proxy"),
    ("sector_rotation", "sector", "Exact sector index + NIFTY_50; 3-session relative return", "NSE_SECTOR_INDEX_MAPPING + CANONICAL_INDEX_OHLC_OBSERVATION", "Mapping is not OHLC readiness"),
    ("primary_trend", "technical", "Distinct certified daily/weekly snapshots", "NSE_UDIFF_DAILY/WEEKLY", "6 daily and 6 genuine weekly observations"),
    ("weinstein", "technical", "Genuine weekly structure", "NSE_UDIFF_WEEKLY", "5 weekly observations; no daily relabel"),
    ("relative_strength", "relative", "Stock/benchmark aligned sessions; sector/peers descriptive", "NSE_UDIFF + canonical PRI index OHLC", "Classification uses stock/benchmark; peers absent, not synthetic"),
    ("smart_money_proxies", "technical", "OHLCV location and volume", "NSE_UDIFF_DAILY", "Observable proxy; not actual institutional transactions"),
    ("liquidity_pools", "technical", "Price/volume clusters", "NSE_UDIFF_DAILY", "Technical evidence only"),
    ("wyckoff_phase", "technical", "Price/volume phase proxies", "NSE_UDIFF_DAILY", "Existing heuristic unchanged"),
    ("market_structure", "technical", "Daily pivot structure", "NSE_UDIFF_DAILY", "6 daily observations"),
    ("volume", "technical", "RVOL and volume continuity", "NSE_UDIFF_DAILY", "4 daily observations"),
    ("ichimoku", "technical", "Daily OHLC; existing 2/3/4/1 parameters", "NSE_UDIFF_DAILY", "5 daily observations"),
    ("chikou", "technical", "Daily OHLC; existing displacement", "NSE_UDIFF_DAILY", "5 daily observations"),
    ("mtf", "technical", "Distinct 1D/1W snapshots; other frames only if real", "NSE_UDIFF_DAILY/WEEKLY", "Partial timeframe coverage; no 4H/1H/15m substitution"),
    ("business_model_moat", "research", "Business/moat predicate ResearchClaims", "ResearchSnapshot primary/secondary documents", "No claim synthesis from financial totals or headlines"),
    ("financial_trend", "annual", "6 annual revenue/EBITDA/PAT/EPS points for 5-year CAGR", "FinancialFact -> FundamentalsEngineAdapter", "Calendar continuity, basis and units must be comparable"),
    ("return_ratios", "annual", "PAT/EBIT; equity/capital denominator; balance-sheet dates", "FinancialFact -> FundamentalsEngineAdapter", "Average equity preferred; documented ending fallback; industrial applicability not inferred for banks"),
    ("cash_flow", "annual", "Annual CFO, CAPEX, PAT", "FinancialFact -> FundamentalsEngineAdapter", "CFO minus CAPEX; missing CAPEX is not zero"),
    ("leverage", "annual", "Debt/equity/cash/EBIT/interest expense", "FinancialFact -> FundamentalsEngineAdapter", "No synthesis from borrowings without governed total-debt bridge"),
    ("working_capital", "annual", "Receivables/revenue; inventory/payables/COGS for CCC", "FinancialFact -> FundamentalsEngineAdapter", "Explicit applicability flag only; missing is not not-applicable"),
    ("ownership", "ownership", "2 comparable promoter holding/pledge periods", "NSE Reg31 OwnershipObservation -> legacy filing fields (not connected)", "One reporting period is not a holding shift"),
    ("institutional_holdings", "ownership", "2 comparable FII/DII/MF holding periods", "NSE Reg31 OwnershipObservation -> legacy filing fields (not connected)", "Quarterly holdings != daily flows != block/bulk transactions"),
    ("corporate_governance", "governance", "Auditor/regulatory/restatement/related-party/pledge claims", "ResearchSnapshot; canonical disclosures/reliability are separate evidence", "No claims must not mean CLEAN; adverse block not overridden by growth"),
    ("earnings_acceleration", "quarterly", "5 quarterly revenue observations", "FinancialFact -> FundamentalsEngineAdapter", "Latest versus year-ago; organic/one-off classification not provided"),
    ("latest_quarter", "quarterly", "5 quarter-only revenue/EBITDA/PAT/EPS observations", "FinancialFact -> FundamentalsEngineAdapter", "Available metrics only; no quarterly interpolation"),
    ("margin_trajectory", "quarterly", "5 quarter-only EBITDA/revenue observations", "FinancialFact -> FundamentalsEngineAdapter", "Operating margin only; gross-margin input unavailable"),
    ("order_book", "business", "Latest order book/order inflow/revenue and prior disclosure", "Typed FinancialObservation business fields", "Exact identity, unit, period, known-at and amendments; no stream present"),
    ("management_guidance", "research", "Dated GuidanceItem expected versus actual", "ResearchSnapshot guidance/documents", "At least one comparable item; repeated misses use existing rule"),
    ("valuation_multiples", "valuation", "Price date; annual EPS; forward EPS/growth; shares/debt/cash/EBITDA/book", "Certified daily price + canonical FinancialFact", "Partial P/E is not full valuation; missing denominators not zero"),
    ("fundamental_catalysts", "event", "Non-cancelled typed Catalyst and canonical document", "ResearchSnapshot catalysts", "News-store existence does not establish Catalyst semantics"),
    ("comprehensive_risk", "synthesis", "Eligible 1/2/19/23/29/46/55/30; ordinal probability-impact", "Existing EvaluatedDiagnostic lineage", "Existing runner order does not yet include Rule46 when Rule31 executes"),
    ("trading_thesis", "synthesis", "Eligible 43/45/46 and risk context", "Existing EvaluatedDiagnostic lineage", "No downstream execution; geometry can still be insufficient"),
    ("investment_thesis", "synthesis", "Eligible 16/17/18/19/23", "Existing EvaluatedDiagnostic lineage", "All required fundamental/governance results needed"),
    ("scenarios", "synthesis", "Eligible 31/32/33", "Existing EvaluatedDiagnostic lineage", "No newly calibrated probabilities"),
    ("vwap", "named_vwap", "Named canonical VWAP/value-area semantics", "No certified named source", "Legacy generic VWAP fallback is not canonical source readiness"),
    ("obv", "technical", "Daily close/volume", "NSE_UDIFF_DAILY", "4 daily observations"),
    ("base_pattern", "technical", "Daily OHLCV structural window", "NSE_UDIFF_DAILY", "5 daily observations; governed heuristic unchanged"),
    ("pullback_quality", "technical", "Daily support/volume", "NSE_UDIFF_DAILY", "5 daily observations"),
    ("indicator_layer", "technical", "Existing RSI/ADX/ATR inputs", "NSE_UDIFF_DAILY", "5 daily observations; no added indicators"),
    ("aggressive_entry", "technical", "Existing daily structure", "NSE_UDIFF_DAILY", "Diagnostic geometry; no order authority"),
    ("confirmation_entry", "technical", "Existing daily structure", "NSE_UDIFF_DAILY", "Diagnostic geometry; no order authority"),
    ("retest_entry", "technical", "Existing daily retest structure", "NSE_UDIFF_DAILY", "Diagnostic geometry; no order authority"),
    ("structural_stop", "technical", "Existing daily structural low", "NSE_UDIFF_DAILY", "Diagnostic geometry; no stop order"),
    ("target_hierarchy", "technical", "Existing daily resistance/structure", "NSE_UDIFF_DAILY", "Diagnostic geometry; no forecast authority"),
    ("risk_reward", "technical", "Existing Rule40/43/44 geometry", "Existing diagnostics + certified daily input", "Input readiness does not guarantee valid reward/risk geometry"),
    ("thesis_invalidation", "technical", "Existing structural/volume invalidation", "NSE_UDIFF_DAILY", "Descriptive invalidation; no automatic sale"),
    ("crowd_sentiment", "crowd", "Typed crowd observations with source/reliability/known-at/dedup", "CrowdSnapshot", "No measured production crowd observations"),
    ("crowd_positioning", "crowd", "Typed positioning observations", "CrowdSnapshot", "Not inferred from daily aggregate institutional flows"),
    ("crowd_data_confidence", "crowd", "Sample, source reliability and independent dedup groups", "CrowdSnapshot", "Not financial-data confidence"),
    ("accumulation_distribution_proxy", "technical", "OHLCV location/participation", "NSE_UDIFF_DAILY", "Not observed institutional ownership"),
    ("stop_clusters", "technical", "OHLCV structural clusters", "NSE_UDIFF_DAILY", "Technical evidence, not actual stop orders"),
    ("liquidity_events", "technical", "Sweep/absorption/acceptance price-volume", "NSE_UDIFF_DAILY", "No execution"),
    ("bull_trap", "technical", "Daily price-volume trap context", "NSE_UDIFF_DAILY", "3 daily observations"),
    ("bear_trap", "technical", "Daily price-volume trap context", "NSE_UDIFF_DAILY", "3 daily observations"),
    ("crowd_trap_probability", "crowd", "Crowd plus price; certified hybrid input required", "CrowdSnapshot + technical input", "Canonical path fails closed; no hybrid adapter"),
    ("crowd_divergence", "crowd", "Crowd plus aligned price", "CrowdSnapshot + technical input", "Canonical path fails closed; no hybrid adapter"),
    ("post_news_reaction", "event", "Canonical event materiality/known-at/completed-session relation", "NewsEvent + technical input (canonical join absent)", "No same-date/post-news-price inference"),
    ("volume_climax", "technical", "Daily price and volume", "NSE_UDIFF_DAILY", "3 daily observations"),
    ("contrarian_ichimoku", "synthesis", "Eligible 47/12/13/14", "Existing EvaluatedDiagnostic lineage", "Missing upstream is INSUFFICIENT_DATA, not CONFLICTING"),
    ("contrarian_quality", "synthesis", "Eligible 55/56/59/49", "Existing EvaluatedDiagnostic lineage", "No missing-to-weak conversion"),
    ("contrarian_verdict", "synthesis", "Eligible 60/49", "Existing EvaluatedDiagnostic lineage", "Legacy diagnostic label is not product/trade authorization"),
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return "sha256:" + sha256(encoded(value).encode()).hexdigest()


def canonical_policy():
    value = json.loads((ROOT / POLICY_PATH).read_text(encoding="utf-8"))
    if value["policy_fingerprint"] != POLICY_FP or fingerprint({k:v for k,v in value.items() if k!="policy_fingerprint"}) != POLICY_FP:
        raise ValueError("COVERAGE_FROZEN_POLICY_FINGERPRINT_MISMATCH")
    if [r["rule_id"] for r in value["rule_horizon_rows"]] != list(range(1, 62)):
        raise ValueError("COVERAGE_FROZEN_POLICY_ROWS_INVALID")
    return value


def _snapshots(connection, family):
    return tuple(snapshot_json_from(row[0]).payload for row in connection.execute(
        "SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY snapshot_id", (family,)))


def _latest(values, key, time, cutoff):
    result = {}
    for item in values:
        if time(item) > cutoff:
            continue
        k = key(item)
        if k not in result or time(item) > time(result[k]):
            result[k] = item
        elif time(item) == time(result[k]) and item != result[k]:
            raise ValueError("COVERAGE_AUDIT_AMBIGUOUS_LATEST")
    return result


class _Facts:
    def __init__(self, values): self.values = values
    def facts(self, instrument_id, **kwargs):
        return _filter(tuple(f for f in self.values if f.instrument.instrument_id == instrument_id), **kwargs)


class _Filings:
    def __init__(self, values): self.values = values
    def list(self, *, instrument_id, as_of, limit):
        return tuple(f for f in self.values if f.instrument.instrument_id == instrument_id and max(f.announced_at, f.received_at) <= as_of)[:limit]


class _Observations:
    def __init__(self, values): self.values = values
    def observations_as_of(self, at): return self.values


def collect(connection, as_of):
    """One readonly transaction, small canonical tables and indexed counts only."""
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    checked = ("financial_facts", "corporate_filings", "observations", "canonical_diagnostic_results",
               "strategy_versions", "diagnostic_results", "portfolio_snapshots", "paper_trades", "trade_plans",
               "canonical_decision_scorecards", "canonical_execution_gate_evaluations", "canonical_execution_gate_decisions",
               "external_intelligence_events", "news_evidence", "canonical_diagnostic_strategy_definitions")
    counts = {t: connection.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0] if t in tables else None for t in checked}
    families = dict(connection.execute("SELECT family, COUNT(*) FROM core_api_snapshots GROUP BY family"))
    raw_facts = tuple(r[0] for r in connection.execute("SELECT payload_json FROM financial_facts ORDER BY fact_id"))
    facts = tuple(_fact(json.loads(r)) for r in raw_facts)
    filings = tuple(_filing(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM corporate_filings ORDER BY filing_id"))
    current = tuple(f for f in facts if f.available_at <= as_of and f.period_end <= as_of)
    grouped = defaultdict(list)
    for f in current: grouped[f.instrument.instrument_id].append(f)
    metrics = []
    metric_groups = defaultdict(list)
    for f in current: metric_groups[(f.metric.value, f.period_type.value, f.value_basis.value, f.statement_scope.value, f.scale.value)].append(f)
    for key, values in sorted(metric_groups.items()):
        metrics.append(dict(zip(("metric", "period_type", "basis", "scope", "scale"), key)) | {
            "rows": len(values), "companies": len({v.instrument.instrument_id for v in values}),
            "first_period": min(v.period_end for v in values).isoformat(), "last_period": max(v.period_end for v in values).isoformat()})
    universe = _latest(_snapshots(connection, "NSE_UNIVERSE"), lambda v: v.instrument_id, lambda v: v.data_as_of, as_of)
    snapshot = max((v for v in _snapshots(connection, "UNIVERSE_SNAPSHOT") if v.as_of <= as_of), key=lambda v: v.as_of)
    taxonomy = _latest(_snapshots(connection, "TAXONOMY_CLASSIFICATION"), lambda v: v.instrument_id, lambda v: v.as_of, as_of)
    technical_ids = {r[0] for r in connection.execute("SELECT DISTINCT canonical_instrument_id FROM nse_udiff_weekly_technical_bars")}
    index = tuple(v for v in _snapshots(connection, "CANONICAL_INDEX_OHLC_OBSERVATION") if v.eligible_as_of(as_of))
    indices = defaultdict(list)
    for v in index: indices[v.canonical_index_id].append(v)
    mappings = _snapshots(connection, "NSE_SECTOR_INDEX_MAPPING")
    sector = audit_current_security_sector_index_coverage(
        audit_as_of=as_of,
        inputs=tuple(SecuritySectorIndexCoverageInput(universe[k], taxonomy.get(k), k in technical_ids) for k in sorted(snapshot.instrument_ids)),
        mappings=mappings, canonical_index_ohlc_session_counts={k: len(v) for k, v in indices.items() if k.startswith("NSE_SECTOR_INDEX:")})
    selected_mappings = _latest(mappings, lambda v: v.canonical_sector, lambda v: v.fetched_at_utc, as_of)
    sector_ready = 0
    benchmark = tuple(indices.get("NIFTY_50", ()))
    benchmark_probe = None
    context_by_sector = {}
    for r in sector.technical_scope_records:
        # No stock data enters Rules 1/2/3. Validate the same canonical index
        # pair once, then count each exact covered security, not another scan.
        key = (r.canonical_sector, r.canonical_index_id)
        if key not in context_by_sector:
            context_by_sector[key] = assemble_current_descriptive_benchmark_sector_input(
                canonical_instrument_id=r.canonical_instrument_id, as_of=as_of, technical_input=None,
                benchmark_observations=benchmark, sector_mapping=selected_mappings.get(r.canonical_sector) if r.canonical_index_id else None,
                sector_observations=tuple(indices.get(r.canonical_index_id, ())) if r.canonical_index_id else ())
        context = context_by_sector[key]
        sector_ready += context.rule_input(2)[0] is not None
        if benchmark_probe is None: benchmark_probe = context
    # Existing wrappers only, no diagnostic persistence, score or gate calls.
    adapter = FundamentalsEngineAdapter(_Facts(facts), _Filings(filings))
    company_audit = []
    selector_states = Counter()
    selector_reasons = Counter()
    for instrument_id, values in sorted(grouped.items()):
        vintage = select_financial_fact_vintages(values, canonical_instrument_id=instrument_id, as_of=as_of,
            policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY)
        selector_states.update(dict((k.value, v) for k,v in vintage.status_counts))
        selector_reasons.update(dict((k.value, v) for k,v in vintage.reason_counts))
        built = adapter.build(instrument_id, as_of=as_of)
        instrument = universe.get(instrument_id)
        evaluations = {}
        if instrument is not None:
            evidence = StockDiagnosticInputAssembler(_Observations(built.snapshot.observations)).assemble(instrument, as_of)
            runner = Canonical61DiagnosticRunner()
            for rule in (16,17,18,19,20,21,22,24,25,26,27):
                try:
                    v = runner._evaluate(rule, evidence, {})
                    evaluations[str(rule)] = {"eligibility": v.eligibility.value, "result": v.record.result}
                except (ValueError, TypeError, ZeroDivisionError):
                    evaluations[str(rule)] = {"eligibility": "ineligible", "result": "INSUFFICIENT_DATA"}
        company_audit.append({"instrument_id": instrument_id, "symbol": values[0].instrument.symbol,
            "fact_count": len(values), "scope": None if built.statement_scope is None else built.statement_scope.value,
            "annual_periods": sorted({f.period_end.isoformat() for f in values if f.period_type.value == "ANNUAL"}),
            "quarter_only_periods": sorted({f.period_end.isoformat() for f in values if f.value_basis.value == "QUARTER_ONLY"}),
            "earliest_known_at": min(f.available_at for f in values).isoformat(),
            "latest_known_at": max(f.available_at for f in values).isoformat(),
            "selector_fingerprint": vintage.fingerprint, "adapter_warnings": sorted(built.warnings),
            "existing_wrapper_results_not_comparability_certification": evaluations})
    owners = _snapshots(connection, "OWNERSHIP_OBSERVATION")
    ownership = [{"category": cat, "rows": len(v), "companies": len({x.canonical_instrument_id for x in v}),
        "periods": sorted({x.reporting_period.isoformat() for x in v}),
        "latest_known_at": max(max(x.published_at, x.received_at) for x in v).isoformat()}
        for cat,v in sorted(_group(owners, lambda x: x.category.value).items())]
    protected = {}
    for table in ("portfolio_snapshots", "paper_trades", "trade_plans", "canonical_diagnostic_strategy_definitions"):
        if table in tables:
            rows = sorted(connection.execute('SELECT * FROM "' + table + '"').fetchall(), key=repr)
            protected[table] = {"rows": len(rows), "fingerprint": fingerprint(rows)}
    return {"table_counts": counts, "snapshot_family_counts": families, "protected_tables": protected,
        "financial_fact_content_fingerprint": fingerprint([json.loads(v) for v in raw_facts]),
        "financial_fact_companies": len(grouped), "financial_metrics": metrics, "financial_companies": company_audit,
        "vintage_selection_states": dict(sorted(selector_states.items())), "vintage_selection_reasons": dict(sorted(selector_reasons.items())),
        "source_known_at_rule": "max(published_at,received_at); never backdate received facts to fiscal period",
        "facts_excluded_after_audit_as_of": len(facts)-len(current),
        "universe_denominator": len(snapshot.instrument_ids), "universe_snapshot_id": snapshot.snapshot_id,
        "sector": {"technical_denominator": len(sector.technical_scope_records), "exact_mappings": sector.mapped_count(technical_scope_only=True),
            "with_ohlc_history": sector.canonical_history_ready_count(technical_scope_only=True), "aligned_rule_2_3_inputs": sector_ready,
            "reason_counts": dict(sector.reason_counts(technical_scope_only=True)), "fingerprint": sector.fingerprint},
        "indices": {k: {"sessions": len(v), "latest_session": max(x.session for x in v).isoformat(),
            "latest_known_at": max(x.retrieved_at for x in v).isoformat(), "basis": sorted({x.index_return_family for x in v})} for k,v in sorted(indices.items())},
        "benchmark_input_ready": benchmark_probe is not None and benchmark_probe.rule_input(1)[0] is not None,
        "ownership": ownership,
        "canonical_15m_snapshot_rows": families.get("PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR", 0),
        "canonical_15m_conflict_rows": families.get("PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT", 0),
        "intraday_table_names": sorted(t for t in tables if "fifteen_minute" in t or "15m" in t),
        "latest_weekly_end": connection.execute("SELECT MAX(week_end) FROM nse_udiff_weekly_technical_bars").fetchone()[0],
        "authoritative_peer_cohorts": 0,
        "peer_count_evidence": "Canonical61DiagnosticRunner supplies literal empty peer tuple; no governed cohort reader",
        "daily_institutional_flows": "NOT_APPLICABLE: no canonical evaluator consumes this stream"}


def _group(values, key):
    result = defaultdict(list)
    for v in values: result[key(v)].append(v)
    return result


def build_artifact(*, measured, technical, as_of):
    if as_of.tzinfo is None: raise ValueError("COVERAGE_AS_OF_TIMEZONE_REQUIRED")
    definitions = tuple(DIAGNOSTIC_RULES)
    if tuple(r.rule_id for r in definitions) != tuple(range(1,62)) or len(ANNOTATIONS) != 61:
        raise ValueError("COVERAGE_CANONICAL_61_REQUIRED")
    policy = canonical_policy()
    records = []
    for definition, annotation, horizon in zip(definitions, ANNOTATIONS, policy["rule_horizon_rows"], strict=True):
        number = definition.rule_id
        method, domain, inputs, source, caveat = annotation
        evaluator = getattr(DeterministicDiagnosticEvaluators, method)
        technical_rule = technical["rules"].get(str(number))
        blockers = set()
        # A ready price component is not a ready valuation/synthesis/event
        # input. Preserve its own 2,538-security component denominator below;
        # never promote it to whole-rule coverage over the 2,553 universe.
        count = technical_rule["states"].get("READY",0) if technical_rule and domain == "technical" else None
        contract = "READY" if domain in {"technical","market","sector","relative","synthesis","research","governance","crowd"} else "PARTIAL"
        current = "NOT_READY"
        if domain == "technical":
            current = "READY" if count else "NOT_READY"
            if count != technical["securities_with_certified_daily_and_weekly_input"]: blockers.add("HISTORICAL_DEPTH_INSUFFICIENT")
        elif domain == "market":
            current = "READY" if measured["benchmark_input_ready"] else "NOT_READY"
            count = int(measured["benchmark_input_ready"])
        elif domain == "sector":
            count = measured["sector"]["aligned_rule_2_3_inputs"]
            current = "READY" if count else "NOT_READY"
            blockers.add("SECTOR_CONTEXT_PARTIAL")
        elif domain == "relative":
            current = "PARTIAL"; count = None
            blockers.update(("PEER_COHORT_NOT_READY", "SECTOR_CONTEXT_PARTIAL"))
        elif domain in {"annual","quarterly","valuation"}:
            current = "PARTIAL"
            blockers.update(("SOURCE_CONTRACT_INCOMPLETE","DATA_UNAVAILABLE","FRESHNESS_POLICY_UNSET"))
            if measured.get("vintage_selection_states", {}).get("CONFLICTED", 0):
                blockers.add("EVIDENCE_CONFLICTED")
        elif domain == "ownership":
            blockers.update(("HISTORICAL_DEPTH_INSUFFICIENT","SOURCE_CONTRACT_INCOMPLETE"))
        elif domain == "named_vwap": blockers.add("NAMED_VWAP_SEMANTICS_UNAVAILABLE")
        elif domain == "event": blockers.add("EVENT_EVIDENCE_NOT_READY")
        elif domain == "synthesis":
            current = "PARTIAL"
            blockers.add("DATA_UNAVAILABLE")
            if number == 31: blockers.add("SOURCE_CONTRACT_INCOMPLETE")
        else: blockers.add("DATA_UNAVAILABLE")
        if number == 14:
            current = "PARTIAL"; blockers.add("TIMEFRAME_DATA_NOT_READY")
        # Readiness is for the explicitly supplied snapshot, not 'fresh live
        # now'. Horizon definition acceptance does not activate consumers.
        blockers.add("HORIZON_RUNTIME_NOT_ACTIVE")
        blockers.add("PIT_NOT_PROVEN")
        prospective = "PARTIAL" if domain in {"annual","quarterly","valuation","ownership","research","governance","event","crowd"} else "NOT_READY"
        historical = "PARTIAL" if domain in {"annual","quarterly","valuation","ownership"} else "NOT_READY"
        op = "OPERATIONAL_CURRENT_DESCRIPTIVE" if current == "READY" else "PARTIAL" if current == "PARTIAL" else "NOT_READY"
        records.append({"rule_id": number, "rule_name": definition.canonical_name, "purpose": definition.purpose,
            "category": definition.category, "audit_domain": domain,
            "evaluator": "app.diagnostics.evaluators.DeterministicDiagnosticEvaluators."+method,
            "evaluator_source_line": inspect.getsourcelines(evaluator)[1],
            "input_dependencies": inputs, "source_dependencies": source, "limitations": caveat,
            "registry_required_inputs": list(definition.required_inputs), "registry_dependencies": list(definition.dependencies),
            "missing_data_behavior": definition.missing_data_behavior, "output_type": definition.output_type,
            "registry_output_states": [s.value for s in definition.possible_statuses],
            "applicability": "CURRENT_NSE_EQUITY; no missing-data to NOT_APPLICABLE conversion",
            "horizon_policy": {"definition": "READY", "governance": "FROZEN", "runtime_consumption": "PARTIAL", "source_cells_unchanged": horizon},
            "timeframe_policy": {"definition": "READY", "profile": horizon["technical_profile"], "runtime": "PARTIAL",
                "daily_weekly_component_audit_excludes_benchmark_sector_join": technical_rule, "other_timeframes": "NOT_READY; no 15m/30m/1H/4H/1M substitution"},
            "axes": {"REGISTRY_READY":"READY", "EVALUATOR_READY":"READY", "INPUT_CONTRACT_READY":contract,
                "CANONICAL_DATA_AVAILABLE": current, "SOURCE_AUTHORITY_READY": "READY" if domain in {"technical","market","sector","relative"} else "PARTIAL",
                "IDENTITY_READY": "READY" if domain in {"technical","market","sector","relative","synthesis"} else "PARTIAL",
                "APPLICABILITY_READY": "PARTIAL" if domain in {"annual","quarterly","business","valuation"} else "READY",
                "HORIZON_POLICY_READY":"READY", "TIMEFRAME_POLICY_READY":"READY", "CURRENT_DESCRIPTIVE_READY":current,
                "PROSPECTIVE_PIT_READY":prospective, "STRICT_HISTORICAL_PIT_READY":historical,
                "PRODUCTION_INPUT_READY":current, "EVALUATION_READY":current,
                "DOWNSTREAM_USE_READY":"PARTIAL", "BLOCKER_CLASS": sorted(blockers)},
            "coverage": {"certified_input_ready_count":count, "denominator":1 if domain == "market" else measured["sector"]["technical_denominator"] if domain in {"technical","sector","relative"} else measured["universe_denominator"],
                "unit":"benchmark series" if domain == "market" else "securities", "unknown_count_is_null":True,
                "note":"Input prerequisite count, NOT whole-universe successful evaluations; financial wrapper probes in measurements"},
            "operational_state":op, "blockers":sorted(blockers),
            "next_requirement":caveat,
            "temporal_semantics": "Filing/ownership max(publication,receipt) eligible only at/after receipt; current descriptive market observations are NOT historical availability proof. No new freshness days.",
            "downstream": {"status":"DOWNSTREAM_EXISTING_AUTHORITY / NOT_INVOKED_IN_THIS_SLICE",
                "mandatory_score_components":[c.component_id for c in COMPONENTS if number in c.mandatory],
                "optional_score_components":[c.component_id for c in COMPONENTS if number in c.optional],
                "six_gates":"Existing policy/evidence consumer, not a Rule result or execution permission"}})
    result = {"contract":CONTRACT, "version":VERSION, "as_of":as_of.astimezone(UTC).isoformat(),
        "canonical_registry_version":DIAGNOSTIC_REGISTRY_VERSION, "policy_reference":POLICY_PATH,
        "policy_content_fingerprint":POLICY_FP, "policy_definition":"READY / FROZEN", "horizon_rows":183,
        "policy_legacy_status_preserved":policy["status"], "runtime_consumption":"PARTIAL / NOT_ACTIVE",
        "records":records, "measurements":measured, "technical_audit":technical,
        "technical_audit_fingerprint":fingerprint(technical),
        "summary":{key:dict(sorted(Counter(r["axes"][key] for r in records).items())) for key in records[0]["axes"] if key!="BLOCKER_CLASS"},
        "operational_counts":dict(sorted(Counter(r["operational_state"] for r in records).items())),
        "blocker_counts":dict(sorted(Counter(b for r in records for b in r["blockers"]).items())),
        "authority":"AUDIT_ONLY / WATCH_ONLY / NON_EXECUTABLE",
        "missing_count_semantics":"null=not proven; zero=measured absence; source counts never certify all-rule readiness"}
    return result | {"fingerprint":fingerprint(result)}


def validate_artifact(value):
    if value["fingerprint"] != fingerprint({k:v for k,v in value.items() if k!="fingerprint"}):
        raise ValueError("COVERAGE_FINGERPRINT_MISMATCH")
    if [(r["rule_id"],r["rule_name"]) for r in value["records"]] != [(r.rule_id,r.canonical_name) for r in DIAGNOSTIC_RULES]:
        raise ValueError("COVERAGE_REGISTRY_MISMATCH")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--technical-audit", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.as_of.tzinfo is None: raise ValueError("COVERAGE_AS_OF_TIMEZONE_REQUIRED")
    if args.output.exists(): raise ValueError("COVERAGE_REPORT_ALREADY_EXISTS")
    with closing(sqlite3.connect(args.database.resolve().as_uri()+"?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        measured = collect(connection,args.as_of)
    result = build_artifact(measured=measured,technical=json.loads(args.technical_audit.read_text(encoding="utf-8")),as_of=args.as_of)
    validate_artifact(result)
    # Explicit generated report only. Never opens production repositories or
    # writes database rows; refuses to replace an earlier report.
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=True)+"\n",encoding="utf-8")
    print(encoded({"fingerprint":result["fingerprint"],"operational_counts":result["operational_counts"]}))
