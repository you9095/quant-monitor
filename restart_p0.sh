#!/bin/bash
# §15 P0 自动重启脚本 - Flask + cloudflared
# 用法: bash restart.sh
# 修改完成后立即全自动重启，不询问

set -e

PROJECT_DIR="/Users/junze/quant-monitor-local"
DEFAULT_PORT=8000
PORT="${1:-$DEFAULT_PORT}"

echo "=== §15 P0 自动重启 ==="

# Step 1: Kill cloudflared残留 + bootout launchd
echo "[1/5] Killing cloudflared残留 + bootout launchd..."
launchctl bootout gui/501 ai.quant.cloudflared 2>/dev/null || true
pkill -f cloudflared 2>/dev/null || true
sleep 2

# Step 2: Kill Flask进程 + bootout launchd
echo "[2/5] Killing Flask进程 + bootout launchd..."
launchctl bootout gui/501 ai.quant.flask 2>/dev/null || true
pkill -f "real_data_server_v2.py" 2>/dev/null || true
sleep 2

# Step 3: Re-bootstrap Flask
echo "[3/5] Re-bootstrap Flask..."
cd "$PROJECT_DIR"
source api/venv/bin/activate
nohup python api/real_data_server_v2.py > logs/server.log 2>&1 &
FLASK_PID=$!
echo "Flask started with PID $FLASK_PID"

# Health check
echo "[3/5] Waiting for Flask health check..."
for i in {1..15}; do
    sleep 1
    if curl -fsS "http://localhost:$PORT/api/v1/health" &>/dev/null; then
        echo "✓ Flask health check through (PID=$FLASK_PID)"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "✗ Flask启动超时，日志："
        tail -20 logs/server.log
        kill "$FLASK_PID" 2>/dev/null
        exit 1
    fi
    echo -n "."
done
echo ""

# Step 4: Re-bootstrap cloudflared (terminal background fallback)
echo "[4/5] Re-bootstrap cloudflared (fallback: terminal background)..."
/Users/junze/npm-global/lib/node_modules/cloudflared/bin/cloudflared tunnel     --url http://127.0.0.1:8000     --no-autoupdate     --protocol http2     > ~/.hermes/logs/cf-qm-tunnel.log 2>&1 &
CLOUDFLARED_PID=$!
echo "cloudflared started with PID $CLOUDFLARED_PID"
sleep 5

# Step 5: 端到端 5 API 验证
echo "[5/5] 端到端 5 API 验证..."
TUNNEL_URL=$(grep -oP 'https://\S+' ~/.hermes/logs/cf-qm-tunnel.log | head -1)
if [ -z "$TUNNEL_URL" ]; then
    echo "✗ 无法获取隧道URL，请检查 ~/.hermes/logs/cf-qm-tunnel.log"
    exit 1
fi
echo "隧道URL: $TUNNEL_URL"

SUCCESS=0
TOTAL=5
for endpoint in "/" "/api/v1/health" "/api/v1/strategies" "/api/v1/dashboard/portfolio_summary" "/api/v1/dashboard/overview"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$TUNNEL_URL$endpoint")
    if [ "$code" = "200" ]; then
        echo "  ✓ $endpoint -> 200"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "  ✗ $endpoint -> $code"
    fi
done

echo ""
echo "=== 结果: $SUCCESS/$TOTAL API 返回 200 ==="

if [ "$SUCCESS" -eq "$TOTAL" ]; then
    echo "✓ §15 P0 验证通过：全部 5 API 200"
    exit 0
else
    echo "✗ §15 P0 验证失败：$((TOTAL - SUCCESS)) 个 API 非 200"
    exit 1
fi
