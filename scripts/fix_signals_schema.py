#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_signals_schema.py — 修复 6 策略 signals schema 不一致
==========================================================

修复原则 (用户原话 2026-08-12 P0):
- 不修历史 signals (留 .backup/2026-08-12_audit/)
- 只补 signals/{sid}_2026-08-12.json (今天日期)

修复 3 类 schema 错误:
1. D2 cost 字段语义错误 (qixing 7-30~8-03: cost 是 total 不是 per-share)
2. D5 name 字段缺失中文名 (r32/sanhe: name=code)
3. D6 cash 字段缺失 (全部 6 策略, 由 API 计算)

输入: signals/{sid}_*.json (最新 mtime)
输出: signals/{sid}_2026-08-12.json (修复 schema)
"""

import json
import sys
import shutil
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/junze/quant-monitor-local")
SIG_DIR = REPO / "signals"
TODAY = "2026-08-12"
TODAY_DISPLAY = "2026-08-12"

# 真实 ETF 价格参考 (从派单接口契约字段, 不允许自由填)
ETF_NAMES = {
    "511880": "银华日利ETF",
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "513100": "纳指ETF",
    "513520": "日经ETF",
    "518880": "黄金ETF",
    "159985": "豆粕ETF",
    "510050": "A50ETF",
    "588080": "科创50ETF",
    "512100": "中证1000ETF",
    "512040": "国泰价值ETF",
    "512890": "红利低波ETF",
    "513130": "恒生科技ETF",
    "511010": "国债ETF",
    "513030": "纳指科技ETF",
    "161226": "国泰商品ETF",
    "159201": "自由现金流ETF",
    "159509": "景顺纳斯达克",
    "159529": "标普500ETF",
    "159920": "恒生ETF",
    "159967": "创成长ETF",
    "159980": "有色ETF",
    "159981": "能源化工ETF",
    "159985": "豆粕ETF",
    "510210": "上证指数ETF",
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "510050": "A50ETF",
    "513030": "纳指科技ETF",
    "513050": "中概互联网ETF",
    "513080": "法国CAC40ETF",
    "513100": "纳指ETF",
    "513130": "恒生科技ETF",
    "513290": "纳指生物科技ETF",
    "513310": "中韩半导体ETF",
    "513400": "道琼斯ETF",
    "513500": "标普500ETF",
    "513520": "日经ETF",
    "513690": "恒生股息ETF",
    "513730": "东南亚科技ETF",
    "563300": "中证2000ETF",
    "563360": "科创AIETF",
}

# 6 策略最新信号文件 (按 mtime)
SOURCE_FILES = {
    "qixing":    "qixing_2026-08-03.json",
    "r32":       "r32_2026-08-03.json",
    "zhuidian":  "zhuidian_2026-08-08.json",
    "sanhe":     "sanhe_2026-08-03.json",
    "lightning": "lightning_2026-08-03.json",
    "goldcombo": "goldcombo_2026-08-12.json",
}


def fix_cost_field(cost: float, qty: int, market_value: float) -> float:
    """
    修复 cost 字段语义 — 统一为 per-share。
    判断逻辑:
      - 如果 cost * qty ≈ market_value (误差 <1%) → cost 已是 per-share, 不改
      - 否则 (cost * qty ≠ market_value):
        - 如果 mv / qty ∈ [0.5, 200] → cost 应改为 mv / qty (cost 原本是 total)
        - 其他异常 → 跳过 (抛错由调用方处理)
    """
    if qty <= 0 or cost <= 0:
        return cost  # 空仓/零值不动

    cost_times_qty = cost * qty
    # 已经一致 (cost=per-share)
    if abs(cost_times_qty - market_value) / max(market_value, 1) < 0.01:
        return cost

    # cost 是 total, 改为 per-share
    implied_per_share = market_value / qty
    if 0.5 <= implied_per_share <= 200:
        return round(implied_per_share, 4)

    # 异常情况
    return cost


def fix_name_field(code: str, name: str) -> str:
    """
    修复 name 字段 — 必须有中文名 (不能是代码本身)
    """
    if not name or name == code:
        return ETF_NAMES.get(code, code)  # fallback 到 code
    return name


def calc_cash(initial_capital: float, live_total_pnl: float,
              positions: list) -> float:
    """
    计算 cash = max(0, asset - sum(mv))
    asset = initial_capital + live_total_pnl
    """
    asset = initial_capital + live_total_pnl
    sum_mv = sum(p.get("market_value", 0) for p in positions if p.get("qty", 0) > 0)
    return round(max(0, asset - sum_mv), 2)


def fix_signal(sid: str) -> dict:
    """读取最新信号 → 修复 schema → 返回 dict"""
    src = SIG_DIR / SOURCE_FILES[sid]
    sig = json.load(open(src, encoding="utf-8"))

    # 1) 复制基础字段, 把 date 改为 TODAY
    out = dict(sig)
    out["date"] = TODAY
    out["strategy_id"] = sid
    # 加 schema_version 字段 (新增, 标记修复版 schema)
    out["schema_version"] = "2.0-fixed-2026-08-12"

    # 2) 修复 positions: cost 字段语义 + name 字段中文
    fixed_positions = []
    for p in sig.get("positions", []):
        p_new = dict(p)
        qty = p.get("qty", 0)
        cost = p.get("cost", 0)
        mv = p.get("market_value", 0)

        # D2: cost 字段语义
        p_new["cost"] = fix_cost_field(cost, qty, mv)

        # D5: name 字段中文
        p_new["name"] = fix_name_field(p.get("code", ""), p.get("name", ""))

        fixed_positions.append(p_new)
    out["positions"] = fixed_positions

    # 3) D6: cash 字段新增 (由 API 计算口径)
    out["cash"] = calc_cash(
        sig.get("initial_capital", 0),
        sig.get("live_total_pnl", 0),
        out["positions"],
    )

    # 4) schema 修复备注
    out["schema_fix"] = {
        "fix_date": TODAY_DISPLAY,
        "fix_reason": "用户原话 2026-08-12: '511880 银华日利ETF 1,000股 ¥100,000,000' 显示离谱 → 全量审计 + schema 修复",
        "fixes_applied": [
            "D2 cost 字段统一为 per-share (修复 qixing 7-30~8-03 cost=total bug)",
            "D5 name 字段填充中文名 (修复 r32/sanhe name=code bug)",
            "D6 新增 cash 字段 = max(0, asset - sum(mv))",
        ],
        "source_signal_file": SOURCE_FILES[sid],
    }

    return out


def main():
    print(f"修复 {TODAY} 6 策略 signals schema...")
    print(f"源目录: {SIG_DIR}")
    print(f"输出: signals/{{sid}}_{TODAY}.json")
    print()

    fixed_files = []
    for sid in ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]:
        print(f"--- {sid} ---")
        sig = fix_signal(sid)

        out_path = SIG_DIR / f"{sid}_{TODAY}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sig, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 写入 {out_path} ({out_path.stat().st_size} bytes)")

        # 简要校验
        positions = sig["positions"]
        if positions:
            for p in positions:
                if p.get("qty", 0) > 0:
                    print(f"    {p['code']:8s} qty={p['qty']:5d} cost={p['cost']:8.4f} mv={p['market_value']:10.2f} "
                          f"implied_price={p['market_value']/p['qty']:.2f} name={p['name']!r}")
        else:
            print(f"    (空仓, 0 positions)")

        print(f"    cash = {sig['cash']}")
        print()
        fixed_files.append(out_path)

    print("=" * 60)
    print(f"修复完成: {len(fixed_files)} 文件")
    for f in fixed_files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
