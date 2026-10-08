#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
⚠️  UI 走查专用 · 虚拟数据生成器（UI MOCK ONLY）  ⚠️
--------------------------------------------------------------------------------
用途：仅为前端 UI/交互走查，在【完全隔离】目录生成 35 天窗口的六策略虚拟账本。
铁律：
  - 输出只写入 <repo>/ui-mock/live-data/（已被 .gitignore 忽略），
    绝不写入真实 live-data/、绝不 commit/push、绝不冒充实盘或回测。
  - 价格由【固定随机种子】确定性生成（可重复），不是真实行情。
  - 成交/费用/印花税/滑点/T+1/账本 全部调用真实撮合引擎 matching_engine.Broker
    与真实动量决策器产出，保证 JSON schema 与真实引擎完全一致、账本自洽。
启动隔离面板：
  QM_LIVE_DATA_DIR="$PWD/ui-mock/live-data" QM_PORT=8010 \
    /usr/local/bin/python3 api/real_data_server_v2.py
================================================================================
"""
import sys
import json
import math
import random
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "api"))

from run_daily_engine import STRATEGIES, DECIDERS, ETF_NAMES  # noqa: E402
from matching_engine import Broker                        # noqa: E402

# 贴近真实量级的基准价（仅用于让 UI 数字顺眼，不代表真实行情）
BASE_PRICE = {
    "511880": 102.0, "518880": 6.4, "513100": 1.85, "513500": 1.62,
    "513030": 1.18, "513520": 1.08, "513690": 0.98, "513080": 1.12,
    "513130": 0.82, "510300": 4.05, "510500": 6.1, "512040": 1.05,
    "512100": 2.25, "512890": 1.25, "159915": 2.05, "159967": 0.92,
    "159980": 1.55, "159981": 0.88, "159985": 3.05, "161226": 1.25,
    "501018": 0.72, "588080": 1.02,
}

DATA_NATURE = "UI测试虚拟数据(确定性生成, 非实盘, 非回测, 不接券商)"
DATA_SOURCE = "UI_MOCK(仅UI走查, 固定种子虚拟价格)"
PRICE_SOURCE = "mock_deterministic"


def trade_days_between(start: date, end: date):
    """用真实 A股交易日历取区间内交易日（自动排除国庆等节假日）。"""
    try:
        from market_data import load_trade_dates
        cal = load_trade_dates()
    except Exception:
        cal = None
    days, cur = [], start
    while cur <= end:
        s = cur.isoformat()
        if cal is not None:
            if s in cal:
                days.append(s)
        elif cur.weekday() < 5:
            days.append(s)
        cur += timedelta(days=1)
    return days


def gen_series(code: str, n: int, crash_at: dict):
    """确定性虚拟收盘价：长期漂移 + 中期轮动正弦 + 共同回撤 + 高斯噪声。"""
    rng = random.Random(int(code))           # 数字代码做种子，可重复
    base = BASE_PRICE.get(code, 1.5)
    phase = (int(code) % 360) / 180.0 * math.pi
    drift = (rng.random() - 0.46) * 0.004    # 每只 ETF 不同的长期漂移
    beta = 0.7 + (int(code) % 10) / 20.0     # 对市场回撤的敏感度 0.7~1.15
    prices = [base]
    for t in range(1, n):
        cycle = 0.012 * math.sin(t / 6.0 + phase) + \
                0.007 * math.sin(t / 13.0 + phase * 2)
        shock = rng.gauss(0, 0.011)
        crash = crash_at.get(t, 0.0) * beta
        r = drift + cycle + shock + crash
        prices.append(round(max(0.2, prices[-1] * (1 + r)), 4))
    return prices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BASE_DIR / "ui-mock" / "live-data"))
    ap.add_argument("--end", default="2026-10-06")
    ap.add_argument("--days", type=int, default=35, help="自然日窗口")
    ap.add_argument("--warmup", type=int, default=60, help="预热交易日(供动量)")
    args = ap.parse_args()

    end_d = date.fromisoformat(args.end)
    start_d = end_d - timedelta(days=args.days)
    days = trade_days_between(start_d, end_d)
    if not days:
        print("[错误] 窗口内无交易日"); sys.exit(1)

    repo = Path(args.out)
    daily_dir, latest_dir, state_dir = (repo / "daily",
                                        repo / "latest", repo / "_account_state")
    for d in (daily_dir, latest_dir, state_dir):
        d.mkdir(parents=True, exist_ok=True)

    all_codes = sorted({c for cfg in STRATEGIES.values() for c in cfg["pool"]})
    # 在回放窗口内人为安排两段共同回撤（相对预热后的索引），制造净值回撤
    crash_at = {args.warmup + 9: -0.020, args.warmup + 10: -0.016,
                args.warmup + 17: -0.013}
    n_total = args.warmup + len(days)
    series = {c: gen_series(c, n_total, crash_at) for c in all_codes}

    brokers, prev_asset = {}, {}
    n_trades_total = 0
    for k, d in enumerate(days):
        t = args.warmup + k
        for sid, cfg in STRATEGIES.items():
            hist = {c: series[c][:t + 1] for c in cfg["pool"]}
            prices = {c: series[c][t] for c in cfg["pool"]}
            b = brokers.get(sid) or Broker(cfg["capital"], sid)
            b.end_of_day()                                  # T+1
            target = DECIDERS[sid](hist)                    # 真实动量决策
            b.pending_target = target
            trades = b.rebalance(target, prices, date=d,
                                 names=ETF_NAMES)   # 真实撮合
            snap = b.settle(prices)
            b.save(state_dir / f"{sid}.json")
            brokers[sid] = b

            init = cfg["capital"]
            prev = prev_asset.get(sid, init)
            today_pnl = round(snap["total_asset"] - prev, 2)
            today_ret = round(today_pnl / prev * 100, 2) if prev else 0.0
            prev_asset[sid] = snap["total_asset"]
            n_trades_total += len(trades)

            rec = {
                "date": d, "strategy_id": sid,
                "strategy_name": cfg["name"],
                "initial_capital": init,
                "data_source": DATA_SOURCE,
                "data_nature": DATA_NATURE,
                "is_ui_mock": True,
                "phase": "trade",
                "price_source": PRICE_SOURCE,
                "run_time": f"{d}T13:0{sid and 3}:00",
                "today_pnl": today_pnl,
                "today_return": today_ret,
                "live_total_pnl": snap["total_pnl"],
                "live_total_return": snap["total_return"],
                "live_days": k + 1,
                "cash": snap["cash"],
                "market_value": snap["market_value"],
                "total_asset": snap["total_asset"],
                "realized_pnl": snap["realized_pnl"],
                "positions": snap["positions"],
                "pending_target": target,
                "trades_today": trades,
            }
            day_dir = daily_dir / d
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / f"{sid}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            if k == len(days) - 1:
                (latest_dir / f"{sid}.json").write_text(
                    json.dumps(rec, ensure_ascii=False, indent=2),
                    encoding="utf-8")
        print(f"  {d}  累计成交 {n_trades_total} 笔")

    marker = {
        "is_ui_mock": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": days[0], "end": days[-1],
                   "trade_days": len(days), "natural_days": args.days},
        "warning": "UI走查虚拟数据，禁止提交、禁止冒充实盘/回测",
        "strategies": list(STRATEGIES.keys()),
    }
    (repo / "_mock_marker.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[完成] 虚拟数据已写入隔离目录: {repo}")
    print(f"  交易日 {len(days)} 天（{days[0]} ~ {days[-1]}），"
          f"六策略，总成交 {n_trades_total} 笔")


if __name__ == "__main__":
    main()
