#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘数据双向同步脚本（数据仓库 quant-monitor-live-data）

用法：
    python sync_live_data.py push     # Windows 端：提交并上传当天实盘数据
    python sync_live_data.py pull     # macOS 端：拉取 Windows 实盘数据
    python sync_live_data.py status   # 查看数据仓库状态

设计原则：
- 数据仓库与代码仓库物理隔离：本目录是独立 git clone，不污染代码仓库
- push 受时间窗口限制：仅工作日 13:00-17:00 允许（与开机成交窗口一致，避免 7x24）
- pull 不限制时间：macOS 随时可拉取查看
- 任何 git 失败都不能让主流程崩：只打印警告，不抛异常
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# ---- 路径配置 ----
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_REPO_DIR = BASE_DIR / "live-data"   # 独立数据仓库 clone 在此
REMOTE_URL = "git@github.com:you9095/quant-monitor-live-data.git"

# ---- 时间窗口（仅 push 生效）----
PUSH_WEEKDAYS = {0, 1, 2, 3, 4}   # 周一~周五（0=周一）
# 现行单段式：仅交易日 13:00-17:00 开机成交，成交后即上传，窗口与之对齐
PUSH_WINDOWS = [(13, 0, 17, 0)]


def is_push_window(now=None):
    """是否在允许 push 的时间窗口内（工作日 13:00-17:00）"""
    now = now or datetime.now()
    if now.weekday() not in PUSH_WEEKDAYS:
        return False, "今天是周末，不执行上传"
    hm = now.hour * 60 + now.minute
    for sh, sm, eh, em in PUSH_WINDOWS:
        if sh * 60 + sm <= hm < eh * 60 + em:
            return True, "在允许窗口内"
    return False, f"当前 {now.strftime('%H:%M')} 不在允许窗口（交易日 13:00-17:00）"


def git(args, cwd=DATA_REPO_DIR, timeout=60):
    """执行 git 命令，返回 (ok, stdout)"""
    try:
        r = subprocess.run(
            ["git"] + args, cwd=str(cwd),
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, "未找到 git 命令（请安装 Git for Windows）"
    except Exception as e:
        return False, f"git 异常: {e}"


def ensure_repo():
    """确保数据仓库目录存在且是 git 仓库"""
    if not DATA_REPO_DIR.exists():
        return False, f"数据目录不存在: {DATA_REPO_DIR}（请先 git clone 数据仓库）"
    ok, out = git(["rev-parse", "--is-inside-work-tree"])
    if not ok or "true" not in out:
        return False, f"不是 git 仓库: {DATA_REPO_DIR}\n{out}"
    return True, "ok"


def current_branch():
    """获取数据仓库当前分支名（自动适配 main/master）"""
    ok, out = git(["rev-parse", "--abbrev-ref", "HEAD"])
    return out.strip() if ok and out.strip() else "master"


def cmd_push(force=False, note=""):
    """Windows 端：提交当天实盘数据并 push。

    force=True 用于【显式人工/补记修复】（如事后补记、运维补传），跳过
    "仅交易日 13:00-17:00" 的自动窗口限制；日常无人值守自动上传仍受窗口约束。
    """
    ok, msg = is_push_window()
    if force:
        print("[时间窗口检查] 显式强制上传（--force，事后补记/运维补传），跳过窗口限制")
    else:
        print(f"[时间窗口检查] {msg}")
        if not ok:
            print("[跳过] 不在上传时间窗口，本次不上传数据。")
            return 0

    ok, msg = ensure_repo()
    if not ok:
        print(f"[错误] {msg}")
        return 1

    branch = current_branch()
    # 拉取远程最新（避免 push 被拒）
    git(["pull", "--rebase", "origin", branch], timeout=120)

    today = datetime.now().strftime("%Y-%m-%d")
    msg = note or ("live data backfill/manual sync " + today if force else "")
    commit_msg = msg if msg else f"live data {today} auto update"
    # 添加所有变更
    git(["add", "-A"])
    # 检查是否有变更
    ok, out = git(["status", "--porcelain"])
    if not out.strip():
        print("[提示] 今天没有新数据变更，无需上传。")
        return 0

    ok, out = git(["commit", "-m", commit_msg])
    if not ok:
        print(f"[警告] commit 失败: {out}")
        return 1

    ok, out = git(["push", "origin", branch], timeout=120)
    if ok:
        print(f"[成功] 实盘数据已上传 GitHub（{today}）")
    else:
        print(f"[失败] push 失败，请检查 Git 认证: {out}")
    return 0 if ok else 1


def cmd_pull():
    """macOS 端：拉取 Windows 实盘数据"""
    ok, msg = ensure_repo()
    if not ok:
        print(f"[错误] {msg}")
        print("首次使用请执行: git clone " + REMOTE_URL + " \"" + str(DATA_REPO_DIR) + "\"")
        return 1
    branch = current_branch()
    ok, out = git(["pull", "origin", branch], timeout=120)
    if ok:
        print("[成功] 已拉取 Windows 实盘数据到本地 live-data/")
        # 显示最新数据日期
        daily = DATA_REPO_DIR / "daily"
        if daily.exists():
            days = sorted([d.name for d in daily.iterdir() if d.is_dir()])
            if days:
                print(f"  最新数据日期: {days[-1]}（共 {len(days)} 天）")
    else:
        print(f"[失败] pull 失败: {out}")
    return 0 if ok else 1


def cmd_status():
    ok, msg = ensure_repo()
    if not ok:
        print(msg)
        return 1
    ok, out = git(["log", "--oneline", "-5"])
    print("=== 数据仓库最近 5 次提交 ===")
    print(out if ok else "(无提交记录)")
    daily = DATA_REPO_DIR / "daily"
    if daily.exists():
        days = sorted([d.name for d in daily.iterdir() if d.is_dir()])
        print(f"\n已积累实盘数据天数: {len(days)}")
        if days:
            print(f"数据日期范围: {days[0]} ~ {days[-1]}")
    return 0


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "push":
        rest = sys.argv[2:]
        force = "--force" in rest
        note = " ".join(a for a in rest if not a.startswith("--")).strip()
        sys.exit(cmd_push(force=force, note=note))
    elif action == "pull":
        sys.exit(cmd_pull())
    else:
        sys.exit(cmd_status())
