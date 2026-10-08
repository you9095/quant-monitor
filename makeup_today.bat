@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Quant Monitor - Makeup Today (one-off)

REM ============================================================
REM  ONE-OFF makeup for the first trading day (2026-10-08).
REM  Use ONLY when the normal 13:00-17:00 window was missed but
REM  you still need today's REAL closing-price fills. It fills at
REM  today's real close via multi-source quotes
REM  (eastmoney -> tencent -> sina), then force-uploads, bypassing
REM  the 13:00-17:00 push window for this one run only.
REM  Run from your Downloads folder; do NOT move this file into
REM  D:\quant-monitor (the engine resets that folder).
REM  Simulation only - local matching, NO broker, NO real account.
REM ============================================================

set "APPDIR=D:\quant-monitor"
cd /d "%APPDIR%"
if errorlevel 1 (
  echo [ERROR] Cannot find %APPDIR%
  echo Edit APPDIR in this file if you installed to another drive.
  echo.
  pause
  exit /b 1
)

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

echo ==================================================
echo  Makeup TODAY at the REAL closing price (one-off)
echo  Time: %date% %time%
echo  Dir : %CD%
echo ==================================================
echo.

echo [Step 1/3] Sync newest code + align to the empty ledger...
echo --------------------------------------------------
"%PY%" scripts\fix_and_report.py
echo.

echo [Step 2/3] Engine once --force (fill at today real close)...
echo --------------------------------------------------
"%PY%" run_daily_engine.py once --force
echo.

echo [Step 3/3] Force-upload today fills + heartbeat...
echo --------------------------------------------------
"%PY%" scripts\report_deploy.py
echo.

echo ==================================================
echo  ALL DONE - MAKEUP FINISHED.
echo  Above, the price source line should read:
echo    source=realtime  detail=tencent (or sina / em)
echo  It must NOT say close_fallback.
echo  Log: live-data\_run_logs\ (today's .log)
echo ==================================================
echo.
pause
