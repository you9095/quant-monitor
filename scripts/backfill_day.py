#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史交易日事后补记（backfill）
================================
用途：某一交易日 Windows 计划任务/监督器【没有成交】（如 2026-10-09 开机却漏跑），
事后按该日【真实收盘价】把六策略的决策→撮合→盯市结算补齐，并在每条记录上
明确标注"事后补记"。

铁律（与盘中一致，不得违反）：
  * 只用该日【真实收盘价】（东财缓存/akshare → 新浪日K → 腾讯日K，多源取数）；
    任何必需标的当日真实价取不到，就【不补该策略】并报错，绝不用别的日期价格、
    绝不伪造、绝不用旧价兜底；
  * 全程本机模拟撮合，【不连接任何券商真实账号/资金账号】，非回测；
  * 必须按交易日顺序补（账本 latest 日期须早于补记日），不得在中间乱序插入；
  * 当日已存在 phase=trade 记录的策略幂等跳过，不覆盖。

用法：
  python scripts/backfill_day.py --date 2026-10-09 --yes
  python scripts/backfill_day.py --date 2026-10-09 --yes --no-push   # 只落盘不上传
  python scripts/backfill_day.py --date 2026-10-09,2026-10-10 --yes  # 按顺序补多日
"""
import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "api"))

import run_daily_engine as eng  # noqa: E402

DATA_REPO = BASE_DIR / "live-data"
DAILY_DIR = DATA_REPO / "daily"
LATEST_DIR = DATA_REPO / "latest"

DONE = {"traded", "idle", "already"}


def latest_dates():
    """六策略 latest 快照日期 → {sid: date}。"""
    out = {}
    for sid in eng.STRATEGIES:
        f = LATEST_DIR / f"{sid}.json"
        if f.exists():
            try:
                out[sid] = json.loads(f.read_text(encoding="utf-8")).get("date")
            except Exception:
                out[sid] = None
    return out


def existing_trade_dates():
    """daily 下已存在的交易日目录（升序）。"""
    if not DAILY_DIR.exists():
        return []
    return sorted(p.name for p in DAILY_DIR.iterdir() if p.is_dir())


def day_already_complete(day):
    """该日六策略是否都已有 phase=trade 记录。"""
    d = DAILY_DIR / day
    if not d.exists():
        return False, []
    done = []
    for sid in eng.STRATEGIES:
        f = d / f"{sid}.json"
        if f.exists():
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                if rec.get("date") == day and rec.get("phase") == "trade":
                    done.append(sid)
            except Exception:
                pass
    return len(done) == len(eng.STRATEGIES), done


def prefetch_hist(day, sleep_s=1.2):
    """为全 pool 预取截至 day 的历史日 K，返回 (hist_map, close_map, src_map, missing)。"""
    pool = sorted(set(sum((c["pool"] for c in eng.STRATEGIES.values()), [])))
    hist_map, close_map, src_map, missing = {}, {}, {}, []
    for i, code in enumerate(pool):
        rows, src = eng.load_hist_klines(code, day, n=60)
        if rows and rows[-1][0] == day:
            hist_map[code] = [p for _, p in rows]
            close_map[code] = rows[-1][1]
            src_map[code] = src
            print(f"    [{i+1}/{len(pool)}] {code} {day} 收盘={rows[-1][1]}（源 {src}）")
        else:
            missing.append(code)
            print(f"    [{i+1}/{len(pool)}] {code} 取不到 {day} 真实收盘价（源 {src}）")
        time.sleep(sleep_s)
    return hist_map, close_map, src_map, missing


def push_live_data():
    try:
        py = sys.executable
        r = subprocess.run([py, str(BASE_DIR / "scripts" / "sync_live_data.py"),
                            "push", "--force",
                            f"live data backfill {day} real close"],
                           cwd=str(BASE_DIR), capture_output=True, text=True, timeout=240)
        out = (r.stdout or "") + (r.stderr or "")
        ok = ("[成功]" in out) or ("[提示]" in out)
        return ok, out.strip()[-400:]
    except Exception as e:
        return False, str(e)


def backfill_one(day, reason, no_push):
    print("=" * 64)
    print(f"事后补记交易日 {day}")
    print("=" * 64)

    # 1) 必须是交易日
    if not eng.is_trading_day(day):
        print(f"[跳过] {day} 非 A股交易日，不补记。")
        return 2

    # 2) 连续性 / 乱序保护
    ld = latest_dates()
    have_dates = existing_trade_dates()
    later = [d for d in have_dates if d > day]
    base_dates = {d for d in ld.values() if d}
    if later:
        print(f"[拒绝] daily 已存在晚于 {day} 的交易日 {later}，不能乱序补记；"
              f"请从最早缺失日按顺序补。")
        return 3
    if any(d and d > day for d in base_dates):
        print(f"[拒绝] 存在策略账本 latest 日期晚于 {day}：{ld}，乱序补记会导致资金口径错误。")
        return 3
    print(f"  补记前各策略最新交易日：{ld}")

    # 3) 幂等：已齐全则跳过
    complete, done = day_already_complete(day)
    if complete:
        print(f"[跳过] {day} 六策略均已有成交记录：{done}（幂等，不重复补记）。")
        return 0
    if done:
        print(f"  {day} 已有部分策略记录 {done}，仅补缺失策略（已有的不覆盖）。")

    # 4) 预取当日真实收盘价（多源，限速）
    print("  拉取当日真实收盘价（东财缓存/akshare→新浪→腾讯，多源）...")
    hist_map, close_map, src_map, missing_all = prefetch_hist(day)
    src_tags = sorted(set(src_map.values()))
    if not close_map:
        print("[失败] 一个标的的当日真实价都取不到，按铁律不补记、不伪造。")
        return 4

    # 5) 逐策略复用引擎：决策→撮合→盯市→落盘（标注事后补记）
    results = {}
    for sid, cfg in eng.STRATEGIES.items():
        r = eng.run_once(
            sid, cfg, day, force=False,
            hist_map={c: hist_map[c] for c in cfg["pool"] if c in hist_map},
            quote_map=close_map,
            backfill={"reason": reason, "hist_source": "+".join(src_tags) or "multi"})
        results[sid] = r["status"]
        st = r["status"]
        if st in ("traded", "idle"):
            rec = r["rec"]
            print(f"  [{sid}] {st} 成交{r['trades_n']}笔 持仓{len(rec['positions'])}只 "
                  f"现金={rec['cash']:.2f} 总资产={rec['total_asset']:.2f} "
                  f"当日盈亏={rec['today_pnl']:.2f} 价源={rec['price_source_detail']}")
        elif st == "already":
            print(f"  [{sid}] already（当日已有记录，跳过）")
        else:
            print(f"  [{sid}] {st} missing={r.get('missing')} error={r.get('error')}")

    failed = {s: v for s, v in results.items() if v not in DONE}
    if failed:
        print(f"[未完成] {day} 以下策略未补成功：{failed}。")
        print("        按铁律未取全真实价不得补；本次不 push，请在行情恢复后重跑本脚本（幂等）。")
        return 5

    # 6) 汇总
    print(f"\n  {day} 补记完成，六策略当日快照：")
    total_asset = 0.0
    for sid in eng.STRATEGIES:
        rec = json.loads((DAILY_DIR / day / f"{sid}.json").read_text(encoding="utf-8"))
        total_asset += rec["total_asset"]
        print(f"    {rec['strategy_name']}({sid}): 总资产={rec['total_asset']:.2f} "
              f"当日盈亏={rec['today_pnl']:.2f}({rec['today_return']}%) "
              f"成交={len(rec['trades_today'])}笔 运行天数={rec['live_days']} "
              f"[{rec['data_nature']}]")
    print(f"  六策略合计总资产={total_asset:.2f}（初始合计 60000）")

    if no_push:
        print("  --no-push：已落盘，未上传。")
        return 0
    ok, msg = push_live_data()
    print(("  已上传数据仓库。" if ok else f"  上传失败（数据已本地落盘，可稍后重跑同步）：{msg}"))
    return 0 if ok else 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True,
                    help="补记交易日 YYYY-MM-DD，多个用逗号分隔（按升序逐日补）")
    ap.add_argument("--reason", default="当日 Windows 计划任务未成交，按当日真实收盘价事后补记"
                                       "（本机模拟撮合，非回测，不接券商）")
    ap.add_argument("--yes", action="store_true", help="跳过确认")
    ap.add_argument("--no-push", action="store_true", help="只落盘不上传 GitHub")
    args = ap.parse_args()

    days = sorted({d.strip() for d in args.date.split(",") if d.strip()})
    print("将按以下顺序事后补记（真实收盘价、本机模拟撮合、不接券商）：", days)
    for d in days:
        print(f"  - {d}")
    if not args.yes:
        ans = input("确认补记以上交易日？输入 yes 继续：").strip().lower()
        if ans != "yes":
            print("已取消。")
            return 1

    code = 0
    for d in days:
        c = backfill_one(d, args.reason, args.no_push)
        if c not in (0, 2):
            code = c
            if c in (3, 4, 5):
                break
    return code


if __name__ == "__main__":
    sys.exit(main())
