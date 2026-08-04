#!/bin/bash
# M03 Audit: 组合总览 + 首页渲染验证
# Date: 2026-08-04
# Repo: /Users/junze/quant-monitor-local
# Live URL: https://you9095.github.io/quant-monitor/
# CDP Port: 9222

set -e

echo "=========================================="
echo "M03 Audit Command Script"
echo "=========================================="
echo ""

# === STEP 1: Verify local repo state ===
echo "[1/6] Repo state"
cd /Users/junze/quant-monitor-local
echo "  HEAD: $(git rev-parse HEAD)"
echo "  Last commit: $(git log --oneline -1)"
echo "  index.html size: $(wc -c < index.html) bytes"
echo "  assets/data.js size: $(wc -c < assets/data.js) bytes"
echo ""

# === STEP 2: Verify portfolio stats in source ===
echo "[2/6] Portfolio stats in index.html"
grep -n 'total_value\|total_pnl\|total_return_pct\|ps-pnl\|ps-return\|ps-total\|ps-initial' index.html | grep -v '//' | head -20
echo ""

# === STEP 3: Verify mockData portfolio values ===
echo "[3/6] mockData portfolio values in assets/data.js"
grep -n 'total_value\|total_pnl\|total_return_pct' assets/data.js | head -10
echo ""

# === STEP 4: Verify today's action bar signals ===
echo "[4/6] Today's action bar - signal sources"
echo "  --- signals latest dates ---"
for f in signals/qixing_2026-08-03.json signals/r32_2026-08-03.json signals/sanhe_2026-08-03.json signals/lightning_2026-08-03.json; do
    [ -f "$f" ] && echo "  EXISTS: $f ($(wc -c < "$f") bytes)" || echo "  MISSING: $f"
done
echo "  zhuidian latest: $(ls -t signals/zhuidian_*.json 2>/dev/null | head -1)"
echo ""

# === STEP 5: Verify action bar rendering logic ===
echo "[5/6] Action bar rendering logic"
grep -n 'renderActionItems\|today_action\|action-bar\|MAX_STALE_DAYS\|isStrategyActive\|activeStrategies' index.html | head -20
echo ""

# === STEP 6: Local static serve + browser verification ===
echo "[6/6] Local static serve verification"
echo "  Starting python3 http.server on port 8765..."
python3 -m http.server 8765 > /dev/null 2>&1 &
SERVER_PID=$!
sleep 1
echo "  Server PID: $SERVER_PID"
echo "  Curl status: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8765/)"
echo ""
echo "  --- DOM verification ---"
echo "  Portfolio summary elements:"
grep -o 'ps-pnl\|ps-return\|ps-total\|ps-initial\|总盈亏\|总资金\|收益率\|今日动作\|action-bar' index.html | sort -u
echo ""
echo "  Stopping server..."
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
echo "  Server stopped."

echo ""
echo "=========================================="
echo "M03 Audit Complete"
echo "=========================================="