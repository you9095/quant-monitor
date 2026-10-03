@echo off
setlocal enabledelayedexpansion
title AI Quant - Connection Diagnostics

REM ============================================================
REM  Connection diagnostics for the AI Quant Monitor.
REM  Tests Git, Python and GitHub access over BOTH SSH and HTTPS
REM  WITHOUT changing your installation. Writes everything to
REM  D:\qm_diag.txt and, if reachable, pushes it to the data repo.
REM ============================================================

set "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
set "OUT=D:\qm_diag.txt"
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "DATA_SSH=git@github.com:you9095/quant-monitor-live-data.git"
set "DATA_HTTPS=https://github.com/you9095/quant-monitor-live-data.git"
set "STATUS_DIR=D:\_qm_live"

echo AI Quant Monitor - Connection Diagnostics > "%OUT%"
echo Time: %DATE% %TIME% >> "%OUT%"
echo Computer: %COMPUTERNAME%  User: %USERNAME% >> "%OUT%"
echo ============================================ >> "%OUT%"

echo.
echo Running diagnostics, please wait...
echo.

echo [STEP 1] Git version >> "%OUT%" 2>&1
git --version >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 2] Python version >> "%OUT%" 2>&1
python --version >> "%OUT%" 2>&1
py -3 --version >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 3] SSH authentication (success prints "Hi username!") >> "%OUT%" 2>&1
ssh -T git@github.com >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 4a] CODE repo over SSH >> "%OUT%" 2>&1
git ls-remote %CODE_SSH% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 4b] CODE repo over HTTPS >> "%OUT%" 2>&1
git ls-remote %CODE_HTTPS% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 5a] DATA repo over SSH >> "%OUT%" 2>&1
git ls-remote %DATA_SSH% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 5b] DATA repo over HTTPS >> "%OUT%" 2>&1
git ls-remote %DATA_HTTPS% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 6] D drive and existing install >> "%OUT%" 2>&1
if exist D:\ (echo D drive: OK >> "%OUT%" 2>&1) else (echo D drive: MISSING >> "%OUT%" 2>&1)
if exist "D:\quant-monitor" (echo D:\quant-monitor exists >> "%OUT%" 2>&1) else (echo D:\quant-monitor missing >> "%OUT%" 2>&1)
if exist "D:\quant-monitor\.git" (echo it is a git repo: YES >> "%OUT%" 2>&1) else (echo it is a git repo: NO >> "%OUT%" 2>&1)
echo. >> "%OUT%" 2>&1

echo [STEP 7] Try to clone data repo and push this report >> "%OUT%" 2>&1
if exist "%STATUS_DIR%\.git" (
    cd /d "%STATUS_DIR%"
    git pull origin master >> "%OUT%" 2>&1
) else (
    echo trying SSH clone... >> "%OUT%" 2>&1
    git clone %DATA_SSH% "%STATUS_DIR%" >> "%OUT%" 2>&1
    if not exist "%STATUS_DIR%\.git" (
        echo SSH clone failed, trying HTTPS... >> "%OUT%" 2>&1
        if exist "%STATUS_DIR%" rmdir /s /q "%STATUS_DIR%"
        git clone %DATA_HTTPS% "%STATUS_DIR%" >> "%OUT%" 2>&1
    )
)
if exist "%STATUS_DIR%\.git" (
    if not exist "%STATUS_DIR%\_install_status" mkdir "%STATUS_DIR%\_install_status"
    copy /y "%OUT%" "%STATUS_DIR%\_install_status\%COMPUTERNAME%-diag.txt" >nul 2>&1
    cd /d "%STATUS_DIR%"
    git add -A >> "%OUT%" 2>&1
    git commit -m "diag %COMPUTERNAME%" >> "%OUT%" 2>&1
    git push origin master >> "%OUT%" 2>&1
    echo PUSH_ATTEMPTED >> "%OUT%" 2>&1
) else (
    echo BOTH_SSH_AND_HTTPS_FAILED >> "%OUT%" 2>&1
)

echo. >> "%OUT%" 2>&1
echo Done: %DATE% %TIME% >> "%OUT%" 2>&1

cls
echo ============================================================
echo   DIAGNOSTICS FINISHED
echo ============================================================
type "%OUT%"
echo ============================================================
echo.
echo Full report saved at:  %OUT%
echo.
pause
