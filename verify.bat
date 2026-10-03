@echo off
cd /d "%~dp0"
echo ========================================
echo   Environment Check
echo ========================================
echo.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run deploy_all.bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe verify_environment.py
pause
