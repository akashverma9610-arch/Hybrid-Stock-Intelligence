from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def _script(name: str) -> str:
    return (ROOT / "scripts" / "dev" / name).read_text(encoding="utf-8")


def test_backend_task_installer_is_fixed_to_logon_existing_launcher_and_ignore_new() -> None:
    value = _script("install-hsi-backend-task.ps1")
    assert "$taskName = 'HSI Local Backend'" in value
    assert "scripts\\dev\\start-local-backend.cmd" in value
    assert "New-ScheduledTaskTrigger -AtLogOn -User $currentUser" in value
    assert "-MultipleInstances IgnoreNew" in value
    assert "-LogonType Interactive -RunLevel Limited" in value


def test_backend_task_restart_is_bounded_and_no_secret_or_public_network_is_embedded() -> None:
    value = _script("install-hsi-backend-task.ps1").lower()
    assert "-restartcount 3" in value and "new-timespan -minutes 1" in value
    assert not any(token in value for token in ("supabase_secret", "ingest_token", "upstox", "0.0.0.0", "firewall", "-password", "highest"))
    assert "start-local-backend.cmd" in value


def test_backend_task_uninstall_and_status_are_limited_to_the_exact_task() -> None:
    uninstall = _script("uninstall-hsi-backend-task.ps1")
    status = _script("get-hsi-backend-task-status.ps1")
    assert "Unregister-ScheduledTask -TaskName $taskName -Confirm:$false" in uninstall
    assert "Get-ScheduledTask -TaskName $taskName" in uninstall
    assert all(item in status for item in ("Enabled", "LastRunTime", "LastTaskResult", "NextRunTime"))
