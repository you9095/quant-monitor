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
                return []
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
        # 兜底：读旧缓存
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
