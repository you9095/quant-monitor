#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周期守护 --guard 的隔离测试（不碰真实 live-data，全部重定向到临时目录）。

覆盖：
  G1 交易日上午（<13:00）当日未完成 -> waiting_afternoon，不抢跑、不撮合；
  G2 交易日下午三源真实价全失败 -> retrying 心跳，【不】落红标、不放弃（下次守护重试）；
  G3 周末开机、上一交易日漏单 -> 只补"首个已成交日之后"的缺口（10-09），
     绝不向前补系统上线前的 9 月日期。
"""
import json
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "api"))

import trade_supervisor as sup  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  [PASS] " if cond else "  [FAIL] ") + name)


class FakeBF:
    def __init__(self, existing):
        self.existing = set(existing)
        self.backfill_calls = []

    def day_already_complete(self, day):
        return (day in self.existing, [])

    def backfill_one(self, day, reason, no_push):
        self.backfill_calls.append(day)
        return 0


def _patch_dirs(tmp):
    log_dir = tmp / "_run_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    daily = tmp / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    return {
        "DATA_REPO": tmp, "LOG_DIR": log_dir, "DAILY_DIR": daily,
        "HEALTH_FILE": log_dir / "trade_health.json",
        "LOCK_FILE": log_dir / "supervisor.lock",
    }


def _health(sup_mod):
    return json.loads(sup_mod.HEALTH_FILE.read_text(encoding="utf-8"))


def test_g1_morning_wait():
    print("场景 G1：交易日上午未完成 -> waiting，不撮合")
    tmp = Path(tempfile.mkdtemp())
    dirs = _patch_dirs(tmp)
    fake = FakeBF(set())
    with mock.patch.dict({k: getattr(sup, k) for k in []}), \
         mock.patch.object(sup, "DATA_REPO", dirs["DATA_REPO"]), \
         mock.patch.object(sup, "LOG_DIR", dirs["LOG_DIR"]), \
         mock.patch.object(sup, "DAILY_DIR", dirs["DAILY_DIR"]), \
         mock.patch.object(sup, "HEALTH_FILE", dirs["HEALTH_FILE"]), \
         mock.patch.object(sup, "LOCK_FILE", dirs["LOCK_FILE"]), \
         mock.patch.object(sup, "_import_backfill", lambda: fake), \
         mock.patch.object(sup.eng, "is_trading_day", lambda d: True), \
         mock.patch.object(sup, "trading_days_before", lambda d, lookback=12: []), \
         mock.patch.object(sup, "attempt_round") as ar, \
         mock.patch.object(sup, "push_to_github", lambda no_push: (True, "")):
        now_dt = datetime(2026, 10, 9, 10, 30)
        rc = sup.guard_once("2026-10-09", no_push=True, now_dt=now_dt)
        h = _health(sup)
        check("返回码 0", rc == 0)
        check("状态 waiting_afternoon", h.get("status") == "waiting_afternoon")
        check("上午不调用撮合", ar.call_count == 0)
    shutil.rmtree(tmp, ignore_errors=True)


def test_g2_afternoon_all_sources_fail_retry_no_redflag():
    print("场景 G2：交易日下午三源全失败 -> retrying，不锁死、不放弃")
    tmp = Path(tempfile.mkdtemp())
    dirs = _patch_dirs(tmp)
    fake = FakeBF(set())
    strats = {"qixing": {"status": "missing_price", "missing": ["159981"]}}
    agg = {"per_source": {"em": 0, "tencent": 0, "sina": 0},
           "done_count": 0, "trades_total": 0}

    def fake_round(today, attempt):
        return False, strats, agg

    with mock.patch.object(sup, "DATA_REPO", dirs["DATA_REPO"]), \
         mock.patch.object(sup, "LOG_DIR", dirs["LOG_DIR"]), \
         mock.patch.object(sup, "DAILY_DIR", dirs["DAILY_DIR"]), \
         mock.patch.object(sup, "HEALTH_FILE", dirs["HEALTH_FILE"]), \
         mock.patch.object(sup, "LOCK_FILE", dirs["LOCK_FILE"]), \
         mock.patch.object(sup, "_import_backfill", lambda: fake), \
         mock.patch.object(sup.eng, "is_trading_day", lambda d: True), \
         mock.patch.object(sup, "trading_days_before", lambda d, lookback=12: []), \
         mock.patch.object(sup, "attempt_round", side_effect=fake_round), \
         mock.patch.object(sup, "push_to_github", lambda no_push: (True, "")), \
         mock.patch.object(sup.rf, "raise_redflag") as raise_rf:
        now_dt = datetime(2026, 10, 9, 14, 30)
        rc = sup.guard_once("2026-10-09", no_push=True, now_dt=now_dt)
        h = _health(sup)
        check("返回码 0（继续等下次守护）", rc == 0)
        check("状态 retrying", h.get("status") == "retrying")
        check("约10分钟后重试", h.get("backoff_seconds") == 600)
        check("三源全失败【不】落红标", raise_rf.call_count == 0)
    shutil.rmtree(tmp, ignore_errors=True)


def test_g3_weekend_backfill_only_after_go_live():
    print("场景 G3：周末开机补漏，只补上线后缺口（10-09），不补9月")
    tmp = Path(tempfile.mkdtemp())
    dirs = _patch_dirs(tmp)
    (dirs["DAILY_DIR"] / "2026-10-08").mkdir(parents=True, exist_ok=True)
    fake = FakeBF({"2026-10-08"})
    cal_before = ["2026-09-16", "2026-10-08", "2026-10-09"]
    with mock.patch.object(sup, "DATA_REPO", dirs["DATA_REPO"]), \
         mock.patch.object(sup, "LOG_DIR", dirs["LOG_DIR"]), \
         mock.patch.object(sup, "DAILY_DIR", dirs["DAILY_DIR"]), \
         mock.patch.object(sup, "HEALTH_FILE", dirs["HEALTH_FILE"]), \
         mock.patch.object(sup, "LOCK_FILE", dirs["LOCK_FILE"]), \
         mock.patch.object(sup, "_import_backfill", lambda: fake), \
         mock.patch.object(sup.eng, "is_trading_day", lambda d: d != "2026-10-10"), \
         mock.patch.object(sup, "trading_days_before", lambda d, lookback=12: cal_before), \
         mock.patch.object(sup, "push_to_github", lambda no_push: (True, "")), \
         mock.patch.object(sup.rf, "raise_redflag") as raise_rf:
        now_dt = datetime(2026, 10, 10, 14, 30)  # 周六
        rc = sup.guard_once("2026-10-10", no_push=True, now_dt=now_dt)
        check("返回码 0", rc == 0)
        check("只补 2026-10-09 一天", fake.backfill_calls == ["2026-10-09"])
        check("不向前补 9 月日期", "2026-09-16" not in fake.backfill_calls)
        check("补记成功不亮红标", raise_rf.call_count == 0)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_g1_morning_wait()
    test_g2_afternoon_all_sources_fail_retry_no_redflag()
    test_g3_weekend_backfill_only_after_go_live()
    print("\n结果:", "ALL PASS" if not FAIL else f"{len(FAIL)} FAIL: {FAIL}")
    sys.exit(1 if FAIL else 0)
