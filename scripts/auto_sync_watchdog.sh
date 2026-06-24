#!/bin/bash
# auto_sync_watchdog.sh - 策略结果自动同步看门狗
# 每 5 分钟检查一次，若发现新的棘轮结果文件则自动同步
# 由 cron 定时任务触发

MONITOR_DIR="/Users/junze/quant-monitor-local"
RESULTS_DIRS=(
    "/Users/junze/.hermes/outputs/ai_quant_qixing_ratchet_2026-06-14"
    "/Users/junze/.hermes/outputs/ai_quant_r32_ratchet_2026-06-14"
    "/Users/junze/.hermes/outputs/ai_quant_lightning_ratchet_2026-06-14"
    "/Users/junze/.hermes/outputs/ai_quant_sanhe_ratchet_2026-06-14"
    "/Users/junze/.hermes/outputs/ai_quant_zhuidian_ratchet_2026-06-14"
)

# 策略映射
declare -A STRATEGY_MAP
STRATEGY_MAP["qixing"]="qixing_5rounds_R121_R125.json"
STRATEGY_MAP["r32"]="r32_5rounds_R33_R37.json"
STRATEGY_MAP["lightning"]="lightning_5rounds_R5_R9.json"

# 检查每个策略
for sid in "${!STRATEGY_MAP[@]}"; do
    result_file="${RESULTS_DIRS[0]}/qixing_5rounds_R121_R125.json"
    case $sid in
        "qixing") result_file="/Users/junze/.hermes/outputs/ai_quant_qixing_ratchet_2026-06-14/qixing_5rounds_R121_R125.json" ;;
        "r32") result_file="/Users/junze/.hermes/outputs/ai_quant_r32_ratchet_2026-06-14/r32_5rounds_R33_R37.json" ;;
        "lightning") result_file="/Users/junze/.hermes/outputs/ai_quant_lightning_ratchet_2026-06-14/lightning_5rounds_R5_R9.json" ;;
    esac
    
    # 检查信号文件是否存在今天的日期
    today=$(date +%Y-%m-%d)
    signal_file="$MONITOR_DIR/signals/${sid}_${today}.json"
    
    if [ -f "$result_file" ] && [ ! -f "$signal_file" ]; then
        echo "[$(date +%H:%M:%S)] Found new $sid results, syncing..."
        bash "$MONITOR_DIR/scripts/sync_strategy_results_to_monitor.sh" "$sid" "$result_file"
    fi
done

echo "[$(date +%H:%M:%S)] Watchdog check complete"