#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日实盘引擎
============
不连接任何券商。所有买卖为本地模拟撮合（含佣金/印花税/滑点/T+1）。

【现行方案 · 2026-10-04 起】单段式（once），适配"只在交易日 13:00-17:00 开机"：
  开机后（onlogon 或 15:10 兜底）一次完成：
    拉历史收盘算动量信号 → 取开机时刻最新价（盘中实时价 / 收盘后当日收盘价）
    → end_of_day(T+1) → 按目标真实撮合 → settle 记净值 → 写账本
  当日幂等：daily/<today>/<sid>.json 已存在 phase=trade 则不再成交，防止重复。

【已废弃但保留兼容】两段式 decide/execute（T日15:30决策、T+1 09:35开盘成交），
  因电脑上午不开机、09:35 任务永不触发，已不再注册计划任务，仅留作测试。

用法：
  python run_daily_engine.py once     # 现行：开机即决策+成交（Windows 任务调用）
  python run_daily_engine.py decide   # 旧两段式-决策（测试用）
  python run_daily_engine.py execute  # 旧两段式-成交（测试用）
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


def _write_live_record(sid, cfg, broker, snap, today, phase, trades=None,
                       data_source="Windows实盘引擎(本机模拟撮合)", price_source=None):
    """写 live-data/latest 和 daily/<today>/"""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "date": today, "strategy_id": sid, "strategy_name": cfg["name"],
        "initial_capital": cfg["capital"],
        "data_source": data_source,
        "data_nature": "实盘模拟(本机真实撮合, 非回测, 不接券商)",
        "phase": phase,
        "price_source": price_source,
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
# 现行方案：开机即决策 + 成交（单段式 once）
# ============================================================
def already_traded(sid: str, today: str) -> bool:
    """当日幂等：今天该策略已按 once 成交过则返回 True（含空仓结果）。"""
    f = DAILY_DIR / today / f"{sid}.json"
    if not f.exists():
        return False
    try:
        rec = json.loads(f.read_text(encoding="utf-8"))
        return rec.get("date") == today and rec.get("phase") == "trade"
    except Exception:
        return False


def fetch_trade_prices(pool: list):
    """开机时刻成交价。

    盘中(13:00-15:00)：ETF 实时最新价；收盘后(>=15:00)：接口返回的当日收盘价。
    实时接口缺失的标的，用最新一根日线收盘价兜底。
    返回 (prices, source)，source ∈ realtime / mixed / close_fallback。
    """
    realtime = {}
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        for code in pool:
            row = df[df["代码"] == code]
            if len(row):
                v = float(row.iloc[0]["最新价"])
                if v > 0:
                    realtime[code] = v
    except Exception as e:
        print(f"  [行情] 实时价接口失败: {e}")

    prices = dict(realtime)
    if len(prices) < len(pool):
        try:
            from api.market_data import load_etf_close
            for code in pool:
                if code in prices:
                    continue
                closes = load_etf_close(code, days=5)
                if closes:
                    prices[code] = closes[-1]
        except Exception as e:
            print(f"  [行情] 日线兜底失败: {e}")

    if len(realtime) == len(pool):
        source = "realtime"
    elif realtime:
        source = "mixed"
    else:
        source = "close_fallback"
    return prices, source


def is_trading_day(today: str) -> bool:
    """今天是否 A股交易日（节假日不成交）。

    优先用权威交易日历（akshare 新浪日历，覆盖全年，盘中/盘后都准确），
    休市日（如国庆 10-01~10-07）即使开机也不会拿上一交易日旧价误成交。
    交易日历取不到（断网等）才退回兜底：周末必不交易；盘后用最新日线日期
    复核；盘中无法确认时不阻断真实交易日。
    """
    # 1) 优先权威交易日历（盘中/盘后都准确，休市日开机也不会拿旧价误成交）
    try:
        from api.market_data import is_trade_date
        cal = is_trade_date(today)
        if cal is not None:
            return bool(cal)
    except Exception:
        pass

    # 2) 交易日历取不到时的保守兜底
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    if now.hour < 15:
        return True
    try:
        from api.market_data import load_etf_dates
        for code in ("510300", "513100", "518880"):
            dates = load_etf_dates(code, days=3)
            if dates and dates[-1] == today:
                return True
        return False
    except Exception:
        # 取不到日期就不阻断（宁可不误杀真实交易日）
        return True


def run_once(sid: str, cfg: dict, today: str, force: bool = False):
    """单段式：开机即 决策→成交→结算，写账本。返回 record 或 None。"""
    if not force and already_traded(sid, today):
        print(f"  [{sid}] 今日已成交，幂等跳过。")
        return None

    from api.market_data import load_etf_close

    # 1) 历史收盘 → 动量目标
    hist_map = {}
    for code in cfg["pool"]:
        closes = load_etf_close(code, days=60)
        if closes:
            hist_map[code] = closes
    if not hist_map:
        print(f"  [{sid}] 历史行情失败，跳过。")
        return None
    target = DECIDERS.get(sid, lambda h: {})(
        {c: hist_map.get(c, []) for c in cfg["pool"]})

    # 2) 开机时刻成交价
    prices, source = fetch_trade_prices(cfg["pool"])
    # 目标标的必须有价；持仓标的也要有价才能结算
    need = set(target) | set()  # 目标为空时也要能结算（用持仓代码）
    if not prices:
        print(f"  [{sid}] 成交价全部取不到，跳过。")
        return None

    # 3) 撮合
    state_path = STATE_DIR / f"{sid}.json"
    broker = Broker.load_or_new(state_path, cfg["capital"], sid)
    broker.end_of_day()                          # T+1：昨日买入转可卖
    broker.pending_target = target
    trades = broker.rebalance(target, prices, date=today)
    snap = broker.settle(prices)
    broker.save(state_path)

    rec = _write_live_record(
        sid, cfg, broker, snap, today, "trade", trades,
        data_source="Windows实盘引擎(开机当日最新价成交,本机模拟撮合)",
        price_source=source)
    return rec


def run_once_all(today: str, force: bool = False):
    if not is_trading_day(today):
        print(f"=== [{today}] 判断为非交易日，不成交。 ===")
        return
    print(f"=== [{today}] 开机即决策+成交（单段式） ===")
    for sid, cfg in STRATEGIES.items():
        try:
            rec = run_once(sid, cfg, today, force=force)
            if rec is None:
                continue
            tgt = list(rec["pending_target"].keys())
            print(f"  [{sid}] 成交{len(rec['trades_today'])}笔 "
                  f"持仓{len(rec['positions'])}只 现金={rec['cash']:.0f} "
                  f"目标={tgt or '空仓'} 价源={rec['price_source']}")
        except Exception as e:
            import traceback
            print(f"  [{sid}] 异常: {e}")
            traceback.print_exc()


# ============================================================
# 旧两段式（保留兼容，不再注册任务）
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


def fetch_realtime_prices(pool: list) -> dict:
    """开盘后：拉实时价（接近开盘价）"""
    prices, _ = fetch_trade_prices(pool)
    return prices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", nargs="?", default="once",
                    choices=["once", "decide", "execute", "both"])
    ap.add_argument("--force", action="store_true",
                    help="once 模式忽略当日幂等，强制再成交（慎用）")
    args = ap.parse_args()
    today = date.today().isoformat()
    from api.market_data import load_etf_close

    if args.phase == "once":
        run_once_all(today, force=args.force)
        return

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
