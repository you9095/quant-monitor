#!/bin/bash
# ============================================================
# 一键启动 AI 量化监控面板（macOS）
# 双击本文件：若 8000 数据后台没运行就自动拉起，然后用默认浏览器打开实盘页。
# 也可以直接双击 index.html —— 后台在运行时同样能打开（页面会自动连本机 8000）。
# 模拟盘、本机真实撮合，不连接任何券商真实账号。
# ============================================================
cd "$(dirname "$0")" || exit 1
PORT=8000
URL="http://localhost:${PORT}/?data_mode=live"

port_listening() { lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; }

if ! port_listening; then
  echo "数据后台未运行，正在启动（端口 ${PORT}）..."
  # 优先交给 launchd 常驻服务（若已安装）
  launchctl kickstart -k "gui/$(id -u)/ai.quant.flask" >/dev/null 2>&1
  i=0
  while [ $i -lt 20 ]; do
    if port_listening; then break; fi
    sleep 1
    i=$((i+1))
    # launchd 不顶用时，第 5 秒直接后台拉起
    if [ "$i" -eq 5 ] && ! port_listening; then
      if [ -x "api/venv/bin/python" ]; then PY="api/venv/bin/python"; else PY="/usr/local/bin/python3"; fi
      mkdir -p logs
      nohup "$PY" api/real_data_server_v2.py >> logs/panel_launch.log 2>&1 &
    fi
  done
fi

if port_listening; then
  echo "数据后台已就绪，打开面板：${URL}"
  open "${URL}"
else
  echo "后台 30 秒内未启动，请查看 logs/panel_launch.log"
fi
sleep 2
exit 0
