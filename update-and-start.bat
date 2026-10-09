@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  Quant Panel - Update and Restart
echo  Simulation only, local matching, NO real broker account.
echo ============================================================
echo.
echo [1/3] Fetching latest code from GitHub...
git fetch origin master
if errorlevel 1 (
  echo [WARN] git fetch reported an error. Trying reset anyway...
)
git reset --hard origin/master
if errorlevel 1 (
  echo.
  echo [ERROR] Could not update code from GitHub.
  echo Check the network, or run Git Bash: cd /d/quant-monitor then
  echo git fetch origin master and git reset --hard origin/master.
  echo This window stays open so you can read the error.
  pause
  exit /b 1
)
echo Code updated to latest.
echo.
echo [2/3] Stopping the old panel on port 8000...
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr ":8000" ^| findstr LISTENING') do (
  echo stopping old backend PID %%a
  taskkill /F /PID %%a >nul 2>&1
)
ping -n 4 127.0.0.1 >nul
echo.
echo [3/3] Starting the panel with the unified launcher...
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0scripts\launch_panel.py"
set RC=%errorlevel%
echo.
if "%RC%"=="0" (
  echo [OK] Panel is ready. Now double-click index.html.
) else (
  echo [FAILED] Launcher exit code %RC%.
  echo Please send these two log files to the assistant:
  echo   %~dp0logs\backend_boot.log
  echo   %~dp0logs\self_register.log
)
echo.
pause
