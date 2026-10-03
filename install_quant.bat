@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - single-file bootstrap installer
REM  Target dir: D:\quant-monitor  (kept off the C system drive)
REM  Simulation mode only - never connects to a real broker.
REM
REM  This installer reports EVERY step to the private data repo
REM  (folder _install_status), so the macOS side can see progress
REM  and the exact failing step even if the window is closed.
REM ============================================================

REM ----- auto request administrator (for schtasks) -----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges, please click Yes...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=D:\quant-monitor"
set "CODE_REPO=git@github.com:you9095/quant-monitor.git"
set "DATA_REPO=git@github.com:you9095/quant-monitor-live-data.git"
set "STATUS_DIR=D:\_qm_live"
set "LOG=D:\quant-monitor-install.log"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   Target : %INSTALL_DIR%
echo   Mode   : Simulation (no real broker)
echo ========================================
echo.
echo Install log: %LOG%
echo.

REM ----- reporting helper (writes + pushes current step) -----
goto :after_report
:report
REM %~1 = short status token, %~2 = detail
set "TOKEN=%~1"
set "DETAIL=%~2"
if not exist "%STATUS_DIR%\.git" goto :eof
if not exist "%STATUS_DIR%\_install_status" mkdir "%STATUS_DIR%\_install_status"
echo %DATE% %TIME% ^| %TOKEN% ^| %DETAIL% >> "%STATUS_DIR%\_install_status\%COMPUTERNAME%.txt"
cd /d "%STATUS_DIR%"
git add -A >nul 2>&1
git commit -m "install %COMPUTERNAME% %TOKEN%" >nul 2>&1
git push origin master >nul 2>&1
cd /d "%~dp0"
goto :eof
:after_report

echo [%DATE% %TIME%] installer started on %COMPUTERNAME% > "%LOG%"

REM ----- check Git -----
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git for Windows not found.
    echo Install from https://git-scm.com/download/win then run again.
    echo [ERROR] git-not-found >> "%LOG%"
    pause
    exit /b 1
)
echo [1/6] Git found.

REM ----- find Python -----
set "PYCMD="
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
    echo [ERROR] Python not found. Install Python 3.11 and tick "Add Python to PATH".
    echo [ERROR] python-not-found >> "%LOG%"
    pause
    exit /b 1
)
echo [2/6] Python found (%PYCMD%).

REM ----- D drive must exist -----
if not exist D:\ (
    echo [ERROR] D drive not found.
    echo [ERROR] no-d-drive >> "%LOG%"
    pause
    exit /b 1
)

REM ----- establish reporting channel by cloning the DATA repo -----
echo [3/6] Connecting to GitHub data repo (status channel)...
if exist "%STATUS_DIR%\.git" (
    cd /d "%STATUS_DIR%"
    git pull origin master >nul 2>&1
) else (
    git clone %DATA_REPO% "%STATUS_DIR%"
    if errorlevel 1 (
        echo [ERROR] Cannot clone data repo. SSH key or network problem.
        echo Make sure your SSH public key is added to GitHub, then retry.
        echo [ERROR] data-repo-clone-failed >> "%LOG%"
        pause
        exit /b 1
    )
)
cd /d "%~dp0"
call :report STARTED "installer started, git/python ok"
echo       Status channel connected.

REM ----- clone or hard-update the CODE repo -----
echo [4/6] Getting latest code...
if exist "%INSTALL_DIR%\.git" (
    cd /d "%INSTALL_DIR%"
    git fetch origin master >> "%LOG%" 2>&1
    git reset --hard origin/master >> "%LOG%" 2>&1
) else (
    if exist "%INSTALL_DIR%" (
        call :report BACKUP "old non-git folder renamed to -old"
        move "%INSTALL_DIR%" "%INSTALL_DIR%-old" >> "%LOG%" 2>&1
    )
    git clone %CODE_REPO% "%INSTALL_DIR%" >> "%LOG%" 2>&1
    if errorlevel 1 (
        call :report FAILED "code clone failed"
        echo [ERROR] Code clone failed. See %LOG%
        pause
        exit /b 1
    )
)
call :report CODE_OK "code at %INSTALL_DIR%"
echo       Code ready.

REM ----- run in-repo setup (venv, deps, data repo, tasks, heartbeat) -----
cd /d "%INSTALL_DIR%"
echo [5/6] Installing dependencies and configuring (a few minutes)...
echo.
call :report SETUP_START "running setup.py"
%PYCMD% setup.py
set "RC=%errorlevel%"
echo.
echo setup.py exit code = %RC% >> "%LOG%"

REM ----- finish -----
echo [6/6] Finishing.
if %RC%==0 (
    call :report SUCCESS "install finished, setup rc=0"
    echo ========================================
    echo   INSTALL FINISHED SUCCESSFULLY
    echo   Start panel: double-click start.bat in
    echo   %INSTALL_DIR%
    echo ========================================
) else (
    call :report FAILED "setup.py returned rc=%RC%"
    echo ========================================
    echo   SETUP ENCOUNTERED AN ERROR (code %RC%)
    echo   The failing step has been reported.
    echo   Log: %LOG%
    echo ========================================
)
echo.
pause
