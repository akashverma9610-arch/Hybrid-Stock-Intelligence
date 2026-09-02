[CmdletBinding()]
param(
    [ValidateSet('Research', 'Live')]
    [string]$Mode = 'Research'
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'HsiLocalRuntime.psm1') -Force
Set-HsiLocalRuntimeEnvironment $Mode

# Check both ports before creating either process; startup never kills or adopts
# an existing listener and cannot leave a half-started runtime on collision.
foreach ($port in @(8000, 3001)) {
    $listener = Get-HsiListener $port
    if ($listener) { throw "HSI_LOCAL_RUNTIME_PORT_${port}_IN_USE pid=$($listener.OwningProcess)" }
}
$database = Assert-HsiPersistentDatabase

$backend = Start-HsiLocalBackend
$backendHealth = Wait-HsiEndpoint 'http://127.0.0.1:8000/health'
if (-not $backendHealth) { throw 'HSI_LOCAL_RUNTIME_BACKEND_HEALTH_FAILED' }
$frontend = Start-HsiLocalFrontend
$frontendHealth = Wait-HsiEndpoint 'http://127.0.0.1:3001/'
if (-not $frontendHealth) { throw 'HSI_LOCAL_RUNTIME_FRONTEND_HEALTH_FAILED' }

$backendListener = Get-HsiListener 8000
$frontendListener = Get-HsiListener 3001
$receipt = @{
    receipt_version = 'HSI_LOCAL_RUNTIME_V1'
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode.ToUpperInvariant()
    database = 'sqlite:///data/nse_stock_manager.db'
    backend_url = 'http://127.0.0.1:8000'
    frontend_url = 'http://127.0.0.1:3001'
    backend_pid = $backend.Id
    frontend_pid = $frontend.Id
    backend_listener_pid = if ($backendListener) { $backendListener.OwningProcess } else { $null }
    frontend_listener_pid = if ($frontendListener) { $frontendListener.OwningProcess } else { $null }
}
Set-HsiRuntimeReceipt $receipt
Write-Output "HSI_LOCAL_RUNTIME_STARTED mode=$($receipt.mode) database=$database backend=$($receipt.backend_url) frontend=$($receipt.frontend_url)"
Write-Output 'HSI_LOCAL_READY'
