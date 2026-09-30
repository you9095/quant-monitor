#!/usr/bin/env python3
"""
TickDB 接入演示脚本 — quant-monitor-local/api/_demo_tickdb.py
================================================================

演示 4 种用例:
  1) 无 Key:打印 schema 文档 + 引导去 tickdb.ai 注册
  2) 有 Key:真实调用 GET /v1/market/ticker
  3) 鉴权失败(TickDB 401 模拟):自动 fallback 到 qt.gtimg.cn
  4) 多市场:A 股 / 港股 / 美股 / 加密币 各取一个

跑法:
  python3 _demo_tickdb.py
  TICKDB_API_KEY=tk_xxx python3 _demo_tickdb.py   # 有 Key 时跑真 API

⚠️ 本脚本仅做本地 stdlib 演示,无任何副作用。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 同一目录的 tickdb_client
sys.path.insert(0, str(Path(__file__).parent))
import tickdb_client  # noqa: E402
from tickdb_client import (  # noqa: E402
    TickDBClient,
    fetch_realtime_prices_v2,
    fallback_to_tencent,
    normalize_code,
)


def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_1_no_key() -> None:
    """演示 1: 无 Key 时友好提示 + normalize_code + 模块级 fallback 跑通。"""
    banner("演示 1: 无 TICKDB_API_KEY — schema + normalize_code 自检")

    api_key = os.environ.get("TICKDB_API_KEY")
    print(f"  TICKDB_API_KEY 当前值: {api_key!r}(为空时触发 demo_1 路径)")

    # 1.1 normalize_code 自检
    print("\n  [1.1] normalize_code 自检:")
    test_codes = ["159915", "510300", "000001", "700", "9988", "NVDA", "BTCUSDT", "600519"]
    for c in test_codes:
        print(f"    {c!r:>15} → {normalize_code(c)!r}")

    # 1.2 未配 Key 时调用客户端,应给出 schema + 注册引导
    print("\n  [1.2] TickDBClient().get_ticker() 在无 Key 时的预期行为:")
    client = TickDBClient()
    print(f"    client.has_key = {client.has_key}")
    try:
        client.get_ticker(["AAPL.US"])
    except tickdb_client.TickDBAuthError as e:
        print(f"    ✓ 抛出 TickDBAuthError: {e}")

    # 1.3 tencent fallback 跑真 A 股(这段永远可跑,不走 Key)
    print("\n  [1.3] fallback_to_tencent(直接跑 qt.gtimg.cn 验证可联通):")
    tencent_prices = fallback_to_tencent(["159915", "510300", "510050"])
    print(f"    tencent 返回: {tencent_prices}")

    print("\n  ✓ demo_1 完成")


def demo_2_with_key() -> None:
    """演示 2: 有 Key 时跑真 TickDB API,展示多市场。"""
    banner("演示 2: 有 TICKDB_API_KEY — 真实 TickDB 多市场拉取")

    if not os.environ.get("TICKDB_API_KEY"):
        print("  ⚠️ 未配 TICKDB_API_KEY,跳过 demo_2(自动转 demo_3 模拟 fallback)")
        return

    client = TickDBClient()
    # 跨 4 个市场取样本
    multi_market = [
        ("A 股    ", "600519.SH"),
        ("A 股 ETF", "510300.SH"),
        ("港股    ", "700.HK"),
        ("美股    ", "AAPL.US"),
        ("加密币  ", "BTCUSDT"),
    ]
    symbols = [s for _, s in multi_market]

    try:
        rows = client.get_ticker(symbols)
    except tickdb_client.TickDBError as e:
        print(f"  ✗ TickDB 调用失败: {e}")
        return

    print(f"  请求 symbols: {symbols}")
    print(f"  返回 {len(rows)} 条:\n")
    for row in rows:
        sym = row.get("symbol", "?")
        # 找到 label
        label = next((lbl for lbl, s in multi_market if s == sym), "未知 ")
        last = row.get("last_price")
        chg_pct = row.get("price_change_percent_24h")
        ts = row.get("timestamp")
        print(f"    [{label}] {sym:<12}  last={last!r:<10}  24h%={chg_pct!r:<8}  ts={ts}")

    print("\n  ✓ demo_2 完成")


def demo_3_fallback() -> None:
    """演示 3: 用 monkeypatch 模拟 TickDB 401,验证 fallback_to_tencent 接管。"""
    banner("演示 3: 鉴权失败 → 自动 fallback 到腾讯")

    # 临时把 client 换成 bogus key,触发 401
    real_key = os.environ.get("TICKDB_API_KEY")
    os.environ["TICKDB_API_KEY"] = "demo-invalid-key-just-for-triggering-auth-failure"
    try:
        # 重新构造 client
        client = TickDBClient(api_key="bogus-key-xxxxx")
        try:
            client.get_ticker(["AAPL.US"])
        except tickdb_client.TickDBAuthError as e:
            print(f"  ✓ TickDB 返回鉴权失败(预期):{e}")
        # 现在通过 fetch_realtime_prices_v2 走完整 fallback 路径
        print("\n  [回退测试] fetch_realtime_prices_v2(['159915', '510300']) 在 Key 失效时:")
        prices = fetch_realtime_prices_v2(["159915", "510300"])
        print(f"    fallback 返回: {prices}")
    finally:
        # 还原环境变量
        if real_key is None:
            os.environ.pop("TICKDB_API_KEY", None)
        else:
            os.environ["TICKDB_API_KEY"] = real_key

    print("\n  ✓ demo_3 完成")


def demo_4_multi_market() -> None:
    """演示 4: 多市场 normalize + 同函数兼容(对调用方透明)。"""
    banner("演示 4: 多市场 normalize 对调用方透明(无 Key 时 fallback,只看 normalize)")

    mixed = ["159915", "510050", "000001", "700", "9988", "NVDA", "BTCUSDT", "SPX"]
    print("  输入(混合格式):")
    for c in mixed:
        print(f"    {c!r:>10} → 标准化 {normalize_code(c)!r}")

    if os.environ.get("TICKDB_API_KEY"):
        print("\n  有 Key — 跑真 TickDB,期望部分品种返回价格:")
        out = fetch_realtime_prices_v2(mixed)
        print(f"    fetch_realtime_prices_v2 返回: {out}")
    else:
        print("\n  无 Key — 只能跑 A 股 fallback(港股/美股/加密币 腾讯不支持):")
        a_share = [c for c in mixed if len(c) == 6 and c.isdigit()]
        out = fallback_to_tencent(a_share) if a_share else {}
        print(f"    fallback_to_tencent(A股子集) 返回: {out}")
        print(f"    非 A 股部分(港股/美股/加密币)在无 Key 时会落到 PRICE_CACHE/账户 current")

    print("\n  ✓ demo_4 完成")


def main() -> None:
    print("TickDB 接入演示 — quant-monitor-local")
    print(f"Python {sys.version.split()[0]} | tickdb_client.py 模块路径: {tickdb_client.__file__}")
    demo_1_no_key()
    demo_2_with_key()
    demo_3_fallback()
    demo_4_multi_market()
    print("\n" + "=" * 70)
    print("  全部演示完成")
    print("  集成报告: /tmp/tickdb_evidence/M05_integration/conclusion.md")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
