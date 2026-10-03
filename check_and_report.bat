@echo off
cd /d "%~dp0"
echo ========================================
echo   Check and Report Deploy Status
echo ========================================
echo.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run deploy_all.bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe scripts\report_deploy.py
echo.
pause
