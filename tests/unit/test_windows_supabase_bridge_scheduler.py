from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def _script(name: str) -> str:
    return (ROOT / "scripts" / "dev" / name).read_text(encoding="utf-8")


def test_runner_is_bounded_uses_the_exact_runtime_and_preserves_bridge_exit_code() -> None:
    value = _script("run-external-intelligence-bridge-once.cmd")
    assert 'cd /d "%~dp0\\..\\.."' in value
    assert r'%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' in value
    assert 'if not exist "%PYTHON_EXE%"' in value
    assert '"%PYTHON_EXE%" -m app.runtime bridge-external-intelligence-inbox --once' in value
    assert 'exit /b %BRIDGE_EXIT_CODE%' in value


def test_runner_checks_environment_presence_without_expanding_or_logging_secret_values() -> None:
    value = _script("run-external-intelligence-bridge-once.cmd")
    for name in ("HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL", "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_SECRET_KEY", "HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN"):
        assert f"call :require_environment {name}" in value
    assert "if not defined %~1" in value
    assert "external_intelligence_bridge.log" in value and "%%~zI GEQ 1048576" in value
    assert "set HSI_EXTERNAL_INTELLIGENCE" not in value


def test_installer_is_fixed_to_the_task_one_minute_interactive_principal_and_ignore_new() -> None:
    value = _script("install-external-intelligence-bridge-task.ps1")
    assert "$taskName = 'HSI External Intelligence Bridge'" in value
    assert "[EnvironmentVariableTarget]::User" in value
    assert "New-TimeSpan -Minutes 1" in value
    assert "-MultipleInstances IgnoreNew" in value
    assert "-LogonType Interactive -RunLevel Limited" in value
    assert "-Password" not in value and "-RunLevel Highest" not in value
    assert "Start-ScheduledTask -TaskName $taskName" in value


def test_task_scripts_do_not_embed_secrets_or_add_non_bridge_authority() -> None:
    values = "\n".join(_script(name) for name in (
        "run-external-intelligence-bridge-once.cmd",
        "install-external-intelligence-bridge-task.ps1",
        "uninstall-external-intelligence-bridge-task.ps1",
        "get-external-intelligence-bridge-task-status.ps1",
    )).lower()
    assert "sb_secret_" not in values and "authorization: bearer" not in values
    assert not any(word in values for word in ("broker", "portfolio", "cash mutation", "order execution"))


def test_uninstall_and_status_are_limited_to_the_exact_task() -> None:
    uninstall = _script("uninstall-external-intelligence-bridge-task.ps1")
    status = _script("get-external-intelligence-bridge-task-status.ps1")
    assert "Unregister-ScheduledTask -TaskName $taskName -Confirm:$false" in uninstall
    assert "Get-ScheduledTask -TaskName $taskName" in uninstall
    assert "Get-ScheduledTaskInfo -TaskName $taskName" in status
    assert all(field in status for field in ("LastRunTime", "LastTaskResult", "NextRunTime"))
