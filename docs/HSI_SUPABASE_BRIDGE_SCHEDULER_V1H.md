# HSI Supabase Bridge Scheduler V1H

The scheduler runs exactly one local bridge cycle every minute while the normal
Windows user session is logged on. It is not a Windows service and does not run
the bridge's continuous worker mode.

Install from an interactive PowerShell session after setting the three required
values as **Windows User** environment variables:

```powershell
Set-Location D:\nse-stock-manager
.\scripts\dev\install-external-intelligence-bridge-task.ps1
```

The task is named `HSI External Intelligence Bridge`. It uses the current
interactive Windows user with limited privilege, `MultipleInstances=IgnoreNew`,
and a five-minute execution limit. It starts once immediately after install,
repeats every minute, and also runs at user logon. Missed runs can start when
the user returns to the session.

The task definition and scripts contain no credential values. The runner reads
only the normal process environment and fails closed if any required value is
missing. It writes only concise operational records to
`reports/runtime/external_intelligence_bridge.log`; the log rotates at 1 MiB.

Useful commands:

```powershell
.\scripts\dev\get-external-intelligence-bridge-task-status.ps1
Start-ScheduledTask -TaskName 'HSI External Intelligence Bridge'
.\scripts\dev\uninstall-external-intelligence-bridge-task.ps1
```
