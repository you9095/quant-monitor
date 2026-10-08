@echo off
rem ============================================================
rem Idempotent panel starter (ASCII only).
rem Start the Flask panel on port 8000 minimized if not already
rem listening. Called by panel_guard.vbs (scheduled task / quant://).
rem Simulation only, local matching, NO real broker account.
rem ============================================================
cd /d "%~dp0.."

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

netstat -ano -p tcp | findstr /C:":8000" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 exit /b 0

start "quant-panel" /min "%PY%" run_simulation.py
exit /b 0
