[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'HSI Local Backend'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Output "task_name=$taskName exists=false"
    exit 0
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Output "task_name=$taskName removed=true"
