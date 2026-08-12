#!/bin/bash
#
# goldcombo · 黄金组合A 棘轮迭代 cron 启动脚本
# 触发时间: 2026-08-13 02:30
# 任务: 跑 R1-R50 棘轮迭代 + 备份节点 + 详细报告
# 触发词: goldcombo ratchet / 棘轮迭代
#
# 用法:
#   /Users/junze/quant-monitor-local/scripts/run_goldcombo_ratchet_cron.sh
#
# 幂等: 再跑一遍不会重新覆盖已有产物 (除非 --force)
# 串行依赖: 等 ratchet_baseline.json 存在, 最长等 10 分钟
#

set -e

WORKSPACE="/Users/junze/quant-monitor-local"
VENV_PY="/Users/junze/qixing_strategy/venv/bin/python"
STRATEGY_DIR="$WORKSPACE/strategies/goldcombo"
LOG_DIR="$WORKSPACE/logs"
BASELINE_FILE="$STRATEGY_DIR/ratchet_baseline.json"

# 清理 PYTHONPATH 污染 (与策略代码 1:1)
unset PYTHONPATH

mkdir -p "$LOG_DIR"
mkdir -p "$STRATEGY_DIR"

LOG_FILE="$LOG_DIR/工作日志_2026-08-13_ratchet_goldcombo.md"

echo "[run_goldcombo_ratchet_cron] === START $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG_FILE"

# 串行依赖: 等 ratchet_baseline.json 存在 (最多 10 分钟)
WAIT_COUNT=0
MAX_WAIT=10  # 10 分钟
while [ ! -f "$BASELINE_FILE" ]; do
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "[run_goldcombo_ratchet_cron] ❌ FAIL: $BASELINE_FILE 不存在, 等待超时 (10 分钟)" | tee -a "$LOG_FILE"
        exit 1
    fi
    echo "[run_goldcombo_ratchet_cron] 等待 $BASELINE_FILE ... ($WAIT_COUNT/$MAX_WAIT 分钟)" | tee -a "$LOG_FILE"
    sleep 60
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

echo "[run_goldcombo_ratchet_cron] ✅ 基线文件存在: $BASELINE_FILE" | tee -a "$LOG_FILE"

# 跑棘轮迭代 (R1-R50)
cd "$STRATEGY_DIR"
"$VENV_PY" "$STRATEGY_DIR/goldcombo_ratchet_v2.py" \
    --start-round 1 \
    --end-round 50 \
    --baseline-path "$BASELINE_FILE" \
    --output-path "$STRATEGY_DIR/ratchet_log.json" \
    --report-prefix "ratchet_report" \
    --backup-prefix "ratchet_backup" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo "[run_goldcombo_ratchet_cron] === END $(date '+%Y-%m-%d %H:%M:%S') exit=$EXIT_CODE ===" | tee -a "$LOG_FILE"

exit $EXIT_CODE