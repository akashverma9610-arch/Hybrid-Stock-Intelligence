[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'HsiLocalRuntime.psm1') -Force
$receipt = Get-HsiRuntimeReceipt
$backend = Get-HsiListener 8000
$frontend = Get-HsiListener 3001
$result = [ordered]@{
    receipt = $receipt
    backend_listener_pid = if ($backend) { $backend.OwningProcess } else { $null }
    frontend_listener_pid = if ($frontend) { $frontend.OwningProcess } else { $null }
    api_health = $null
    local_readiness = $null
    market_wide_watch = $null
    dhan_live = $null
    frontend_reachable = $false
}
foreach ($item in @(
    @{ Key = 'api_health'; Url = 'http://127.0.0.1:8000/health'; Timeout = 5 },
    @{ Key = 'local_readiness'; Url = 'http://127.0.0.1:8000/api/v1/runtime/local-readiness'; Timeout = 20 },
    @{ Key = 'market_wide_watch'; Url = 'http://127.0.0.1:8000/api/v1/market-wide-watch'; Timeout = 10 },
    @{ Key = 'dhan_live'; Url = 'http://127.0.0.1:8000/api/v1/live-market/health'; Timeout = 5 }
)) {
    try {
        $value = Invoke-RestMethod -Uri $item.Url -TimeoutSec $item.Timeout
        $result[$item.Key] = switch ($item.Key) {
            'market_wide_watch' {
                @{
                    state = 'AVAILABLE'; run_id = $value.run_id; watch_as_of = $value.watch_as_of
                    universe_count = $value.universe_count; evidence_ready_count = $value.evidence_ready_count
                    watch_candidate_count = $value.watch_candidate_count; top3_eligible_count = $value.top3_eligible_count
                }
            }
            default { $value }
        }
    } catch { $result[$item.Key] = @{ state = 'UNAVAILABLE'; safe_reason = $_.Exception.GetType().Name } }
}
try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:3001/' -UseBasicParsing -TimeoutSec 5; $result.frontend_reachable = $true } catch { }
$result | ConvertTo-Json -Depth 6
