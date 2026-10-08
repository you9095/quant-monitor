@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Quant Monitor - Run Now (manual)

REM ============================================================
REM  Manual one-click trigger: self-heal + sync + trade + push
REM  Run this from your Downloads folder; do NOT move it into
REM  D:\quant-monitor (the engine resets that folder).
REM  Safe to re-run: the engine is idempotent within one day.
REM ============================================================

set "APPDIR=D:\quant-monitor"
cd /d "%APPDIR%"
if errorlevel 1 (
  echo [ERROR] Cannot find %APPDIR%
  echo Edit APPDIR in this file if you installed to another drive\folder.
  echo.
  pause
  exit /b 1
)

echo ==================================================
echo  Quant Monitor - run TODAY now (manual trigger)
echo  Time: %date% %time%
echo  Dir : %CD%
echo ==================================================
echo.

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" (
  where python >nul 2>nul
  if not errorlevel 1 (
    set "PY=python"
  ) else (
    echo [ERROR] Python not found. Neither venv nor PATH python is available.
    pause
    exit /b 1
  )
)
echo Using Python: %PY%
echo.

echo [Step 1/2] Self-heal network, sync code/data, report heartbeat...
echo --------------------------------------------------
"%PY%" scripts\fix_and_report.py
echo.

echo [Step 2/2] Engine: decide -^> fill -^> push -^> heartbeat...
echo --------------------------------------------------
"%PY%" daily_task.py trade
echo.

echo ==================================================
echo  ALL DONE.
echo  - If you saw "[trade] done" and an upload/heartbeat
echo    line above, today's data has been pushed to GitHub.
echo  - Re-running this same day is safe (no duplicate fills).
echo  - Log file: live-data\_run_logs\ (today's .log)
echo ==================================================
echo.
pause
