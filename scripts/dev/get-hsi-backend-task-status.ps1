[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'HSI Local Backend'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    [PSCustomObject]@{ TaskName = $taskName; Exists = $false; Enabled = $false; State = 'ABSENT'; LastRunTime = $null; LastTaskResult = $null; NextRunTime = $null }
    exit 1
}

$info = Get-ScheduledTaskInfo -TaskName $taskName
[PSCustomObject]@{
    TaskName = $task.TaskName
    Exists = $true
    Enabled = [bool]$task.Settings.Enabled
    State = $task.State.ToString()
    LastRunTime = $info.LastRunTime
    LastTaskResult = $info.LastTaskResult
    NextRunTime = $info.NextRunTime
}
