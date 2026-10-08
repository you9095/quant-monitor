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
                       data_source="Windows实盘引擎(本机模拟撮合)", price_source=None,
                       price_source_detail=None):
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
        "data_nature": "实盘模拟(本机真实撮合, 非回测, 不接券商)",
        "phase": phase,
        "price_source": price_source,
        "price_source_detail": price_source_detail,
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "total_asset": round(total_asset, 2),
        "today_pnl": today_pnl,
        "today_return": today_return,
        "live_total_pnl": snap["total_pnl"],
        "live_total_return": snap["total_return"],
        "live_days": past_days + 1,
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


def fetch_realtime_quotes(pool: list, spot_em_df=None):
    """仅取三源【当日真实价】（盘中=实时最新价；收盘后接口现价=当日收盘价）。

    【铁律 · 2026-10-08 起】绝不使用历史日线收盘价（load_etf_close）兜底成交：
    旧价一旦在行情故障时被当成当日价，会造成"作废价成交"的假账。三源全失败或
    个别必需标的缺失时，如实返回缺失，由 trade_supervisor 按退避计划持续重试，
    直到拿到当日真实价（15:00 后即真实收盘价），从机制上消灭"旧价成交"。

    源链：东财 akshare(含代理绕过+直连) → 腾讯 qt.gtimg.cn → 新浪 hq.sinajs.cn，
    前源缺失标的由后源补齐。spot_em_df 可传入本轮已取的东财快照以避免重复请求。
    返回 (prices, source, detail, per_source)：
      prices  仅含三源真实命中的 {code: price}；
      source  realtime(pool 全命中) / partial(部分命中) / none(全部失败)；
      detail  实际命中源标签，如 tencent、em+tencent、none；
      per_source 各源命中数 {em:n, tencent:n, sina:n}。
    """
    hits = []  # (源标签, {code: price})，按优先级

    # 源1：东财 akshare（已含 NO_PROXY + 禁代理直连；其节点偶发 502）
    try:
        df = spot_em_df if spot_em_df is not None else _ak_spot_em_no_proxy()
        got = {}
        for code in pool:
            row = df[df["代码"] == code]
            if len(row):
                v = float(row.iloc[0]["最新价"])
                if v > 0:
                    got[code] = v
        hits.append(("em", got))
        print(f"  [行情] 东财源取到 {len(got)}/{len(pool)}")
    except Exception as e:
        print(f"  [行情] 东财源不可用: {str(e)[:120]}")

    # 源2/3：腾讯、新浪（requests trust_env=False 强制直连，不读系统代理）
    for tag, fn in (("tencent", _fetch_spot_tencent),
                    ("sina", _fetch_spot_sina)):
        try:
            got = fn(pool)
            hits.append((tag, got))
            print(f"  [行情] {tag}源取到 {len(got)}/{len(pool)}")
        except Exception as e:
            print(f"  [行情] {tag}源不可用: {str(e)[:120]}")

    # 按源优先级合并：先到先得，后续源只补缺失标的（绝不补历史旧价）
    realtime, detail, per_source = {}, [], {}
    for tag, got in hits:
        per_source[tag] = len(got)
        added = 0
        for code, price in got.items():
            if code in pool and code not in realtime:
                realtime[code] = price
                added += 1
        if added:
            detail.append(tag)

    if pool and len(realtime) == len(pool):
        source = "realtime"
    elif realtime:
        source = "partial"
    else:
        source = "none"
    detail_str = "+".join(detail) if detail else "none"
    print(f"  [行情] 汇总: 当日真实价 {len(realtime)}/{len(pool)} "
          f"source={source} detail={detail_str} per_source={per_source}")
    return dict(realtime), source, detail_str, per_source


def fetch_trade_prices(pool: list, spot_em_df=None):
    """兼容旧签名（三元组）的严格真实价获取——已移除历史日线旧价兜底。
    返回 (prices, source, detail)，source ∈ realtime / partial / none。
    """
    prices, source, detail, _ = fetch_realtime_quotes(pool, spot_em_df=spot_em_df)
    return prices, source, detail


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


def run_once(sid: str, cfg: dict, today: str, force: bool = False,
             spot_em_df=None):
    """单段式单策略：决策 → 按当日真实价撮合 → 结算 → 写账本。

    返回结构化 dict（绝不以历史旧价成交），status 取值：
      already        当日已成交（幂等跳过）
      traded         已按当日真实价结算/成交（含换手 0 笔的继续持有）
      idle           无持仓且无目标（空仓 HOLD），已落盘当日记录
      no_history     历史 K 线取不到、无法产生信号（监督器应重试）
      missing_price  必需标的当日真实价未取全（监督器应重试，绝不旧价兜底）
      error          其他异常（监督器记录并重试）
    """
    res = {"sid": sid, "status": None, "missing": [], "required": [],
           "target": {}, "price_source": None, "detail": None,
           "trades_n": 0, "rec": None, "error": None, "per_source": {}}
    if not force and already_traded(sid, today):
        res["status"] = "already"
        return res

    from api.market_data import load_etf_close
    try:
        # 1) 历史收盘 → 动量目标（历史数据允许读缓存，它不是当日成交价）
        hist_map = {}
        for code in cfg["pool"]:
            closes = load_etf_close(code, days=60)
            if closes:
                hist_map[code] = closes
        if not hist_map:
            res["status"] = "no_history"
            res["error"] = "历史行情全部取不到"
            return res
        target = DECIDERS.get(sid, lambda h: {})(
            {c: hist_map.get(c, []) for c in cfg["pool"]})
        res["target"] = target

        # 2) 载入账户、T+1 解冻，确定当日"必须有真实价"的标的 = 目标 ∪ 现持仓
        state_path = STATE_DIR / f"{sid}.json"
        broker = Broker.load_or_new(state_path, cfg["capital"], sid)
        broker.end_of_day()                          # T+1：昨日买入转可卖
        held = sorted(broker.positions.keys())
        required = sorted(set(target) | set(held))
        res["required"] = required

        # 3) 空仓且无目标 → 无需行情，直接落一条 idle(HOLD) 当日记录
        if not required:
            broker.pending_target = {}
            snap = broker.settle({})
            broker.save(state_path)
            rec = _write_live_record(
                sid, cfg, broker, snap, today, "trade", [],
                data_source="Windows实盘引擎(空仓无信号,本机模拟撮合)",
                price_source="idle", price_source_detail="no_position_no_target")
            res.update(status="idle", rec=rec)
            return res

        # 4) 当日真实价（三源）；必需标的缺一个都不撮合，交监督器持续重试
        quotes, source, detail, per = fetch_realtime_quotes(
            required, spot_em_df=spot_em_df)
        res["price_source"], res["detail"], res["per_source"] = source, detail, per
        missing = [c for c in required if c not in quotes]
        if missing:
            res["status"] = "missing_price"
            res["missing"] = missing
            return res

        # 5) 真实撮合 → 结算 → 落盘
        broker.pending_target = target
        trades = broker.rebalance(target, quotes, date=today, names=ETF_NAMES)
        snap = broker.settle(quotes)
        broker.save(state_path)
        rec = _write_live_record(
            sid, cfg, broker, snap, today, "trade", trades,
            data_source="Windows实盘引擎(开机当日真实价成交,本机模拟撮合)",
            price_source="realtime", price_source_detail=detail)
        res.update(status="traded", trades_n=len(trades), rec=rec)
        return res
    except Exception as e:
        import traceback
        res["status"] = "error"
        res["error"] = f"{type(e).__name__}: {e}"
        res["tb"] = traceback.format_exc()
        return res


def run_once_all(today: str, force: bool = False, spot_em_df=None):
    """单轮尝试所有策略（命令行 once / makeup 用）。返回 {trading_day, results}。
    带持续重试与心跳的常驻流程见 trade_supervisor.py。"""
    if not is_trading_day(today):
        print(f"=== [{today}] 判断为非交易日，不成交。 ===")
        return {"trading_day": False, "results": {}}
    print(f"=== [{today}] 开机即决策+成交（单段式·单轮） ===")
    if spot_em_df is None:
        try:
            spot_em_df = _ak_spot_em_no_proxy()
        except Exception as e:
            print(f"  [行情] 东财快照预取失败（将以腾讯/新浪为主）: {str(e)[:120]}")
            spot_em_df = None
    results = {}
    for sid, cfg in STRATEGIES.items():
        r = run_once(sid, cfg, today, force=force, spot_em_df=spot_em_df)
        results[sid] = r
        st, rec = r["status"], r.get("rec")
        if st in ("traded", "idle"):
            tgt = list(rec["pending_target"].keys())
            print(f"  [{sid}] {st} 成交{r['trades_n']}笔 持仓{len(rec['positions'])}只 "
                  f"现金={rec['cash']:.0f} 目标={tgt or '空仓'} 价源={rec['price_source']}")
        elif st == "already":
            print(f"  [{sid}] 今日已成交，幂等跳过。")
        else:
            print(f"  [{sid}] 未成交 status={st} missing={r.get('missing')} "
                  f"价源={r.get('price_source')} {r.get('error') or ''}")
    return {"trading_day": True, "results": results}


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
    trades = broker.rebalance(broker.pending_target, prices_open, date=today,
                              names=ETF_NAMES)
    snap = broker.settle(prices_open)
    broker.save(state_path)
    rec = _write_live_record(sid, cfg, broker, snap, today, "execute", trades)
    return rec


def fetch_realtime_prices(pool: list) -> dict:
    """开盘后：拉实时价（接近开盘价）"""
    prices, _, _ = fetch_trade_prices(pool)
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

    # 跨日红灯锁定（纵深防御）：红标未人工解除前，任何命令行成交/决策入口一律拒绝，
    # 杜绝绕过监督器的自动补单。
    import trade_redflag as rf
    flag = rf.load_redflag(DATA_REPO / "_run_logs")
    if flag:
        print(f"🚩 成交红灯锁定中（事故日 {flag.get('failed_date')}）：已冻结自动成交与补单，"
              f"本次 phase={args.phase} 拒绝执行。请人工核对账目后运行 "
              f"scripts/ack_trade_redflag.py 解除（被冻结日不补单）。")
        sys.exit(3)

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
