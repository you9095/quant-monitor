@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - single-file bootstrap installer
REM  Target dir: D:\quant-monitor  (kept off the C system drive)
REM  Simulation mode only - never connects to a real broker.
REM ============================================================

REM ----- auto request administrator (for schtasks) -----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges, please click Yes...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=D:\quant-monitor"
set "REPO=git@github.com:you9095/quant-monitor.git"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   Target : %INSTALL_DIR%
echo   Mode   : Simulation (no real broker)
echo ========================================
echo.

REM ----- check Git -----
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git for Windows not found.
    echo Please install it from https://git-scm.com/download/win then run again.
    pause
    exit /b 1
)
echo [1/5] Git found.

REM ----- find Python -----
set "PYCMD="
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
    echo [ERROR] Python not found. Please install Python 3.11 first:
    echo https://www.python.org/downloads/release/python-3119/
    echo Remember to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [2/5] Python found (%PYCMD%).

REM ----- D drive must exist -----
if not exist D:\ (
    echo [ERROR] D drive not found on this machine.
    pause
    exit /b 1
)

REM ----- clone latest code, or hard-update existing -----
if exist "%INSTALL_DIR%\.git" (
    echo [3/5] Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git fetch origin master
    git reset --hard origin/master
) else (
    if exist "%INSTALL_DIR%" (
        echo [3/5] Old non-git folder found, backing it up...
        move "%INSTALL_DIR%" "%INSTALL_DIR%-old" >nul
    ) else (
        echo [3/5] Cloning latest code from GitHub...
    )
    git clone %REPO% "%INSTALL_DIR%"
    if errorlevel 1 (
        echo [ERROR] git clone failed. Check your SSH key and network.
        pause
        exit /b 1
    )
)

cd /d "%INSTALL_DIR%"

REM ----- run in-repo setup: venv, deps, data repo, tasks, heartbeat -----
echo [4/5] Installing dependencies and configuring (may take a few minutes)...
echo.
%PYCMD% setup.py
set "RC=%errorlevel%"
echo.

echo [5/5] Done.
echo ========================================
if %RC%==0 (
    echo   INSTALL FINISHED SUCCESSFULLY
    echo.
    echo   Start the panel anytime by double-clicking start.bat
    echo   in  D:\quant-monitor
) else (
    echo   SETUP ENCOUNTERED AN ERROR (code %RC%)
    echo   Please report the messages above.
)
echo ========================================
pause
