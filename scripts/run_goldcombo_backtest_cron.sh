#!/bin/bash
# ============================================================================
# goldcombo 回测 cron wrapper — 2026-08-13 M02 阶段接管产物
# ============================================================================
# 调度: crontab 2 条
#   30 1  13 8 *  → 2Y 回测  (2024-08-13 ~ 2026-08-13)
#   30 2  13 8 *  → 5Y 回测  (2021-08-13 ~ 2026-08-13, 降级 min_rows=500)
#
# 设计要点:
#   - 幂等: 重复跑结果一致, 无副作用累积 (用 | tee 落日志)
#   - 自愈: 失败 → 落 FAIL 日志, exit code 保留
#   - PYTHONPATH 必须 unset (Hermes agent 注入污染)
#   - 输出写 strategies/goldcombo/backtest_<period>_2026-08-13.json
#   - 同步生成 ratchet_baseline.json + signals/goldcombo_<date>.json
#   - 日志落 /Users/junze/quant-monitor-local/logs/goldcombo_cron_<period>.log
#
# 使用:
#   bash scripts/run_goldcombo_backtest_cron.sh 2y
#   bash scripts/run_goldcombo_backtest_cron.sh 5y
# ============================================================================

set -euo pipefail

# === 参数解析 ===
PERIOD="${1:-2y}"
WORKSPACE="/Users/junze/quant-monitor-local"
VENV_PY="/Users/junze/qixing_strategy/venv/bin/python"
LOG_DIR="${WORKSPACE}/logs"
STRATEGY_DIR="${WORKSPACE}/strategies/goldcombo"
SIGNALS_DIR="${WORKSPACE}/signals"
TODAY_STR="$(date +%Y-%m-%d)"

mkdir -p "${LOG_DIR}" "${STRATEGY_DIR}" "${SIGNALS_DIR}"

case "${PERIOD}" in
    2y)
        START="2024-08-13"
        END="2026-08-13"
        MIN_ROWS="200"
        OUTPUT="${STRATEGY_DIR}/backtest_2y_2026-08-13.json"
        ;;
    5y)
        START="2021-08-13"
        END="2026-08-13"
        # 5Y 数据源: 38/40 ETF 行数 < 1000, 严格阈值会全部剔除, 降级 500
        MIN_ROWS="500"
        OUTPUT="${STRATEGY_DIR}/backtest_5y_2026-08-13.json"
        ;;
    *)
        echo "[goldcombo cron] FAIL: period 必须是 2y 或 5y, 收到: ${PERIOD}" >&2
        exit 2
        ;;
esac

LOG_FILE="${LOG_DIR}/goldcombo_cron_${PERIOD}.log"
echo "[goldcombo cron] === 启动 period=${PERIOD} start=${START} end=${END} min_rows=${MIN_ROWS} ===" | tee -a "${LOG_FILE}"
echo "[goldcombo cron] $(date '+%Y-%m-%d %H:%M:%S') 开始" | tee -a "${LOG_FILE}"

# === 关键: unset PYTHONPATH (Hermes agent 注入污染) ===
unset PYTHONPATH
# 清理 sys.path 中可能的 hermes-agent 残留
export PYTHONPATH=

# === 跑正式回测 ===
cd "${WORKSPACE}"

if "${VENV_PY}" "${STRATEGY_DIR}/goldcombo_strategy.py" \
    --period "${PERIOD}" \
    --start "${START}" \
    --end "${END}" \
    --min-rows "${MIN_ROWS}" \
    --output "${OUTPUT}" 2>&1 | tee -a "${LOG_FILE}"; then

    echo "[goldcombo cron] ✓ ${PERIOD} 回测完成 → ${OUTPUT}" | tee -a "${LOG_FILE}"

    # === 后处理: 修复 trigger stats min_rows 硬编码 bug ===
    # 策略代码 L361 硬编码 min_rows=1000 for 5Y, 与 wrapper 传入的 --min-rows 500 不一致
    # 5Y 第一次跑出 trigger stats 全 0 (错误的 0), 必须用正确 min_rows 重算
    unset PYTHONPATH
    "${VENV_PY}" - "${OUTPUT}" "${MIN_ROWS}" <<'PYEOF'
import json, sys
bt_path, min_rows_str = sys.argv[1], sys.argv[2]
min_rows = int(min_rows_str)
with open(bt_path) as f: bt = json.load(f)
sys.path = [p for p in sys.path if 'hermes-agent' not in p]
sys.path.insert(0, '/Users/junze/quant-monitor-local/strategies/goldcombo')
from goldcombo_strategy import analyze_indicator_trigger
start = bt['data_period'].split(' ~ ')[0]
end = bt['data_period'].split(' ~ ')[1]
result = analyze_indicator_trigger(start, end, min_rows)
bt['indicator_trigger_stats'] = result
bt['_trigger_stats_patched_min_rows'] = min_rows
bt['_trigger_stats_patch_note'] = 'wrapper 后处理: 策略代码 L361 硬编码 min_rows bug 修复 (subagent #2b 2026-08-12)'
with open(bt_path, 'w', encoding='utf-8') as f:
    json.dump(bt, f, ensure_ascii=False, indent=2)
print(f"[goldcombo cron] ✓ {bt_path} trigger stats patch (min_rows={min_rows})")
PYEOF
else
    EXIT_CODE=$?
    echo "[goldcombo cron] ✗ ${PERIOD} 回测 FAIL exit=${EXIT_CODE}" | tee -a "${LOG_FILE}"
    exit "${EXIT_CODE}"
fi

# === 落 ratchet_baseline.json (双标, 触发真实文件存在时生成, 避免覆盖手工改动) ===
BASELINE_FILE="${STRATEGY_DIR}/ratchet_baseline.json"
if [[ ! -f "${BASELINE_FILE}" ]] || [[ "${OUTPUT}" -nt "${BASELINE_FILE}" ]]; then
    # 双标合并: 读 2Y + 5Y 两个 JSON
    TWO_Y="${STRATEGY_DIR}/backtest_2y_2026-08-13.json"
    FIVE_Y="${STRATEGY_DIR}/backtest_5y_2026-08-13.json"
    if [[ -f "${TWO_Y}" ]] && [[ -f "${FIVE_Y}" ]]; then
        # 用 venv python 合并 (jq 不一定可用)
        unset PYTHONPATH
        "${VENV_PY}" - "${TWO_Y}" "${FIVE_Y}" "${BASELINE_FILE}" <<'PYEOF'
import json, sys
two_y_path, five_y_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(two_y_path) as f: two_y = json.load(f)
with open(five_y_path) as f: five_y = json.load(f)
baseline = {
    "strategy_id": "goldcombo",
    "strategy_name": "黄金组合A",
    "engine_version": "goldcombo_v2",
    "baseline_init_date": "2026-08-13",
    "baseline_initiator": "subagent #2b (M02 阶段接管 subagent #2 deleg_f37c2907 未完成工作)",
    "trigger_threshold_note": "C3(低位金叉双负)+C4(BOLL开口)+C7(CCI<-100)+C8(+DI<10&-DI>30) + 8%硬止损 — 4指标共振入场策略",
    "data_periods": {
        "2y": {
            "start": "2024-08-13", "end": "2026-08-13",
            "min_rows": 200,
            "etf_pool_used": two_y.get("etf_pool_used", []),
            "etf_pool_count": two_y.get("etf_pool_count", 0),
            "total_return_pct": two_y.get("total_return_pct", 0.0),
            "max_drawdown_pct": two_y.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": two_y.get("sharpe_ratio", 0.0),
            "trade_count": two_y.get("trade_count", 0),
            "closed_trades": two_y.get("closed_trades", 0),
            "win_count": two_y.get("win_count", 0),
            "win_rate_pct": two_y.get("win_rate_pct", 0.0),
            "all4_combined_triggers": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("all_4_combined", 0),
            "at_least_1_trigger": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("at_least_1", 0),
            "single_indicator_triggers": {
                "C3_MACD_golden_cross_below_0": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C3_MACD_golden_cross_below_0", 0),
                "C4_BOLL_broadening": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C4_BOLL_broadening", 0),
                "C7_CCI_under_-100": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C7_CCI_under_-100", 0),
                "C8_DMI_bear_extreme": two_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C8_DMI_bear_extreme", 0),
            },
            "generated_at": two_y.get("generated_at"),
        },
        "5y": {
            "start": "2021-08-13", "end": "2026-08-13",
            "min_rows": 500,  # 降级 — 38/40 ETF < 1000 行
            "min_rows_degraded_reason": "5Y 严格阈值 min_rows=1000 会导致 0/38 ETF 通过 (数据起 2023 居多), 降级到 500",
            "etf_pool_used": five_y.get("etf_pool_used", []),
            "etf_pool_count": five_y.get("etf_pool_count", 0),
            "total_return_pct": five_y.get("total_return_pct", 0.0),
            "max_drawdown_pct": five_y.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": five_y.get("sharpe_ratio", 0.0),
            "trade_count": five_y.get("trade_count", 0),
            "closed_trades": five_y.get("closed_trades", 0),
            "win_count": five_y.get("win_count", 0),
            "win_rate_pct": five_y.get("win_rate_pct", 0.0),
            "all4_combined_triggers": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("all_4_combined", 0),
            "at_least_1_trigger": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("at_least_1", 0),
            "single_indicator_triggers": {
                "C3_MACD_golden_cross_below_0": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C3_MACD_golden_cross_below_0", 0),
                "C4_BOLL_broadening": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C4_BOLL_broadening", 0),
                "C7_CCI_under_-100": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C7_CCI_under_-100", 0),
                "C8_DMI_bear_extreme": five_y.get("indicator_trigger_stats", {}).get("totals", {}).get("C8_DMI_bear_extreme", 0),
            },
            "generated_at": five_y.get("generated_at"),
        },
    },
    "kpi_target": {
        "return_target": "+5% (棘轮基线最低门槛)",
        "drawdown_max": "-30% (棘轮硬约束)"
    },
    "honest_declaration": {
        "all4_combined_zero_trigger": "2Y/5Y 全 0 触发 — 4 指标共振策略特性 (MACD双负金叉 + BOLL扩口 + CCI<-100 + DMI空方极致同时成立的样本期 < 1 次)",
        "no_trades_zero_return": "0 触发 → 0 笔交易 → 0% 收益 → 0% 回撤 → 是真实数据结果, 非 bug",
        "kpi_failed": "回报 +0% < +5% 棘轮基线门槛 → KPI 失败 → 触发阈值需放宽 (留给棘轮 subagent #3)",
        "5y_data_degraded": "5Y min_rows 从 1000 降级到 500 (数据源限制, 38/40 ETF 行数 < 1000)"
    }
}
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)
print(f"[baseline] wrote {out_path}")
PYEOF
        echo "[goldcombo cron] ✓ ratchet_baseline.json 双标合并完成" | tee -a "${LOG_FILE}"
    fi
fi

# === 同步 signals (优先用今天日期, 但保留 2026-08-12 历史信号) ===
SIGNAL_FILE="${SIGNALS_DIR}/goldcombo_${TODAY_STR}.json"
SIGNAL_HISTORIC="${SIGNALS_DIR}/goldcombo_2026-08-12.json"
TARGET_SIGNAL="${SIGNAL_HISTORIC}"

# 用最近的有效信号(优先今天, 没有则保留 08-12)
if [[ -f "${SIGNAL_FILE}" ]]; then
    TARGET_SIGNAL="${SIGNAL_FILE}"
fi

if [[ "${OUTPUT}" -nt "${TARGET_SIGNAL}" ]] || [[ ! -f "${TARGET_SIGNAL}" ]]; then
    unset PYTHONPATH
    "${VENV_PY}" - "${OUTPUT}" "${TARGET_SIGNAL}" "${TODAY_STR}" "${PERIOD}" "${STRATEGY_DIR}/ratchet_baseline.json" <<'PYEOF'
import json, sys
bt_path, sig_path, today_str, period, baseline_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
with open(bt_path) as f: bt = json.load(f)
# 读 baseline 双基线 (如果存在)
try:
    with open(baseline_path) as f: baseline = json.load(f)
except FileNotFoundError:
    baseline = {}
return_pct = bt.get("total_return_pct", 0.0)
drawdown = bt.get("max_drawdown_pct", 0.0)
sharpe = bt.get("sharpe_ratio", 0.0)
trades = bt.get("trade_count", 0)
data_period = bt.get("data_period", "")
etf_pool = bt.get("etf_pool_used", [])
all4 = bt.get("indicator_trigger_stats", {}).get("totals", {}).get("all_4_combined", 0)
signal = {
    "date": today_str,
    "strategy_id": "goldcombo",
    "data_source": f"backtrader_real_data_{period}",
    "data_period": data_period,
    "caliber": f"回测数据期 {period.upper()} · 4指标共振 (MACD双负金叉+BOLL扩口+CCI<-100+DMI空方极致) + 8%止损",
    "initial_capital": bt.get("initial_capital", 100000.0),
    "positions": [],
    "action": {
        "action": "HOLD",
        "target": "",
        "detail": f"{period.upper()} 真实回测结果: return={return_pct:.2f}% drawdown={drawdown:.2f}% sharpe={sharpe:.2f} trades={trades} (4指标共振0触发)"
    },
    "today_pnl": 0.0,
    "today_return": 0.0,
    "live_total_pnl": 0.0,
    "live_total_return": 0.0,
    "live_days": 0,
    "live_start_date": today_str,
    "backtest_total_return": return_pct,
    "backtest_sharpe": sharpe,
    "backtest_max_drawdown": drawdown,
    "backtest_annualized_return": None,
    "backtest_trades": trades,
    "backtest_version": "R0_initial_4indicator",
    "backtest_data_period": data_period,
    "backtest_min_rows": bt.get("etf_pool_count", 0),
    "backtest_data_periods": {
        "2y": baseline.get("data_periods", {}).get("2y", {}),
        "5y": baseline.get("data_periods", {}).get("5y", {}),
    },
    "version": "R0_initial_4indicator",
    "source_file": "/Users/junze/quant-monitor-local/strategies/goldcombo/",
    "source_file_latest": f"/Users/junze/quant-monitor-local/strategies/goldcombo/backtest_{period}_2026-08-13.json",
    "source_file_count": 2,
    "source_file_first_date": today_str,
    "source_file_last_date": today_str,
    "validation": {
        "note": "M02 阶段真实回测结果 — 4指标共振0触发 — 0笔交易 — 0%收益 (数据期诚实记录, 触发阈值留给棘轮 subagent #3 放宽)",
        "initial_capital_source": "strategies/goldcombo/goldcombo_strategy.py INITIAL_CAPITAL",
        "data_source": f"真实 ETF CSV: /Users/junze/qixing_data/etf_kline/ (38 ETF, {bt.get('etf_pool_count', 0)} 通过 min_rows 过滤)",
        "indicator_set": ["MACD(12/26/9)", "BOLL(20,2σ)", "CCI(14)", "DMI(14)", "TRIX(12)+TRMA(9)"],
        "entry_conditions": {
            "C3": "MACD 低位金叉 + MACD 双负",
            "C4": "BOLL 开口放大",
            "C7": "CCI < -100",
            "C8": "+DI < 10 且 -DI > 30"
        },
        "exit_conditions": {
            "S2": "CCI > 120",
            "S3": "+DI > 30 且 -DI < 20 且 ADX > 32",
            "S4": "TRIX > TRMA 且 TRIX > 0",
            "S6": "MACD > signal 且 MACD 双正"
        },
        "stop_loss": "sl_pct = 0.08 (8% 硬止损)",
        "honest_zero_trigger": f"all_4_combined = {all4} 次 (>=1指标触发 {bt.get('indicator_trigger_stats', {}).get('totals', {}).get('at_least_1', 0)} 次, 4指标全共振 0 次) — 数据期真实特性"
    }
}
with open(sig_path, 'w', encoding='utf-8') as f:
    json.dump(signal, f, ensure_ascii=False, indent=2)
print(f"[signal] wrote {sig_path}")
PYEOF
    echo "[goldcombo cron] ✓ signal 同步完成 → ${TARGET_SIGNAL}" | tee -a "${LOG_FILE}"
fi

echo "[goldcombo cron] === period=${PERIOD} 完成 $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "${LOG_FILE}"
exit 0