[CmdletBinding()]
param(
    [ValidateSet('Research', 'Live')]
    [string]$Mode = 'Research'
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'stop_hsi_local.ps1')
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot 'start_hsi_local.ps1') -Mode $Mode
