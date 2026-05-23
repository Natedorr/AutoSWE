@echo off
REM update.bat — Pull latest autoSWE code from origin/master (Windows batch wrapper)
REM
REM Usage:
REM   update.bat          REM pull latest code
REM   update.bat --force  REM discard local changes if there are any

powershell.exe -NonInteractive -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
