#!/usr/bin/env python3
"""
TickDB 接入骨架 — quant-monitor-local/api/tickdb_client.py
============================================================

TickDB 官网: https://tickdb.ai
鉴权方式: Header X-API-Key(单一 Key 全渠道通用)
关键 REST: GET https://api.tickdb.ai/v1/market/ticker?symbols=...

设计约束:
  - 纯 stdlib(urllib + json + os + pathlib),不引入 requests/aiohttp/websockets
  - os.environ.get('TICKDB_API_KEY') 读 Key,缺 Key 时 print 提示优雅降级

调用方:
  from tickdb_client import fetch_realtime_prices_v2
  prices = fetch_realtime_prices_v2(['159915', '510300'])  # 返回 {'159915': x.xx, ...}

"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ────────────────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────────────────
DEFAULT_BASE_URL = "https://api.tickdb.ai"
DEFAULT_TIMEOUT = 10  # 秒
DEFAULT_USER_AGENT = "quant-monitor-local/1.0 (+https://tickdb.ai)"
PRICE_CACHE: dict[str, float] = {}  # 模块级缓存,供外部复用


# ────────────────────────────────────────────────────────────────────
# 异常类型
# ────────────────────────────────────────────────────────────────────
class TickDBError(Exception):
    """TickDB API 调用失败基类"""


class TickDBAuthError(TickDBError):
    """401/403 鉴权失败(Key 缺/错/失效)"""


class TickDBRateLimitError(TickDBError):
    """429 限流"""


class TickDBNetworkError(TickDBError):
    """网络层错误(超时/DNS/连接重置)"""


# ────────────────────────────────────────────────────────────────────
# Code 格式转换工具
# ────────────────────────────────────────────────────────────────────
def _detect_market(code: str) -> str:
    """
    根据代码判断市场归属(用于从 raw code 自动转 TickDB 格式)。

    输入: "159915" / "700" / "NVDA" / "BTCUSDT" / "600519"
    输出: "SH" / "SZ" / "BJ" / "HK" / "US" / "CRYPTO" / "FUTURES"
    """
    c = code.upper().strip()
    # 港股前缀 0 归一化: "00700" -> "700" 是港股常见格式
    # 但要避开 6 位 A 股代码(000001 平安银行),只有 ≤5 位才允许 strip
    if c.isdigit() and c.startswith('0') and len(c) <= 5:
        c = c.lstrip('0') or '0'
    # 指数:白名单(SPX / NDX / DJI / FTSE / N225 / HSI 等)
    # 不能用纯字母 ≤5 位一刀切,会把美股 NVDA/AAPL 误判
    if c in {"SPX", "NDX", "DJI", "FTSE", "N225", "HSI", "SX5E", "VIX", "DXY"}:
        return "IDX"
    # 加密币:无数字 + 常见字母结尾(suffix USDT/USD/BUSD)
    if c.endswith(("USDT", "USD", "BUSD", "BTC", "ETH")) and not c[:1].isdigit():
        return "CRYPTO"
    # 中国期货: BU2609 / IC2606 / AP8888 — 字母开头 + 数字
    if c[:1].isalpha() and any(ch.isdigit() for ch in c):
        first_alpha = c.rstrip("0123456789")
        if first_alpha in {"BU", "IC", "AP", "CU", "AL", "ZN", "AU", "AG"}:
            return "FUTURES"
    # 纯字母(美股/港股缩写) — 但港股代码 4 位数字
    if c.isalpha():
        return "US"
    # A 股: 6 位数字(优先判断)
    if len(c) == 6 and c.isdigit():
        if c.startswith(("60", "68", "90")):  # 60xxxx=沪, 68xxxx=科创板, 90xxxx=B 股(并入 .SH)
            return "SH"
        if c.startswith(("00", "30", "20")):  # 00/30=深主板创业板, 20=B 股
            return "SZ"
        if c.startswith(("8", "92")):  # 8xxxxx/92xxxx=北证
            return "BJ"
        return "SH"  # 兜底沪市
    # 港股: 1~5 位纯数字(且不是 6 位)。A 股代码都是 6 位,其他位数的纯数字 → 港股。
    # 前缀 0 归一化: "00700" -> "700" 是港股常见格式
    if c.isdigit() and len(c) <= 5:
        return "HK"
    # 美股兜底(已含字母或包含字母数字混合)
    return "US"


def normalize_code(raw_code: str) -> str:
    """
    将 raw code 转 TickDB 标准格式。

    159915  → "159915.SH"
    600519  → "600519.SH"
    000001  → "000001.SZ"
    700     → "700.HK"
    9988    → "9988.HK"
    NVDA    → "NVDA.US"
    AAPL    → "AAPL.US"
    BTCUSDT → "BTCUSDT"
    SPX     → "SPX"(指数无后缀)
    """
    c = raw_code.strip()
    upper = c.upper()
    # 已是 TickDB 格式(带 .)
    if "." in c and not c.startswith("."):
        return c
    # 港股前缀 0 归一化("00700" -> "700"),与 _detect_market 保持一致
    if upper.isdigit() and upper.startswith('0') and len(upper) <= 5:
        upper = upper.lstrip('0') or '0'
    market = _detect_market(upper)
    if market in ("CRYPTO", "FUTURES"):
        return upper  # 加密币/期货原始形态
    if market == "US":
        return f"{upper}.US"  # 纯字母美股代码补 .US 后缀
    if market in ("SH", "SZ", "BJ", "HK"):
        return f"{upper}.{market}"
    return upper  # 兜底


# ────────────────────────────────────────────────────────────────────
# 主客户端
# ────────────────────────────────────────────────────────────────────
class TickDBClient:
    """
    TickDB REST 客户端(纯 stdlib)。

    用法:
        client = TickDBClient()  # 自动读 os.environ['TICKDB_API_KEY']
        client = TickDBClient(api_key='tb_xxxxx')  # 显式传
        client.get_ticker(['700.HK', 'AAPL.US'])
        client.fetch_realtime_prices_v2(['159915', 'NVDA'])
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.environ.get("TICKDB_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.has_key = bool(self.api_key)

    # ── 内部辅助 ──
    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise TickDBAuthError("TICKDB_API_KEY 未配置(export TICKDB_API_KEY=xxx 或显式传入)")
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def _request(self, method: str, path: str, params: dict | None = None) -> dict[str, Any]:
        """底层 HTTP 调用,统一错误处理。"""
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, method=method, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.status
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            if e.code in (401, 403):
                raise TickDBAuthError(f"鉴权失败 [{e.code}]: {err_body[:200]}") from e
            if e.code == 429:
                raise TickDBRateLimitError(f"限流 [429]: {err_body[:200]}") from e
            raise TickDBError(f"HTTP {e.code}: {err_body[:200]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise TickDBNetworkError(f"网络错误: {e}") from e

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise TickDBError(f"响应非 JSON [{status}]: {body[:200]}") from e

        # TickDB 标准响应: {code, message, data}
        if isinstance(data, dict) and data.get("code") not in (0, None):
            raise TickDBError(f"业务错误 [{data.get('code')}]: {data.get('message')}")
        return data

    # ── REST 接口 ──
    def get_ticker(
        self, symbols: list[str], symbol_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        实时行情快照 — GET /v1/market/ticker。

        Args:
            symbols: 标准化 tick 列表(如 ['700.HK', 'AAPL.US']),最多 50
            symbol_type: 可选,stock/indices/crypto/forex/futures,歧义时传

        Returns:
            data 字段 list,如
            [{"symbol":"700.HK", "last_price":543.0, "volume_24h":..., ...}, ...]
        """
        if not symbols:
            return []
        if len(symbols) > 50:
            raise TickDBError(f"symbols 最多 50 个,收到 {len(symbols)}")
        params: dict[str, Any] = {"symbols": ",".join(symbols)}
        if symbol_type:
            params["type"] = symbol_type
        resp = self._request("GET", "/v1/market/ticker", params=params)
        return resp.get("data") or []

    def get_kline(
        self, symbol: str, interval: str = "1d", limit: int = 100
    ) -> list[dict[str, Any]]:
        """K 线 — GET /v1/market/kline(留接口,后续补)。"""
        return self._request(
            "GET",
            "/v1/market/kline",
            params={"symbol": symbol, "interval": interval, "limit": min(limit, 1000)},
        ).get("data") or []

    def search_symbols(self, query: str) -> list[dict[str, Any]]:
        """品种查询 — GET /v1/symbols/available(留接口,后续补)。"""
        return self._request(
            "GET", "/v1/symbols/available", params={"q": query, "limit": 50}
        ).get("data") or []

    # ── 腾讯行情兼容层 ──
    def fetch_realtime_prices_v2(self, codes: list[str]) -> dict[str, float]:
        """
        兼容旧版 fetch_realtime_prices(codes) 接口签名。

        输入(任意格式):
            159915 / 510300 / '700.HK' / 'NVDA' / 'BTCUSDT'
        输出:
            {'159915': 2.345, '510300': 4.123, ...}

        ⚠️ 失败时**不抛异常**,返回 {},让调用方走 PRICE_CACHE 兜底。
        """
        if not codes:
            return {}
        # 先 normalize,再保持 raw key 给调用方
        normalized = [normalize_code(c) for c in codes]
        try:
            rows = self.get_ticker(normalized)
        except TickDBAuthError as e:
            print(f"[tickdb] 鉴权失败,跳过本次拉取: {e}")
            return {}
        except TickDBRateLimitError as e:
            print(f"[tickdb] 限流,稍后重试: {e}")
            return {}
        except TickDBNetworkError as e:
            print(f"[tickdb] 网络错误,fallback 到腾讯: {e}")
            return fallback_to_tencent(codes, error=e)
        except TickDBError as e:
            print(f"[tickdb] 接口错误,fallback 到腾讯: {e}")
            return fallback_to_tencent(codes, error=e)
        # 解析:用 normalized symbol 反查 raw code
        sym_to_raw = dict(zip(normalized, codes))
        prices: dict[str, float] = {}
        for row in rows:
            sym = row.get("symbol", "")
            if not sym:
                continue
            try:
                price = float(row.get("last_price", 0))
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            raw = sym_to_raw.get(sym, sym)
            prices[raw] = float(price)
        if prices:
            PRICE_CACHE.update(prices)
        return prices

    # ── WebSocket ──
    def ws_subscribe_url(
        self,
        symbols: list[str],
        channel: str = "ticker",
    ) -> str | None:
        """
        返回 TickDB WebSocket 订阅 URL(含 api_key 参数),给前端/独立脚本用。

        本客户端**不直接实现 WS 收发**(避免引入 websockets 依赖),只生成 URL。
        """
        if not self.api_key:
            print("[tickdb] 未配置 Key,无法生成 WS URL")
            return None
        symbols_q = ",".join(symbols[:50])
        return (
            f"wss://ws.tickdb.ai/v1/market/{channel}"
            f"?symbols={urllib.parse.quote(symbols_q)}"
            f"&api_key={urllib.parse.quote(self.api_key)}"
        )


# ────────────────────────────────────────────────────────────────────
# 腾讯行情 fallback(纯 stdlib,同源逻辑)
# ────────────────────────────────────────────────────────────────────
def fallback_to_tencent(codes: list[str], error: Exception | None = None) -> dict[str, float]:
    """
    TickDB 失败时回退到腾讯 qt.gtimg.cn。

    Returns:
        {'159915': 2.345, ...}(只支持 A 股 ETF,A 股代码前缀 0/3 → sz,其余 → sh)
        空 dict 表示 fallback 也失败。
    """
    if not codes:
        return {}
    try:
        # 仅对 A 股 raw code 做前缀拼接(港股/美股/加密币腾讯不支持,跳过)
        a_share_parts: list[str] = []
        a_share_codes: list[str] = []
        for c in codes:
            if not c.isdigit() or len(c) != 6:
                continue
            if c.startswith(("00", "30", "20")):
                a_share_parts.append(f"sz{c}")
            else:
                a_share_parts.append(f"sh{c}")
            a_share_codes.append(c)
        if not a_share_parts:
            return {}
        url = f"https://qt.gtimg.cn/q={''.join(a_share_parts)}"
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read().decode("gbk", errors="replace")
        prices: dict[str, float] = {}
        for line in data.split(";"):
            if "~" not in line:
                continue
            parts = line.split("~")
            if len(parts) < 4:
                continue
            raw = parts[0]
            if "v_" in raw:
                code = raw.split("v_")[-1].strip()
                try:
                    prices[code] = float(parts[3])
                except (ValueError, IndexError):
                    pass
        # 只回传给 A 股 raw code,避免污染
        out = {code: prices[code] for code in a_share_codes if code in prices}
        if out:
            PRICE_CACHE.update(out)
        return out
    except Exception as exc:
        print(f"[tencent fallback] 也失败: {exc}(原 tickdb 错误: {error})")
        return {}


# ────────────────────────────────────────────────────────────────────
# 模块级便捷函数
# ────────────────────────────────────────────────────────────────────
_default_client: TickDBClient | None = None


def _get_default_client() -> TickDBClient:
    global _default_client
    if _default_client is None:
        _default_client = TickDBClient()
    return _default_client


def fetch_realtime_prices_v2(codes: list[str]) -> dict[str, float]:
    """
    模块级便捷入口 — 同名接口签名。

    用法:
        from tickdb_client import fetch_realtime_prices_v2
        prices = fetch_realtime_prices_v2(['159915', '510300'])
    """
    return _get_default_client().fetch_realtime_prices_v2(codes)


__all__ = [
    "TickDBClient",
    "TickDBError",
    "TickDBAuthError",
    "TickDBRateLimitError",
    "TickDBNetworkError",
    "normalize_code",
    "fetch_realtime_prices_v2",
    "fallback_to_tencent",
    "PRICE_CACHE",
]


if __name__ == "__main__":
    # 自检:未配 Key 时友好提示
    if not os.environ.get("TICKDB_API_KEY"):
        print("=" * 60)
        print("⚠️  TICKDB_API_KEY 未配置")
        print("-" * 60)
        print("TickDB 真实官网: https://tickdb.ai")
        print("注册方式: GitHub / Google / Telegram 三选一(邮箱不可用)")
        print("试用政策: 7 天免费试用 + $79/月基础版")
        print("-" * 60)
        print("注册后执行:")
        print("    export TICKDB_API_KEY='your_key_here'")
        print("    python3 tickdb_client.py")
        print("=" * 60)
    else:
        client = TickDBClient()
        rows = client.get_ticker(["AAPL.US", "700.HK"])
        print(json.dumps(rows, indent=2, ensure_ascii=False))
