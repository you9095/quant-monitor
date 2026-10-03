@echo off
setlocal enabledelayedexpansion
title AI Quant - Connection Diagnostics

REM ============================================================
REM  Connection diagnostics for the AI Quant Monitor.
REM  Tests Git, Python and GitHub SSH access WITHOUT changing
REM  your installation. Writes everything to D:\qm_diag.txt
REM  and, if the data repo is reachable, pushes the result so
REM  the macOS side can read it directly.
REM ============================================================

set "GIT_TERMINAL_PROMPT=0"
set "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
set "OUT=D:\qm_diag.txt"
set "CODE_REPO=git@github.com:you9095/quant-monitor.git"
set "DATA_REPO=git@github.com:you9095/quant-monitor-live-data.git"
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

echo [STEP 3] SSH authentication to GitHub >> "%OUT%" 2>&1
echo (a successful auth prints "Hi username! ...") >> "%OUT%" 2>&1
ssh -T git@github.com >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 4] Read access to CODE repo >> "%OUT%" 2>&1
git ls-remote %CODE_REPO% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 5] Read access to DATA repo >> "%OUT%" 2>&1
git ls-remote %DATA_REPO% HEAD >> "%OUT%" 2>&1
echo. >> "%OUT%" 2>&1

echo [STEP 6] D drive and existing install >> "%OUT%" 2>&1
if exist D:\ (echo D drive: OK >> "%OUT%" 2>&1) else (echo D drive: MISSING >> "%OUT%" 2>&1)
if exist "D:\quant-monitor" (echo D:\quant-monitor exists >> "%OUT%" 2>&1) else (echo D:\quant-monitor missing >> "%OUT%" 2>&1)
if exist "D:\quant-monitor\.git" (echo it is a git repo: YES >> "%OUT%" 2>&1) else (echo it is a git repo: NO >> "%OUT%" 2>&1)
echo. >> "%OUT%" 2>&1

echo [STEP 7] Try to push this report to the data repo >> "%OUT%" 2>&1
if exist "%STATUS_DIR%\.git" (
    cd /d "%STATUS_DIR%"
    git pull origin master >> "%OUT%" 2>&1
) else (
    git clone %DATA_REPO% "%STATUS_DIR%" >> "%OUT%" 2>&1
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
    echo DATA_REPO_NOT_CLONED_SSH_LIKELY_FAILING >> "%OUT%" 2>&1
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
echo The full report is saved at:  %OUT%
echo.
pause
