#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日实盘引擎：两段式（决策与执行分离）
==========================================
不连接任何券商。所有买卖为本地模拟撮合（含佣金/印花税/滑点/T+1）。

时序：
  T日 15:30  decide: 拉收盘价 → settle净值 → 算动量信号 → 存 pending_target
  T+1日 9:35 execute: 拉开盘价 → 按昨日 pending_target 真实撮合买卖

这样成交用的是次日开盘价，贴近真实日频轮动策略。

用法：
  python run_daily_engine.py decide    # 收盘后跑（15:30）
  python run_daily_engine.py execute   # 开盘后跑（次日9:35）
  python run_daily_engine.py          # 两段都跑（macOS 测试用）
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
    "qixing": {"name": "七星策略", "capital": 10000, "pool":
               ["159967","159980","159981","159985","161226","501018","511880",
                "512100","513030","513080","513100","513500","513520","513690","588080"],
               "mom_window": 20, "hold": 1},
    "r32":    {"name": "三驾马车", "capital": 10000, "pool":
               ["510500", "512040", "512100"], "mom_window": 20, "hold": 1},
    "zhuidian": {"name": "追电策略", "capital": 10000, "pool":
                 ["513100","513500","513030","513520","513690"], "mom_window": 10, "hold": 1},
    "sanhe":  {"name": "三合策略", "capital": 10000, "pool":
               ["159915","159967","159980","159981","510300","510500","512100",
                "512890","513030","513100","513500","513520","518880","588080"],
               "mom_window": 20, "hold": 1},
    "lightning": {"name": "闪电策略", "capital": 10000,
                  "pool": ["513100", "513520", "513030", "513130"],
                  "mom_window": 3, "hold": 1},
    "goldcombo": {"name": "黄金组合A", "capital": 10000, "pool":
                  ["518880"], "mom_window": 20, "hold": 1, "trend_filter": True},
}


# ============================================================
# 动量轮动决策
# ============================================================
def momentum_rotate(hist_map: dict, window: int, hold: int = 1,
                     trend_filter: bool = False) -> dict:
    scores = []
    for code, closes in hist_map.items():
        if len(closes) < window + 1:
            continue
        mom = closes[-1] / closes[-1 - window] - 1
        if trend_filter:
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            if closes[-1] < ma20:
                continue
        scores.append((mom, code))
    scores.sort(reverse=True)
    picks = [(m, c) for m, c in scores if m > 0][:hold]
    if not picks:
        return {}
    w = 1.0 / len(picks)
    return {c: w for _, c in picks}


def decide_for(sid: str, cfg: dict) -> callable:
    w = cfg.get("mom_window", 20)
    h = cfg.get("hold", 1)
    tf = cfg.get("trend_filter", False)
    def _decide(hist_map):
        return momentum_rotate(hist_map, w, h, tf)
    return _decide


DECIDERS = {sid: decide_for(sid, cfg) for sid, cfg in STRATEGIES.items()}


def _write_live_record(sid, cfg, broker, snap, today, phase, trades=None):
    """写 live-data/latest 和 daily/<today>/"""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "date": today, "strategy_id": sid, "strategy_name": cfg["name"],
        "initial_capital": cfg["capital"],
        "data_source": "Windows实盘引擎(次日开盘成交)",
        "phase": phase,
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "live_total_pnl": snap["total_pnl"],
        "live_total_return": snap["total_return"],
        "live_days": len(broker.trades),
        "cash": snap["cash"], "market_value": snap["market_value"],
        "positions": snap["positions"],
        "pending_target": broker.pending_target,
        "trades_today": trades or [],
    }
    day_dir = DAILY_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (LATEST_DIR / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


# ============================================================
# 阶段1：收盘后决策（15:30）
# ============================================================
def run_decide(sid, cfg, hist_map, prices_close, today):
    """end_of_day → settle → 算信号存 pending_target，不买卖"""
    state_path = STATE_DIR / f"{sid}.json"
    broker = Broker.load_or_new(state_path, cfg["capital"], sid)
    broker.end_of_day()                       # T+1：昨日买入转可卖
    snap = broker.settle(prices_close)        # 按收盘价记录今日净值
    decider = DECIDERS.get(sid, lambda h: {})
    broker.pending_target = decider(
        {c: hist_map.get(c, []) for c in cfg["pool"]})
    broker.save(state_path)
    rec = _write_live_record(sid, cfg, broker, snap, today, "decide")
    return rec


# ============================================================
# 阶段2：次日开盘执行（9:35）
# ============================================================
def run_execute(sid, cfg, prices_open, today):
    """按昨日 pending_target 用今天开盘价真实撮合"""
    state_path = STATE_DIR / f"{sid}.json"
    broker = Broker.load_or_new(state_path, cfg["capital"], sid)
    if not broker.pending_target:
        snap = broker.settle(prices_open)
        rec = _write_live_record(sid, cfg, broker, snap, today, "execute_hold")
        return rec
    trades = broker.rebalance(broker.pending_target, prices_open, date=today)
    snap = broker.settle(prices_open)
    broker.save(state_path)
    rec = _write_live_record(sid, cfg, broker, snap, today, "execute", trades)
    return rec


# ============================================================
# 行情
# ============================================================
def fetch_realtime_prices(pool: list) -> dict:
    """开盘后：拉实时价（接近开盘价）"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        return {code: float(df[df["代码"] == code].iloc[0]["最新价"])
                for code in pool if len(df[df["代码"] == code])}
    except Exception as e:
        print(f"  [行情] 实时价失败: {e}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", nargs="?", default="both",
                    choices=["decide", "execute", "both"])
    args = ap.parse_args()
    today = date.today().isoformat()
    from api.market_data import load_etf_close

    if args.phase in ("decide", "both"):
        print(f"=== [{today}] 阶段1：收盘决策 ===")
        for sid, cfg in STRATEGIES.items():
            hist_map, prices = {}, {}
            for code in cfg["pool"]:
                closes = load_etf_close(code, days=60)
                if closes:
                    hist_map[code] = closes
                    prices[code] = closes[-1]
            if not prices:
                print(f"  [{sid}] 行情失败，跳过")
                continue
            rec = run_decide(sid, cfg, hist_map, prices, today)
            tgt = list(rec["pending_target"].keys())
            print(f"  [{sid}] 净值={rec['cash']+rec['market_value']:.0f} "
                  f"明日目标={tgt or '空仓'}")

    if args.phase in ("execute", "both"):
        print(f"=== [{today}] 阶段2：开盘执行 ===")
        for sid, cfg in STRATEGIES.items():
            prices = fetch_realtime_prices(cfg["pool"])
            if not prices:
                print(f"  [{sid}] 实时价失败，跳过")
                continue
            rec = run_execute(sid, cfg, prices, today)
            print(f"  [{sid}] 成交{len(rec['trades_today'])}笔 "
                  f"持仓{len(rec['positions'])}只 现金={rec['cash']:.0f}")


if __name__ == "__main__":
    main()
