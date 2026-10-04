@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - ALL-IN-ONE installer (single file)
REM  Target: D:\quant-monitor   (Simulation only, no real broker)
REM
REM  STEP ORDER (network is proven FIRST, before anything heavy):
REM   1. self-check Git / Python / D drive
REM   2. connect to GitHub + clone the small DATA repo, trying
REM        SSH22 -> SSH443 (ssh.github.com) -> HTTPS
REM      and IMMEDIATELY push an "ONLINE" heartbeat (first report)
REM   3. clone/update the CODE repo (same 3 channels)
REM   4. run setup.py: venv, deps (CN mirror), live-data,
REM      scheduled tasks, self-test, final heartbeat
REM  Every step is pushed to the data repo as it happens.
REM  Log: D:\quant-monitor-install.log
REM ============================================================

REM ----- auto request administrator (needed for schtasks) -----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges, please click Yes...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=D:\quant-monitor"
set "STATUS_DIR=D:\_qm_live"
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "DATA_SSH=git@github.com:you9095/quant-monitor-live-data.git"
set "DATA_HTTPS=https://github.com/you9095/quant-monitor-live-data.git"
set "LOG=D:\quant-monitor-install.log"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   VERSION: 2026-10-04  v4  FIRST-HEARTBEAT
echo   Target: %INSTALL_DIR%
echo   Mode  : Simulation (no real broker)
echo ========================================
echo.
echo Full log: %LOG%
echo [%DATE% %TIME%] installer v4 started on %COMPUTERNAME% > "%LOG%"
echo.

goto :main

REM ============== helper: enable SSH over port 443 ==============
:enable_ssh_443
if not exist "%USERPROFILE%\.ssh" mkdir "%USERPROFILE%\.ssh"
if not exist "%USERPROFILE%\.ssh\config" type nul > "%USERPROFILE%\.ssh\config"
findstr /C:"ssh.github.com" "%USERPROFILE%\.ssh\config" >nul 2>&1
if errorlevel 1 (
    echo.>> "%USERPROFILE%\.ssh\config"
    echo # AI Quant: route GitHub SSH over port 443>> "%USERPROFILE%\.ssh\config"
    echo Host github.com>> "%USERPROFILE%\.ssh\config"
    echo   HostName ssh.github.com>> "%USERPROFILE%\.ssh\config"
    echo   Port 443>> "%USERPROFILE%\.ssh\config"
    echo   User git>> "%USERPROFILE%\.ssh\config"
)
goto :eof

REM ============== helper: report a step to the data repo ==============
REM %~1 = token, %~2 = detail
:report
if not exist "%STATUS_DIR%\.git" goto :eof
if not exist "%STATUS_DIR%\_install_status" mkdir "%STATUS_DIR%\_install_status"
>> "%STATUS_DIR%\_install_status\%COMPUTERNAME%.txt" echo %DATE% %TIME% ^| %~1 ^| %~2
cd /d "%STATUS_DIR%"
git add -A >nul 2>&1
git commit -m "install %COMPUTERNAME% %~1" >nul 2>&1
git pull --no-rebase origin master >nul 2>&1
git push origin master >nul 2>&1
cd /d "%~dp0"
goto :eof

REM ============== helper: smart clone (SSH22/SSH443/HTTPS) ==============
REM %~1 = target dir, %~2 = ssh url, %~3 = https url ; sets CLONE_MODE
:smart_clone
set "GC_DIR=%~1"
if exist "%GC_DIR%\.git" (
    set "CLONE_MODE=existing"
    goto :eof
)
echo       Trying SSH over port 22...
set "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=15"
git clone "%~2" "%GC_DIR%" >> "%LOG%" 2>&1
if not errorlevel 1 (
    set "CLONE_MODE=ssh22"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"
echo       SSH22 failed. Enabling SSH over port 443...
call :enable_ssh_443
git clone "%~2" "%GC_DIR%" >> "%LOG%" 2>&1
if not errorlevel 1 (
    set "CLONE_MODE=ssh443"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"
echo       SSH failed. Trying HTTPS...
echo       ** If a GitHub sign-in window opens, complete it once. **
set "GIT_SSH_COMMAND="
git config --global credential.helper manager >> "%LOG%" 2>&1
git clone "%~3" "%GC_DIR%"
if not errorlevel 1 (
    set "CLONE_MODE=https"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"
set "CLONE_MODE=FAIL"
goto :eof

:main

REM ----- 1. self-check -----
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git for Windows not found. Install from https://git-scm.com/download/win
    echo [ERROR] git-not-found >> "%LOG%"
    pause
    exit /b 1
)
echo [1/5] Git found.

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
echo [2/5] Python found (%PYCMD%).

if not exist D:\ (
    echo [ERROR] D drive not found.
    echo [ERROR] no-d-drive >> "%LOG%"
    pause
    exit /b 1
)
echo [3/5] D drive ready.

REM ----- 2. FIRST: connect + clone the small DATA repo, report ONLINE immediately -----
echo [4/5] Connecting to GitHub and establishing status channel FIRST...
git config --global credential.helper manager >> "%LOG%" 2>&1
if exist "%STATUS_DIR%\.git" (
    cd /d "%STATUS_DIR%"
    git pull --no-rebase origin master >> "%LOG%" 2>&1
    cd /d "%~dp0"
    set "CLONE_MODE=existing"
) else (
    call :smart_clone "%STATUS_DIR%" "%DATA_SSH%" "%DATA_HTTPS%"
)
if "!CLONE_MODE!"=="FAIL" (
    echo.
    echo ========================================
    echo   [ERROR] Cannot reach GitHub.
    echo   Tried SSH22, SSH443 and HTTPS, all failed.
    echo   If a GitHub sign-in window appeared, finish it.
    echo   Otherwise check network/proxy, then run again.
    echo   Details: %LOG%
    echo ========================================
    echo [%DATE% %TIME%] NETWORK_FAIL all 3 channels >> "%LOG%"
    pause
    exit /b 1
)
call :report ONLINE "connected via !CLONE_MODE!; git/python/drive OK"
echo       Status channel connected via !CLONE_MODE!.

REM ----- 3. clone/update the CODE repo -----
echo [5/5] Getting the latest code (same auto network path)...
if exist "%INSTALL_DIR%\.git" (
    echo       Existing installation found, updating...
    call :enable_ssh_443
    cd /d "%INSTALL_DIR%"
    git config --global credential.helper manager >nul 2>&1
    git fetch origin master >> "%LOG%" 2>&1
    git reset --hard origin/master >> "%LOG%" 2>&1
    cd /d "%~dp0"
    set "CLONE_MODE=existing"
) else (
    if exist "%INSTALL_DIR%" (
        echo       Old non-git folder found, backing it up...
        move "%INSTALL_DIR%" "%INSTALL_DIR%-old" >> "%LOG%" 2>&1
    )
    call :smart_clone "%INSTALL_DIR%" "%CODE_SSH%" "%CODE_HTTPS%"
)
if "!CLONE_MODE!"=="FAIL" (
    call :report FAILED "code clone failed on all channels"
    echo [ERROR] Could not get the code. Details: %LOG%
    pause
    exit /b 1
)
call :report CODE_READY "code at %INSTALL_DIR% via !CLONE_MODE!"
echo       Code ready via !CLONE_MODE!.

REM ----- 4. run the in-repo all-in-one setup -----
cd /d "%INSTALL_DIR%"
call :report SETUP_START "setup.py starting"
echo.
echo ========================================
echo   Running setup: venv + deps + live-data
echo   + scheduled tasks + self-test.
echo   This can take several minutes (CN mirror)...
echo ========================================
echo.
%PYCMD% setup.py
set "RC=%errorlevel%"
echo setup.py exit code = %RC% >> "%LOG%"

echo.
if %RC%==0 (
    call :report SUCCESS "install finished, setup rc=0"
    echo ========================================
    echo   ALL DONE - INSTALL FINISHED
    echo.
    echo   Start the panel: double-click
    echo     %INSTALL_DIR%\start.bat
    echo   then open http://localhost:8000
    echo.
    echo   Simulation mode - no real broker.
    echo ========================================
) else (
    call :report FAILED "setup.py returned rc=%RC%"
    echo ========================================
    echo   SETUP REPORTED AN ERROR (code %RC%).
    echo   It was reported; the boot self-check will
    echo   retry after login. Details: %LOG%
    echo ========================================
)
echo.
pause
