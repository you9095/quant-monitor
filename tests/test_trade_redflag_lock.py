#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红标（跨日红灯）锁定测试
========================
验证用户铁律（2026-10-08）：
  A. 17:00 极端失败落下红标后，次日（含周末/节假日）监督器【不判断窗口、不跑成交、
     不补单】，心跳恒为红灯且 held_over=True；
  B. 只要红标未解除，即使当日心跳是 done，聚合层也强制面板恒红；
  C. 人工 acknowledge 解除后，下一交易日监督器恢复正常真实价成交（被冻结日不补）；
  D. 引擎命令行入口（once/execute/...）在红标锁定时一律拒绝（退出码 3），杜绝绕过补单。

全程临时目录，不触碰真实 live-data，不上传。
运行：python3 tests/test_trade_redflag_lock.py
"""
import sys, tempfile, json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE)); sys.path.insert(0, str(BASE / "api"))

import run_daily_engine as eng
import trade_supervisor as ts
import trade_redflag as rf
import live_aggregator as la
import api.market_data as md

ok = True
def check(name, cond):
    global ok
    print(("  [PASS] " if cond else "  [FAIL] ") + name)
    ok = ok and bool(cond)


def fresh_dirs():
    tmp = Path(tempfile.mkdtemp(prefix="qm_rf_"))
    ld = tmp / "live-data"
    (ld / "_run_logs").mkdir(parents=True)
    (ld / "_account_state").mkdir(parents=True)
    eng.DATA_REPO = ld; eng.DAILY_DIR = ld/"daily"; eng.LATEST_DIR = ld/"latest"
    eng.STATE_DIR = ld/"_account_state"
    ts.DATA_REPO = ld; ts.LOG_DIR = ld/"_run_logs"
    ts.HEALTH_FILE = ld/"_run_logs"/"trade_health.json"
    ts.LOCK_FILE = ld/"_run_logs"/"supervisor.lock"
    return ld


def two_strategies():
    eng.STRATEGIES = {
        "zhuidian": {"name": "追电测试", "capital": 10000,
                     "pool": ["513100", "513500"], "mom_window": 10, "hold": 1},
        "r32": {"name": "三驾马车测试", "capital": 10000,
                "pool": ["510500"], "mom_window": 20, "hold": 1},
    }


# 保存会被场景 A 临时替换的真实函数，便于场景 C 还原
ORIG_ATTEMPT_ROUND = ts.attempt_round


# ---------- 场景 A：红标锁定，次日不成交、恒红灯 ----------
print("=== 场景 A：红标锁定次日，监督器必须冻结成交 ===")
ld = fresh_dirs(); two_strategies()
rf.raise_redflag(failed_date="2026-10-08", log_dir=ld/"_run_logs",
                 pending_strategies=["zhuidian"], attempt=99,
                 retry_reasons={"missing_price": ["zhuidian"]},
                 price_sources={"em": 0, "tencent": 0, "sina": 0})

def _boom(*a, **k):
    raise AssertionError("红标锁定期间不应判断交易日/窗口或跑成交轮")
eng.is_trading_day = _boom
ts.in_trade_window = _boom
ts.minutes_to_window_end = _boom
ts.attempt_round = _boom
ts.push_to_github = lambda no_push: (True, "")

rc = ts.supervise("2026-10-09", no_push=True)
h = json.loads(ts.HEALTH_FILE.read_text(encoding="utf-8"))
daily_files = list((ld/"daily").rglob("*.json")) if (ld/"daily").exists() else []
check("返回码 2（红灯）", rc == 2)
check("status=pending_overnight", h["status"] == "pending_overnight")
check("redflag_active=True", h.get("redflag_active") is True)
check("held_over=True（次日跨日持续）", h.get("held_over") is True)
check("failed_date=2026-10-08", h.get("failed_date") == "2026-10-08")
check("成交笔数 0", h.get("trades_total") == 0)
check("没有任何 daily 成交落盘（未补单）", len(daily_files) == 0)

# 周末/节假日同样恒红（不判断交易日）
rc_we = ts.supervise("2026-10-11", no_push=True)
h_we = json.loads(ts.HEALTH_FILE.read_text(encoding="utf-8"))
check("周末仍返回红灯 2", rc_we == 2 and h_we.get("redflag_active") is True)

# ---------- 场景 B：聚合层红标优先于 done ----------
print("=== 场景 B：红标未解除，即使当日 done 也强制恒红 ===")
# 用必然早于今天的事故日，验证跨日 held_over=True
rp = rf.redflag_path(ld/"_run_logs"); rp.unlink(missing_ok=True)
rf.raise_redflag(failed_date="2026-09-30", log_dir=ld/"_run_logs",
                 pending_strategies=["zhuidian"])
(ld/"_run_logs"/"trade_health.json").write_text(json.dumps({
    "date": "2026-10-09", "status": "done", "done_count": 2, "total": 2,
    "trades_total": 4, "is_trading_day": True}), encoding="utf-8")
agg = la.build_trade_health(root=ld)
check("聚合层 status 仍为 pending_overnight", agg["status"] == "pending_overnight")
check("聚合层 redflag_active=True", agg.get("redflag_active") is True)
check("聚合层 held_over=True", agg.get("held_over") is True)

# ---------- 场景 D：引擎命令行闸门（先于解除验证） ----------
print("=== 场景 D：红标锁定时引擎 once 拒绝执行（退出码 3） ===")
sys.argv = ["run_daily_engine.py", "once"]
se_code = None
try:
    eng.main()
except SystemExit as e:
    se_code = e.code
check("eng.main once 被拒绝退出码 3", se_code == 3)

# ---------- 场景 C：人工解除后恢复正常成交 ----------
print("=== 场景 C：人工解除红标后，下一交易日恢复真实价成交 ===")
okc, info = rf.acknowledge(ld/"_run_logs", note="测试人工解除")
check("解除成功", okc and info.get("acknowledged") is True)
check("解除后 load_redflag 为空", rf.load_redflag(ld/"_run_logs") is None)
agg2 = la.build_trade_health(root=ld)
check("解除后聚合层不再被红标强制（读到 done 心跳）", agg2["status"] == "done")

# 重新搭一套干净目录验证恢复成交（ack 后的新交易日）
ld2 = fresh_dirs(); two_strategies()
def fake_close(code, days=60, use_cache=True):
    if code == "513100":
        return [1.0 + i * 0.01 for i in range(40)]
    return [2.0 - i * 0.005 for i in range(40)]
md.load_etf_close = fake_close
eng.is_trading_day = lambda today: True
ts.attempt_round = ORIG_ATTEMPT_ROUND  # 还原场景 A 替换掉的真实成交轮函数
ts.in_trade_window = lambda dt=None: True
ts.minutes_to_window_end = lambda dt=None: 120.0
ts.time.sleep = lambda s: None
eng._ak_spot_em_no_proxy = lambda: (_ for _ in ()).throw(RuntimeError("SIM 东财 502"))
def fake_quotes(pool, spot_em_df=None):
    prices = {c: 2.3764 for c in pool}
    return prices, "realtime", "tencent+sina", {"em": 0, "tencent": len(pool), "sina": len(pool)}
eng.fetch_realtime_quotes = fake_quotes
rc_r = ts.supervise("2026-10-09", no_push=True)
h_r = json.loads(ts.HEALTH_FILE.read_text(encoding="utf-8"))
check("解除后监督器返回 done", rc_r == 0 and h_r["status"] == "done")
check("恢复后产生真实价成交", h_r["trades_total"] >= 1)
check("恢复后无红标标记", not h_r.get("redflag_active"))

print("\n结果:", "ALL PASS" if ok else "HAS FAILURE")
sys.exit(0 if ok else 1)
