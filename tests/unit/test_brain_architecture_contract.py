from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hardened_brain_docs_define_the_canonical_flow_and_change_control():
    architecture = (ROOT / "docs" / "architecture" / "brain_architecture.md").read_text(encoding="utf-8")
    required = (
        "Brain Architecture v2.2-hardened", "Data Sources", "Data Reliability & Fallback",
        "Historical Integrity", "Data Validation", "Market Regime", "Sector Intelligence",
        "Opportunity Discovery", "Stock Research", "Market Integrity", "Setup Engine",
        "Decision Engine", "Hard Execution Gates", "Portfolio Brain", "Capital Rotation",
        "Risk & Execution", "Monitoring", "Outcomes", "Benchmark Engine", "Model Governance & Drift",
        "Self-Improvement", "Audit & Reproducibility", "Validated Deployment",
    )
    assert all(item in architecture for item in required)
    assert "Repository documentation and tested code are authoritative" in architecture
    assert "No downstream engine may silently bypass" in architecture
    for name in (
        "brain_contract.md", "defensive_engines.md", "data_flow.md", "decision_flow.md",
        "model_governance.md", "audit_reproducibility.md", "versioning_and_change_control.md",
    ):
        assert (ROOT / "docs" / "architecture" / name).is_file()


def test_defensive_facades_do_not_create_public_api_routes_or_mutate_governance():
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app" / "reliability").glob("*.py"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app" / "historical_integrity").glob("*.py"))
    sources += "\n" + (ROOT / "app" / "governance" / "drift.py").read_text(encoding="utf-8")
    assert "APIRouter" not in sources
    assert "save_approved_strategy" not in sources
    assert "save_strategy_activation" not in sources
