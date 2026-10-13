#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端验收测试（Mac 本地可重复，不依赖网络/Windows/真实账本）。

用一个简化单标的策略（510300，本金10000），通过临时账本 + mock 行情/历史/交易日，
验证"把零件串起来的主流程"端到端正确：

  T1 完整交易日买入：整手、买入滑点、最低佣金、T+1 当日买入不可卖(avail=0)、现金/总资产
  T2 幂等：同一日重复跑 -> already，不重复成交、现金不变
  T3 次日卖出：end_of_day 释放 T+1、卖出滑点、印花税、佣金、已实现盈亏、空仓
  T4 三源全失败：missing_price，不动账（现金仍10000，无持仓无成交）
  T5 模拟/实盘隔离：两套独立账本，数据不串

口径基准（手算，见 calculator 复算）：
  Day1 参考收盘价 4.000 -> 买入成交价 4.004（+0.1%滑点），24手=2400股，
        成交额9609.6，佣金5.0（最低），现金385.4，持仓成本9614.6，
        市值9600，总资产9985.4，avail=0。
  Day2 参考收盘价 4.050 -> 卖出成交价 4.04595（-0.1%滑点），成交额9710.28，
        印花税4.85514，佣金5.0，净收9700.42486，现金10085.82486，已实现盈亏85.82486。
"""
import sys
import json
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "api"))

import run_daily_engine as eng
import market_data as md

SID = "e2e"
CFG = {"name": "E2E测试", "pool": ["510300"], "capital": 10000,
       "mom_window": 20, "momentum_threshold": 0.0}
eng.DECIDERS[SID] = eng.decide_for(SID, CFG)

PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}")


def redirect(tmp):
    """把引擎数据路径重定向到临时目录，返回 (state, daily, latest)。"""
    data = tmp / "live-data"
    daily = data / "daily"
    latest = data / "latest"
    state = data / "_account_state"
    for d in (daily, latest, state):
        d.mkdir(parents=True, exist_ok=True)
    eng.DATA_REPO = data
    eng.DAILY_DIR = daily
    eng.LATEST_DIR = latest
    eng.STATE_DIR = state
    return state, daily, latest


def install_mocks(day_price, trend):
    """day_price: 当日参考收盘价(None=三源全失败)；trend: 'up'/'down' 控制历史动量。"""
    def fake_close(code, days=60, use_cache=True):
        if trend == "up":
            return [round(3.0 + i * 0.01, 4) for i in range(days)]
        return [round(5.0 - i * 0.01, 4) for i in range(days)]
    md.load_etf_close = fake_close

    def fake_quotes(pool, spot_em_df=None):
        if day_price is None:
            return {}, "none", "none", {"em": 0, "tencent": 0, "sina": 0}
        prices = {c: day_price for c in pool}
        return prices, "realtime", "tencent", {"em": 0, "tencent": len(pool), "sina": 0}
    eng.fetch_realtime_quotes = fake_quotes


def near(a, b, tol=0.02):
    return abs(a - b) <= tol


# ---------- T1 + T2 + T3：一个临时账本里走完 Day1 买入 -> 幂等 -> Day2 卖出 ----------
tmp1 = Path(tempfile.mkdtemp(prefix="qm_e2e_"))
state_dir, daily_dir, latest_dir = redirect(tmp1)
install_mocks(day_price=4.000, trend="up")

print("=== T1 完整交易日买入（参考收盘价4.000）===")
r1 = eng.run_once(SID, CFG, "2026-10-08")
rec1 = r1["rec"]
b = eng.Broker.load_or_new(state_dir / f"{SID}.json", CFG["capital"], SID)
check("T1 status=traded", r1["status"] == "traded", r1["status"])
check("T1 买入1笔", r1["trades_n"] == 1)
check("T1 成交价=4.004(含买入滑点)", near(rec1["trades_today"][0]["price"], 4.004),
      f"={rec1['trades_today'][0]['price']}")
check("T1 持仓2400股", b.positions["510300"].qty == 2400)
check("T1 当日买入T+1不可卖(avail=0)", b.positions["510300"].avail_qty == 0)
check("T1 现金≈385.4", near(b.cash, 385.4), f"={b.cash}")
check("T1 佣金=5.0(最低)", near(rec1["trades_today"][0]["commission"], 5.0))
check("T1 总资产≈9985.4", near(rec1["total_asset"], 9985.4), f"={rec1['total_asset']}")
check("T1 账本已落盘", (state_dir / f"{SID}.json").exists())
check("T1 daily/latest 已写", (daily_dir / "2026-10-08" / f"{SID}.json").exists()
      and (latest_dir / f"{SID}.json").exists())

print("=== T2 幂等：当日重复跑 -> already，不重复成交 ===")
r1b = eng.run_once(SID, CFG, "2026-10-08")
b2 = eng.Broker.load_or_new(state_dir / f"{SID}.json", CFG["capital"], SID)
check("T2 status=already", r1b["status"] == "already", r1b["status"])
check("T2 成交数仍为1(无重复)", r1b["trades_n"] == 0)
check("T2 现金仍≈385.4", near(b2.cash, 385.4), f"={b2.cash}")

print("=== T3 次日卖出（参考收盘价4.050，动量转空清仓）===")
install_mocks(day_price=4.050, trend="down")
r2 = eng.run_once(SID, CFG, "2026-10-09")
rec2 = r2["rec"]
b3 = eng.Broker.load_or_new(state_dir / f"{SID}.json", CFG["capital"], SID)
check("T3 status=traded", r2["status"] == "traded", r2["status"])
check("T3 卖出1笔", r2["trades_n"] == 1 and rec2["trades_today"][0]["side"] == "SELL")
check("T3 T+1已释放(次日可卖)", r2["trades_n"] == 1)
check("T3 卖出成交价=4.04595(滑点)", near(rec2["trades_today"][0]["price"], 4.04595),
      f"={rec2['trades_today'][0]['price']}")
check("T3 印花税≈4.85514", near(rec2["trades_today"][0].get("stamp_tax", 0), 4.85514),
      f"={rec2['trades_today'][0].get('stamp_tax')}")
check("T3 佣金=5.0", near(rec2["trades_today"][0]["commission"], 5.0))
check("T3 已清仓(无持仓)", len(b3.positions) == 0)
check("T3 现金≈10085.82", near(b3.cash, 10085.82486), f"={b3.cash}")
check("T3 realized_pnl(卖出口径)≈90.82", near(rec2.get("realized_pnl", 0), 90.82486),
      f"={rec2.get('realized_pnl')}")
check("T3 空仓净盈亏(live_total_pnl)≈85.82", near(rec2.get("live_total_pnl", 0), 85.82486),
      f"={rec2.get('live_total_pnl')}")

# ---------- T4：三源全失败，不动账 ----------
tmp2 = Path(tempfile.mkdtemp(prefix="qm_e2e_noprice_"))
s4, d4, l4 = redirect(tmp2)
install_mocks(day_price=None, trend="up")
print("=== T4 三源全失败 -> missing_price，不动账 ===")
r4 = eng.run_once(SID, CFG, "2026-10-08")
b4 = eng.Broker.load_or_new(s4 / f"{SID}.json", CFG["capital"], SID)
check("T4 status=missing_price", r4["status"] == "missing_price", r4["status"])
check("T4 现金仍10000", near(b4.cash, 10000))
check("T4 无持仓", len(b4.positions) == 0)
check("T4 无成交/无daily落盘", r4["trades_n"] == 0
      and not (d4 / "2026-10-08" / f"{SID}.json").exists())

# ---------- T5：模拟/实盘两本账隔离 ----------
print("=== T5 模拟/实盘账本隔离（不同目录，数据不串）===")
sim_tmp = Path(tempfile.mkdtemp(prefix="qm_e2e_sim_"))
live_tmp = Path(tempfile.mkdtemp(prefix="qm_e2e_live_"))
# 模拟账本：Day1 买入价 4.0
redirect(sim_tmp)
install_mocks(day_price=4.0, trend="up")
eng.run_once(SID, CFG, "2026-10-08")
# 实盘账本：下跌→不选，成功但空仓（idle），状态文件存在、现金10000
redirect(live_tmp)
install_mocks(day_price=4.0, trend="down")
eng.run_once(SID, CFG, "2026-10-08")
sim_state = sim_tmp / "live-data" / "_account_state" / f"{SID}.json"
live_state = live_tmp / "live-data" / "_account_state" / f"{SID}.json"
sim_j = json.loads(sim_state.read_text(encoding="utf-8"))
live_j = json.loads(live_state.read_text(encoding="utf-8"))
check("T5 模拟账本有持仓、现金≈385.4", near(sim_j["cash"], 385.4)
      and len(sim_j.get("positions", {})) == 1)
check("T5 实盘账本空仓、现金10000", near(live_j["cash"], 10000)
      and len(live_j.get("positions", {})) == 0)
check("T5 两本账现金不同(隔离)", sim_j["cash"] != live_j["cash"])

print("\n" + "=" * 56)
print(f"结果: {'ALL PASS' if not FAIL else 'HAS FAILURE'} "
      f"（{len(PASS)} 通过 / {len(FAIL)} 失败）")
sys.exit(1 if FAIL else 0)
