#!/bin/bash
# ============================================================
# 一键启动 AI 量化监控面板（macOS）
# 双击本文件：交给统一启动器确保 8000 后台在运行，然后用默认浏览器打开实盘页。
# 主路径仍是双击 index.html（后台在运行时直接可用；未运行可在页面里点绿色按钮）。
# 模拟盘、本机真实撮合，不连接任何券商真实账号。
# ============================================================
cd "$(dirname "$0")" || exit 1
PY="$(pwd)/api/venv/bin/python"
if [ ! -x "$PY" ]; then PY=/usr/local/bin/python3; fi

"$PY" "$(pwd)/scripts/launch_panel.py"
open "http://localhost:8000/?data_mode=live"
exit 0
