# HSI V1 local runtime and release readiness

The supported local operator profile is persistent and loopback-only:

```text
DATABASE_BACKEND=sqlite
DATABASE_URL=sqlite:///data/nse_stock_manager.db
backend=http://127.0.0.1:8000
frontend=http://127.0.0.1:3001
CORS_ORIGINS=http://localhost:3001,http://127.0.0.1:3001
```

Start research-only mode with:

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\start_hsi_local.ps1 -Mode Research
```

Use `-Mode Live` only to enable the already-governed Dhan in-memory observer. It does not start acquisition, BSE collection, diagnostics, broker actions, or orders. The start command rejects a missing, transient, or non-approved database with `HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE`; normal test factories retain isolated in-memory SQLite behavior.

`tools\status_hsi_local.ps1` reports only safe receipt/process, loopback health, database integrity/counts, Watch state, and Dhan safe health. `tools\stop_hsi_local.ps1` stops only processes whose command lines match the runtime receipt. `tools\restart_hsi_local.ps1` composes those two commands. Existing listeners are reported and never killed by startup.

The Dev Console reads `/api/v1/runtime/local-readiness` and `/api/v1/live-market`; both are read-only. A degraded Dhan WebSocket state is displayed as a governed observation issue, not as permission to alter canonical evidence or decisions.

## Release and backup boundary

`data/`, `reports/`, `.env*`, SQLite journals, logs, and frontend build output are ignored and must not be packaged as source release artifacts. Before an operator upgrade, stop the owned runtime and make a byte-for-byte copy of `data/nse_stock_manager.db` outside the repository (for example, a dated protected backup directory). Retain the original until the replacement runtime has passed `/health`, `/api/v1/runtime/local-readiness`, and the operator's required smoke checks. Backups and secrets must never be committed or pasted into tickets.

The local runtime has no public binding, tunnel, firewall rule, broker route, or credential export. The existing scheduled task still uses `scripts\dev\start-local-backend.cmd`, which now applies the same persistent loopback database guard in research-only mode.
