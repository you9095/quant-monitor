@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ============================================
echo   AI Quant - Daily Trade Chain (Simulation)
echo   Local matching, NO real broker account.
echo ============================================
echo.
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" daily_task.py trade
) else (
    if exist "api\venv\Scripts\python.exe" (
        "api\venv\Scripts\python.exe" daily_task.py trade
    ) else (
        py -3 daily_task.py trade
    )
)
echo.
echo ============================================
echo   Chain finished. Read messages above.
echo ============================================
pause
