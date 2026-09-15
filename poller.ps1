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

# --- UTF-8 without BOM across console, Python, and log output ---------------
# The PS 5.1 default log cmdlet writes UTF-16 LE (BOM on first write) and the
# console defaults to the OEM code page (CP1252-class on en-US Windows), so
# non-ASCII poller output could corrupt the log or abort the child.  Use
# UTF8Encoding($false) — UTF-8, no BOM — for the log, and pin the child
# Python to UTF-8.  Console-encoding assignment can fail under a Task
# Scheduler redirect, so it is best-effort: the Python env vars below are
# the real workhorse.
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
try {
    [Console]::InputEncoding  = $Utf8NoBom
    [Console]::OutputEncoding = $Utf8NoBom
    $OutputEncoding = $Utf8NoBom
} catch {
    Write-Warning "poller.ps1: could not set console to UTF-8 (best effort); continuing"
}
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8      = "1"

function Write-Log {
    param([string]$Message)
    $line = "[$([datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))] $Message`n"
    Write-Output $line.TrimEnd()
    # AppendAllText with an explicit no-BOM UTF-8 encoding (PS 5.1
    # compatible); the legacy cmdlet would write UTF-16 LE and drop or
    # mangle non-ASCII.
    [System.IO.File]::AppendAllText($LOGFILE, $line, $Utf8NoBom)
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

$pollerExitCode = 0
try {
    Write-Log "[START] poller run (acquired lock)"

    # Run the poller with redirected stderr captured as data, not as a
    # terminating error: the default $ErrorActionPreference="Stop" would
    # abort the script on native stderr redirected through 2>&1.  Temporarily
    # lower it for the call and restore it in the finally.
    $priorErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PYTHON $AUTOSWE_PY poller --drain 2>&1 | ForEach-Object {
            [System.IO.File]::AppendAllText($LOGFILE, "$_`n", $Utf8NoBom)
            Write-Output $_
        }
        # Capture the native exit code BEFORE any further command resets it.
        $pollerExitCode = [int]$LASTEXITCODE
    } finally {
        $ErrorActionPreference = $priorErrorActionPreference
    }
    Write-Log "[DONE] poller run complete (exit=$pollerExitCode)"
} catch {
    Write-Log "[ERROR] poller aborted: $_"
    $pollerExitCode = 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

# Propagate the poller's exit code so Task Scheduler / monitoring sees real
# failures (previously the script always exited 0 unless a PowerShell-level
# catch fired).
exit $pollerExitCode
