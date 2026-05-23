# cleanup.ps1 - autoSWE Full Reset (Windows)
#
# Kills stuck poller / claude / node processes, releases the mutex (by killing
# the holder), and clears running/ PID artifacts so the next Task Scheduler
# firing comes up clean.
#
# WARNING: kills ALL `claude` and `node` processes - including any interactive
# Claude Code session in another terminal.
#
# Idempotent - safe to run on a clean system (exits 0, all-zero summary).
#
# Manual: .\cleanup.ps1

$ErrorActionPreference = "SilentlyContinue"

$SCRIPT_DIR = Split-Path $MyInvocation.MyDefinition.Path -Parent
$AUTOSWE_DIR = if ($env:AUTOSWE_DIR) { $env:AUTOSWE_DIR } else { $SCRIPT_DIR }
$RUNNING_DIR = Join-Path $AUTOSWE_DIR "running"

function Write-Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ' -AsUtc)] $Message"
    Write-Output $line
}

# -- Banner / Warning --------------------------------------------------------
Write-Log "============================================================"
Write-Log "  autoSWE FULL RESET - cleaning up stuck poller state"
Write-Log "============================================================"
Write-Log "WARNING: this script will kill ALL 'claude' and 'node' processes,"
Write-Log "         including any interactive Claude Code session."

# -- Helpers --------------------------------------------------------------------
function Get-ChildPids {
    param([int]$ParentId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" 2>$null
    if ($children) {
        foreach ($c in $children) {
            Get-ChildPids -ParentId $c.ProcessId
        }
        $children
    }
}

# -- Counters ----------------------------------------------------------------
$pollerKilled = 0
$claudeNodeKilled = 0
$mutexReleased = "no"
$pidFiles = 0
$doneFiles = 0
$resultFiles = 0

# -- Step 1: Kill all claude and node processes (deepest leaves first) ---------
foreach ($name in @('claude', 'node')) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            Write-Log "KILL $name PID=$($p.Id)"
            Stop-Process -Id $p.Id -Force 2>$null
            $claudeNodeKilled++
        }
    }
    else {
        Write-Log "No $name processes found."
    }
}

# -- Step 2: Kill poller process tree (bottom-up: children first, parent last) -
# poller.ps1 holds the named mutex. Killing it releases the lock and terminates
# any zombie python children. We kill deepest descendants first.

$pollerPs1 = Get-CimInstance Win32_Process `
    -Filter "Name='pwsh.exe' OR Name='powershell.exe'" 2>$null |
    Where-Object { $_.CommandLine -like '*poller.ps1*' }

$pythonPoller = Get-CimInstance Win32_Process `
    -Filter "Name='python.exe' OR Name='python3.exe'" 2>$null |
    Where-Object { $_.CommandLine -like '*autoswe.py*poller*' }

$pollerToKill = @()
if ($pollerPs1) {
    foreach ($parent in $pollerPs1) {
        Write-Log "Found poller.ps1 PID=$($parent.ProcessId)"
        $pollerToKill += $parent
        $children = Get-ChildPids -ParentId $parent.ProcessId
        if ($children) {
            foreach ($c in $children) {
                Write-Log "Found child of poller.ps1 PID=$($c.ProcessId)"
                $pollerToKill += $c
            }
        }
    }
}

# Also add any python autoswe poller processes not already in the list
if ($pythonPoller) {
    foreach ($p in $pythonPoller) {
        if ($pollerToKill.ProcessId -notcontains $p.ProcessId) {
            $pollerToKill += $p
        }
    }
}

if ($pollerToKill) {
    # Kill children first (reverse order = parents last)
    [array]::Reverse($pollerToKill)
    foreach ($proc in $pollerToKill) {
        Write-Log "KILL poller-tree PID=$($proc.ProcessId)"
        Stop-Process -Id $proc.ProcessId -Force 2>$null
        $pollerKilled++
    }
    Write-Log "Killed poller process tree ($pollerKilled processes)"
}
else {
    Write-Log "No poller process tree found."
}

# -- Step 3: Mutex release ---------------------------------------------------
# The Global\AutoSWEPoller named mutex is process-bound - it dies with the
# holder (killed in Step 1). No explicit file action needed.
Write-Log "Named mutex Global\AutoSWEPoller auto-released (holder killed in Step 2)."
$mutexReleased = "yes"

# -- Step 4: Clear running/ --------------------------------------------------
if (Test-Path $RUNNING_DIR) {
    Get-ChildItem -Path $RUNNING_DIR -Filter '*.pid' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force; $script:pidFiles++ }
    Get-ChildItem -Path $RUNNING_DIR -Filter '*.done' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force; $script:doneFiles++ }
    Get-ChildItem -Path $RUNNING_DIR -Filter '*.result.json' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force; $script:resultFiles++ }
}
else {
    Write-Log "Running directory $RUNNING_DIR does not exist."
}

# -- Summary -----------------------------------------------------------------
Write-Log "------------------------------------------------------------"
Write-Log "  SUMMARY"
Write-Log "------------------------------------------------------------"
Write-Log "  Poller processes killed : $pollerKilled"
Write-Log "  claude/node procs killed : $claudeNodeKilled"
Write-Log "  Mutex auto-released     : $mutexReleased"
Write-Log "  PID files deleted       : $pidFiles"
Write-Log "  DONE files deleted      : $doneFiles"
Write-Log "  Result files deleted    : $resultFiles"
Write-Log "============================================================"
Write-Log "  Done - next poller run should start clean."
Write-Log "============================================================"

exit 0
