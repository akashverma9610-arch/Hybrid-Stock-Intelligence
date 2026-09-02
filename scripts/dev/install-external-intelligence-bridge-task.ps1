[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'HSI External Intelligence Bridge'
$requiredVariables = @(
    'HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL',
    'HSI_EXTERNAL_INTELLIGENCE_SUPABASE_SECRET_KEY',
    'HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN'
)

foreach ($name in $requiredVariables) {
    $value = [Environment]::GetEnvironmentVariable($name, [EnvironmentVariableTarget]::User)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Required Windows User environment variable is not configured: $name"
    }
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$runner = Join-Path $repositoryRoot 'scripts\dev\run-external-intelligence-bridge-once.cmd'
$python = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'Bridge runner script is not available.' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'HSI bridge Python runtime is not available.' }

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument ('/d /c ""{0}""' -f $runner) -WorkingDirectory $repositoryRoot
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 0
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($repeat, $atLogon) -Settings $settings -Principal $principal -Description 'Runs one bounded local HSI Supabase inbox bridge cycle; no secrets are stored in the task.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "task_name=$taskName installed=true trigger=one_minute multiple_instances=IgnoreNew logon_type=Interactive"
