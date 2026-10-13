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
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "api"))

# 国内行情/日历域名强制绕过代理：科学上网软件关闭后常残留 127.0.0.1:xxxx 代理，
# 导致 eastmoney/sina 等国内接口 ProxyError、实时价取不到而回退旧收盘价。
# GitHub 等确需代理的域名不在此列表，不受影响。
_NO_PROXY_DOMAINS = [
    "localhost", "127.0.0.1",
    ".eastmoney.com", "eastmoney.com",
    ".sina.com.cn", "sina.com.cn", ".sinajs.cn", "sinajs.cn",
    ".sse.com.cn", "sse.com.cn", ".szse.cn", ".csindex.com.cn",
    ".10jqka.com.cn", ".xueqiu.com",
]
_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
               "ALL_PROXY", "all_proxy")


def _bypass_proxy_for_domestic():
    for key in ("NO_PROXY", "no_proxy"):
        items = [x.strip() for x in os.environ.get(key, "").split(",") if x.strip()]
        for d in _NO_PROXY_DOMAINS:
            if d not in items:
                items.append(d)
        os.environ[key] = ",".join(items)


_bypass_proxy_for_domestic()


def _ak_spot_em_no_proxy():
    """ETF 实时行情；经当前代理失败时，临时彻底关闭代理直连重试（国内行情站无需代理）。"""
    import akshare as ak
    try:
        return ak.fund_etf_spot_em()
    except Exception as e1:
        print(f"  [行情] 实时价经当前代理失败（{str(e1)[:120]}），关闭代理直连重试...")
        saved = {k: os.environ.get(k) for k in _PROXY_KEYS}
        try:
            for k in _PROXY_KEYS:
                os.environ.pop(k, None)
            return ak.fund_etf_spot_em()
        except Exception as e2:
            print(f"  [行情] 实时价关闭代理直连仍失败: {str(e2)[:160]}")
            raise
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


def _market_prefix(code: str) -> str:
    """ETF 代码加交易所前缀：5/6 开头沪市 sh，其余（1 开头等）深市 sz。"""
    return ("sh" if code[0] in "56" else "sz") + code


def _direct_session():
    """不读系统代理的 requests Session（国内行情站强制直连，绕开失效代理）。"""
    import requests
    s = requests.Session()
    s.trust_env = False
    return s


def _fetch_spot_tencent(pool: list) -> dict:
    """腾讯行情 qt.gtimg.cn；盘后现价即当日收盘价。返回 {code: price}。"""
    q = ",".join(_market_prefix(c) for c in pool)
    r = _direct_session().get(
        "https://qt.gtimg.cn/q=" + q, timeout=10,
        headers={"Referer": "https://gu.qq.com/"})
    r.encoding = "gbk"
    r.raise_for_status()
    out = {}
    for line in r.text.strip().split("\n"):
        if "~" not in line:
            continue
        f = line.split("~")
        try:
            code, price = f[2], float(f[3])
            if code in pool and price > 0:
                out[code] = price
        except (IndexError, ValueError):
            continue
    return out


def _fetch_spot_sina(pool: list) -> dict:
    """新浪行情 hq.sinajs.cn；盘后现价即当日收盘价。返回 {code: price}。"""
    q = ",".join(_market_prefix(c) for c in pool)
    r = _direct_session().get(
        "https://hq.sinajs.cn/list=" + q, timeout=10,
        headers={"Referer": "https://finance.sina.com.cn"})
    r.encoding = "gbk"
    r.raise_for_status()
    out = {}
    for line in r.text.strip().split("\n"):
        if '="' not in line:
            continue
        head, payload = line.split('="', 1)
        code = head.split("_")[-1].strip()[2:]   # var hq_str_sh513100 -> 513100
        v = payload.strip('";').split(",")
        try:
            price = float(v[3])                   # v[2]=昨收, v[3]=现价/收盘
            if code in pool and price > 0:
                out[code] = price
        except (IndexError, ValueError):
            continue
    return out


import market_data as md  # noqa: E402  # 固定单一模块对象（避免 api.market_data 双重加载）
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
                 ["513100","513500","513030","513520","513690"], "mom_window": 10, "hold": 1, "momentum_threshold": 0.01},
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

# ETF 代码 → 名称（成交记录/对账单显示用；实时行情接口返回名称时以接口为准）
ETF_NAMES = {
    "511880": "银华日利ETF", "510300": "沪深300ETF", "510500": "中证500ETF",
    "159915": "创业板ETF", "513100": "纳指ETF", "513520": "日经ETF",
    "518880": "黄金ETF", "159985": "豆粕ETF", "588080": "科创50ETF",
    "512100": "中证1000ETF", "512040": "国泰价值ETF", "512890": "红利低波ETF",
    "513130": "恒生科技ETF", "513030": "纳指科技ETF", "161226": "国泰商品ETF",
    "159967": "创成长ETF", "159980": "有色ETF", "159981": "能源化工ETF",
    "513080": "法国CAC40ETF", "513500": "标普500ETF", "513690": "恒生股息ETF",
    "501018": "南方原油LOF",
}


# ============================================================
# 动量轮动决策
# ============================================================
def momentum_rotate(hist_map: dict, window: int, hold: int = 1,
                      trend_filter: bool = False, momentum_threshold: float = 0.0) -> dict:
    scores = []
    for code, closes in hist_map.items():
        if len(closes) < window + 1:
            continue
        mom = closes[-1] / closes[-1 - window] - 1
        if mom <= momentum_threshold:
            continue
        if trend_filter:
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            if closes[-1] < ma20:
                continue
        scores.append((mom, code))
    scores.sort(reverse=True)
    picks = [(m, c) for m, c in scores][:hold]
    if not picks:
        return {}
    w = 1.0 / len(picks)
    return {c: w for _, c in picks}


def decide_for(sid: str, cfg: dict) -> callable:
    w = cfg.get("mom_window", 20)
    h = cfg.get("hold", 1)
    tf = cfg.get("trend_filter", False)
    mt = cfg.get("momentum_threshold", 0.0)  # New: momentum threshold
    def _decide(hist_map):
        return momentum_rotate(hist_map, w, h, tf, mt)
    return _decide


DECIDERS = {sid: decide_for(sid, cfg) for sid, cfg in STRATEGIES.items()}


def _write_live_record(sid, cfg, broker, snap, today, phase, trades=None,
                       data_source="Windows实盘引擎(本机模拟撮合)", price_source=None,
                       price_source_detail=None, data_nature=None, extra_fields=None):
    """写 live-data/latest 和 daily/<today>/"""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    total_asset = snap["total_asset"]
    # 今日盈亏：相对上一交易日总权益；首日（无历史）相对初始本金
    prev_asset = cfg["capital"]
    prev_latest = LATEST_DIR / f"{sid}.json"
    if prev_latest.exists():
        try:
            prev = json.loads(prev_latest.read_text(encoding="utf-8"))
            prev_asset = prev.get("total_asset",
                                  prev.get("cash", 0) + prev.get("market_value", 0))
        except Exception:
            pass
    today_pnl = round(total_asset - prev_asset, 2)
    today_return = round(today_pnl / prev_asset * 100, 2) if prev_asset else 0.0

    # 真实运行天数 = daily 下该策略已落盘的交易日记录数 + 今日
    past_days = len(list(DAILY_DIR.glob(f"*/{sid}.json")))

    record = {
        "date": today, "strategy_id": sid, "strategy_name": cfg["name"],
        "initial_capital": cfg["capital"],
        "data_source": data_source,
        "data_nature": data_nature or "实盘模拟(本机真实撮合, 非回测, 不接券商)",
        "phase": phase,
        "price_source": price_source,
        "price_source_detail": price_source_detail,
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "total_asset": round(total_asset, 2),
        "today_pnl": today_pnl,
        "today_return": today_return,
        "live_total_pnl": snap["total_pnl"],
        "live_total_return": snap["total_return"],
        "realized_pnl": snap.get("realized_pnl", 0.0),
        "live_days": past_days + 1,
        "cash": snap["cash"], "market_value": snap["market_value"],
        "positions": snap["positions"],
        "pending_target": broker.pending_target,
        "trades_today": trades or [],
    }
    if extra_fields:
        record.update(extra_fields)
    day_dir = DAILY_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (LATEST_DIR / f"{sid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同步写入 ~/.hermes/work_logs/<sid>/，供 bridge_worklog_to_signal.py 读取
    # （含 pending_target，便于恢复 target_etfs 提取）。
    try:
        wl = Path.home() / ".hermes" / "work_logs" / sid
        wl.mkdir(parents=True, exist_ok=True)
        (wl / f"{today}_{sid}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return record


# ============================================================
# 主流程胶水（once 单段式）：交易日判断 / 当日真实价 / 单策略执行 / 每日入口
# ============================================================
def is_trading_day(today):
    """today('YYYY-MM-DD') 是否 A股交易日。日历取不到时退化为周末判断（保守）。"""
    r = md.is_trade_date(today)
    if r is None:
        return datetime.strptime(today, "%Y-%m-%d").weekday() < 5
    return bool(r)


def _prices_from_em(df, pool):
    """从东财 fund_etf_spot_em 快照（DataFrame）提取 {code: price}。"""
    out = {}
    if df is None:
        return out
    try:
        for _, r in df.iterrows():
            c = str(r.get("代码", "")).strip().zfill(6)
            if c in pool:
                p = float(r.get("最新价"))
                if p > 0:
                    out[c] = p
    except Exception:
        pass
    return out


def fetch_realtime_quotes(pool, spot_em_df=None):
    """三源取当日真实价（收盘后现价=收盘价）：东财→腾讯→新浪，缺失的再兜底。
    返回 (prices, mode, source_detail, per_source)。
    全失败返回 ({}, 'none', 'none', {em:0,tencent:0,sina:0})。"""
    per_source = {"em": 0, "tencent": 0, "sina": 0}
    prices = {}
    if spot_em_df is not None:
        em = _prices_from_em(spot_em_df, pool)
        per_source["em"] = len(em)
        prices.update(em)
    miss = [c for c in pool if c not in prices]
    if miss:
        try:
            t = _fetch_spot_tencent(miss)
            per_source["tencent"] = len(t)
            prices.update(t)
        except Exception:
            pass
    miss = [c for c in pool if c not in prices]
    if miss:
        try:
            s = _fetch_spot_sina(miss)
            per_source["sina"] = len(s)
            prices.update(s)
        except Exception:
            pass
    if not prices:
        return {}, "none", "none", per_source
    detail = "+".join(k for k, v in per_source.items() if v)
    return prices, "realtime", detail, per_source


def load_hist_map(pool, days=60):
    """拉取 pool 全部历史收盘 {code: closes}；个别失败不影响其它。"""
    hist = {}
    for code in pool:
        cl = md.load_etf_close(code, days=max(days, 60))
        if cl:
            hist[code] = cl
    return hist


def run_once(sid, cfg, today, force=False, spot_em_df=None):
    """单策略完整执行：加载账本→历史动量目标→当日真实价→撮合→结算→写记录→存账本。
    返回 dict（status/rec/per_source/missing/required/target/trades_n/price_source/detail）。
    当日已成交（非 force）幂等返回 already。"""
    state_file = STATE_DIR / f"{sid}.json"
    day_file = DAILY_DIR / today / f"{sid}.json"
    if not force and day_file.exists():
        try:
            old = json.loads(day_file.read_text(encoding="utf-8"))
            if old.get("phase") == "trade":
                return {"status": "already", "rec": None, "per_source": None,
                        "missing": [], "required": [], "target": None,
                        "trades_n": 0, "price_source": old.get("price_source"),
                        "detail": None}
        except Exception:
            pass
    try:
        pool = cfg["pool"]
        broker = Broker.load_or_new(state_file, cfg["capital"], sid)
        broker.end_of_day()  # 上一交易日买入转为可卖（T+1）

        # 1) 历史收盘 → 动量目标
        hist = load_hist_map(pool)
        if not hist:
            return {"status": "no_history", "rec": None, "per_source": None,
                    "missing": [], "required": pool, "target": None,
                    "trades_n": 0, "price_source": None, "detail": None}
        target = DECIDERS[sid](hist)
        broker.pending_target = target

        # 2) 当日真实价（收盘价）
        prices, mode, detail, per_source = fetch_realtime_quotes(pool, spot_em_df)
        # 三源全失败是整体性故障：任何策略（含空仓无目标）都不在本轮落盘，等行情恢复
        if mode == "none":
            return {"status": "missing_price", "rec": None, "per_source": per_source,
                    "missing": pool, "required": pool, "target": target,
                    "trades_n": 0, "price_source": mode, "detail": detail}
        required = list(target.keys()) + list(broker.positions.keys())
        missing = [c for c in required if c not in prices]
        if missing:
            # 缺真实价（卖出现持仓 / 买入目标都需要）：绝不动账、绝不用旧价，等重试
            return {"status": "missing_price", "rec": None, "per_source": per_source,
                    "missing": missing, "required": required, "target": target,
                    "trades_n": 0, "price_source": mode, "detail": detail}

        # 3) 真实撮合（先卖非目标、再买目标）
        names = {c: ETF_NAMES.get(c, "") for c in pool}
        trades = broker.rebalance(target, prices, date=today, names=names)
        # 4) 当日结算
        snap = broker.settle(prices)
        # 5) 状态：有成交=traded；无成交但已持有目标=traded（就位）；空仓无目标=idle
        if trades or broker.positions:
            status = "traded"
        else:
            status = "idle"
        # 6) 写记录 + 存账本
        rec = _write_live_record(sid, cfg, broker, snap, today, "trade",
                                 trades=trades, price_source=mode,
                                 price_source_detail=detail)
        broker.save(state_file)
        return {"status": status, "rec": rec, "per_source": per_source,
                "missing": [], "required": required, "target": target,
                "trades_n": len(trades), "price_source": mode, "detail": detail}
    except Exception as e:
        import traceback
        return {"status": "error", "rec": None, "per_source": None,
                "missing": [], "required": [], "target": None,
                "trades_n": 0, "error": str(e), "tb": traceback.format_exc()}


def main(argv=None):
    """每日入口（run_daily.py 转发）：once 单段式，遍历六策略。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", nargs="?", default="once",
                    choices=["once", "decide", "execute"])
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    today = args.date
    print(f"[每日引擎] {today} 模式 {args.phase}（模拟盘，本机真实撮合，不接券商）")

    # 红标闸门：红标锁定时，在任何交易日判断 / 成交之前直接拒绝（退出码 3）
    try:
        import trade_redflag as _rf
        if _rf.load_redflag(DATA_REPO / "_run_logs"):
            print(f"🚩 成交红标锁定中（事故日 "
                  f"{_rf.load_redflag(DATA_REPO / '_run_logs').get('failed_date')}），"
                  "本次不成交、不补单；解除运行 scripts/ack_trade_redflag.py。")
            sys.exit(3)
    except SystemExit:
        raise
    except Exception:
        pass

    if not is_trading_day(today):
        print("非交易日，跳过。")
        return 0
    spot = None
    try:
        spot = _ak_spot_em_no_proxy()
    except Exception as e:
        print("东财快照预取失败，腾讯/新浪兜底:", str(e)[:120])
    done, trades_total = 0, 0
    for sid, cfg in STRATEGIES.items():
        r = run_once(sid, cfg, today, force=args.force, spot_em_df=spot)
        st = r["status"]
        asset = (r.get("rec") or {}).get("total_asset")
        print(f"  [{sid}] {st} 成交 {r.get('trades_n')} 笔 总资产 {asset}")
        if st in ("traded", "idle", "already"):
            done += 1
        trades_total += r.get("trades_n", 0)
    print(f"[每日引擎] 完成 {done}/{len(STRATEGIES)}，成交 {trades_total} 笔。")
    return 0 if done == len(STRATEGIES) else 1

