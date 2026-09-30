#!/bin/bash
# ============================================================================
# daily_catchup_runner.sh — 自动补跑 + 当日运行（2026-09-20 根治断更）
# ============================================================================
# 设计目标（解决 cron 休眠错过任务、数据源延迟、脚本被跳过等问题）:
#   1. 幂等: 可在任意时间重复运行, 自动检测最近 LOOKBACK 个工作日中
#      哪些交易日缺 work_logs, 逐日补跑, 已存在的不重跑
#   2. 先拉最新 ETF K 线（akshare 主源, 新浪 fallback）
#   3. 对每个缺失工作日调用 daily_runner_v2.py --date <日期>（5 个 ETF 策略）
#   4. goldcombo(黄金组合A策略): venv 增量更新 V24 池 K 线 + goldcombo_daily_run.py
#      逐日真实模拟（实盘起点 2026-09-21, 起点前留空）；棘轮回测绝不写 work_logs
#   5. 全部完成后从 work_logs 全量重建 signals（6 策略统一, 禁止快照）
#   6. launchd 在唤醒后会补跑本脚本, 因此电脑休眠/关机也不会断更
#
# 由 launchd 每个工作日 17:45 与 20:15 各触发一次（20:15 为数据源延迟兜底）。
# ============================================================================
set -uo pipefail

export NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""

PYTHON="/usr/local/bin/python3"
P7="/Users/junze/.hermes/scripts/p7"
P6="/Users/junze/.hermes/scripts/p6"
MONITOR="/Users/junze/quant-monitor-local"
WORK_LOGS="/Users/junze/.hermes/work_logs"
LOG_FILE="/Users/junze/.hermes/logs/daily_catchup.log"
LOOKBACK=12   # 向前检查的自然日数（覆盖周末/节假日/短假期）

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

SIDS=("qixing" "r32" "zhuidian" "sanhe" "lightning")

log "================ daily_catchup_runner 开始 ================"

# ---------- 1. 拉取最新 ETF K 线 ----------
log "[1/5] 拉取最新 ETF K 线"
if "$PYTHON" "$P6/fetch_etf_kline.py" --days 20 >>"$LOG_FILE" 2>&1; then
  log "  ✅ K 线拉取完成"
else
  log "  ⚠️ K 线拉取部分失败（将使用本地已有数据继续）"
fi

# ---------- 2. 计算最近 LOOKBACK 天中的工作日，并检测缺失 ----------
log "[2/5] 检测缺失交易日"
MISSING_DATES=()
for ((i=1; i<=LOOKBACK; i++)); do
  D=$(date -v-${i}d '+%Y-%m-%d' 2>/dev/null)
  DOW=$(date -v-${i}d '+%u' 2>/dev/null)   # 1=周一 ... 7=周日
  [ "$DOW" -ge 6 ] && continue               # 跳过周末
  # 2026-09-20 加固: 不能只看文件是否存在(0 字节空文件=历史失败遗留会造成"假完整")。
  # 必须 5 个策略当日日志都【非空且含 afternoon session】才算生成成功;
  # qixing 以 _fusion 文件为准(普通文件是单日直跑、口径不同)。任一无效即判定需补跑。
  day_ok=1
  for sid in qixing r32 zhuidian sanhe lightning; do
    if [ "$sid" = "qixing" ]; then
      lf="$WORK_LOGS/qixing/qixing_${D}_fusion.json"
    else
      lf="$WORK_LOGS/${sid}/${sid}_${D}.json"
    fi
    if [ ! -s "$lf" ] || ! grep -q "afternoon" "$lf" 2>/dev/null; then
      day_ok=0
      break
    fi
  done
  if [ "$day_ok" -eq 0 ]; then
    MISSING_DATES+=("$D")
  fi
done

# ---------- 3. 逐日补跑（旧 → 新）----------
if [ ${#MISSING_DATES[@]} -eq 0 ]; then
  log "[3/5] 无缺失交易日，无需补跑"
else
  log "[3/5] 发现 ${#MISSING_DATES[@]} 个缺失交易日，按时间顺序补跑"
  # 倒序数组 → 正序
  for ((idx=${#MISSING_DATES[@]}-1; idx>=0; idx--)); do
    D="${MISSING_DATES[$idx]}"
    # 数据可用性闸门: 本地 K 线必须已包含该日期, 否则跳过（禁止用旧数据切片假装当日）
    KLINE_LAST=$(tail -1 /Users/junze/qixing_data/etf_kline/510300.csv 2>/dev/null | awk -F',' '{print $1}')
    if [[ "$KLINE_LAST" < "$D" ]]; then
      log "  ⏭️  ${D} 跳过: 本地K线仅到 ${KLINE_LAST:-无}, 数据源尚未更新, 下次运行重试（不用旧数据假装）"
      continue
    fi
    log "  → 补跑 ${D}（K线已到 ${KLINE_LAST}）"
    if "$PYTHON" "$P7/daily_runner_v2.py" --date "${D}" --strategy all --skip-fetch >>"$LOG_FILE" 2>&1; then
      log "    ✅ ${D} 补跑成功"
    else
      log "    ❌ ${D} 补跑失败（可能该日非交易日，下次运行会重试）"
    fi
  done
fi

# ---------- 4. goldcombo(黄金组合A策略) 真实每日模拟（venv+backtrader，独立解释器）----------
# 2026-09-21 接入：与 5 个 ETF 策略严格同构的"真实行情逐日模拟"，实盘起点 2026-09-21。
# 铁律：棘轮回测/5Y 回测绝不写入 work_logs（规则7 物理隔离）；本步只跑每日引擎。
VENV_PY="/Users/junze/qixing_strategy/venv/bin/python"
GC_LIVE_START="2026-09-21"

log "[4/5] goldcombo V24 池真实 K 线增量更新"
# 数据下载只用 requests/pandas, 用系统 python(venv 无 requests); 每日引擎才必须用 venv(backtrader)
if "$PYTHON" "$MONITOR/scripts/fetch_v24_pool_kline.py" >>"$LOG_FILE" 2>&1; then
  log "  ✅ goldcombo V24 池 K 线更新完成"
else
  log "  ⚠️ goldcombo V24 池 K 线更新部分失败（用本地已有数据继续，不造数）"
fi

log "[4/5] goldcombo 真实每日模拟（实盘起点 ${GC_LIVE_START}，逐日补跑、幂等）"
V24_LAST=$(tail -1 "$MONITOR/data/v24_etf_kline/510300.csv" 2>/dev/null | awk -F',' '{print $1}')
for ((i=1; i<=LOOKBACK; i++)); do
  D=$(date -v-${i}d '+%Y-%m-%d' 2>/dev/null)
  DOW=$(date -v-${i}d '+%u' 2>/dev/null)   # 1=周一 ... 7=周日
  [ "$DOW" -ge 6 ] && continue
  [[ "$D" < "$GC_LIVE_START" ]] && continue  # 实盘起点之前一律不模拟、留空
  gf="$WORK_LOGS/goldcombo/goldcombo_${D}.json"
  if [ -s "$gf" ] && grep -q "afternoon" "$gf" 2>/dev/null; then
    continue  # 已存在有效当日日志，幂等跳过
  fi
  # 数据可用性闸门: V24 K 线必须已包含该日, 否则等下次（禁止用旧数据假装当日）
  if [[ "$V24_LAST" < "$D" ]]; then
    log "  ⏭️  goldcombo ${D} 跳过: V24 K线仅到 ${V24_LAST:-无}, 数据源未更新, 下次重试"
    continue
  fi
  log "  → goldcombo 真实模拟 ${D}（V24 K线到 ${V24_LAST}）"
  if "$VENV_PY" "$MONITOR/scripts/goldcombo_daily_run.py" --date "$D" >>"$LOG_FILE" 2>&1; then
    log "    ✅ goldcombo ${D} 真实模拟完成"
  else
    log "    ❌ goldcombo ${D} 模拟失败（下次运行重试）"
  fi
done

# ---------- 5. 从 work_logs 全量重建 signals（6 策略统一，禁止快照）----------
log "[5/5] 从 work_logs 全量重建 signals（含 goldcombo）"
if "$PYTHON" "$MONITOR/scripts/rebuild_signals_from_worklogs.py" >>"$LOG_FILE" 2>&1; then
  log "  ✅ 全部策略 signals 重建完成"
else
  log "  ❌ signals 重建失败"
fi

log "================ daily_catchup_runner 结束 ================"
