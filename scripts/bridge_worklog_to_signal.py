#!/usr/bin/env python3
"""
桥接 work_logs → signals (v3 禁止快照版)
=====================================
修复历史:
  v1 (原始): 只处理 qixing, 直接复制 .txt 文件到 signals/, 不生成 JSON, 不处理其他5策略
  v2 (2026-09-17, 已废弃): 曾在无当日 work_logs 时复制上一日信号生成"快照", 制造假数据, 已在 v3 彻底删除
  v3 (2026-09-20 禁止快照, 当前版本):
    - 彻底删除快照机制, 禁止任何形式的复制、前向填充、假装正常
    - 若无当日 work_logs, 不生成信号文件, 明确报"数据陈旧/缺失"错误
    - 数据缺失就空着, 绝不掩盖问题
    - 2026-09-22: 新增 target_etfs 从 worklog 搬运（针对 zhuidian 等策略）
"""

import json
import os
import sys
from datetime import datetime

# ===== 统一字段契约（2026-09-21 强制引入） ====
sys.path.insert(0, "/Users/junze/.hermes/scripts/p7")
from trade_schema import validate_positions, validate_signal, normalize_positions_list

# ==================== 配置 ====================
WORK_LOGS_ROOT = os.path.expanduser("~/.hermes/work_logs")
SIGNALS_DIR = os.path.expanduser("~/quant-monitor-local/signals")
STRATEGIES = ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]
# TODAY = datetime.now().strftime("%Y-%m-%d")  # Original: only current date
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

    # action / signal
    if "signal" in wl and isinstance(wl["signal"], dict):
        sig = wl["signal"]
        action_map = {
            "DEFENSIVE": "防御",
            "HOLD": "持有",
            "REBALANCE": "调仓",
            "EMPTY": "空仓",
            "OBSERVE": "观望",
        }
        action_en = sig.get("action", "")
        # 2026-09-21 修复：当无 ETF 通过动量筛选时，action 设为 HOLD 且 target_etfs 设为空列表
        # 这样可以避免前端显示虚高收益（因 target_value=0 导致的虚假抬高）
        # 从 worklog signal 字段搬运 target_etfs（针对 zhuidian 等策略，2026-09-22 修复）
        # 此字段在 worklog 中完整存在，但桥接时曾被忽略，导致 target_etfs 一律丢失
        # 兼容两种 work_log 格式：旧格式有 signal.sub.dict，新格式(2026-09-23+) 无 signal键，改有 pending_target 顶层字段
        if sid == "zhuidian" and isinstance(sig, dict):
            # 情况 A：旧格式——signal.sub.dict 含 target_etfs（2026-09-22 及之前）
            wl_target_etfs = sig.get("target_etfs") or sig.get("live_target_etfs") or []
            if wl_target_etfs:
                valid_etfs = [t for t in wl_target_etfs 
                             if (float(t.get("target_value", 0) or t.get("live_target_value", 0) or 0)) > 0]
                if valid_etfs:
                    signal["target_etfs"] = valid_etfs
                    tw = sig.get("target_weight") or sig.get("live_target_weight")
                    if tw and float(tw) > 0:
                        signal["target_weight"] = float(tw)
                    else:
                        n = len(valid_etfs)
                        signal["target_weight"] = round(1.0 / n, 4) if n else 0
                else:
                    signal["target_etfs"] = []
                    signal["target_weight"] = 0
            else:
                # 情况 B：新格式——worklog 无 signal 键，改有 pending_target 顶层字段（2026-09-23+）
                pending_target = wl.get("pending_target") or {}
                if pending_target:
                    # 将 engine 的 pending_target dict {'513100': 1.0} 
                    # 转换为 signal target_etfs list [{'code': '513100', 'target_value': 1.0, 'weight': 1.0}]
                    target_etfs_list = []
                    for code, weight in pending_target.items():
                        target_value = round(float(weight), 4) if weight > 0 else 0
                        if target_value > 0:
                            target_etfs_list.append({
                                "code": code,
                                "target_value": target_value,
                                "weight": float(weight)
                            })
                    if target_etfs_list:
                        signal["target_etfs"] = target_etfs_list
                        signal["target_weight"] = round(1.0 / len(target_etfs_list), 4)
                    else:
                        signal["target_etfs"] = []
                        signal["target_weight"] = 0
                else:
                    # 情况 C：既无 signal 也无 pending_target——可能全未通过动量筛选
                    signal["target_etfs"] = []
                    signal["target_weight"] = 0
        # 检查是否所有 target_value 为 0（即无有效信号通过筛选）
        # 支持 both 原始名称和 live_ 前缀
        target_etfs_from_wl = sig.get("target_etfs") or sig.get("live_target_etfs") or []
        all_zero_value = all(
            float(t.get("target_value", 0) or t.get("live_target_value", 0) or 0) == 0 
            for t in target_etfs_from_wl
        )
        if all_zero_value and len(target_etfs_from_wl) > 0:
            # 无 ETF 通过筛选：清空 target_etfs，action 设为 HOLD
            signal["action"] = {
                "type": "HOLD",
                "label": action_map.get("HOLD", "HOLD"),
                "target_etf": "",
                "target_weight": 0,
            }
            # 重新构造 signal，移除 target_etfs 中的 0-value 条目
            sig = {"action": "HOLD", "target_etf": None, "target_etfs": [], "target_weight": 0.0}
        else:
            signal["action"] = {
                "type": action_en,
                "label": action_map.get(action_en, action_en) if isinstance(action_en, str) else action_en,
                "target_etf": sig.get("target_etf", ""),
                "target_weight": sig.get("target_weight", 0),
            }

    # daily_pnl / live_* (兼容旧格式 daily_pnl 与新格式 live_* 两种 work_logs 口径)
        # 优先级：新格式 live_* > 旧格式 daily_pnl，确保真实实盘数据不被回测值冒充
        # 2026-09-22 根治: 只有当日实际有成交(非零 qty/amount)才 carry over live_total_pnl/live_total_return
        # 否则这些累计值是旧账/回测数据，冒充实盘会导致收益失真(前端显示+143%但实际全0)
        has_real_trades = False
        if "trade" in wl and isinstance(wl["trade"], dict):
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
            dp = wl["daily_pnl"]
            # qixing格式: total / per_etf / cumulative / return_pct
            # 其他策略可能格式: pnl / return_pct
            today_pnl_val = dp.get("total", dp.get("pnl", 0))
            signal["today_pnl"] = float(today_pnl_val)
            if "return_pct" in dp:
                signal["today_return"] = float(dp["return_pct"])

            # 2026-09-22 根治: 只有当日实际有成交(非零 qty/amount)才 carry over cumulative/return_pct
            # 否则这些累计值是旧账/回测数据，冒充实盘会导致收益失真
            if has_real_trades:
                if "cumulative" in dp:
                    signal["live_total_pnl"] = float(dp["cumulative"])
                if "return_pct" in dp:
                    signal["live_total_return"] = float(dp["return_pct"])
            # else: 不更新 live_total_pnl/live_total_return，防止回测数据冒充实盘
            if "trade_count" in dp:
                signal["trade_count"] = int(dp["trade_count"])
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