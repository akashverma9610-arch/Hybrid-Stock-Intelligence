# HSI Windows Backend Auto-Start V1I

The `HSI Local Backend` Windows Scheduled Task starts only the existing
`scripts/dev/start-local-backend.cmd` launcher at interactive user logon. The
launcher retains the existing loopback binding at `127.0.0.1:8000`.

Install or update the task:

```powershell
Set-Location D:\nse-stock-manager
.\scripts\dev\install-hsi-backend-task.ps1
```

The task uses the current interactive user, limited privilege, and no stored
Windows password. It has `MultipleInstances=IgnoreNew`. If the backend exits,
Task Scheduler retries at most three times, one minute apart. It does not create
a service, firewall rule, public listener, or a second backend launcher.

Task Scheduler status is the safe operational record for this long-running
process; no application-output log redirection is added, avoiding accidental
request or environment logging.

Useful commands:

```powershell
Start-ScheduledTask -TaskName 'HSI Local Backend'
.\scripts\dev\get-hsi-backend-task-status.ps1
.\scripts\dev\uninstall-hsi-backend-task.ps1
```
