Set-StrictMode -Version Latest

$script:HsiRuntimeReceiptName = 'hsi_local_runtime.json'
$script:HsiBackendPort = 8000
$script:HsiFrontendPort = 3001

function Get-HsiRepositoryRoot {
    (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}

function Get-HsiRuntimeDirectory {
    $directory = Join-Path (Get-HsiRepositoryRoot) 'reports\runtime'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    return $directory
}

function Get-HsiRuntimeReceiptPath { Join-Path (Get-HsiRuntimeDirectory) $script:HsiRuntimeReceiptName }

function Get-HsiPython {
    $candidate = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "HSI_LOCAL_RUNTIME_PYTHON_NOT_FOUND path=$candidate"
    }
    return $candidate
}

function Get-HsiListener([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) { return $listener }
    # Some restricted Windows sessions do not return other processes through
    # Get-NetTCPConnection. netstat remains read-only and prevents unsafe reuse.
    $line = netstat -ano -p tcp | Where-Object { $_ -match (":$Port\s+.*LISTENING\s+(\d+)\s*$") } | Select-Object -First 1
    if ($line -and $line -match 'LISTENING\s+(\d+)\s*$') {
        return [pscustomobject]@{ OwningProcess = [int]$Matches[1] }
    }
    return $null
}

function Get-HsiProcessCommandLine([int]$ProcessId) {
    $item = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($item) { return [string]$item.CommandLine }
    return ''
}

function Test-HsiProcessIdentity([int]$ProcessId, [ValidateSet('backend', 'frontend')] [string]$Kind) {
    $commandLine = Get-HsiProcessCommandLine $ProcessId
    if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
    if ($Kind -eq 'backend') { return $commandLine -match 'uvicorn\s+app\.api\.main:app' }
    return $commandLine -match 'vite'
}

function Get-HsiRuntimeReceipt {
    $path = Get-HsiRuntimeReceiptPath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json } catch { return $null }
}

function Set-HsiRuntimeReceipt([hashtable]$Receipt) {
    $Receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Get-HsiRuntimeReceiptPath) -Encoding utf8
}

function Set-HsiLocalRuntimeEnvironment([ValidateSet('Research', 'Live')] [string]$Mode) {
    $env:APP_ENV = 'local'
    $env:DATABASE_BACKEND = 'sqlite'
    $env:DATABASE_URL = 'sqlite:///data/nse_stock_manager.db'
    $env:CORS_ORIGINS = 'http://localhost:3001,http://127.0.0.1:3001'
    $env:HSI_LOCAL_OPERATOR_RUNTIME = 'true'
    $env:DHAN_LIVE_MARKET_ENABLED = if ($Mode -eq 'Live') { 'true' } else { 'false' }
}

function Assert-HsiPersistentDatabase {
    $root = Get-HsiRepositoryRoot
    $database = Join-Path $root 'data\nse_stock_manager.db'
    if (-not (Test-Path -LiteralPath $database -PathType Leaf)) {
        throw 'HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE'
    }
    $python = Get-HsiPython
    # Windows PowerShell 5.x does not preserve nested quotes passed to Python
    # with -c reliably. Feed the complete program on stdin instead.
    $code = @'
import sqlite3
import sys

database_path = sys.argv[1]
connection = sqlite3.connect(database_path)
try:
    print(connection.execute("PRAGMA integrity_check").fetchone()[0])
finally:
    connection.close()
'@
    $integrity = $code | & $python - $database
    if ($LASTEXITCODE -ne 0 -or @($integrity).Count -ne 1 -or $integrity -ne 'ok') {
        throw 'HSI_LOCAL_RUNTIME_DATABASE_INTEGRITY_FAILED'
    }
    return $database
}

function Wait-HsiEndpoint([string]$Url, [int]$Seconds = 20) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $response }
        } catch { }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Start-HsiLocalBackend {
    $root = Get-HsiRepositoryRoot
    $listener = Get-HsiListener $script:HsiBackendPort
    if ($listener) { throw "HSI_LOCAL_RUNTIME_PORT_8000_IN_USE pid=$($listener.OwningProcess)" }
    $python = Get-HsiPython
    $logs = Get-HsiRuntimeDirectory
    return Start-Process -FilePath $python -WorkingDirectory $root -ArgumentList @('-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', '8000') -RedirectStandardOutput (Join-Path $logs 'hsi_backend.stdout.log') -RedirectStandardError (Join-Path $logs 'hsi_backend.stderr.log') -PassThru
}

function Start-HsiLocalFrontend {
    $root = Get-HsiRepositoryRoot
    $listener = Get-HsiListener $script:HsiFrontendPort
    if ($listener) { throw "HSI_LOCAL_RUNTIME_PORT_3001_IN_USE pid=$($listener.OwningProcess)" }
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw 'HSI_LOCAL_RUNTIME_NPM_NOT_FOUND' }
    $logs = Get-HsiRuntimeDirectory
    return Start-Process -FilePath $env:ComSpec -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList @('/d', '/c', 'npm.cmd run dev -- --host 127.0.0.1 --port 3001') -RedirectStandardOutput (Join-Path $logs 'hsi_frontend.stdout.log') -RedirectStandardError (Join-Path $logs 'hsi_frontend.stderr.log') -PassThru
}

function Stop-HsiOwnedRuntime {
    $receipt = Get-HsiRuntimeReceipt
    if (-not $receipt) { Write-Output 'HSI_LOCAL_RUNTIME_NO_OWNED_RECEIPT'; return }
    $startedAt = [datetime]::Parse($receipt.started_at).ToUniversalTime()
    foreach ($item in @(@{ Pid = $receipt.backend_listener_pid; Kind = 'backend'; Port = 8000 }, @{ Pid = $receipt.frontend_listener_pid; Kind = 'frontend'; Port = 3001 })) {
        if ($null -eq $item.Pid) { continue }
        $process = Get-Process -Id ([int]$item.Pid) -ErrorAction SilentlyContinue
        $listener = Get-HsiListener $item.Port
        $receiptMatchedListener = $process -and $listener -and ([int]$listener.OwningProcess -eq [int]$item.Pid) -and ($process.StartTime.ToUniversalTime() -ge $startedAt.AddMinutes(-1))
        if ((Test-HsiProcessIdentity ([int]$item.Pid) $item.Kind) -or $receiptMatchedListener) {
            Stop-Process -Id ([int]$item.Pid) -ErrorAction SilentlyContinue
        } else {
            Write-Output "HSI_LOCAL_RUNTIME_OWNERSHIP_UNVERIFIED pid=$($item.Pid) port=$($item.Port)"
        }
    }
    Write-Output 'HSI_LOCAL_RUNTIME_OWNED_PROCESSES_STOP_REQUESTED'
}

Export-ModuleMember -Function *-Hsi*
