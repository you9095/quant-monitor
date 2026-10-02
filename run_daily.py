#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日实盘引擎（Windows 端每天 15:30 调用）

当前版本：心跳 + 快照记录
- 为 6 策略在 live-data/daily/<今天>/ 生成当日记录
- 维护 live-data/latest/<sid>.json 最新持仓快照
- 不连接任何券商账号

后续迭代方向（roadmap）：接入 akshare 当日行情，按各策略规则产生真实买卖信号、
更新持仓与盈亏，替换当前的占位记录。
"""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_REPO = BASE_DIR / "live-data"
DAILY_DIR = DATA_REPO / "daily"
LATEST_DIR = DATA_REPO / "latest"

STRATEGIES = [
    ("qixing", "七星策略", 10000),
    ("r32", "三驾马车", 10000),
    ("zhuidian", "追电策略", 10000),
    ("sanhe", "三合策略", 10000),
    ("lightning", "闪电策略", 10000),
    ("goldcombo", "黄金组合A", 10000),
]


def load_latest(sid):
    f = LATEST_DIR / f"{sid}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = DAILY_DIR / today
    today_dir.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    for sid, name, capital in STRATEGIES:
        prev = load_latest(sid)
        # 占位：延续上一快照，无交易时持仓与盈亏不变
        # TODO: 接入真实撮合后，此处根据当日行情与策略规则计算 today_pnl / positions / action
        record = {
            "date": today,
            "strategy_id": sid,
            "strategy_name": name,
            "initial_capital": capital,
            "data_source": "Windows本地实盘引擎",
            "run_time": datetime.now().isoformat(timespec="seconds"),
            "today_pnl": prev.get("today_pnl", 0.0) if prev else 0.0,
            "today_return": prev.get("today_return", 0.0) if prev else 0.0,
            "live_total_pnl": prev.get("live_total_pnl", 0.0) if prev else 0.0,
            "live_total_return": prev.get("live_total_return", 0.0) if prev else 0.0,
            "live_days": (prev.get("live_days", 0) + 1) if prev else 1,
            "positions": prev.get("positions", []) if prev else [],
            "action": prev.get("action", {"type": "NONE", "label": "未启动"}) if prev else {"type": "NONE", "label": "未启动"},
        }
        (today_dir / f"{sid}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        (LATEST_DIR / f"{sid}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[run_daily] 已生成 {today} 当日记录，{len(STRATEGIES)} 个策略")


if __name__ == "__main__":
    main()
