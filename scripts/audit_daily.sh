#!/bin/bash
# quant-monitor 每日 14:30 数据完整性 audit
# 2026-07-30 P0 反馈:sanhe 陈旧 17 天 / zhuidian today_pnl 超 -10% 红线
#                  / review/dates 缺 3 天 → 加 sanity check 兜底
#
# Cron 建议: 14 30 * * * /Users/junze/quant-monitor-local/scripts/audit_daily.sh
#
# 退出码: 0=全部 OK, 1=发现问题(飞书告警)

set -euo pipefail

PROJECT_DIR="/Users/junze/quant-monitor-local"
SIGNALS_DIR="$PROJECT_DIR/signals"
REVIEW_DIR="$PROJECT_DIR/review"
LOG_FILE="$PROJECT_DIR/logs/audit_daily.log"
FAIL_COUNT=0
WARNINGS=""

# 当前日期(用本地时区,避免 UTC 误判)
TODAY=$(date +%Y-%m-%d)
STALE_THRESHOLD_DAYS=5
MISSING_REVIEW_THRESHOLD_DAYS=2

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== 每日 audit 开始 ==="
log "今天: $TODAY"
log "陈旧阈值: ${STALE_THRESHOLD_DAYS} 天 / review 缺失阈值: ${MISSING_REVIEW_THRESHOLD_DAYS} 天"

# === 1. signals/ 5 策略数据陈旧检查 ===
log ""
log "--- 1. signals/ 5 策略数据陈旧检查 ---"
for sid in qixing r32 zhuidian sanhe lightning; do
  latest_file=$(ls -t "$SIGNALS_DIR"/${sid}_*.json 2>/dev/null | head -1 || echo "")
  if [ -z "$latest_file" ]; then
    log "  ❌ $sid: 无任何 signal 文件"
    FAIL_COUNT=$((FAIL_COUNT+1))
    WARNINGS="$WARNINGS\n$sid: 无 signal 文件"
    continue
  fi
  latest_date=$(basename "$latest_file" .json | sed "s/${sid}_//")
  gap_days=$(( ( $(date -j -f "%Y-%m-%d" "$TODAY" +%s 2>/dev/null || date -d "$TODAY" +%s) - $(date -j -f "%Y-%m-%d" "$latest_date" +%s 2>/dev/null || date -d "$latest_date" +%s) ) / 86400 ))
  if [ "$gap_days" -gt "$STALE_THRESHOLD_DAYS" ]; then
    log "  ❌ $sid: 最新 $latest_date ($gap_days 天前) > ${STALE_THRESHOLD_DAYS} 天红线"
    FAIL_COUNT=$((FAIL_COUNT+1))
    WARNINGS="$WARNINGS\n$sid: 数据陈旧 $gap_days 天 (最新 $latest_date)"
  else
    log "  ✅ $sid: 最新 $latest_date ($gap_days 天)"
  fi
done

# === 2. signals/ today_pnl 红线检查 ===
log ""
log "--- 2. signals/ today_pnl 红线检查 (|today_pnl| < IC × 10%) ---"
for sid in qixing r32 zhuidian sanhe lightning; do
  latest_file=$(ls -t "$SIGNALS_DIR"/${sid}_*.json 2>/dev/null | head -1 || echo "")
  [ -z "$latest_file" ] && continue
  today_pnl=$(/usr/bin/python3 -c "import json; d=json.load(open('$latest_file')); print(d.get('today_pnl', 0))" 2>/dev/null || echo "0")
  ic=$(/usr/bin/python3 -c "import json; d=json.load(open('$latest_file')); print(d.get('initial_capital', 10000))" 2>/dev/null || echo "10000")
  threshold=$(/usr/bin/python3 -c "print($ic * 0.10)")
  abs_pnl=$(/usr/bin/python3 -c "print(abs($today_pnl))")
  if [ "$(/usr/bin/python3 -c "print(1 if $abs_pnl >= $threshold else 0)")" = "1" ]; then
    log "  ❌ $sid: today_pnl=$today_pnl 超红线 ±$threshold (IC=$ic)"
    FAIL_COUNT=$((FAIL_COUNT+1))
    WARNINGS="$WARNINGS\n$sid: today_pnl=$today_pnl 超 -10% 红线 ±$threshold"
  else
    log "  ✅ $sid: today_pnl=$today_pnl (红线 ±$threshold)"
  fi
done

# === 3. review/ 缺失检查 ===
log ""
log "--- 3. review/ 缺失检查 (≥ ${MISSING_REVIEW_THRESHOLD_DAYS} 天没生成则 FAIL) ---"
if [ -d "$REVIEW_DIR" ]; then
  latest_review=$(ls -t "$REVIEW_DIR"/*.json 2>/dev/null | head -1 || echo "")
  if [ -z "$latest_review" ]; then
    log "  ❌ review/: 无任何 review 文件"
    FAIL_COUNT=$((FAIL_COUNT+1))
    WARNINGS="$WARNINGS\nreview/: 无 review 文件"
  else
    latest_review_date=$(basename "$latest_review" .json | cut -c1-10)
    gap_days=$(( ( $(date -j -f "%Y-%m-%d" "$TODAY" +%s 2>/dev/null || date -d "$TODAY" +%s) - $(date -j -f "%Y-%m-%d" "$latest_review_date" +%s 2>/dev/null || date -d "$latest_review_date" +%s) ) / 86400 ))
    if [ "$gap_days" -ge "$MISSING_REVIEW_THRESHOLD_DAYS" ]; then
      log "  ❌ review/: 最新 $latest_review_date ($gap_days 天前) ≥ ${MISSING_REVIEW_THRESHOLD_DAYS} 天红线"
      FAIL_COUNT=$((FAIL_COUNT+1))
      WARNINGS="$WARNINGS\nreview/: 缺 $gap_days 天(最新 $latest_review_date)"
    else
      log "  ✅ review/: 最新 $latest_review_date ($gap_days 天)"
    fi
  fi
else
  log "  ❌ review/: 目录不存在"
  FAIL_COUNT=$((FAIL_COUNT+1))
  WARNINGS="$WARNINGS\nreview/: 目录不存在"
fi

# === 总结 + 飞书告警 ===
log ""
log "=== audit 总结 ==="
log "FAIL 总数: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  log "⚠️  告警:发现 $FAIL_COUNT 个问题"
  log "详情:$(echo -e "$WARNINGS")"
  # 飞书告警(如果配置了 webhook)
  if [ -n "${FEISHU_WEBHOOK:-}" ]; then
    msg=$(printf '{"msg_type":"text","content":{"text":"quant-monitor 每日 audit 告警: %d 个问题\\n%s"}}' "$FAIL_COUNT" "$WARNINGS")
    curl -s -X POST -H "Content-Type: application/json" -d "$msg" "$FEISHU_WEBHOOK" || log "飞书告警失败(可忽略)"
  fi
  exit 1
else
  log "✅ 全部 OK,无需告警"
  exit 0
fi
