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
    """提交并上传 live-data（含账本与健康心跳）。失败只告警，不抛异常。"""
    if no_push:
        return False, "no-push(本地测试)"
    try:
        py = sys.executable
        r = subprocess.run([py, str(BASE_DIR / "scripts" / "sync_live_data.py"), "push"],
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

    code = supervise(args.date, no_push=args.no_push, max_minutes=args.max_minutes)
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
