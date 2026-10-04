@echo off
setlocal enabledelayedexpansion
title AI Quant Monitor - One-click Installer

REM ============================================================
REM  AI Quant Monitor - ALL-IN-ONE SELF-HEALING installer
REM  Target: D:\quant-monitor   (Simulation only, no real broker)
REM  VERSION: 2026-10-04  v7  SELF-HEAL
REM
REM  Single file, double-click, no admin/UAC. It detects and
REM  AUTO-FIXES every common failure before reporting:
REM   - locate Git/Python (PATH, common dirs, winget fallback)
REM   - git identity (user.name/email) auto-set so commits work
REM   - SSH key: auto-generate, fix private-key permissions,
REM     test auth over ssh.github.com:443, and if the key is not
REM     linked to GitHub: upload via gh CLI, or open the key page
REM     with the public key copied, then poll until linked
REM   - channels: SSH443 -> SSH22 -> HTTPS, auto-detect a local
REM     proxy (Clash/v2ray/etc) and configure git to use it
REM   - single-instance lock, full log, on-failure diagnostics
REM  Only needs the user (rarely): link the key once in browser,
REM  or turn on a VPN/proxy if the network fully blocks GitHub.
REM ============================================================

set "INSTALL_DIR=D:\quant-monitor"
set "STATUS_DIR=D:\_qm_live"
set "LOCKDIR=D:\_qm_install.lock"
set "CODE_SSH=git@github.com:you9095/quant-monitor.git"
set "CODE_HTTPS=https://github.com/you9095/quant-monitor.git"
set "DATA_SSH=git@github.com:you9095/quant-monitor-live-data.git"
set "DATA_HTTPS=https://github.com/you9095/quant-monitor-live-data.git"
set "LOG=D:\quant-monitor-install.log"
set "SSHTEST=%TEMP%\qm_sshtest.txt"
set "PUBKEY=%USERPROFILE%\.ssh\id_ed25519.pub"

echo ========================================
echo   AI Quant Monitor - One-click Installer
echo   VERSION: 2026-10-04  v7  SELF-HEAL
echo   Target: %INSTALL_DIR%
echo   Mode  : Simulation (no real broker)
echo ========================================
echo.
echo Full log: %LOG%
echo [%DATE% %TIME%] installer v7 started on %COMPUTERNAME% > "%LOG%"
echo.

goto :main

REM ===================== exit point =====================
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

REM ===================== persist SSH-over-443 =====================
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

REM ===================== git identity (commits need this) =====================
:git_identity
git config --global --get user.name >nul 2>&1
if errorlevel 1 git config --global user.name "quant-windows"
git config --global --get user.email >nul 2>&1
if errorlevel 1 git config --global user.email "quant@local"
git config --global credential.helper manager >nul 2>&1
git config --global http.version HTTP/1.1 >nul 2>&1
goto :eof

REM ===================== locate Git =====================
:find_git
git --version >nul 2>&1 && goto :eof
for %%P in ("%ProgramFiles%\Git\cmd" "%ProgramFiles(x86)%\Git\cmd" "%LOCALAPPDATA%\Programs\Git\cmd") do (
    if exist "%%~P\git.exe" set "PATH=%%~P;%PATH%"
)
git --version >nul 2>&1 && goto :eof
echo       Git not on PATH, trying winget install...
where winget >nul 2>&1
if not errorlevel 1 (
    winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements --silent >> "%LOG%" 2>&1
    for %%P in ("%ProgramFiles%\Git\cmd" "%LOCALAPPDATA%\Programs\Git\cmd") do if exist "%%~P\git.exe" set "PATH=%%~P;%PATH%"
)
goto :eof

REM ===================== locate Python =====================
:find_python
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD ( py -3 --version >nul 2>&1 && set "PYCMD=py -3" )
if not defined PYCMD (
    for %%V in (313 312 311 310 39) do (
        for %%D in ("%LOCALAPPDATA%\Programs\Python\Python%%V" "%ProgramFiles%\Python%%V" "%ProgramFiles(x86)%\Python%%V") do (
            if exist "%%~D\python.exe" set "PATH=%%~D;%PATH%"
        )
    )
    python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
    echo       Python not on PATH, trying winget install...
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install -e --id Python.Python.3.11 --scope user --accept-source-agreements --accept-package-agreements --silent >> "%LOG%" 2>&1
        for %%D in ("%LOCALAPPDATA%\Programs\Python\Python311") do if exist "%%~D\python.exe" set "PATH=%%~D;%PATH%"
        python --version >nul 2>&1 && set "PYCMD=python"
    )
)
goto :eof

REM ===================== detect local proxy (Clash/v2ray/...) =====================
:detect_proxy
set "PROXYPORT="
for /f "delims=" %%p in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports=7890,7897,10809,10808,1080,8888,8080,2080,33210; foreach($p in $ports){try{$c=New-Object Net.Sockets.TcpClient;$iar=$c.BeginConnect('127.0.0.1',$p,$null,$null);if($iar.AsyncWaitHandle.WaitOne(150,$false)){try{$c.EndConnect($iar)|Out-Null;Write-Output $p}catch{}};$c.Close()}catch{}}"') do set "PROXYPORT=%%p"
if defined PROXYPORT (
    echo       [DIAG] Local proxy detected on port !PROXYPORT!
    echo [DIAG] local proxy port !PROXYPORT! >> "%LOG%"
) else (
    echo [DIAG] no local proxy detected >> "%LOG%"
)
goto :eof

REM ===================== fix Windows OpenSSH key permissions =====================
:fix_key_perms
if exist "%~1" (
    icacls "%~1" /inheritance:r /grant:r "%USERNAME%:F" >nul 2>&1
    icacls "%~1" /grant:r "SYSTEM:F" >nul 2>&1
)
goto :eof

REM ===================== SSH key + 443 auth self-test =====================
REM result in SSH_AUTH = ok / denied / netfail / nokey
:ssh_auth_test
set "SSH_AUTH=unknown"
set "KEYFILE="
if exist "%USERPROFILE%\.ssh\id_ed25519" set "KEYFILE=%USERPROFILE%\.ssh\id_ed25519"
if not defined KEYFILE if exist "%USERPROFILE%\.ssh\id_rsa" set "KEYFILE=%USERPROFILE%\.ssh\id_rsa"
if not defined KEYFILE (
    echo       No SSH key found, generating an ed25519 key...
    echo [DIAG] generating SSH key >> "%LOG%"
    ssh-keygen -t ed25519 -N "" -C "quant-windows" -f "%USERPROFILE%\.ssh\id_ed25519" >> "%LOG%" 2>&1
    if exist "%USERPROFILE%\.ssh\id_ed25519" set "KEYFILE=%USERPROFILE%\.ssh\id_ed25519"
)
if not defined KEYFILE (
    set "SSH_AUTH=nokey"
    goto :eof
)
call :fix_key_perms "%KEYFILE%"
call :enable_ssh_443
echo       Testing SSH auth via ssh.github.com port 443...
ssh -p 443 -o HostName=ssh.github.com -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=20 -T git@github.com > "%SSHTEST%" 2>&1
findstr /C:"successfully authenticated" "%SSHTEST%" >nul 2>&1
if not errorlevel 1 (
    set "SSH_AUTH=ok"
    echo       [DIAG] SSH443 auth OK
    echo [DIAG] SSH443_AUTH_OK >> "%LOG%"
    goto :eof
)
findstr /C:"Permission denied" "%SSHTEST%" >nul 2>&1
if not errorlevel 1 (
    set "SSH_AUTH=denied"
    echo       [DIAG] SSH key exists but is NOT linked to GitHub
    echo [DIAG] SSH_AUTH_DENIED >> "%LOG%"
    type "%SSHTEST%" >> "%LOG%"
    goto :eof
)
set "SSH_AUTH=netfail"
echo       [DIAG] SSH443 network failed:
type "%SSHTEST%"
echo [DIAG] SSH443_NETFAIL >> "%LOG%"
type "%SSHTEST%" >> "%LOG%"
goto :eof

REM ===================== link SSH key to GitHub =====================
:upload_key
where gh >nul 2>&1
if not errorlevel 1 (
    gh auth status >nul 2>&1
    if not errorlevel 1 (
        echo       Uploading SSH key via GitHub CLI...
        gh ssh-key add "%PUBKEY%" --title "quant-windows-%COMPUTERNAME%" >> "%LOG%" 2>&1
        echo       Key upload attempted via gh.
        goto :eof
    )
)
echo       Copying public key to clipboard and opening GitHub key page...
if exist "%PUBKEY%" clip < "%PUBKEY%"
start "" https://github.com/settings/ssh/new
echo       In the browser: paste the key (already copied), give it a
echo       title, click "Add SSH key", then return here - it continues.
goto :eof

REM ===================== report a step =====================
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

REM ===================== smart clone: SSH443 -^> SSH22 -^> HTTPS(+proxy) =====================
:smart_clone
set "GC_DIR=%~1"
if exist "%GC_DIR%\.git" (
    set "CLONE_MODE=existing"
    goto :eof
)
echo       [1/3] Trying SSH over port 443 (best for CN networks)...
call :enable_ssh_443
set "GIT_SSH_COMMAND=ssh -p 443 -o HostName=ssh.github.com -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=20"
git clone "%~2" "%GC_DIR%" >> "%LOG%" 2>&1
if not errorlevel 1 (
    set "CLONE_MODE=ssh443"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"

echo       [2/3] Trying SSH over port 22...
set "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=15"
git clone "%~2" "%GC_DIR%" >> "%LOG%" 2>&1
if not errorlevel 1 (
    set "CLONE_MODE=ssh22"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"

echo       [3/3] Trying HTTPS (a browser sign-in window may open)...
set "GIT_SSH_COMMAND="
git config --global credential.helper manager >> "%LOG%" 2>&1
if defined PROXYPORT (
    git config --global http.proxy http://127.0.0.1:!PROXYPORT! >> "%LOG%" 2>&1
    git config --global https.proxy http://127.0.0.1:!PROXYPORT! >> "%LOG%" 2>&1
)
git clone "%~3" "%GC_DIR%" >> "%LOG%" 2>&1
if not errorlevel 1 (
    set "CLONE_MODE=https"
    goto :eof
)
if exist "%GC_DIR%" rmdir /s /q "%GC_DIR%"
set "CLONE_MODE=FAIL"
goto :eof

:main

REM ----- D drive -----
if not exist D:\ (
    echo [ERROR] D drive not found. This installer requires a D drive.
    pause
    exit /b 1
)

REM ----- single-instance lock -----
if exist "%LOCKDIR%" (
    set "LOCKAGE=fresh"
    for /f %%a in ('powershell -NoProfile -Command "try{if(((Get-Date)-(Get-Item 'D:\_qm_install.lock').CreationTime).TotalMinutes -gt 30){'stale'}else{'fresh'}}catch{'stale'}"') do set "LOCKAGE=%%a"
    if "!LOCKAGE!"=="stale" (
        rmdir /s /q "%LOCKDIR%" 2>nul
    ) else (
        echo ========================================
        echo   Another installer is already running.
        echo   This window closes in 8 seconds.
        echo   If sure nothing else runs, delete:
        echo     %LOCKDIR%
        echo ========================================
        timeout /t 8
        exit /b
    )
)
mkdir "%LOCKDIR%" 2>nul

REM ----- locate Git / Python -----
echo [1/5] Locating Git...
call :find_git
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Install Git for Windows from https://git-scm.com/download/win then run again.
    echo [ERROR] git-not-found >> "%LOG%"
    call :quit 1
)
echo       Git OK.

echo [2/5] Locating Python...
call :find_python
if not defined PYCMD (
    echo [ERROR] Python not found. Install Python 3.11 and tick "Add Python to PATH", then run again.
    echo [ERROR] python-not-found >> "%LOG%"
    call :quit 1
)
echo       Python OK (%PYCMD%).

echo [3/5] Preparing git identity and network diagnostics...
call :git_identity
call :detect_proxy

REM ----- SSH auth self-test; link key if needed; poll up to 5 minutes -----
echo [4/5] SSH authentication self-test...
call :ssh_auth_test
if "!SSH_AUTH!"=="denied" (
    call :upload_key
    echo       Waiting for the key to be linked (up to 5 minutes, retrying every 10s)...
    for /l %%n in (1,1,30) do (
        if not "!SSH_AUTH!"=="ok" (
            timeout /t 10 >nul
            call :ssh_auth_test
        )
    )
)
call :ssh_auth_test
echo       SSH auth result: !SSH_AUTH! (proxy: !PROXYPORT!)

REM ----- clone DATA repo, report ONLINE immediately -----
echo [5/5] Connecting data channel first...
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
    echo   [ERROR] Cannot reach GitHub on all channels.
    echo   Diagnosed cause and fix:
    echo ========================================
    if "!SSH_AUTH!"=="denied" echo   - SSH key not linked to GitHub. Add it at the page that opened ^(key was copied^).
    if "!SSH_AUTH!"=="nokey"   echo   - No SSH key could be created. Check %USERPROFILE%\.ssh permissions.
    if "!SSH_AUTH!"=="netfail" if not defined PROXYPORT echo   - Network blocks GitHub and NO local proxy found. Start your VPN/Clash, then run again.
    if "!SSH_AUTH!"=="netfail" if defined PROXYPORT     echo   - Network blocks GitHub even via proxy port !PROXYPORT!. Set proxy to global/TUN mode.
    echo   - If the repo reports 404/not-found, the key belongs to a different GitHub account.
    echo ----------------------------------------
    echo   Log tail ^(photo this screen if needed^):
    powershell -NoProfile -Command "Get-Content '%LOG%' -Tail 40"
    echo ========================================
    echo [%DATE% %TIME%] NETWORK_FAIL auth=!SSH_AUTH! proxy=!PROXYPORT! >> "%LOG%"
    call :quit 1
)
call :report ONLINE "connected via !CLONE_MODE!; auth=!SSH_AUTH!; proxy=!PROXYPORT!"
echo       Data channel connected via !CLONE_MODE!.

REM ----- clone/update CODE repo -----
echo Getting the latest code...
if exist "%INSTALL_DIR%\.git" (
    echo       Existing installation found, updating...
    call :enable_ssh_443
    cd /d "%INSTALL_DIR%"
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
    call :report FAILED "code clone failed"
    echo [ERROR] Could not get the code.
    powershell -NoProfile -Command "Get-Content '%LOG%' -Tail 25"
    call :quit 1
)
call :report CODE_READY "code at %INSTALL_DIR% via !CLONE_MODE!"
echo       Code ready via !CLONE_MODE!.

REM ----- run in-repo setup -----
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
    call :report FAILED "setup.py rc=%RC%"
    echo ========================================
    echo   SETUP REPORTED AN ERROR (code %RC%).
    echo   Details: %LOG%
    echo   and %INSTALL_DIR%\install_setup.log
    echo ========================================
)
call :quit %RC%
