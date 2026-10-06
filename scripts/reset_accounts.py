#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘账户归零（一次性运维脚本）
================================
背景：用户明确指令 —— 2026-10-06（国庆假期最后一天）17:00 把六策略账本全部
清空归零，2026-10-07 为实盘模拟第一天，所有数据从零开始。

本脚本做什么：
  1. 六策略 live-data/_account_state/{sid}.json 重置为：现金 10000、空仓、
     无成交流水、无 pending_target（用撮合引擎 Broker 直接生成，结构保证正确）
  2. 清空 live-data/daily/、live-data/latest/、live-data/_run_logs/
  3. 写 _reset_marker.json 留痕（谁、何时、为何归零）
  4. 自动 git add/commit/push 到【数据仓库】quant-monitor-live-data

明确保留（不是交易数据，不清）：
  - data/etf_cache/        行情 K 线/收盘价缓存（清了要重新下载，浪费）
  - _deploy_status/、_install_status/   Windows 上线/部署心跳（Mac 端监控要用）

用法：
  python scripts/reset_accounts.py --yes      # 直接执行（定时任务用）
  python scripts/reset_accounts.py            # 交互式，需手动确认
  python scripts/reset_accounts.py --dry-run  # 只打印将做什么，不动手
  python scripts/reset_accounts.py --yes --no-push   # 只归零不 push
"""
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "api"))
sys.path.insert(0, str(BASE_DIR))

from run_daily_engine import STRATEGIES  # noqa: E402  复用六策略定义(sid/name/capital)
from matching_engine import Broker       # noqa: E402

DATA_REPO = BASE_DIR / "live-data"
STATE_DIR = DATA_REPO / "_account_state"
CLEAR_DIRS = ["daily", "latest", "_run_logs"]
KEEP_NOTE = ["_deploy_status", "_install_status", "data/etf_cache"]


def run_git(args, timeout=180):
    return subprocess.run(["git"] + args, cwd=str(DATA_REPO),
                          capture_output=True, text=True, timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    ap.add_argument("--dry-run", action="store_true", help="只预演不执行")
    ap.add_argument("--no-push", action="store_true", help="归零但不 push")
    args = ap.parse_args()

    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = now.strftime("%Y-%m-%d")

    print("=" * 56)
    print("  实盘账户归零脚本 reset_accounts.py")
    print("  模式: 模拟盘（不接任何券商），仅清空本机撮合账本")
    print("=" * 56)

    if not DATA_REPO.exists():
        print(f"[错误] 数据仓库不存在: {DATA_REPO}")
        sys.exit(1)

    # 预演 / 确认
    print(f"将重置 {len(STRATEGIES)} 个策略账户为各持现金 10000、空仓：")
    for sid, cfg in STRATEGIES.items():
        print(f"  - {cfg['name']}({sid})  本金 {cfg['capital']}")
    print(f"将清空目录: {CLEAR_DIRS}")
    print(f"明确保留: {KEEP_NOTE}")

    if args.dry_run:
        print("\n[dry-run] 未做任何改动。")
        return

    if not args.yes:
        ans = input("\n确认归零？此操作清空全部实盘成交记录，输入 YES 继续: ").strip()
        if ans != "YES":
            print("已取消。")
            return

    # 0) 先把数据仓库对齐 GitHub 最新（避免本地落后导致 push non-fast-forward，
    #    同时拿到 Windows 最新部署心跳；交易数据随后仍会被清空）
    print("同步数据仓库到 GitHub 最新 ...")
    run_git(["fetch", "origin", "master"])
    rs = run_git(["reset", "--hard", "origin/master"])
    print("  " + ("已对齐 origin/master" if rs.returncode == 0
                  else "警告: 对齐失败（继续本地归零，push 可能被拒）"))

    # 1) 重置账户状态（用全新 Broker 生成，结构保证正确）
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for sid, cfg in STRATEGIES.items():
        b = Broker(initial_capital=cfg["capital"], strategy_id=sid)
        b.pending_target = {}
        b.save(STATE_DIR / f"{sid}.json")
        print(f"  [重置] {sid}: 现金 {cfg['capital']}，空仓，0 笔成交")

    # 2) 清空交易数据目录
    for d in CLEAR_DIRS:
        p = DATA_REPO / d
        if not p.exists():
            continue
        n = 0
        for f in p.rglob("*"):
            # 保留 .gitkeep 占位，使空目录仍被 git 跟踪
            if f.is_file() and f.name != ".gitkeep":
                f.unlink()
                n += 1
        # 删空的日期子目录
        for sub in sorted([x for x in p.rglob("*") if x.is_dir()], reverse=True):
            try:
                sub.rmdir()
            except OSError:
                pass
        print(f"  [清空] {d}/  删除 {n} 个文件")

    # 3) 归零留痕
    marker = {
        "reset_time": stamp,
        "reset_date": today,
        "ordered_by": "用户明确指令",
        "reason": "2026-10-06 17:00 归零；10-07休市，2026-10-08(节后首个交易日)实盘从零开始",
        "strategies": {sid: {"name": c["name"], "cash": c["capital"],
                             "positions": 0, "trades": 0}
                       for sid, c in STRATEGIES.items()},
        "kept": KEEP_NOTE,
    }
    (DATA_REPO / "_reset_marker.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  [留痕] _reset_marker.json")

    if args.no_push:
        print("\n[完成] 已本地归零，未 push（--no-push）。")
        return

    # 4) 提交并推送数据仓库
    print("\n提交到数据仓库...")
    run_git(["add", "-A"])
    run_git(["commit", "-m",
             f"reset: 实盘账户归零 {stamp}（用户指令，10-07从零开始）"])
    r = run_git(["push", "origin", "master"], timeout=300)
    if r.returncode == 0:
        print("[完成] 已归零并 push 到 quant-monitor-live-data。")
    else:
        print("[警告] push 失败（本地已归零）：")
        print((r.stderr or r.stdout)[-500:])
        print("可在网络恢复后于 live-data/ 手动执行: git push origin master")
        sys.exit(2)


if __name__ == "__main__":
    main()
