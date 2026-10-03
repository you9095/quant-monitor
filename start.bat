@echo off
cd /d "%~dp0"
echo ========================================
echo   Starting AI Quant Monitor (Simulation)
echo ========================================
echo.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run deploy_all.bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe run_simulation.py
pause
