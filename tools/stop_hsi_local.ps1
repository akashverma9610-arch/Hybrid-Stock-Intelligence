[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'HsiLocalRuntime.psm1') -Force
Stop-HsiOwnedRuntime
