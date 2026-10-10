#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
当日成交监督器（trade supervisor）
=================================
适配"Windows 仅交易日 13:00-17:00 开机"。由计划任务（onlogon / 13:05 / 15:10）
触发，启动后常驻并对【当日成交】负责到底。

交易日循环（引擎 run_once 已禁止历史旧价兜底成交）：
  1. 每轮取一次东财快照，逐策略按【当日真实价】撮合（盘中=实时价，15:00 后=当日收盘价）；
  2. 六策略全部当日落盘（traded / idle / already）→ 上传数据 + 写 done 心跳，退出；
  3. 有策略 no_history / missing_price / error → 写"重试中"健康心跳并上传（Mac 可见），
     按退避计划等待后重试，循环往复，直到成功或窗口结束；
  4. 退避：前 3 轮 2 / 3 / 5 分钟（覆盖开机网络/DNS 抖动），之后固定 10 分钟（用户指定）；
  5. 到 17:00 仍有策略未成交 → 落【持久红标】pending_overnight：红灯跨日持续
     （次日/周末/节假日都一直亮），冻结一切自动成交与补单，只等人工核对后解除。

铁律：
  * 三源（东财→腾讯→新浪）全失败时【持续重试】，绝不直接判定当日不成交，也绝不用旧价；
  * 17:00 后仍失败【绝不自动跨日补单】，红灯一直亮到人工运行解除脚本；
  * 不连接任何券商真实账号/资金账号，全部为本机模拟撮合；
  * 只在工作日 13:00-17:00 成交与上传，绝不 7x24；
  * 单实例锁：onlogon/13:05/15:10 多触发器重复启动时，只保留一个监督器在跑。

用法（Windows 计划任务调用）：
  python trade_supervisor.py              # 正常当日监督
  python trade_supervisor.py --no-push    # 不上传（本地测试）
  python trade_supervisor.py --redflag-status                 # 查看红灯是否锁定
  python trade_supervisor.py --ack-redflag                    # 人工核对后解除红灯
  python trade_supervisor.py --date 2026-10-08 --max-minutes 30   # 回归测试
"""
import os
import sys
import json
import time
import socket
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "api"))

import run_daily_engine as eng  # noqa: E402
import trade_redflag as rf  # noqa: E402  # 跨日红灯锁定（禁止自动补单）

DATA_REPO = BASE_DIR / "live-data"
LOG_DIR = DATA_REPO / "_run_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DAILY_DIR = DATA_REPO / "daily"

HEALTH_FILE = LOG_DIR / "trade_health.json"
LOCK_FILE = LOG_DIR / "supervisor.lock"

# 成交/上传窗口（工作日）
WINDOW_START = (13, 0)
WINDOW_END = (17, 0)
# 退避计划（秒）：前 3 轮快速重试，之后固定 10 分钟
BACKOFF = [120, 180, 300]
FAST_RETRY_MAX = len(BACKOFF)
STEADY_INTERVAL = 600
# 锁被视为"仍有实例在跑"的新鲜阈值（须 > 稳态重试间隔）
LOCK_STALE_SECONDS = STEADY_INTERVAL + 240
# 窗口末预留 push 时间，到点即收尾
WRAP_UP_MINUTES = 4

DONE_STATUSES = {"traded", "idle", "already"}
RETRY_STATUSES = {"missing_price", "no_history", "error"}


def now():
    return datetime.now()


def log(msg):
    line = f"[{now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / f"{now().strftime('%Y-%m-%d')}_supervisor.log",
                  "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------- 单实例软锁（按心跳时间戳判活，跨平台） ----------------
def _read_lock():
    try:
        return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_lock():
    try:
        LOCK_FILE.write_text(json.dumps({
            "pid": os.getpid(), "host": socket.gethostname(),
            "date": now().strftime("%Y-%m-%d"),
            "started": now().isoformat(timespec="seconds"),
            "heartbeat": now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _touch_lock():
    lk = _read_lock() or {}
    lk.update({"pid": os.getpid(), "host": socket.gethostname(),
               "date": now().strftime("%Y-%m-%d"),
               "heartbeat": now().isoformat(timespec="seconds")})
    try:
        LOCK_FILE.write_text(json.dumps(lk, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    except Exception:
        pass


def acquire_lock():
    """已有当日新鲜锁则放弃启动（另一实例在跑）；陈旧锁则接管。"""
    lk = _read_lock()
    if lk and lk.get("date") == now().strftime("%Y-%m-%d"):
        hb = lk.get("heartbeat")
        if hb:
            try:
                age = (now() - datetime.fromisoformat(hb)).total_seconds()
                if age < LOCK_STALE_SECONDS and int(lk.get("pid", -1)) != os.getpid():
                    log(f"检测到另一监督器仍在运行（pid={lk.get('pid')}，"
                        f"{int(age)}s 前心跳），本次触发幂等退出。")
                    return False
            except Exception:
                pass
    _write_lock()
    return True


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


# ---------------- 时间窗口 ----------------
def in_trade_window(dt=None):
    dt = dt or now()
    if dt.weekday() >= 5:
        return False
    hm = dt.hour * 60 + dt.minute
    return WINDOW_START[0] * 60 + WINDOW_START[1] <= hm < WINDOW_END[0] * 60 + WINDOW_END[1]


def minutes_to_window_end(dt=None):
    dt = dt or now()
    end = dt.replace(hour=WINDOW_END[0], minute=WINDOW_END[1], second=0, microsecond=0)
    return (end - dt).total_seconds() / 60.0


def wait_until_window_start(max_wait_min=30):
    """早于 13:00 启动时，最多等到 13:00（onlogon 一般 13:0x 触发，几乎不等）。"""
    n = now()
    if n.weekday() >= 5:
        return False
    start = n.replace(hour=WINDOW_START[0], minute=WINDOW_START[1],
                      second=0, microsecond=0)
    secs = (start - n).total_seconds()
    if secs <= 0:
        return True
    secs = min(secs, max_wait_min * 60)
    log(f"距 13:00 窗口还有 {int(secs // 60)} 分 {int(secs % 60)} 秒，等待...")
    slept = 0
    while slept < secs and not in_trade_window():
        time.sleep(min(20, secs - slept))
        slept += 20
        _touch_lock()
    return in_trade_window()


# ---------------- 健康心跳 ----------------
def write_health(payload):
    payload.setdefault("host", socket.gethostname())
    payload.setdefault("updated_at", now().isoformat(timespec="seconds"))
    payload["mode"] = "live_simulation_local_match_no_broker"
    payload["window"] = f"{WINDOW_START[0]:02d}:{WINDOW_START[1]:02d}-" \
                        f"{WINDOW_END[0]:02d}:{WINDOW_END[1]:02d}"
    try:
        HEALTH_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"心跳写入失败: {e}")


def push_to_github(no_push):
    """提交并上传 live-data（含账本与健康心跳）。失败只告警，不抛异常。

    监督器/守护是事件驱动（非交易日、已成交都会秒退、根本不调用本函数），
    故用 --force 跳过"仅工作日13-17点"的日常窗口限制：触发心跳、重试心跳、
    收盘后补成交、跨日补记、红标等都必须能随时上传，让 Mac 端可见。
    """
    if no_push:
        return False, "no-push(本地测试)"
    try:
        py = sys.executable
        r = subprocess.run([py, str(BASE_DIR / "scripts" / "sync_live_data.py"),
                            "push", "--force", "trade supervisor/guard heartbeat"],
                           cwd=str(BASE_DIR), capture_output=True, text=True, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        ok = ("[成功]" in out) or ("[提示]" in out)
        log(f"上传: {'成功' if ok else '失败/告警'} {out.strip()[-160:]}")
        return ok, out.strip()[-200:]
    except Exception as e:
        log(f"上传异常: {e}")
        return False, str(e)


# ---------------- 单轮尝试 ----------------
def attempt_round(today, attempt):
    """跑一轮六策略，返回 (all_done, health_strategies, agg)。"""
    spot = None
    try:
        spot = eng._ak_spot_em_no_proxy()
        em_ok, em_n = True, None
    except Exception as e:
        em_ok, em_n, spot = False, str(e)[:120], None
        log(f"  东财快照预取失败（腾讯/新浪兜底）: {em_n}")

    strats, agg_per_source = {}, {}
    done_count, trades_total = 0, 0
    for sid, cfg in eng.STRATEGIES.items():
        r = eng.run_once(sid, cfg, today, force=False, spot_em_df=spot)
        st = r["status"]
        rec = r.get("rec")
        for k, v in (r.get("per_source") or {}).items():
            agg_per_source[k] = agg_per_source.get(k, 0) + v
        item = {"status": st, "missing": r.get("missing", []),
                "required": r.get("required", []),
                "target": list((r.get("target") or {}).keys()),
                "trades": r.get("trades_n", 0),
                "price_source": r.get("price_source"),
                "detail": r.get("detail")}
        if rec:
            item["total_asset"] = rec.get("total_asset")
            item["today_pnl"] = rec.get("today_pnl")
        if r.get("error"):
            item["error"] = r["error"]
        strats[sid] = item
        if st in DONE_STATUSES:
            done_count += 1
        trades_total += r.get("trades_n", 0)
        if st == "error" and r.get("tb"):
            log(f"  [{sid}] 异常: {r.get('error')}")

    all_done = done_count == len(eng.STRATEGIES)
    agg = {"per_source": agg_per_source, "done_count": done_count,
           "trades_total": trades_total}
    return all_done, strats, agg


# ---------------- 主监督流程 ----------------
def supervise(today, no_push=False, max_minutes=None):
    started = now()
    log("=" * 56)
    log(f"当日成交监督器启动（{today}），窗口 {WINDOW_START[0]:02d}:00-{WINDOW_END[0]:02d}:00，"
        f"模拟盘本机撮合、不接任何券商。")

    if not acquire_lock():
        return 0

    try:
        # 跨日红灯锁定（最高优先，先于交易日/窗口判断）：
        # 只要存在未人工解除的红标，任何一天（含周末/节假日/次日）都不自动成交、不补单，
        # 持续把心跳写成红灯并上传，红灯一直亮到人工核对解除。
        flag = rf.load_redflag(LOG_DIR)
        if flag:
            held_over = today != flag.get("failed_date")
            cross = "，已跨日持续" if held_over else ""
            hold = {
                "date": today, "is_trading_day": None,
                "status": "pending_overnight", "redflag_active": True,
                "failed_date": flag.get("failed_date"), "held_over": held_over,
                "attempt": flag.get("attempt"),
                "price_sources": flag.get("price_sources", {}),
                "strategies": flag.get("strategies", {}),
                "done_count": 0, "total": len(eng.STRATEGIES), "trades_total": 0,
                "pending_strategies": flag.get("pending_strategies", []),
                "retry_reasons": flag.get("retry_reasons", {}),
                "next_retry_at": None,
                "note": (f"成交红灯持续中（事故日 {flag.get('failed_date')}{cross}）："
                         "已冻结一切自动成交与补单，红灯一直亮到人工核对解除；"
                         "解除运行 scripts/ack_trade_redflag.py，被冻结日不补单。"),
            }
            write_health(hold)
            push_to_github(no_push)
            log(f"🚩 红标锁定中（事故日 {flag.get('failed_date')}）：今日不自动成交、"
                f"不补单，红灯持续，等待人工解除。")
            return 2

        # 非交易日：写心跳直接退出（节假日/周末开机不成交）
        if not eng.is_trading_day(today):
            log("判定为非交易日，不成交。")
            write_health({"date": today, "is_trading_day": False,
                          "status": "no_trade_day", "attempt": 0,
                          "strategies": {}, "next_retry_at": None})
            return 0

        # 早于窗口则等待；晚于窗口（理论上不会被计划任务触发）则退出
        if not in_trade_window():
            if now().weekday() < 5 and now().hour < WINDOW_START[0]:
                if not wait_until_window_start():
                    return 0
            else:
                write_health({"date": today, "is_trading_day": True,
                              "status": "outside_window", "attempt": 0,
                              "strategies": {}, "next_retry_at": None})
                log("当前不在 13:00-17:00 窗口，退出（由窗口内计划任务负责）。")
                return 0

        attempt = 0
        while True:
            attempt += 1
            elapsed_min = (now() - started).total_seconds() / 60.0
            if max_minutes and elapsed_min >= max_minutes:
                log(f"达到测试限时 {max_minutes} 分钟，停止（仅测试）。")
                return 0
            if minutes_to_window_end() <= WRAP_UP_MINUTES:
                # 窗口将尽，做最后一轮判定
                log("接近 17:00 窗口结束，做最后判定。")

            log(f"--- 第 {attempt} 轮尝试 ---")
            all_done, strats, agg = attempt_round(today, attempt)

            if all_done:
                health = {
                    "date": today, "is_trading_day": True, "status": "done",
                    "attempt": attempt, "started_at": started.isoformat(timespec="seconds"),
                    "price_sources": agg["per_source"],
                    "strategies": strats, "done_count": agg["done_count"],
                    "total": len(eng.STRATEGIES), "trades_total": agg["trades_total"],
                    "next_retry_at": None,
                    "note": "六策略当日真实价成交/结算完成（本机模拟撮合，不接券商）。"}
                write_health(health)
                ok, _ = push_to_github(no_push)
                log(f"✅ 当日成交全部完成：{agg['done_count']}/6，"
                    f"成交 {agg['trades_total']} 笔，价源 {agg['per_source']}，上传={ok}")
                return 0

            # 未完成：统计缺哪些、为什么，写"重试中"心跳并上传
            missing_sids = [s for s, v in strats.items() if v["status"] in RETRY_STATUSES]
            reasons = {}
            for s in missing_sids:
                reasons.setdefault(strats[s]["status"], []).append(s)
            wait_s = BACKOFF[min(attempt - 1, FAST_RETRY_MAX - 1)] \
                if attempt <= FAST_RETRY_MAX else STEADY_INTERVAL
            next_retry = datetime.fromtimestamp(time.time() + wait_s).isoformat(timespec="seconds")
            health = {
                "date": today, "is_trading_day": True, "status": "retrying",
                "attempt": attempt, "started_at": started.isoformat(timespec="seconds"),
                "price_sources": agg["per_source"],
                "strategies": strats, "done_count": agg["done_count"],
                "total": len(eng.STRATEGIES), "trades_total": agg["trades_total"],
                "pending_strategies": missing_sids, "retry_reasons": reasons,
                "next_retry_at": next_retry,
                "backoff_seconds": wait_s,
                "note": "行情未取全或历史数据未就绪，按计划持续重试（绝不用旧价成交）。"}
            write_health(health)
            push_to_github(no_push)
            log(f"⏳ 未完成 {len(missing_sids)}/6（{reasons}），"
                f"{wait_s // 60} 分后重试（第 {attempt} 次）。")

            # 窗口结束仍未成功 → 落持久红标：红灯跨日持续，不自动补单，等人工解除
            remain_min = minutes_to_window_end()
            if remain_min <= WRAP_UP_MINUTES:
                health["status"] = "pending_overnight"
                health["redflag_active"] = True
                health["failed_date"] = today
                health["next_retry_at"] = None
                health["note"] = ("17:00 窗口结束仍未取到三源真实价成交（理论上持续全失败"
                                  "不应发生）。已落红标：红灯跨日持续、冻结自动成交与补单，"
                                  "须人工核对后运行 scripts/ack_trade_redflag.py 解除。")
                rf.raise_redflag(
                    failed_date=today, strategies=health.get("strategies"),
                    pending_strategies=missing_sids, retry_reasons=reasons,
                    price_sources=agg["per_source"], attempt=attempt,
                    note=health["note"], log_dir=LOG_DIR)
                write_health(health)
                push_to_github(no_push)
                log("🚩 红灯：窗口结束仍未全部成交，已落持久红标（跨日持续、禁止自动补单）。")
                return 2

            # 可中断、到点即停、并持续刷新锁心跳的等待
            sleep_total = min(wait_s, max(0, int((remain_min - WRAP_UP_MINUTES) * 60)))
            slept = 0
            while slept < sleep_total:
                time.sleep(min(20, sleep_total - slept))
                slept += 20
                _touch_lock()
                if minutes_to_window_end() <= WRAP_UP_MINUTES:
                    break
    finally:
        release_lock()


def _import_backfill():
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    import backfill_day as bf  # noqa: E402
    return bf


def trading_days_before(today, lookback=12):
    """today 之前（不含 today）的最近 lookback 个 A股交易日，升序。"""
    try:
        from api.market_data import load_trade_dates
        from datetime import timedelta as _td
        cal = load_trade_dates()
        if cal:
            ds = sorted(d for d in cal if d < today)
            return ds[-lookback:]
    except Exception:
        pass
    # 兜底：仅跳过周末（节假日近似，权威日历可用时不走这里）
    from datetime import timedelta as _td
    cur = datetime.strptime(today, "%Y-%m-%d").date() - _td(days=1)
    out = []
    while len(out) < lookback:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur -= _td(days=1)
    return sorted(out)


def _health_date():
    try:
        return json.loads(HEALTH_FILE.read_text(encoding="utf-8")).get("date")
    except Exception:
        return None


# ---------------- 周期守护（--guard，计划任务每 10 分钟幂等唤醒） ----------------
def guard_once(today=None, no_push=False, now_dt=None):
    """单次守护，幂等、非交易/已完成秒退，不长驻。

    顺序：
      0) 单实例锁；每天首次触发先上报一条"守护已触发"心跳（Mac 可区分没触发/触发后崩）；
      1) 红标激活（历史真实价三源全失败、人工锁定中）→ 维持红灯、秒退，不自动成交；
      2) 跨日补记：补齐 today 之前缺失的交易日（取当日真实收盘价，自动标"事后补记"），
         周末/节假日开机也会补最近一个交易日；历史真实价三源全失败才落红标；
      3) today 非交易日 → 秒退；
      4) today 交易日上午（<13:00）→ 不抢跑，秒退（用户下午开机）；
      5) today 13:00 后（盘中实时价 / 收盘后当日收盘价）→ 未成交则跑一轮，
         取得到当日真实价就成交；三源全失败写"重试中"心跳，下次守护（10 分钟后）再来，
         绝不用旧价、绝不放弃；当天始终没成，次日由步骤 2 自动按收盘价补记。
    """
    from datetime import timedelta as _td
    n = now_dt or now()
    today = today or n.strftime("%Y-%m-%d")
    log("=" * 56)
    log(f"成交守护唤醒（--guard，{today} {n.strftime('%H:%M')}），幂等补判。")

    if not acquire_lock():
        return 0
    try:
        bf = _import_backfill()

        # 0) 每天首次触发：上报"已触发"心跳并上传一次（最早期可见，之后不重复刷提交）
        if _health_date() != today:
            write_health({"date": today, "is_trading_day": eng.is_trading_day(today),
                          "status": "guard_triggered", "attempt": 0,
                          "strategies": {}, "next_retry_at": None,
                          "note": "成交守护已被计划任务触发（本机模拟撮合，不接券商）。"})
            push_to_github(no_push)

        # 1) 红标锁定中：维持红灯，不自动成交/补单，秒退（红灯一直亮到人工解除）
        flag = rf.load_redflag(LOG_DIR)
        if flag:
            write_health({
                "date": today, "is_trading_day": None,
                "status": "pending_overnight", "redflag_active": True,
                "failed_date": flag.get("failed_date"),
                "pending_strategies": flag.get("pending_strategies", []),
                "attempt": flag.get("attempt"), "strategies": flag.get("strategies", {}),
                "done_count": 0, "total": len(eng.STRATEGIES), "trades_total": 0,
                "next_retry_at": None,
                "note": "成交红灯持续中（三源真实价持续取不到）：已冻结自动成交，"
                        "红灯亮到人工核对解除；解除运行 scripts/ack_trade_redflag.py。"})
            log(f"🚩 红标锁定中（事故日 {flag.get('failed_date')}），本次守护不成交。")
            return 2

        # 2) 跨日补记：只补"首个已成交交易日之后、today 之前"的缺口（自动标"事后补记"）。
        #    系统归零/上线之前的历史日期（daily 里本就没有）不属于漏单，绝不向前乱补。
        existing_days = set()
        if DAILY_DIR.exists():
            existing_days = {p.name for p in DAILY_DIR.iterdir() if p.is_dir()}
        missing_days = []
        if existing_days:
            first_day = min(existing_days)
            missing_days = [d for d in trading_days_before(today, 40)
                            if d > first_day and d not in existing_days]
        for d in missing_days:
            log(f"检测到上线后交易日 {d} 缺失成交，按当日真实收盘价事后补记...")
            rc = bf.backfill_one(
                d, "成交守护跨日补记：当日计划任务未成交，按当日真实收盘价补记"
                   "（本机模拟撮合，非回测，不接券商）", no_push)
            if rc == 0:
                log(f"  {d} 事后补记完成。")
                push_to_github(no_push)
            elif rc == 2:
                log(f"  {d} 非交易日，跳过。")
            elif rc in (4, 5):
                # 历史当日真实收盘价三源全失败（理论上几乎不可能）→ 才落红标锁死等人工
                note = (f"事后补记 {d} 时，东财/腾讯/新浪三源历史真实收盘价均取不到"
                        f"（rc={rc}）。按铁律不得用旧价/伪造，已落红标，等人工核对。")
                rf.raise_redflag(
                    failed_date=d, strategies={},
                    pending_strategies=list(eng.STRATEGIES.keys()),
                    retry_reasons={"no_hist_real_price": list(eng.STRATEGIES.keys())},
                    price_sources={}, attempt=99, note=note, log_dir=LOG_DIR)
                write_health({"date": today, "is_trading_day": None,
                              "status": "pending_overnight", "redflag_active": True,
                              "failed_date": d, "done_count": 0,
                              "total": len(eng.STRATEGIES), "trades_total": 0,
                              "next_retry_at": None, "note": note})
                push_to_github(no_push)
                log("🚩 " + note)
                return 2
            else:
                # rc=3 乱序/连续性等保护：不亮红灯，记下并停止本轮向前补，等下次守护
                log(f"  {d} 补记被连续性保护拦截（rc={rc}），本轮跳过，不亮红灯。")
                break

        # 3) 今日非交易日：秒退（节假日/周末，跨日补记已在上面处理）
        if not eng.is_trading_day(today):
            write_health({"date": today, "is_trading_day": False,
                          "status": "no_trade_day", "attempt": 0,
                          "strategies": {}, "next_retry_at": None})
            log("今日非交易日，不成交，秒退。")
            return 0

        # 4) 今日已齐全：秒退
        complete, _ = bf.day_already_complete(today)
        if complete:
            write_health({"date": today, "is_trading_day": True, "status": "done",
                          "attempt": 0, "strategies": {}, "done_count": len(eng.STRATEGIES),
                          "total": len(eng.STRATEGIES), "trades_total": 0,
                          "next_retry_at": None,
                          "note": "今日六策略已成交/结算完成（幂等守护，秒退）。"})
            log("今日六策略已完成，秒退。")
            return 0

        # 5) 交易日但上午（<13:00）：不抢跑，秒退，等下午的守护
        if n.hour < 13:
            write_health({"date": today, "is_trading_day": True,
                          "status": "waiting_afternoon", "attempt": 0,
                          "strategies": {}, "next_retry_at": "13:00",
                          "note": "上午不成交（用户下午开机），等 13:00 后的守护。"})
            log("上午时段，不抢跑，秒退。")
            return 0

        # 6) 13:00 后（盘中实时价 / 收盘后当日收盘价）：跑一轮，拿真实价成交
        log("今日尚未完成且已进入下午成交时段，跑一轮真实价撮合...")
        all_done, strats, agg = attempt_round(today, 1)
        if all_done:
            write_health({"date": today, "is_trading_day": True, "status": "done",
                          "attempt": 1, "price_sources": agg["per_source"],
                          "strategies": strats, "done_count": agg["done_count"],
                          "total": len(eng.STRATEGIES), "trades_total": agg["trades_total"],
                          "next_retry_at": None,
                          "note": "守护按当日真实价成交/结算完成（本机模拟撮合，不接券商）。"})
            push_to_github(no_push)
            log(f"✅ 守护完成当日成交 {agg['done_count']}/6，成交 {agg['trades_total']} 笔。")
            return 0

        # 未取全真实价：写"重试中"，下次守护（约 10 分钟）持续重试；不锁死、不用旧价
        missing_sids = [s for s, v in strats.items() if v["status"] in RETRY_STATUSES]
        reasons = {}
        for s in missing_sids:
            reasons.setdefault(strats[s]["status"], []).append(s)
        write_health({"date": today, "is_trading_day": True, "status": "retrying",
                      "attempt": 1, "price_sources": agg["per_source"],
                      "strategies": strats, "done_count": agg["done_count"],
                      "total": len(eng.STRATEGIES), "trades_total": agg["trades_total"],
                      "pending_strategies": missing_sids, "retry_reasons": reasons,
                      "next_retry_at": (n + _td(minutes=10)).isoformat(timespec="seconds"),
                      "backoff_seconds": 600,
                      "note": "守护：当日真实价未取全，约 10 分钟后下次守护持续重试"
                              "（绝不用旧价）；若当天持续失败，次日自动按收盘价事后补记。"})
        push_to_github(no_push)
        log(f"⏳ 守护本轮未完成 {len(missing_sids)}/6（{reasons}），约 10 分钟后重试。")
        return 0
    finally:
        release_lock()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat(),
                    help="指定交易日期（测试用，默认今天）")
    ap.add_argument("--no-push", action="store_true", help="不上传 GitHub（本地测试）")
    ap.add_argument("--max-minutes", type=float, default=None,
                    help="监督最长分钟数（测试用）")
    ap.add_argument("--ack-redflag", action="store_true",
                    help="人工核对后解除跨日红灯（红标），解除后下一交易窗口恢复自动成交、不补单")
    ap.add_argument("--redflag-status", action="store_true",
                    help="查看当前是否存在未解除的红灯（红标）")
    ap.add_argument("--guard", action="store_true",
                    help="周期守护模式：计划任务每10分钟幂等唤醒，跨日自动补记+当日补成交")
    ap.add_argument("--hour", type=int, default=None,
                    help="测试用：注入当前小时（配合 --date 模拟上午/下午）")
    args = ap.parse_args()

    if args.ack_redflag:
        ok, info = rf.acknowledge(LOG_DIR, note="人工核对后解除（命令行 --ack-redflag）")
        if not ok:
            print(info)
            sys.exit(1)
        print(f"✅ 红灯已人工解除（事故日 {info.get('failed_date')}，"
              f"解除于 {info.get('acknowledged_at')}）。被冻结日不补单。")
        write_health({
            "date": date.today().isoformat(), "is_trading_day": None,
            "status": "redflag_acknowledged", "redflag_active": False,
            "failed_date": info.get("failed_date"),
            "attempt": 0, "strategies": {}, "done_count": 0,
            "total": len(eng.STRATEGIES), "trades_total": 0, "next_retry_at": None,
            "note": "成交红灯已由人工核对解除；下一交易窗口恢复自动成交，被冻结日不补单。"})
        pushed, _ = push_to_github(args.no_push)
        print("解除心跳已上传。" if pushed else "解除已写入本地（--no-push 或上传失败，下次任务补传）。")
        sys.exit(0)

    if args.redflag_status:
        f = rf.load_redflag(LOG_DIR)
        if not f:
            print("无未解除红灯（红标）。")
            sys.exit(0)
        print("🚩 存在未解除红灯（红标）：")
        print(json.dumps({k: f.get(k) for k in
                          ("failed_date", "raised_at", "last_seen_date", "attempt",
                           "pending_strategies", "retry_reasons", "price_sources", "note")},
                         ensure_ascii=False, indent=2))
        sys.exit(2)

    if args.guard:
        now_dt = None
        if args.hour is not None:
            now_dt = datetime.strptime(args.date, "%Y-%m-%d").replace(hour=args.hour, minute=30)
        code = guard_once(args.date, no_push=args.no_push, now_dt=now_dt)
        sys.exit(code or 0)

    code = supervise(args.date, no_push=args.no_push, max_minutes=args.max_minutes)
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
