#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行情数据层：用 akshare 拉ETF历史收盘价，带本地CSV缓存
缓存目录: data/etf_cache/{code}.csv
当天已缓存则不重复拉取（Windows 每天只跑一次，天然缓存）
"""
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "etf_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(code: str) -> Path:
    return CACHE_DIR / f"{code}.csv"


def load_etf_close(code: str, days: int = 120, use_cache: bool = True) -> list:
    """返回最近 days 个交易日的收盘价 list（旧→新）。失败返回[]"""
    cache = _cache_path(code)
    today = datetime.now().strftime("%Y-%m-%d")
    # 缓存当天有效则直接读
    if use_cache and cache.exists():
        try:
            with open(cache, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if len(rows) > 1 and rows[-1][0] >= today:
                closes = [float(r[1]) for r in rows[1:]]
                return closes[-days:]
        except Exception:
            pass
    # 从 akshare 拉（带重试和限流间隔）
    import time
    for attempt in range(3):
        try:
            import akshare as ak
            start = (datetime.now() - timedelta(days=days * 2 + 60)).strftime("%Y%m%d")
            end = today.replace("-", "")
            df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                     start_date=start, end_date=end, adjust="qfq")
            if df is None or len(df) == 0:
                time.sleep(2)
                continue   # 空数据：重试，而非第一次就放弃
            closes = []
            with open(cache, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "close"])
                for _, r in df.iterrows():
                    d = str(r["日期"])[:10]
                    c = float(r["收盘"])
                    w.writerow([d, c])
                    closes.append(c)
            time.sleep(1.2)   # 限流：每只ETF间隔1.2秒，防被东财断连
            return closes[-days:]
        except Exception as e:
            if attempt == 2:
                print(f"  [行情] {code} 拉取失败: {e}")
            time.sleep(2)   # 失败退避2秒再试
    # 3次都失败才兜底旧缓存（旧数据也强于无数据）
    if cache.exists():
        try:
            with open(cache, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            return [float(r[1]) for r in rows[1:]][-days:]
        except Exception:
            pass
    return []


def load_etf_dates(code: str, days: int = 5, use_cache: bool = True) -> list:
    """返回最近 days 个交易日的日期 list（YYYY-MM-DD，旧→新）。失败返回[]。"""
    cache = _cache_path(code)
    if cache.exists():
        try:
            with open(cache, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            dates = [r[0] for r in rows[1:] if r]
            if dates:
                return dates[-days:]
        except Exception:
            pass
    # 无缓存则先拉一次收盘（会写缓存），再读日期
    if load_etf_close(code, days=max(days, 30), use_cache=use_cache):
        return load_etf_dates(code, days, use_cache=True)
    return []


# ===== A股交易日历（判断节假日，防止休市日用旧价误成交）=====
CAL_PATH = BASE_DIR / "data" / "trade_calendar.json"


def load_trade_dates(use_cache: bool = True):
    """返回 A股交易日集合（'YYYY-MM-DD' 的 set）。失败返回 None。

    用新浪交易日历（akshare tool_trade_date_hist_sina），覆盖全年，
    本地缓存到 data/trade_calendar.json；只要缓存仍覆盖未来 7 天就沿用，
    否则重新拉取；拉取失败则回退到旧缓存。
    """
    cached = None
    if use_cache and CAL_PATH.exists():
        try:
            cached = json.loads(CAL_PATH.read_text(encoding="utf-8"))
        except Exception:
            cached = None

    horizon = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    if cached and cached.get("dates") and max(cached["dates"]) >= horizon:
        return set(cached["dates"])

    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        dates = sorted(str(d)[:10] for d in df["trade_date"])
        try:
            CAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            CAL_PATH.write_text(
                json.dumps({"fetched": datetime.now().strftime("%Y-%m-%d"),
                            "dates": dates}, ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass
        return set(dates)
    except Exception as e:
        print(f"  [行情] 交易日历拉取失败: {e}")
        return set(cached["dates"]) if cached and cached.get("dates") else None


def is_trade_date(date_str: str):
    """某天是否 A股交易日。返回 True/False；交易日历取不到时返回 None（未知）。"""
    cal = load_trade_dates()
    if cal is None:
        return None
    return date_str in cal


# ===== 历史日K多源（东财断连时用新浪/腾讯兜底，供事后补记取真实收盘价）=====
_NOPROXY = {"http": None, "https": None}


def _mkt_prefix(code: str) -> str:
    """沪市 ETF（5/6 开头）→ sh；深市（1 开头）→ sz。"""
    return "sh" if code[:1] in ("5", "6") else "sz"


def sina_etf_hist(code: str, days: int = 120):
    """新浪日K（不复权），返回 [(date, close), ...]；失败 []。"""
    import requests
    pre = _mkt_prefix(code)
    u = ("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
         "CN_MarketData.getKLineData"
         f"?symbol={pre}{code}&scale=240&ma=no&datalen={int(days)}")
    r = requests.get(u, timeout=15, proxies=_NOPROXY)
    data = json.loads(r.text)
    return [(str(x["day"])[:10], float(x["close"])) for x in data]


def tencent_etf_hist(code: str, days: int = 120):
    """腾讯日K（前复权），返回 [(date, close), ...]；失败 []。"""
    import requests
    pre = _mkt_prefix(code)
    u = ("http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
         f"?param={pre}{code},day,,,{int(days)},qfq")
    r = requests.get(u, timeout=15, proxies=_NOPROXY)
    d = r.json()["data"][pre + code]
    rows = d.get("qfqday") or d.get("day") or []
    return [(str(x[0])[:10], float(x[2])) for x in rows]


def load_close_qfq_multi(code: str, days: int = 200) -> list:
    """前复权收盘价（多源，旧→新）：东财(akshare qfq)→腾讯(qfq，最多约642根)。
    用于需要长窗口（如 200 日趋势）的策略：保证价格连续、不受份额折算/分红污染，
    且在东财直连不通时由腾讯兜底。返回 list；都失败返回 []。"""
    need = int(days)
    # 1) 东财前复权（含本地缓存）
    try:
        cl = load_etf_close(code, days=need)
        if cl and len(cl) >= need:
            return cl[-need:]
    except Exception:
        pass
    # 2) 腾讯前复权兜底（约 642 根，2.7 年）
    try:
        t = tencent_etf_hist(code, days=max(need, 300))
        if t:
            closes = [c for _, c in t]
            return closes[-need:] if len(closes) >= need else closes
    except Exception:
        pass
    # 3) 东财根数不足时，返回其结果（聊胜于无）
    try:
        cl = load_etf_close(code, days=need)
        if cl:
            return cl
    except Exception:
        pass
    return []


def load_hist_klines_multi(code: str, day: str, n: int = 60):
    """截至 day 的日K（旧→新），多源：东财缓存/东财→新浪→腾讯。
    返回 (rows, src)：rows=[(date, close), ...]，末日应为 day；失败 ([], "none")。
    只取 day 及之前，杜绝未来数据。"""
    # 1) 东财（含本地缓存）
    rows = []
    try:
        cl = load_etf_close(code, days=max(n, 90))
        dates = load_etf_dates(code, days=max(n, 90))
        if cl and dates and len(cl) == len(dates):
            rows = list(zip(dates, cl))
    except Exception:
        rows = []
    # 2) 新浪兜底
    if (not rows) or rows[-1][0] < day:
        try:
            s = sina_etf_hist(code, days=max(n, 90))
            if s and (not rows or s[-1][0] >= rows[-1][0]):
                rows = s
        except Exception:
            pass
    # 3) 腾讯兜底
    if (not rows) or rows[-1][0] < day:
        try:
            t = tencent_etf_hist(code, days=max(n, 90))
            if t and (not rows or t[-1][0] >= rows[-1][0]):
                rows = t
        except Exception:
            pass
    if not rows:
        return [], "none"
    rows = [r for r in rows if r[0] <= day]
    if len(rows) > n:
        rows = rows[-n:]
    src = "multi(sina/tencent/em)" if rows else "none"
    return rows, src
