@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - single-file bootstrap installer
REM  Target dir: D:\quant-monitor  (kept off the C system drive)
REM  Simulation mode only - never connects to a real broker.
REM
REM  GitHub connection: tries SSH first, automatically falls back
REM  to HTTPS (a GitHub sign-in window may appear once for HTTPS;
REM  Windows remembers it afterwards).
REM  Every step is reported to the private data repo folder
REM  _install_status so the macOS side can track progress remotely.
REM ============================================================

REM ----- auto request administrator (for schtasks) -----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges, please click Yes...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=D:\quant-monitor"
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "DATA_SSH=git@github.com:you9095/quant-monitor-live-data.git"
set "DATA_HTTPS=https://github.com/you9095/quant-monitor-live-data.git"
set "STATUS_DIR=D:\_qm_live"
set "LOG=D:\quant-monitor-install.log"
REM Auto-trust GitHub host key on first SSH contact; never hang on prompts
set "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   Target : %INSTALL_DIR%
echo   Mode   : Simulation (no real broker)
echo ========================================
echo.
echo Install log: %LOG%
echo.

goto :after_funcs

REM ===== :report TOKEN DETAIL -- push current step to data repo =====
:report
if not exist "%STATUS_DIR%\.git" goto :eof
if not exist "%STATUS_DIR%\_install_status" mkdir "%STATUS_DIR%\_install_status"
echo %DATE% %TIME% ^| %~1 ^| %~2 >> "%STATUS_DIR%\_install_status\%COMPUTERNAME%.txt"
cd /d "%STATUS_DIR%"
git add -A >nul 2>&1
git commit -m "install %COMPUTERNAME% %~1" >nul 2>&1
git pull --no-rebase origin master >nul 2>&1
git push origin master >nul 2>&1
cd /d "%~dp0"
goto :eof

REM ===== :try_clone DIR SSH_URL HTTPS_URL ; sets CLONE_MODE =====
:try_clone
set "TC_DIR=%~1"
echo       Trying SSH...
git clone "%~2" "%TC_DIR%"
if not errorlevel 1 (
    set "CLONE_MODE=SSH"
    goto :eof
)
if exist "%TC_DIR%" rmdir /s /q "%TC_DIR%"
echo       SSH did not work. Trying HTTPS...
echo       ** If a GitHub sign-in window appears, please complete it once. **
git clone "%~3" "%TC_DIR%"
if not errorlevel 1 (
    set "CLONE_MODE=HTTPS"
) else (
    set "CLONE_MODE=FAIL"
)
goto :eof

:after_funcs

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
    cd /d "%~dp0"
) else (
    call :try_clone "%STATUS_DIR%" "%DATA_SSH%" "%DATA_HTTPS%"
)
if not exist "%STATUS_DIR%\.git" (
    echo.
    echo [ERROR] Could not reach GitHub with either SSH or HTTPS.
    echo Please complete the GitHub sign-in if a window appeared, then run again.
    echo [ERROR] data-repo-unreachable >> "%LOG%"
    pause
    exit /b 1
)
call :report STARTED "installer started, git/python ok, channel=%CLONE_MODE%"
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
    call :try_clone "%INSTALL_DIR%" "%CODE_SSH%" "%CODE_HTTPS%"
    if "!CLONE_MODE!"=="FAIL" (
        call :report FAILED "code clone failed via ssh+https"
        echo [ERROR] Code clone failed. See %LOG%
        pause
        exit /b 1
    )
)
call :report CODE_OK "code ready at %INSTALL_DIR% via %CLONE_MODE%"
echo       Code ready.

REM ----- run in-repo setup (venv, deps, data repo, tasks, heartbeat) -----
cd /d "%INSTALL_DIR%"
echo [5/6] Installing dependencies and configuring (a few minutes)...
echo.
call :report SETUP_START "running setup.py"
%PYCMD% setup.py
set "RC=%errorlevel%"
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
