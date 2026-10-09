@echo off
rem ============================================================
rem Quant panel launcher fallback (ASCII only).
rem Manual double-click fallback. The main one-click path is the
rem in-page green button via quant:// -> pythonw launch_panel.py.
rem All paths converge on scripts\launch_panel.py (idempotent,
rem logs to logs\backend_boot.log, shows a dialog on failure).
rem Simulation only, local matching, NO real broker account.
rem ============================================================
setlocal
cd /d "%~dp0.."

set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting Quant panel launcher, please wait...
"%PY%" "%CD%\scripts\launch_panel.py"
set RC=%errorlevel%

if not "%RC%"=="0" (
  echo.
  echo Launcher failed or timed out. See logs\backend_boot.log
  pause
)
endlocal
