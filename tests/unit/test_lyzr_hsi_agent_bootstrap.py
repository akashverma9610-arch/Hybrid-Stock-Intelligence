"""Portable HSI/Lyzr package checks; no Lyzr account, ingress or network use."""
import importlib.util
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest

from app.api.agent_main import create_app


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "lyzr_bootstrap_hsi_agent_v1.py"
DOCUMENT = ROOT / "docs" / "architecture" / "HSI_AGENT_V1_LYZR_CONNECTION_AND_MASTER_THESIS_V1.md"


def _module():
    specification = importlib.util.spec_from_file_location("lyzr_bootstrap", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    assert specification.loader is not None
    specification.loader.exec_module(module)
    return module


def _schema():
    with TestClient(create_app()) as client:
        return client.get("/hsi/v1/openapi.json").json()


def test_master_thesis_and_portable_acceptance_prompts_are_complete():
    module = _module()
    thesis = module.master_thesis()
    prompts = module.acceptance_prompts()
    assert "FACT → DATA → INTERPRETATION → INFERENCE" in thesis
    assert "RESEARCH_READ_ONLY / WATCH_ONLY /\nNON_EXECUTABLE" in thesis
    assert "Never invent an entry" in thesis and "no broker" in thesis.lower()
    assert [item["id"] for item in prompts["prompts"]] == [
        "deep_stock_analysis", "market_opportunities", "setup", "portfolio", "compare",
    ]
    setup = next(item for item in prompts["prompts"] if item["id"] == "setup")
    market = next(item for item in prompts["prompts"] if item["id"] == "market_opportunities")
    portfolio = next(item for item in prompts["prompts"] if item["id"] == "portfolio")
    assert setup["required_tools"] == ["hsi_get_setup"]
    assert "hsi_scan_market" in setup["forbidden_tools"]
    assert "does not rescan per candidate" in market["assertions"]
    assert "does not run diagnostics for every holding by default" in portfolio["assertions"]
    assert len({item["id"] for item in prompts["prompts"]}) == len(prompts["prompts"])


def test_native_tool_schema_only_allows_actual_hsi_operations_and_public_origin():
    module = _module()
    prepared = module.validate_openapi(_schema(), origin="https://agent.example.in")
    assert prepared["servers"] == [{"url": "https://agent.example.in/hsi/v1", "description": "Approved HSI Agent HTTPS ingress"}]
    operation_ids = {operation["operationId"] for path in prepared["paths"].values() for operation in path.values()}
    assert operation_ids == module.EXPECTED_OPERATIONS
    for operation in (operation for path in prepared["paths"].values() for operation in path.values()):
        assert operation["security"] == [{"HSIAgentKey": []}]
    assert module.public_origin("https://agent.example.in/") == "https://agent.example.in"
    for origin in ("http://agent.example.in", "https://localhost", "https://127.0.0.1", "https://10.0.0.4", "https://agent.local", "https://agent.example.in/hsi/v1"):
        with pytest.raises(module.BootstrapError, match="PUBLIC_HTTPS_INGRESS_REQUIRED"):
            module.public_origin(origin)


def test_tool_and_agent_payloads_have_no_handwritten_route_or_model_defaults():
    module = _module()
    configuration = {
        "LYZR_API_KEY": "test-lyzr-key", "HSI_AGENT_API_KEY": "test-hsi-key",
        "HSI_PUBLIC_BASE_URL": "https://agent.example.in", "LYZR_LLM_CREDENTIAL_ID": "workspace-credential",
        "LYZR_PROVIDER_ID": "workspace-provider", "LYZR_MODEL": "workspace-model",
    }
    schema = module.validate_openapi(_schema(), origin="https://agent.example.in")
    tool = module.tool_payload(schema, hsi_agent_key=configuration["HSI_AGENT_API_KEY"])
    agent = module.agent_payload(["tool-one", "tool-two"], configuration)
    assert tool["default_headers"] == {"Authorization": "Bearer test-hsi-key"}
    assert tool["enhance_descriptions"] is False and tool["openai_api_key"] is None
    assert agent["name"] == "Hybrid Stock Intelligence"
    assert agent["provider_id"] == "workspace-provider" and agent["model"] == "workspace-model"
    assert agent["tools"] == ["tool-one", "tool-two"] and agent["temperature"] == 0.2
    assert agent["store_messages"] is False
    assert "HSI_AGENT_API_KEY" not in json.dumps(agent)
    assert "test-hsi-key" not in json.dumps(agent)


def test_missing_configuration_and_local_files_fail_closed_without_request(monkeypatch):
    module = _module()
    for name in module.REQUIRED_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(module.BootstrapError, match="CONFIGURATION_MISSING"):
        module.configured_environment()
    assert module.acceptance_prompts()["schema_version"] == "hsi-agent-v1-acceptance-prompts/v1"


def test_bootstrap_is_isolated_from_hsi_core_runtime_and_secret_values_are_not_tracked():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from app." not in source and "import app." not in source and "requests" not in source
    assert "--create" in source and "create_requires_explicit_flag" in source
    assert "LYZR_AGENT_CREATED agent_id=" in source and "tool_ids=" in source
    assert "str(error)" not in source
    tracked = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in tracked
    for path in (ROOT / "config" / "hsi_agent_v1_master_thesis.md", ROOT / "config" / "hsi_agent_v1_acceptance_prompts.json", SCRIPT):
        text = path.read_text(encoding="utf-8")
        assert "sk-default-" not in text and "Bearer sk-" not in text


def test_connection_document_local_links_and_whitespace_are_valid():
    text = DOCUMENT.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if "://" not in target and not target.startswith("#"):
            assert (DOCUMENT.parent / target.split("#")[0]).resolve().is_file(), target
    assert all(line == line.rstrip() for line in text.splitlines())
