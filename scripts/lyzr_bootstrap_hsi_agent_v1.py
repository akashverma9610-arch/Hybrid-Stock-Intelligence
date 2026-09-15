"""Explicit, opt-in Lyzr bootstrap for the mounted HSI Agent OpenAPI facade.

This script owns no HSI intelligence and imports no HSI runtime module.  It
uses the public tool-only OpenAPI document at execution time, then creates one
OpenAPI tool set and one Agent only when ``--create`` is supplied.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


LYZR_BASE_URL = "https://agent-prod.studio.lyzr.ai"
TOOL_SET_NAME = "Hybrid Stock Intelligence V1"
AGENT_NAME = "Hybrid Stock Intelligence"
EXPECTED_OPERATIONS = frozenset({
    "hsi_get_capabilities", "hsi_run_diagnostics", "hsi_get_stock_intelligence",
    "hsi_get_market_context", "hsi_get_news_catalysts", "hsi_get_portfolio_state",
    "hsi_scan_market", "hsi_get_setup",
})
REQUIRED_ENVIRONMENT = (
    "LYZR_API_KEY", "HSI_AGENT_API_KEY", "HSI_PUBLIC_BASE_URL",
    "LYZR_LLM_CREDENTIAL_ID", "LYZR_PROVIDER_ID", "LYZR_MODEL",
)
ROOT = Path(__file__).resolve().parents[1]
THESIS_PATH = ROOT / "config" / "hsi_agent_v1_master_thesis.md"
PROMPTS_PATH = ROOT / "config" / "hsi_agent_v1_acceptance_prompts.json"


class BootstrapError(RuntimeError):
    """Safe operational failure; its message must never contain a secret."""


def configured_environment(environment: dict[str, str] | None = None) -> dict[str, str]:
    values = environment if environment is not None else os.environ
    missing = tuple(name for name in REQUIRED_ENVIRONMENT if not values.get(name, "").strip())
    if missing:
        raise BootstrapError("CONFIGURATION_MISSING:" + ",".join(missing))
    return {name: values[name].strip() for name in REQUIRED_ENVIRONMENT}


def public_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise BootstrapError("PUBLIC_HTTPS_INGRESS_REQUIRED")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise BootstrapError("PUBLIC_HTTPS_INGRESS_REQUIRED")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise BootstrapError("PUBLIC_HTTPS_INGRESS_REQUIRED")
    except ValueError:
        pass
    return f"https://{parsed.netloc}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BootstrapError("LOCAL_CONFIGURATION_INVALID") from error
    if not isinstance(value, dict):
        raise BootstrapError("LOCAL_CONFIGURATION_INVALID")
    return value


def master_thesis() -> str:
    try:
        value = THESIS_PATH.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise BootstrapError("MASTER_THESIS_UNAVAILABLE") from error
    if not value:
        raise BootstrapError("MASTER_THESIS_UNAVAILABLE")
    return value


def acceptance_prompts() -> dict[str, Any]:
    value = _read_json(PROMPTS_PATH)
    prompts = value.get("prompts")
    if value.get("schema_version") != "hsi-agent-v1-acceptance-prompts/v1" or not isinstance(prompts, list):
        raise BootstrapError("ACCEPTANCE_PROMPTS_INVALID")
    return value


def validate_openapi(schema: dict[str, Any], *, origin: str) -> dict[str, Any]:
    paths = schema.get("paths")
    if not isinstance(paths, dict) or set(paths) != {
        "/capabilities", "/diagnostics", "/stock-intelligence", "/market-context",
        "/news-catalysts", "/portfolio-state", "/market-scan", "/setup",
    }:
        raise BootstrapError("HSI_AGENT_OPENAPI_ROUTE_INVENTORY_INVALID")
    operation_ids = set()
    operation_count = 0
    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            raise BootstrapError("HSI_AGENT_OPENAPI_ROUTE_INVENTORY_INVALID")
        for method, operation in operations.items():
            if method not in {"get", "post"} or not isinstance(operation, dict):
                raise BootstrapError("HSI_AGENT_OPENAPI_ROUTE_INVENTORY_INVALID")
            if operation.get("security") != [{"HSIAgentKey": []}]:
                raise BootstrapError("HSI_AGENT_OPENAPI_AUTH_INVALID")
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                raise BootstrapError("HSI_AGENT_OPENAPI_ROUTE_INVENTORY_INVALID")
            operation_ids.add(operation_id)
            operation_count += 1
    if operation_count != len(EXPECTED_OPERATIONS) or operation_ids != EXPECTED_OPERATIONS:
        raise BootstrapError("HSI_AGENT_OPENAPI_OPERATION_INVENTORY_INVALID")
    copy = json.loads(json.dumps(schema, sort_keys=True))
    copy["servers"] = [{"url": origin + "/hsi/v1", "description": "Approved HSI Agent HTTPS ingress"}]
    return copy


def tool_payload(schema: dict[str, Any], *, hsi_agent_key: str) -> dict[str, Any]:
    return {
        "tool_set_name": TOOL_SET_NAME,
        "openapi_schema": schema,
        "default_headers": {"Authorization": "Bearer " + hsi_agent_key},
        "default_query_params": {},
        "default_body_params": {},
        "endpoint_defaults": {},
        "enhance_descriptions": False,
        "openai_api_key": None,
    }


def agent_payload(tool_ids: list[str], configuration: dict[str, str]) -> dict[str, Any]:
    if not tool_ids or any(not isinstance(value, str) or not value for value in tool_ids):
        raise BootstrapError("LYZR_TOOL_CREATION_INVALID")
    return {
        "name": AGENT_NAME,
        "description": "Evidence-driven NSE market intelligence using deterministic HSI tools and structured reasoning.",
        "agent_role": "Evidence-driven NSE market intelligence analyst using deterministic HSI tools and structured reasoning.",
        "agent_goal": "Answer HSI research questions honestly while preserving evidence gaps and non-executable authority boundaries.",
        "agent_context": "HSI uses one canonical Brain. Discovery is not trade authorisation.",
        "agent_output": "Concise decision-useful synthesis that separates fact, data, interpretation and inference.",
        "agent_instructions": master_thesis(),
        "features": [],
        "tools": tool_ids,
        "llm_credential_id": configuration["LYZR_LLM_CREDENTIAL_ID"],
        "provider_id": configuration["LYZR_PROVIDER_ID"],
        "model": configuration["LYZR_MODEL"],
        "top_p": 1.0,
        "temperature": 0.2,
        "response_format": {},
        "store_messages": False,
        "max_iterations": 12,
    }


def request_json(url: str, *, method: str, payload: dict[str, Any] | None, lyzr_key: str | None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if lyzr_key is not None:
        headers["x-api-key"] = lyzr_key
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise BootstrapError(f"LYZR_OR_INGRESS_HTTP_FAILED:{error.code}") from None
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        raise BootstrapError("LYZR_OR_INGRESS_REQUEST_FAILED") from None
    if not isinstance(value, dict):
        raise BootstrapError("LYZR_OR_INGRESS_RESPONSE_INVALID")
    return value


def create(configuration: dict[str, str]) -> tuple[tuple[str, ...], str]:
    origin = public_origin(configuration["HSI_PUBLIC_BASE_URL"])
    schema = request_json(origin + "/hsi/v1/openapi.json", method="GET", payload=None, lyzr_key=None)
    prepared = validate_openapi(schema, origin=origin)
    tool_response = request_json(LYZR_BASE_URL + "/v3/tools/", method="POST",
        payload=tool_payload(prepared, hsi_agent_key=configuration["HSI_AGENT_API_KEY"]),
        lyzr_key=configuration["LYZR_API_KEY"])
    tool_ids = tool_response.get("tool_ids")
    if not isinstance(tool_ids, list):
        raise BootstrapError("LYZR_TOOL_CREATION_INVALID")
    agent_response = request_json(LYZR_BASE_URL + "/v3/agents/", method="POST",
        payload=agent_payload(tool_ids, configuration), lyzr_key=configuration["LYZR_API_KEY"])
    agent_id = agent_response.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise BootstrapError("LYZR_AGENT_CREATION_INVALID")
    return tuple(tool_ids), agent_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit HSI/Lyzr configuration bootstrap; no default cloud mutation.")
    parser.add_argument("--create", action="store_true", help="Create one Lyzr OpenAPI tool set and one agent after all checks pass.")
    args = parser.parse_args()
    try:
        acceptance_prompts()
        configuration = configured_environment()
        public_origin(configuration["HSI_PUBLIC_BASE_URL"])
        if not args.create:
            print("LYZR_CONFIGURATION_READY create_requires_explicit_flag=true")
            return 0
        tool_ids, agent_id = create(configuration)
        print("LYZR_AGENT_CREATED agent_id=" + agent_id + " tool_ids=" + ",".join(tool_ids))
        return 0
    except BootstrapError as error:
        print("LYZR_BOOTSTRAP_BLOCKED code=" + error.args[0])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
