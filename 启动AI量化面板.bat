@echo off
rem ============================================================
rem One-click launcher for AI Quant Monitor (Windows)
rem Double-click: start the data backend on :8000 if needed,
rem then open the live dashboard in the default browser.
rem Simulation only, local matching, NO real broker account.
rem Content is pure ASCII on purpose to avoid GBK/UTF-8 parse errors.
rem ============================================================
cd /d "%~dp0"
title quant-panel-launcher

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

netstat -ano -p tcp | findstr /C:":8000" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 goto openui

echo Starting data backend on port 8000, please wait...
start "quant-panel" /min "%PY%" run_simulation.py

set /a n=0
:waitloop
set /a n+=1
timeout /t 1 /nobreak >nul
netstat -ano -p tcp | findstr /C:":8000" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 goto openui
if %n% geq 30 goto fail
goto waitloop

:openui
start "" "http://localhost:8000/?data_mode=live"
exit /b 0

:fail
echo Backend did not start within 30 seconds.
echo Check the venv, or run install_v9.bat once to repair the environment.
pause
exit /b 1
