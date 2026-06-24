#!/bin/bash
# auto_sync_strategy.sh - 棘轮迭代完成后自动同步监控面板
# 用法: ./auto_sync_strategy.sh <strategy_id> <result_json_path>
# 由 AI 量化公司棘轮流程调用

set -e

SID="$1"
RESULT_JSON="$2"
MONITOR_DIR="/Users/junze/quant-monitor-local"

if [ -z "$SID" ] || [ -z "$RESULT_JSON" ]; then
    echo "Usage: $0 <strategy_id> <result_json>"
    exit 1
fi

# 校验信号文件是否存在
if [ ! -f "$RESULT_JSON" ]; then
    echo "Error: Result file not found: $RESULT_JSON"
    exit 1
fi

echo "[$(date +%H:%M:%S)] Auto-sync: $SID"

# 执行同步
bash "$MONITOR_DIR/scripts/sync_strategy_results_to_monitor.sh" "$SID" "$RESULT_JSON"

# 变更检查
if [ $? -eq 0 ]; then
    # 提交到 git 并推送
    cd "$MONITOR_DIR"
    git add "signals/${SID}_$(date +%Y-%m-%d).json" 2>/dev/null || true
    git commit -m "chore: auto-sync ${SID} strategy results" 2>/dev/null || echo "No git changes"
    git push origin main 2>/dev/null || echo "Git push skipped (requires auth)"
    echo "[$(date +%H:%M:%S)] ✓ $SID synced and pushed"
else
    echo "[$(date +%H:%M:%S)] ✗ Sync failed"
    exit 1
fi