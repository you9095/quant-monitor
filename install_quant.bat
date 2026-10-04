@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - ALL-IN-ONE installer (single file)
REM  Target: D:\quant-monitor   (Simulation only, no real broker)
REM
REM  This single double-click does everything, in order:
REM    1. self-check (Git / Python / D drive)
REM    2. auto-fix GitHub connection, trying in order:
REM         SSH port22 -> SSH port443 (ssh.github.com) -> HTTPS
REM    3. clone/update the code
REM    4. run setup.py: venv, deps, data repo, scheduled tasks,
REM       self-test and heartbeat report
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
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "LOG=D:\quant-monitor-install.log"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   Target: %INSTALL_DIR%
echo   Mode  : Simulation (no real broker)
echo ========================================
echo.
echo Full log: %LOG%
echo [%DATE% %TIME%] installer started on %COMPUTERNAME% > "%LOG%"
echo.

goto :main

REM ============== helper: enable SSH over port 443 ==============
:enable_ssh_443
if not exist "%USERPROFILE%\.ssh" mkdir "%USERPROFILE%\.ssh"
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
echo       ** If a GitHub sign-in window opens, please complete it once. **
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

REM ----- 1. check Git -----
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git for Windows not found.
    echo Install it from https://git-scm.com/download/win then run this again.
    echo [ERROR] git-not-found >> "%LOG%"
    pause
    exit /b 1
)
echo [1/4] Git found.

REM ----- 2. find Python -----
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
echo [2/4] Python found (%PYCMD%).

REM ----- 3. D drive -----
if not exist D:\ (
    echo [ERROR] D drive not found.
    echo [ERROR] no-d-drive >> "%LOG%"
    pause
    exit /b 1
)
echo [3/4] D drive ready.

REM ----- 4. obtain the code (clone or update) -----
echo [4/4] Getting the latest code (auto-selecting network path)...
if exist "%INSTALL_DIR%\.git" (
    echo       Existing installation found, updating...
    call :enable_ssh_443
    cd /d "%INSTALL_DIR%"
    git config --global credential.helper manager >nul 2>&1
    git fetch origin master >> "%LOG%" 2>&1
    git reset --hard origin/master >> "%LOG%" 2>&1
    set "CLONE_MODE=existing"
) else (
    if exist "%INSTALL_DIR%" (
        echo       Old non-git folder found, backing it up...
        move "%INSTALL_DIR%" "%INSTALL_DIR%-old" >> "%LOG%" 2>&1
    )
    call :smart_clone "%INSTALL_DIR%" "%CODE_SSH%" "%CODE_HTTPS%"
)

if "!CLONE_MODE!"=="FAIL" (
    echo.
    echo ========================================
    echo   [ERROR] Could not reach GitHub.
    echo   Tried SSH22, SSH443 and HTTPS, all failed.
    echo   Please complete the GitHub sign-in if a window appeared,
    echo   or check your network / proxy, then run this again.
    echo   Details: %LOG%
    echo ========================================
    pause
    exit /b 1
)
echo       Code ready (channel: !CLONE_MODE!).

REM ----- run the in-repo all-in-one setup -----
cd /d "%INSTALL_DIR%"
echo.
echo ========================================
echo   Running setup: venv + deps + data repo
echo   + scheduled tasks + self-test.
echo   This can take several minutes...
echo ========================================
echo.
%PYCMD% setup.py
set "RC=%errorlevel%"
echo setup.py exit code = %RC% >> "%LOG%"

echo.
if %RC%==0 (
    echo ========================================
    echo   ALL DONE - INSTALL FINISHED
    echo.
    echo   Start the panel anytime: double-click
    echo     %INSTALL_DIR%\start.bat
    echo   then open http://localhost:8000
    echo.
    echo   Simulation mode - no real broker.
    echo ========================================
) else (
    echo ========================================
    echo   SETUP REPORTED AN ERROR (code %RC%).
    echo   The installer will retry the network link
    echo   automatically after reboot. Details: %LOG%
    echo ========================================
)
echo.
pause
