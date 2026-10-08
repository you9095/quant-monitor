#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
故障注入测试：成交监督器 trade_supervisor 的"行情三源持续失败→持续重试→恢复后成交"。

验证（#43 成交可靠性闭环）：
  1. 前 N 轮三源全失败时，run_once 返回 missing_price 且【绝不动账、绝不用历史旧价】；
  2. 监督器按退避（2/3/5 分钟后固定 10 分钟）持续重试，行情恢复后用当日真实价成交；
  3. 空仓且无目标的策略返回 idle，后续轮幂等 already；
  4. 买入参考价=真实价、成交价含 0.1% 买入滑点；成交记录性质标注"不接券商"。

全程使用临时账本目录，不触碰真实 live-data；--no-push 不上传。
运行：python3 tests/test_trade_supervisor_fault_injection.py
"""
import sys, tempfile, json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE)); sys.path.insert(0, str(BASE / "api"))

import run_daily_engine as eng
import trade_supervisor as ts
import api.market_data as md

tmp = Path(tempfile.mkdtemp(prefix="qm_ft_"))
ld = tmp / "live-data"; (ld / "_run_logs").mkdir(parents=True)
(ld / "_account_state").mkdir(parents=True)
# 重指引擎与监督器的数据路径到临时目录
eng.DATA_REPO = ld; eng.DAILY_DIR = ld/"daily"; eng.LATEST_DIR = ld/"latest"; eng.STATE_DIR = ld/"_account_state"
ts.DATA_REPO = ld; ts.LOG_DIR = ld/"_run_logs"
ts.HEALTH_FILE = ld/"_run_logs"/"trade_health.json"
ts.LOCK_FILE = ld/"_run_logs"/"supervisor.lock"

# 缩小为两个策略：zhuidian(应买入513100) / r32(应空仓idle)
eng.STRATEGIES = {
    "zhuidian": {"name": "追电测试", "capital": 10000,
                 "pool": ["513100", "513500"], "mom_window": 10, "hold": 1},
    "r32": {"name": "三驾马车测试", "capital": 10000,
            "pool": ["510500"], "mom_window": 20, "hold": 1},
}

# 合成历史收盘：513100 强势上涨(动量为正且最高)；513500/510500 下跌(不选)
def fake_close(code, days=60, use_cache=True):
    if code == "513100":
        return [1.0 + i * 0.01 for i in range(40)]      # 上涨
    return [2.0 - i * 0.005 for i in range(40)]          # 下跌
md.load_etf_close = fake_close

# 交易日恒真、窗口恒在、窗口剩余充足；sleep 不空等
eng.is_trading_day = lambda today: True
ts.in_trade_window = lambda dt=None: True
ts.minutes_to_window_end = lambda dt=None: 120.0
ts.time.sleep = lambda s: None

# 东财快照预取始终失败（模拟东财 502）
def em_fail():
    raise RuntimeError("SIM 东财 502")
eng._ak_spot_em_no_proxy = em_fail

# 三源行情：前 2 轮全失败(none)，第 3 轮起给真实价
state = {"calls": 0, "fail_rounds": 2}
def fake_quotes(pool, spot_em_df=None):
    state["calls"] += 1
    if state["calls"] <= state["fail_rounds"]:
        return {}, "none", "none", {"em": 0, "tencent": 0, "sina": 0}
    prices = {c: 2.3764 for c in pool}
    return prices, "realtime", "tencent+sina", {"em": 0, "tencent": len(pool), "sina": len(pool)}
eng.fetch_realtime_quotes = fake_quotes

print("=== 故障注入开始（前2轮三源全失败，第3轮恢复）===")
rc = ts.supervise("2026-10-08", no_push=True)
print("监督器返回码:", rc)

health = json.loads(ts.HEALTH_FILE.read_text(encoding="utf-8"))
print("最终 status:", health["status"], "| attempt:", health["attempt"],
      "| done:", health["done_count"], "/", health["total"],
      "| 成交笔数:", health["trades_total"])

daily_files = list((ld/"daily").rglob("*.json")) if (ld/"daily").exists() else []
print("daily 落盘文件数:", len(daily_files))

ok = True
def check(name, cond):
    global ok
    print(("  [PASS] " if cond else "  [FAIL] ") + name)
    ok = ok and cond

check("最终 done", health["status"] == "done")
check("经历了3轮（前2失败重试+第3成功）", health["attempt"] == 3)
check("两策略都完成", health["done_count"] == 2)
check("产生买入成交", health["trades_total"] >= 1)
check("zhuidian 状态 traded", health["strategies"]["zhuidian"]["status"] == "traded")
check("zhuidian 价源 realtime", health["strategies"]["zhuidian"]["price_source"] == "realtime")
check("r32 空仓（idle 首轮落盘，后续轮幂等 already）",
      health["strategies"]["r32"]["status"] in ("idle", "already"))
rec = [json.loads(p.read_text(encoding="utf-8")) for p in daily_files]
bad = [r for r in rec if r.get("price_source") in ("close_fallback", "mixed", "partial", "none")]
check("无任何旧价/兜底/部分价成交记录", not bad)
zb = [r for r in rec if r["strategy_id"] == "zhuidian"][0]
t0 = zb.get("trades_today", [{}])[0]
check("zhuidian 参考价=真实价2.3764", abs(t0.get("reference_price", 0) - 2.3764) < 1e-6)
check("zhuidian 成交价含买入滑点≈2.3788", abs(t0.get("price", 0) - 2.3764 * 1.001) < 1e-3)
check("成交性质标注为不接券商", "不接券商" in zb.get("data_nature", ""))
print("\n临时账本:", ld)
print("结果:", "ALL PASS" if ok else "HAS FAILURE")
sys.exit(0 if ok else 1)
