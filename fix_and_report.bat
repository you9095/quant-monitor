@echo off
cd /d "%~dp0"
echo ========================================
echo   Fix git linkage and report status
echo ========================================
echo.
venv\Scripts\python.exe scripts\fix_and_report.py
if errorlevel 1 python scripts\fix_and_report.py
echo.
echo Result saved to fix_result.txt
pause
