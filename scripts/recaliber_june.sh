#!/bin/bash
# ============================================================================
# recaliber_june.sh — 统一历史 work_logs 本金口径（2026-09-20 数据真实性根治）
# ----------------------------------------------------------------------------
# 背景: 2026-06-08~06-25 的 work_logs 是 10 万本金旧口径, 06-26 起切换为 1 万本金。
#       混口径导致收益曲线本金跳变、每日盈亏趋势逐日 total 累加虚高。
# 做法: 以真实 K 线交易日为准, 用 daily_runner_v2（固定 1 万本金、当前上线参数、
#       真实历史 K 线切片）逐日重跑 06-08~06-25, 覆盖旧日志, 得到一条自洽的
#       "当前策略 + 固定本金 + 真实行情" 模拟交易曲线。
# 幂等: 可重复运行, 每天用 'w' 模式覆盖。
# ============================================================================
set -uo pipefail
export NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""

PYTHON="/usr/local/bin/python3"
P7="/Users/junze/.hermes/scripts/p7"
KLINE="/Users/junze/qixing_data/etf_kline/510300.csv"
LOG="/tmp/recaliber_june.log"

START="2026-06-08"
END="2026-06-25"

echo "[$(date '+%F %T')] === 6月旧口径统一重跑开始 $START ~ $END ===" | tee "$LOG"

# 取 K 线中 [START, END] 区间内真实交易日
DATES=$($PYTHON - "$KLINE" "$START" "$END" <<'PY'
import sys, csv
kline, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
with open(kline) as f:
    for row in csv.DictReader(f):
        d = row['date']
        if start <= d <= end:
            print(d)
PY
)

for D in $DATES; do
  echo "[$(date '+%F %T')] → 重跑 ${D}" | tee -a "$LOG"
  if "$PYTHON" "$P7/daily_runner_v2.py" --date "${D}" --strategy all --skip-fetch >>"$LOG" 2>&1; then
    echo "[$(date '+%F %T')]   ✅ ${D} 完成" | tee -a "$LOG"
  else
    echo "[$(date '+%F %T')]   ❌ ${D} 失败" | tee -a "$LOG"
  fi
done

echo "[$(date '+%F %T')] === 重跑结束, 重建 signals ===" | tee -a "$LOG"
"$PYTHON" /Users/junze/quant-monitor-local/scripts/rebuild_signals_from_worklogs.py --keep-goldcombo >>"$LOG" 2>&1
echo "[$(date '+%F %T')] === 全部完成 ===" | tee -a "$LOG"
