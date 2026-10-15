#!/usr/bin/env python3
"""桥接 work_logs → signals (v3 禁止快照版)"""

import json
import os
import sys
from datetime import datetime

# ===== 统一字段契约（2026-09-21 强制引入） =====
sys.path.insert(0, "/Users/junze/.hermes/scripts/p7")
from trade_schema import validate_positions, validate_signal, normalize_positions_list

# ==================== 配置 ====================
WORK_LOGS_ROOT = os.path.expanduser("~/.hermes/work_logs")
SIGNALS_DIR = os.path.expanduser("~/quant-monitor-local/signals")
STRATEGIES = ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]
# Allow date override via environment variable for regeneration purposes
TODAY = os.environ.get("BRIDGE_DATE", datetime.now().strftime("%Y-%m-%d"))

# ==================== 工具函数 ====================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def error(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] {msg}", file=sys.stderr)

def warn(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WARN] {msg}", file=sys.stderr)

def find_latest_worklog(sid):
    """查找策略最新的 work_logs JSON 文件"""
    log_dir = os.path.join(WORK_LOGS_ROOT, sid)
    if not os.path.isdir(log_dir):
        return None
    json_files = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
        if f.endswith(".json") and not f.endswith("_baseline.json")
    ]
    if not json_files:
        return None
    return max(json_files, key=os.path.getmtime)

def find_latest_signal(sid):
    """查找策略最新的信号 JSON 文件 (排除备份)"""
    pattern = f"{sid}_"
    files = [
        os.path.join(SIGNALS_DIR, f)
        for f in os.listdir(SIGNALS_DIR)
        if f.startswith(pattern) and f.endswith(".json") and ".bak" not in f
    ]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def parse_worklog_to_signal(worklog_path, existing_signal, sid: str = "unknown"):
    """解析 work_logs JSON, 提取关键字段更新到信号数据。

    保守策略: 只更新能确定的字段, 其余保持 existing_signal 不变。
    """
    try:
        with open(worklog_path, "r", encoding="utf-8") as f:
            wl = json.load(f)
    except Exception as e:
        error(f"  解析 work_logs 失败: {e}")
        return None

    signal = dict(existing_signal) if existing_signal else {}

    # 日期: 优先 trade_status.date, 然后从文件名提取, 最后用今天
    wl_date = None
    if isinstance(wl.get("trade_status"), dict):
        wl_date = wl["trade_status"].get("date")
    if not wl_date:
        # 从文件名提取日期
        basename = os.path.basename(worklog_path)
        for part in basename.replace(".json", "").split("_"):
            if len(part) == 10 and part[4] == "-" and part[7] == "-":
                wl_date = part
                break
    if not wl_date:
        wl_date = TODAY
    signal["date"] = wl_date
    signal["signal_date"] = wl_date
    signal["latest_signal_date"] = wl_date

    # 2026-09-20 根治: work_logs 关键字段( target_etfs, target_weight, action, live_total_pnl 等)
    # 关键修复: target_etfs 与 target_weight 实际位于 worklog 结构的 signal 子字段下，
    # 而非顶级。必须先从 wl["signal"] 取值，再回退到顶级，防止全丢失。
    # 原因：2026-09-20 以前的 bridge 代码以 wl.get("target_etfs") 为唯一来源，
    # 但 work_logs 关键字段均在 wl["signal"] 下，导致 target_etfs 一律丢失、
    # target_value 永远 0，进而导致下单数量为 0。
    top = wl  # 别名，明确顶级来源
    sig = top.get("signal", {}) if isinstance(top.get("signal"), dict) else {}

    # --- 从 worklog signal子字段读取 target_etfs 与 target_weight (优于顶级) ---
    wl_target_etfs = sig.get("target_etfs") if isinstance(sig.get("target_etfs"), list) else []
    wl_target_weight = sig.get("target_weight") if isinstance(sig.get("target_weight"), (int, float)) else None
    # 兼容旧格式：也尝试从顶级兼容旧版本
    if not wl_target_etfs:
        wl_target_etfs = top.get("target_etfs") if isinstance(top.get("target_etfs"), list) else []
    if wl_target_weight is None:
        wl_target_weight = top.get("target_weight") if isinstance(top.get("target_weight"), (int, float)) else None
        if wl_target_weight is None:
            wl_target_weight = top.get("live_target_weight")

    # --- all-zero check: 如果 worklog 中 target_etfs 存在但 all target_value==0，
    # 则视为无有效信号，清空 target_etfs 并设为 HOLD 动作 ---
    all_zero_value = False
    if wl_target_etfs:
        all_zero_value = all(
            float(t.get("target_value", 0) or t.get("live_target_value", 0) or 0) == 0
            for t in wl_target_etfs
        )

    if all_zero_value and len(wl_target_etfs) > 0:
        # 无 ETF 通过筛选：清空 target_etfs，action 设为 HOLD
        signal["action"] = {
            "type": "HOLD",
            "label": "持有",
            "target_etf": "",
            "target_weight": 0,
        }
        signal["target_etfs"] = []
        signal["target_weight"] = 0
    else:
        # 有效 target_etfs：从 worklog 搬运
        if wl_target_etfs:
            valid_etfs = [t for t in wl_target_etfs
                         if (float(t.get("target_value", 0) or t.get("live_target_value", 0) or 0)) > 0]
            if valid_etfs:
                signal["target_etfs"] = valid_etfs
                # 从 worklog 顶级或 signal 取 target_weight
                tw = wl_target_weight if (wl_target_weight and float(wl_target_weight) > 0) else (sig.get("target_weight") if isinstance(sig.get("target_weight"), (int,float)) and float(sig.get("target_weight")) > 0 else None)
                if tw and float(tw) > 0:
                    signal["target_weight"] = float(tw)
                else:
                    n = len(valid_etfs)
                    signal["target_weight"] = round(1.0 / n, 4) if n else 0
            else:
                signal["target_etfs"] = []
                signal["target_weight"] = 0
        else:
            signal["target_etfs"] = []
            signal["target_weight"] = 0

        # --- 正常动作确定 (基于有效 target_etfs) ---
        if signal.get("target_etfs") and len(signal["target_etfs"]) > 0:
            signal["action"] = {
                "type": "REBALANCE",
                "label": "调仓",
                "target_etf": sig.get("target_etf", ""),
                "target_weight": signal.get("target_weight", 0),
            }
        else:
            # 无有效目标：持有
            signal["action"] = {
                "type": "HOLD",
                "label": "持有",
                "target_etf": "",
                "target_weight": 0,
            }

    # daily_pnl / live_* (兼容旧格式 daily_pnl 与新格式 live_* 两种 work_logs 口径)
    # 优先级：新格式 live_* > 旧格式 daily_pnl，确保真实实盘数据不被回测值冒充
    # 2026-09-22 根治: 只有当日实际有成交(非零 qty/amount)才 carry over live_total_pnl/live_total_return
    # 否则这些累计值是旧账/回测数据，冒充实盘会导致收益失真(前端显示+143%但实际全0)
    # 工作日志两种常见结构：{trade: {..., securities: [...]}} 与 {trades_today: [...]}。
    has_real_trades = False
    # 优先检查新格式：trades_today 列表
    if "trades_today" in wl and isinstance(wl["trades_today"], list):
        if wl["trades_today"]:
            has_real_trades = any(
                float(t.get("qty", 0) or 0) != 0 or float(t.get("amount", 0) or 0) != 0
                for t in wl["trades_today"]
            )
    # 兼容旧格式：trade 字段包含 securities
    if not has_real_trades and "trade" in wl and isinstance(wl["trade"], dict):
        securities = wl["trade"].get("securities", [])
        if securities:
            has_real_trades = any(
                float(t.get("qty", 0) or 0) != 0 or float(t.get("amount", 0) or 0) != 0
                for t in securities
            )

    if "live_total_pnl" in wl and wl["live_total_pnl"] is not None:
        # 新格式：顶层 live_total_pnl（来自 daily_runner 新引擎）
        # 仅在有真实成交时才使用，否则保持原值(可能为None)防止回测值冒充
        if has_real_trades:
            signal["live_total_pnl"] = float(wl["live_total_pnl"])
        # else: 保持 signal 不变，避免回测 cumulative 冒充实盘 PnL
    elif "daily_pnl" in wl and isinstance(wl["daily_pnl"], dict):
        # 旧格式：daily_pnl 包 cumulative/return_pct 等字段
        # qixing格式: total / per_etf / cumulative / return_pct
        # 其他策略可能格式: pnl / return_pct
        today_pnl_val = wl["daily_pnl"].get("total", wl["daily_pnl"].get("pnl", 0))
        signal["today_pnl"] = float(today_pnl_val)
        if "return_pct" in wl["daily_pnl"]:
            signal["today_return"] = float(wl["daily_pnl"]["return_pct"])

        # 2026-09-22 根治: 只有当日实际有成交(非零 qty/amount)才 carry over cumulative/return_pct
        # 否则这些累计值是旧账/回测数据，冒充实盘会导致收益失真
        if has_real_trades:
            if "cumulative" in wl["daily_pnl"]:
                signal["live_total_pnl"] = float(wl["daily_pnl"]["cumulative"])
            if "return_pct" in wl["daily_pnl"]:
                signal["live_total_return"] = float(wl["daily_pnl"]["return_pct"])
        # else: 不更新 live_total_pnl/live_total_return，防止回测数据冒充实盘
        if "trade_count" in wl["daily_pnl"]:
            signal["trade_count"] = int(wl["daily_pnl"]["trade_count"])
    else:
        # 兼容兜底：从 live_* 字段回填未被旧代码覆盖的字段
        if "live_total_return" in wl:
            signal["live_total_return"] = float(wl["live_total_return"])
        if "live_pnl" in wl:
            signal["today_pnl"] = float(wl["live_pnl"])
        if "live_equity" in wl and signal.get("live_total_pnl") is None:
            # 从 equity 反推累计盈亏（仅在无 other 源时兜底）
            init = signal.get("initial_capital") or 10000.0
            signal["live_total_pnl"] = round(float(wl["live_equity"]) - init, 2)

    # 2026-09-20 修复: live_days 从work_logs文件数计算（在main函数中处理）
    # 这里先标记需要更新
    signal["_needs_live_days"] = True

    # 确保 live_total_return 被正确计算
    # 优先从 work_logs 的 live_total_pnl 计算，确保真实实盘数据不被回测值冒充
    # 只有当 live_total_return 在 work_logs 中被显式设置为 None 或未设置时，才从 P&L 计算
    # 如果 work_logs 中 live_total_return 为 0.0 但 live_total_pnl 有实际值，重新计算
    if signal.get("live_total_pnl") is not None:
        if signal.get("live_total_return") is None:
            # live_total_return 未在 work_logs 中设置，从 P&L 计算
            init = signal.get("initial_capital") or 10000.0
            signal["live_total_return"] = round(signal["live_total_pnl"] / init * 100, 2) if init > 0 else 0.0
        elif signal["live_total_return"] == 0.0 and signal.get("live_total_pnl", 0) != 0:
            # work_logs 中 live_total_return 为 0.0 但 live_total_pnl 有实际值，
            # 说明 previous logic 错误地从 work_logs 直接沿用了 0.0，重新从 P&L 计算
            init = signal.get("initial_capital") or 10000.0
            signal["live_total_return"] = round(signal["live_total_pnl"] / init * 100, 2) if init > 0 else 0.0

    # positions (兼容不同字段名: positions / positions_after / holdings)
    positions_data = wl.get("positions") or wl.get("positions_after") or wl.get("holdings") or []
    if isinstance(positions_data, list) and positions_data:
        # 规范化字段名：统一为 qty
        positions_data = normalize_positions_list(positions_data)
        # 校验持仓字段合规
        ok, msg = validate_positions(positions_data, f"bridge/{sid}")
        if not ok:
            warn(f"  {sid} positions 字段不合规: {msg}")
        signal["positions"] = positions_data

    # data_source
    signal["data_source"] = signal.get("data_source", "work_logs")

    return signal

# ==================== 主流程 ====================
def main():
    log(f"===== 桥接 work_logs → signals v3 =====")
    log(f"日期: {TODAY}")
    log(f"策略数: {len(STRATEGIES)}")
    log("")

    os.makedirs(SIGNALS_DIR, exist_ok=True)

    results = []
    for sid in STRATEGIES:
        log(f"--- {sid} ---")
        dst = os.path.join(SIGNALS_DIR, f"{sid}_{TODAY}.json")

        # 如果当天信号已存在, 跳过
        if os.path.exists(dst):
            log(f"  当天信号已存在: {os.path.basename(dst)}, 跳过")
            results.append((sid, "skipped", "已存在"))
            continue

        # 1. 查找最新 work_logs
        wl_path = find_latest_worklog(sid)
        latest_signal_path = find_latest_signal(sid)

        signal_data = None
        source = "none"

        if wl_path:
            wl_mtime = datetime.fromtimestamp(os.path.getmtime(wl_path)).strftime("%Y-%m-%d")
            log(f"  最新 work_logs: {os.path.basename(wl_path)} (修改于 {wl_mtime})")

            # 2026-09-20 修复: 计算该策略的work_logs文件数作为live_days
            wl_dir = os.path.dirname(wl_path)
            wl_file_count = len([f for f in os.listdir(wl_dir)
                                    if f.endswith('.json') and not f.endswith('_baseline.json')
                                    and not f.endswith('_fusion_baseline.json')])

            # 只有当 work_logs 是当天才解析（禁止快照）
            if wl_mtime == TODAY:
                log(f"  work_logs 为当天数据, 解析更新信号")
                existing = {}
                if latest_signal_path:
                    try:
                        with open(latest_signal_path, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except Exception:
                        pass
                signal_data = parse_worklog_to_signal(wl_path, existing, sid)
                source = "work_logs"
            else:
                error(f"  work_logs 非当天 ({wl_mtime}), 禁止生成快照, 跳过")
                results.append((sid, "stale", f"数据陈旧: {wl_mtime}"))
                continue
        else:
            error(f"  无 work_logs JSON 文件, 禁止生成快照, 跳过")
            results.append((sid, "failed", "无 work_logs 文件"))
            continue

        # 3. 写入信号文件
        if signal_data:
            signal_data["strategy_id"] = sid
            # 2026-09-20 修复: 设置真实的live_days
            if signal_data.pop("_needs_live_days", False):
                signal_data["live_days"] = wl_file_count
            # 初始资金
            signal_data.setdefault("initial_capital", 10000.0)
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(signal_data, f, ensure_ascii=False, indent=2)
            log(f"  ✅ 已生成: {os.path.basename(dst)} (来源: {source})")
            results.append((sid, "ok", source))
        else:
            error(f"  ❌ 生成信号失败")
            results.append((sid, "failed", "生成失败"))

    # ==================== 验证 ====================
    log("")
    log("===== 验证 =====")
    ok_count = 0
    stale_count = 0
    failed_count = 0
    for sid, status, source in results:
        dst = os.path.join(SIGNALS_DIR, f"{sid}_{TODAY}.json")
        if status == "ok" and os.path.exists(dst):
            try:
                with open(dst, "r", encoding="utf-8") as f:
                    d = json.load(f)
                sig_date = d.get("date", "?")
                if sig_date == TODAY:
                    log(f"  ✅ {sid}: date={sig_date} (来源: {source})")
                    ok_count += 1
                else:
                    error(f"  ❌ {sid}: date={sig_date} ≠ {TODAY}")
                    failed_count += 1
            except Exception as e:
                error(f"  ❌ {sid}: 读取验证失败 - {e}")
                failed_count += 1
        elif status == "stale":
            warn(f"  ⚠️  {sid}: 数据陈旧 ({source}), 无当天信号文件")
            stale_count += 1
        else:
            error(f"  ❌ {sid}: 失败 - {source}")
            failed_count += 1

    log("")
    log(f"===== 桥接完成 =====")
    log(f"  ✅ 成功: {ok_count} 个策略")
    if stale_count > 0:
        warn(f"  ⚠️  数据陈旧: {stale_count} 个策略 (无当天 work_logs)")
    if failed_count > 0:
        error(f"  ❌ 失败: {failed_count} 个策略")

    # 只要有成功的就不退出错误码（部分失败不影响整体）
    if ok_count > 0:
        sys.exit(0)
    else:
        error(f"===== 桥接失败: 无成功策略 =====")
        sys.exit(1)

if __name__ == "__main__":
    main()