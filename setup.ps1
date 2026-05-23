# setup.ps1 — autoSWE Interactive Setup Wizard (Windows)
#
# Runs the first-run setup wizard to configure credentials and settings.
# Creates config/repos.json and config/autoswe.env.
#
# Usage:
#   .\setup.ps1          # guided first-run setup
#   .\setup.ps1 --force  # overwrite existing config without prompting

$ErrorActionPreference = "Stop"

$AUTOSWE_DIR = if ($env:AUTOSWE_DIR) { $env:AUTOSWE_DIR } else { $PSScriptRoot }
$AUTOSWE_PY  = Join-Path $AUTOSWE_DIR "autoswe.py"
$VENV_PY     = Join-Path $AUTOSWE_DIR ".venv\Scripts\python.exe"

$PYTHON = if (Test-Path $VENV_PY) { $VENV_PY } else { "python" }

& $PYTHON $AUTOSWE_PY setup @args
