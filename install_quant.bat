@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - ALL-IN-ONE installer (single file)
REM  Target: D:\quant-monitor   (Simulation only, no real broker)
REM  VERSION: 2026-10-04  v5  NO-UAC-SINGLE-INSTANCE
REM
REM  No administrator elevation is required: cloning, venv,
REM  deps, the matching engine and heartbeats all run as the
REM  current user. Scheduled tasks are created for the current
REM  logged-in user (also no admin needed). Double-click = one
REM  window, no UAC relaunch, no second instance.
REM
REM  Order (network proven FIRST):
REM   1. single-instance lock + self-check Git/Python/D drive
REM   2. connect GitHub + clone small DATA repo via
REM      SSH22 -> SSH443 -> HTTPS, push ONLINE immediately
REM   3. clone/update CODE repo (same 3 channels)
REM   4. setup.py: venv, deps (CN mirror), live-data,
REM      scheduled tasks, self-test, final heartbeat
REM  Log: D:\quant-monitor-install.log  and
REM       D:\quant-monitor\install_setup.log
REM ============================================================

set "INSTALL_DIR=D:\quant-monitor"
set "STATUS_DIR=D:\_qm_live"
set "LOCKDIR=D:\_qm_install.lock"
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "DATA_SSH=git@github.com:you9095/quant-monitor-live-data.git"
set "DATA_HTTPS=https://github.com/you9095/quant-monitor-live-data.git"
set "LOG=D:\quant-monitor-install.log"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   VERSION: 2026-10-04  v5  NO-UAC
echo   Target: %INSTALL_DIR%
echo   Mode  : Simulation (no real broker)
echo ========================================
echo.
echo Full log: %LOG%
echo [%DATE% %TIME%] installer v5 started on %COMPUTERNAME% > "%LOG%"
echo.

goto :main

REM ============== single exit point (release lock + hold window) ==============
:quit
set "RC=%~1"
if not defined RC set "RC=0"
rmdir /s /q "%LOCKDIR%" 2>nul
echo.
echo ========================================
echo   Window stays open. Read the lines above.
echo ========================================
pause
exit /b %RC%

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

REM ----- 0. D drive must exist (the lock lives on D:) -----
if not exist D:\ (
    echo [ERROR] D drive not found. This installer requires a D drive.
    pause
    exit /b 1
)

REM ----- single-instance lock (atomic mkdir; stale after 30 min is reclaimed) -----
if exist "%LOCKDIR%" (
    set "LOCKAGE=fresh"
    for /f %%a in ('powershell -NoProfile -Command "try{if(((Get-Date)-(Get-Item 'D:\_qm_install.lock').CreationTime).TotalMinutes -gt 30){'stale'}else{'fresh'}}catch{'stale'}"') do set "LOCKAGE=%%a"
    if "!LOCKAGE!"=="stale" (
        rmdir /s /q "%LOCKDIR%" 2>nul
    ) else (
        echo ========================================
        echo   Another installer is already running.
        echo   This window closes in 8 seconds.
        echo   If you are SURE nothing else is running,
        echo   delete this folder and double-click again:
        echo     %LOCKDIR%
        echo ========================================
        timeout /t 8
        exit /b
    )
)
mkdir "%LOCKDIR%" 2>nul

REM ----- 1. self-check -----
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git for Windows not found. Install from https://git-scm.com/download/win
    echo [ERROR] git-not-found >> "%LOG%"
    call :quit 1
)
echo [1/4] Git found.

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
    call :quit 1
)
echo [2/4] Python found (%PYCMD%).
echo [3/4] D drive ready.

REM ----- 2. FIRST: connect + clone the small DATA repo, report ONLINE immediately -----
echo [4/4] Connecting to GitHub and establishing status channel FIRST...
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
    call :quit 1
)
call :report ONLINE "connected via !CLONE_MODE!; git/python/drive OK"
echo       Status channel connected via !CLONE_MODE!.

REM ----- 3. clone/update the CODE repo -----
echo Getting the latest code (same auto network path)...
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
    call :quit 1
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
    echo   and %INSTALL_DIR%\install_setup.log
    echo ========================================
)
call :quit %RC%
