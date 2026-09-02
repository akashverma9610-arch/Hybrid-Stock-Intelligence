[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
try {
    $overview = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/live-market' -TimeoutSec 5
    $health = $overview.health
    $sample = @($overview.targets | Select-Object -First 1)
    $result = [ordered]@{
        state = $health.state
        enabled = $health.enabled
        health = $health.health
        requested_targets = $health.requested_targets
        subscribed_targets = $health.subscribed_targets
        mapped_packets = $health.mapped_packets
        reconnect_count = $health.reconnect_count
        sample_quote = $sample
    }
    $result | ConvertTo-Json -Depth 4
} catch {
    Write-Output "DHAN_LIVE_CANARY_UNAVAILABLE exception=$($_.Exception.GetType().Name)"
}
