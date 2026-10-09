#!/bin/bash
# ============================================================
# 一键启动 AI 量化监控面板（macOS）
# 双击本文件：交给统一启动器确保 8000 后台在运行，就绪后自动用默认浏览器
# 打开同源面板 http://localhost:8000/（默认模拟盘，页面内可切实盘模拟）。
# 模拟盘、本机真实撮合，不连接任何券商真实账号。
# ============================================================
cd "$(dirname "$0")" || exit 1
PY="$(pwd)/api/venv/bin/python"
if [ ! -x "$PY" ]; then PY=/usr/local/bin/python3; fi

"$PY" "$(pwd)/scripts/launch_panel.py" --open
exit 0
