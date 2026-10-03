@echo off
cd /d "%~dp0"
echo ========================================
echo   AI Quant Monitor - One-click Deploy
echo   Simulation mode (no real broker)
echo ========================================
echo.

REM Try python launcher first
python --version >nul 2>&1
if not errorlevel 1 goto :has_python

REM Try py launcher
py -3 --version >nul 2>&1
if not errorlevel 1 goto :has_py

REM No Python found, download and install
echo [1/3] Python not found. Downloading Python 3.11 ...
powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\py311.exe'"
if not exist "%TEMP%\py311.exe" goto :download_fail
echo Installing Python, please wait 1-2 minutes ...
start /wait "" "%TEMP%\py311.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
del "%TEMP%\py311.exe"
set "PATH=C:\Program Files\Python311;C:\Program Files\Python311\Scripts;%PATH%"
python --version >nul 2>&1
if not errorlevel 1 goto :has_python
echo.
echo [ERROR] Python installed but not recognized.
echo Please open a NEW terminal and run this script again.
echo.
pause
exit /b 1

:has_py
echo [1/3] Python found (py launcher)
py -3 setup.py
goto :done

:has_python
echo [1/3] Python found
python setup.py
goto :done

:download_fail
echo.
echo [ERROR] Python download failed.
echo Please install Python 3.11 manually: https://www.python.org/downloads/
echo.
pause
exit /b 1

:done
echo.
echo Deploy script finished.
pause
