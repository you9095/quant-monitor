#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日实盘引擎：读昨日账户 → 拉行情 → 策略决策 → 真实撮合 → 结算 → 写 live-data
================================================================================
不连接任何券商。所有买卖为本地模拟撮合（含佣金/印花税/滑点/T+1）。

策略决策层（可插拔）：
  - lightning：4只跨境ETF，3日动量最强且>0者满仓单持，否则空仓（真实规则）
  - 其余策略：先占位（现金观望），后续逐个接入完整信号规则

用法：
  python run_daily_engine.py            # 生产模式（akshare 拉真实行情）
  python run_daily_engine.py --backtest # 回测模式（合成行情，测性能稳定性）
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "api"))
from matching_engine import Broker  # noqa: E402

DATA_REPO = BASE_DIR / "live-data"
DAILY_DIR = DATA_REPO / "daily"
LATEST_DIR = DATA_REPO / "latest"
STATE_DIR = DATA_REPO / "_account_state"

STRATEGIES = {
    "qixing": {"name": "七星策略", "capital": 10000, "pool": ["510300", "512100"]},
    "r32":    {"name": "三驾马车", "capital": 10000, "pool": ["510300", "512880"]},
    "zhuidian": {"name": "追电策略", "capital": 10000, "pool": ["513100", "513500"]},
    "sanhe":  {"name": "三合策略", "capital": 10000, "pool": ["510500", "159915"]},
    "lightning": {"name": "闪电策略", "capital": 10000,
                  "pool": ["513100", "513520", "513030", "513130"]},
    "goldcombo": {"name": "黄金组合A", "capital": 10000, "pool": ["518880"]},
}


# ============================================================
# 策略决策：给定每只标的近3日收盘价，返回目标持仓 {code: weight}
# weight: 0~1（占总资产比例），单策略单持（weight=1 满仓一只）
# ============================================================
def decide_lightning(prices_hist: dict) -> dict:
    """lightning：4只跨境ETF中，3日动量>0且最强的1只满仓；都<0则空仓"""
    best_code, best_mom = None, 0
    for code, hist in prices_hist.items():
        if len(hist) < 4:
            continue
        mom = hist[-1] / hist[-4] - 1   # 3日动量
        if mom > best_mom:
            best_mom, best_code = mom, code
    if best_code and best_mom > 0:
        return {best_code: 1.0}
    return {}


def decide_hold_cash(prices_hist: dict) -> dict:
    """占位：现金观望（待接入完整策略规则）"""
    return {}


DECIDERS = {
    "lightning": decide_lightning,
    "qixing": decide_hold_cash,
    "r32": decide_hold_cash,
    "zhuidian": decide_hold_cash,
    "sanhe": decide_hold_cash,
    "goldcombo": decide_hold_cash,
}


def rebalance(broker: Broker, target: dict, prices: dict, today: str):
    """把当前持仓调到 target={code: weight}，真实卖出/买入"""
    # 1. 先卖出所有不在 target 或不再需要的持仓
    current_codes = set(broker.positions.keys())
    for code in list(current_codes):
        if code not in target:
            broker.sell(code, prices.get(code, 0), date=today)
    # 2. 计算总资产，按 weight 分配
    snap = broker.settle(prices)
    total_asset = snap["total_asset"]
    for code, weight in target.items():
        if weight <= 0:
            continue
        target_value = total_asset * weight
        price = prices.get(code, 0)
        if price <= 0:
            continue
        # 现有持仓市值
        cur_qty = broker.positions[code].qty if code in broker.positions else 0
        cur_value = cur_qty * price
        diff = target_value - cur_value
        if diff > 200:   # 超过200元才调，避免频繁小额交易
            broker.buy(code, price, diff, date=today)
        elif diff < -200:
            sell_qty = min(int(-diff / price / 100) * 100,
                           broker.positions[code].avail_qty)
            if sell_qty > 0:
                broker.sell(code, price, sell_qty, date=today)


def run_one_day(sid: str, cfg: dict, prices_hist: dict, prices_today: dict,
                today: str) -> dict:
    """跑单个策略一天：load state → 决策 → 撮合 → 结算 → save state"""
    state_path = STATE_DIR / f"{sid}.json"
    broker = Broker.load_or_new(state_path, cfg["capital"], sid)
    decider = DECIDERS.get(sid, decide_hold_cash)
    target = decider({c: prices_hist.get(c, []) for c in cfg["pool"]})
    rebalance(broker, target, prices_today, today)
    snap = broker.settle(prices_today)
    broker.end_of_day()
    broker.save(state_path)
    # 写 live-data
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "date": today, "strategy_id": sid, "strategy_name": cfg["name"],
        "initial_capital": cfg["capital"], "data_source": "Windows实盘引擎(真实撮合)",
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "today_pnl": round(snap["total_pnl"] - broker.realized_pnl, 2),  # 近似
        "today_return": 0.0,
        "live_total_pnl": snap["total_pnl"],
        "live_total_return": snap["total_return"],
        "live_days": (broker.trades and len(broker.trades)) or 0,
        "cash": snap["cash"], "market_value": snap["market_value"],
        "positions": snap["positions"],
        "trades_today": [t for t in broker.trades if t.get("date") == today],
        "action": {"type": "REBALANCE" if target else "HOLD",
                   "label": "调仓" if target else "空仓观望"},
    }
    day_dir = DAILY_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (LATEST_DIR / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def fetch_prices_akshare(pool: list) -> dict:
    """生产模式：用 akshare 拉ETF当日收盘价（失败返回空）"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        prices = {}
        for code in pool:
            row = df[df["代码"] == code]
            if len(row):
                prices[code] = float(row.iloc[0]["最新价"])
        return prices
    except Exception as e:
        print(f"  [行情] akshare 失败: {e}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true")
    args = ap.parse_args()
    today = date.today().isoformat()
    if args.backtest:
        print("回测模式由 test_engine.py 驱动")
        return
    for sid, cfg in STRATEGIES.items():
        prices = fetch_prices_akshare(cfg["pool"])
        if not prices:
            print(f"  [{sid}] 行情获取失败，今日跳过")
            continue
        prices_hist = {c: [prices[c]] * 4 for c in prices}   # 首日无历史，占位
        rec = run_one_day(sid, cfg, prices_hist, prices, today)
        print(f"  [{sid}] 总资产={rec['cash']+rec['market_value']:.0f} "
              f"盈亏={rec['live_total_pnl']:.2f} 持仓数={len(rec['positions'])}")


if __name__ == "__main__":
    main()
