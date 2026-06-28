# poller.ps1 — autoSWE GitHub Poller (Windows)
#
# Task Scheduler setup (run once as admin):
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#                -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$PWD\poller.ps1`""
#   $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 10) -Once `
#                -At (Get-Date)
#   $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3)
#   Register-ScheduledTask -TaskName "AutoSWEPoller" -Action $action -Trigger $trigger `
#                          -Settings $settings -RunLevel Highest

$ErrorActionPreference = "Stop"

$AUTOSWE_DIR = if ($env:AUTOSWE_DIR) { $env:AUTOSWE_DIR } else { $PSScriptRoot }
$AUTOSWE_PY  = Join-Path $AUTOSWE_DIR "autoswe.py"
$VENV_PY     = Join-Path $AUTOSWE_DIR ".venv\Scripts\python.exe"
$LOGFILE     = Join-Path $AUTOSWE_DIR "logs\poller.log"

$PYTHON = if (Test-Path $VENV_PY) { $VENV_PY } else { "python" }

$logDir = Split-Path $LOGFILE -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log {
    param([string]$Message)
    $line = "[$([datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))] $Message"
    Write-Output $line
    Add-Content -Path $LOGFILE -Value $line
}

$mutexName = "Global\AutoSWEPoller"
$mutex = New-Object System.Threading.Mutex($false, $mutexName)

$acquired = $false
try {
    $acquired = $mutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    $acquired = $true
}

if (-not $acquired) {
    Write-Log "[SKIP] poller already running (mutex held)"
    exit 0
}

try {
    Write-Log "[START] poller run (acquired lock)"

    & $PYTHON $AUTOSWE_PY poller --drain 2>&1 | ForEach-Object {
        $_ | Add-Content -Path $LOGFILE
        Write-Output $_
    }
    Write-Log "[DONE] poller run complete"
} catch {
    Write-Log "[ERROR] poller aborted: $_"
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
