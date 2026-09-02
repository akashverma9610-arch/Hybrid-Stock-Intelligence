from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def _tool(name: str) -> str:
    return (ROOT / "tools" / name).read_text(encoding="utf-8")


def test_local_runtime_start_profile_is_explicit_loopback_and_persistent() -> None:
    value = _tool("HsiLocalRuntime.psm1") + _tool("start_hsi_local.ps1")
    assert "DATABASE_BACKEND = 'sqlite'" in value
    assert "DATABASE_URL = 'sqlite:///data/nse_stock_manager.db'" in value
    assert "CORS_ORIGINS = 'http://localhost:3001,http://127.0.0.1:3001'" in value
    assert "--host', '127.0.0.1'" in value and "--port', '8000'" in value
    assert "npm.cmd run dev -- --host 127.0.0.1 --port 3001" in value
    assert "HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE" in value


def test_persistent_database_integrity_uses_python_stdin_not_windows_fragile_dash_c() -> None:
    module = _tool("HsiLocalRuntime.psm1")
    assert "$code | & $python - $database" in module
    assert 'connection.execute("PRAGMA integrity_check")' in module
    assert "& $python -c" not in module


def test_local_runtime_port_and_process_controls_are_owned_and_non_destructive() -> None:
    module = _tool("HsiLocalRuntime.psm1")
    assert "Get-NetTCPConnection -State Listen" in module
    assert "HSI_LOCAL_RUNTIME_PORT_8000_IN_USE" in module
    assert "HSI_LOCAL_RUNTIME_PORT_3001_IN_USE" in module
    assert "Test-HsiProcessIdentity" in module
    assert "Stop-Process -Id" in module
    assert "Stop-Process -Id ([int]$item.Pid) -Force" not in module
    assert "return if" not in module
    assert "receiptMatchedListener" in module


def test_local_runtime_scripts_keep_secrets_and_public_bindings_out_of_source() -> None:
    value = "\n".join(_tool(name).lower() for name in (
        "HsiLocalRuntime.psm1", "start_hsi_local.ps1", "status_hsi_local.ps1", "stop_hsi_local.ps1", "restart_hsi_local.ps1", "dhan_live_canary.ps1",
    ))
    assert all(item not in value for item in ("api_secret", "access_token=", "ingest_token", "0.0.0.0", "firewall"))
    assert "dhan_live_market_enabled" in value
    assert "bse-financial" not in value


def test_status_and_canary_are_read_only_and_expose_only_safe_runtime_fields() -> None:
    status = _tool("status_hsi_local.ps1")
    canary = _tool("dhan_live_canary.ps1")
    assert "/api/v1/runtime/local-readiness" in status
    assert "/api/v1/market-wide-watch" in status
    assert "/api/v1/live-market/health" in status
    assert "sample_quote" in canary and "mapped_packets" in canary
    assert "dhan-live-feed" not in canary
    assert "$health = $overview.health" in canary
    assert "Timeout = 20" in status
    assert "watch_candidate_count" in status
