# update.ps1 — Pull latest autoSWE code from origin/master (Windows)
#
# Safely updates the autoSWE installation without disrupting running polls.
# Usage:
#   .\update.ps1          # pull latest code
#   .\update.ps1 --force  # discard local changes if there are any
#
# Run this before restarting Task Scheduler after a deployment.

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$FORCE      = $args -contains "--force"

$AUTOSWE_DIR = if ($env:AUTOSWE_DIR) { $env:AUTOSWE_DIR } else { $SCRIPT_DIR }
$LOGFILE     = Join-Path $AUTOSWE_DIR "logs\update.log"

$logDir = Split-Path $LOGFILE -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log {
    param([string]$Message)
    $line = "[$([datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))] $Message"
    Write-Output $line
    Add-Content -Path $LOGFILE -Value $line
}

Push-Location $AUTOSWE_DIR
try {
    # Check if we have a git remote
    $remotes = git remote -v 2>&1
    if (-not ($remotes -match "origin")) {
        Write-Log "[ERROR] No git remote 'origin' configured. Is this a clone of the repo?"
        exit 1
    }

    # Check for uncommitted changes
    $diffOutput = git status --porcelain 2>&1
    if ($diffOutput) {
        Write-Log "[WARN] Uncommitted changes detected."
        if ($FORCE) {
            Write-Log "[INFO] --force: discarding local changes..."
            git reset --hard HEAD 2>&1 | Out-Null
        } else {
            Write-Log "[ABORT] Commit or stash your changes first, or use --force to discard."
            exit 1
        }
    }

    Write-Log "[UPDATE] Fetching latest from origin/master..."
    try {
        git fetch origin master 2>&1 | Out-Null
    } catch {
        Write-Log "[ERROR] Fetch failed: $_"
        exit 1
    }

    $local  = (git rev-parse HEAD).Trim()
    $remote = (git rev-parse origin/master).Trim()

    if ($local -eq $remote) {
        Write-Log "[INFO] Already up to date (commit $local)"
        exit 0
    }

    $commitMsg = git log --oneline origin/master -1
    Write-Log "[UPDATE] Updating to $commitMsg"

    try {
        git reset --hard origin/master 2>&1 | Out-Null
    } catch {
        Write-Log "[ERROR] Reset failed: $_"
        exit 1
    }

    # If venv exists, reinstall deps
    $venvPy = Join-Path $AUTOSWE_DIR ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        Write-Log "[UPDATE] Reinstalling pip dependencies..."
        & $venvPy -m pip install -q -r requirements.txt 2>&1 | Out-Null
        Write-Log "[INFO] Dependencies updated."
    } elseif (Test-Path (Join-Path $AUTOSWE_DIR "requirements.txt")) {
        Write-Log "[INFO] No venv detected. Run: python -m venv .venv, then .\.venv\Scripts\Activate.ps1, then pip install -r requirements.txt"
    }

    Write-Log "[DONE] Updated successfully."
} finally {
    Pop-Location
}
