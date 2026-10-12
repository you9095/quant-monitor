@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title AI Quant - One Click Fix and Trade

if exist "D:\quant-monitor\daily_task.py" (cd /d "D:\quant-monitor") else (cd /d "%~dp0")

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] 未找到 venv\Scripts\python.exe
    echo 当前目录: %CD%
    echo 请确认本项目位于 D:\quant-monitor，或重新运行安装器。
    pause
    exit /b 1
)
set "VPY=venv\Scripts\python.exe"
echo Working dir : %CD%
echo Python      : %VPY%
echo.

echo ===== STEP 1/6  更新代码 =====
git fetch origin master
git reset --hard origin/master
echo.

echo ===== STEP 2/6  检查依赖 =====
"%VPY%" -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo dependencies ready.
echo.

echo ===== STEP 3/6  按今日真实收盘价成交（本机撮合，不接券商） =====
"%VPY%" trade_supervisor.py --guard
echo.

echo ===== STEP 4/6  上传实盘数据到 GitHub =====
"%VPY%" scripts\sync_live_data.py push
echo.

echo ===== STEP 5/6  启动数据后台（新窗口，请勿关闭） =====
start "Quant Backend - DO NOT CLOSE" cmd /k "set PYTHONUTF8=1 && venv\Scripts\python.exe api\real_data_server_v2.py"
echo 后台启动中，等待 10 秒就绪...
timeout /t 10 /nobreak >nul
echo.

echo ===== STEP 6/6  打开实盘面板 =====
start "" "http://localhost:8000/?data_mode=live"
echo.

echo ============================================
echo   ALL DONE - 面板应已在浏览器打开。
echo   若后台窗口有红色报错，请勿关闭该窗口。
echo ============================================
pause
