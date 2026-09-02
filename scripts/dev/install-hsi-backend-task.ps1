[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'HSI Local Backend'
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$launcher = Join-Path $repositoryRoot 'scripts\dev\start-local-backend.cmd'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw 'Existing local backend launcher is not available.'
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument ('/d /c ""{0}""' -f $launcher) -WorkingDirectory $repositoryRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Starts the existing loopback-only HSI FastAPI launcher at interactive user logon.' -Force | Out-Null
Write-Output "task_name=$taskName installed=true trigger=AtLogOn multiple_instances=IgnoreNew restart_count=3 restart_interval_seconds=60 logon_type=Interactive"
