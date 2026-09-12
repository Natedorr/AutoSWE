# setup.ps1 — autoSWE Interactive Setup Wizard (Windows)
#
# Runs the first-run setup wizard to configure credentials and settings.
# Creates config/repos.json and config/autoswe.env.
#
# Usage:
#   .\setup.ps1          # guided first-run setup
#   .\setup.ps1 --force  # overwrite existing config without prompting
#   .\setup.ps1 -NoWarmup   # skip the pi-mcp cold-start warm-up

$ErrorActionPreference = "Stop"

$AUTOSWE_DIR = if ($env:AUTOSWE_DIR) { $env:AUTOSWE_DIR } else { $PSScriptRoot }
$AUTOSWE_PY  = Join-Path $AUTOSWE_DIR "autoswe.py"
$VENV_PY     = Join-Path $AUTOSWE_DIR ".venv\Scripts\python.exe"

$PYTHON = if (Test-Path $VENV_PY) { $VENV_PY } else { "python" }

$NoWarmup = $false
$SetupArgs = @()
foreach ($a in $args) {
    if ($a -eq "-NoWarmup") { $NoWarmup = $true }
    else { $SetupArgs += $a }
}

# Run the setup wizard, preserving any user-supplied flags (e.g. -Force).
& $PYTHON $AUTOSWE_PY setup @SetupArgs

# pi Phase 4 cold-start warm-up (docs/autoswe/PLAN-pi-mcp.md): populate each pi
# profile's mcp-cache.json so the first real run uses the direct
# mcp__autoswe_comment_* tools. Skips cleanly when no pi profile with an
# agent_dir is configured, so non-pi setups are unaffected. Skipped with
# -NoWarmup.
if (-not $NoWarmup) {
    & $PYTHON $AUTOSWE_PY warmup
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pi-mcp warm-up did not complete (first pi run will use proxy tool shapes)"
    }
}
