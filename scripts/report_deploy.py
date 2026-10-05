#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署心跳上报：Windows 部署/更新完成后，把本机部署状态 push 到数据仓库。
macOS 端 pull 后即可远程判断 Windows 是否部署成功、卡在哪一步。

与实盘数据不同：部署心跳不受交易时间窗口限制，任何时间都可上报。

用法：
    python scripts/report_deploy.py
"""
import os
import sys
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = BASE_DIR / "live-data"


def git(args, cwd, timeout=120):
    try:
        r = subprocess.run(["git"] + args, cwd=str(cwd),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def collect_status():
    status = {
        "hostname": socket.gethostname(),
        "report_time": datetime.now().isoformat(timespec="seconds"),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "venv_exists": (BASE_DIR / "venv" / "Scripts" / "python.exe").exists()
                       or (BASE_DIR / "venv" / "bin" / "python").exists(),
    }
    # 关键依赖
    deps = {}
    for mod in ["flask", "akshare", "pandas", "numpy", "requests"]:
        try:
            m = __import__(mod)
            deps[mod] = getattr(m, "__version__", "ok")
        except Exception:
            deps[mod] = "MISSING"
    status["dependencies"] = deps

    # 代码仓库状态
    ok, out = git(["rev-parse", "--abbrev-ref", "HEAD"], BASE_DIR)
    status["code_branch"] = out if ok else "?"
    ok, out = git(["rev-parse", "--short", "HEAD"], BASE_DIR)
    status["code_commit"] = out if ok else "?"

    # 数据仓库状态
    status["live_data_exists"] = LIVE_DIR.exists()
    if LIVE_DIR.exists():
        ok, out = git(["rev-parse", "--is-inside-work-tree"], LIVE_DIR)
        status["live_data_is_repo"] = ok and "true" in out
        ok, out = git(["remote", "get-url", "origin"], LIVE_DIR)
        status["live_data_remote"] = out if ok else "(无remote)"
    else:
        status["live_data_is_repo"] = False
        status["live_data_remote"] = "(目录不存在)"

    # Windows 定时任务
    if sys.platform == "win32":
        import ctypes
        try:
            status["is_admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            status["is_admin"] = None

        def task_exists(name):
            r = subprocess.run(["schtasks", "/query", "/tn", name],
                               capture_output=True, text=True)
            return r.returncode == 0

        # 现行（单段式，2026-10-04 起）任务
        for t in ["QuantDailyTrade", "QuantDailyTradePM", "QuantBootCheck"]:
            status[f"task_{t}"] = "REGISTERED" if task_exists(t) else "MISSING"
        # 旧两段式任务，正确状态应为 MISSING（迁移后已删除）
        for t in ["QuantExecuteTask", "QuantDecideTask"]:
            status[f"legacy_{t}"] = "EXISTS_SHOULD_DELETE" if task_exists(t) else "MISSING"

        # 枚举系统里所有 Quant* 任务，便于 macOS 端远程核对
        try:
            r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"],
                               capture_output=True, timeout=30)
            txt = r.stdout.decode("gbk", errors="ignore")
            names = set()
            for line in txt.splitlines():
                if "Quant" in line:
                    first = line.split(",")[0].strip().strip('"')
                    names.add(first.rsplit("\\", 1)[-1])
            status["tasks_all_Quant"] = sorted(names)
        except Exception as e:
            status["tasks_all_Quant"] = f"enum_failed: {e}"
    return status


def main():
    if not LIVE_DIR.exists():
        print("[心跳] live-data 目录不存在，无法上报（数据仓库未 clone）")
        return 1
    ok, out = git(["rev-parse", "--is-inside-work-tree"], LIVE_DIR)
    if not ok or "true" not in out:
        print(f"[心跳] live-data 不是 git 仓库: {out}")
        return 1

    status = collect_status()
    report_dir = LIVE_DIR / "_deploy_status"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"{status['hostname']}.json"
    report_file.write_text(json.dumps(status, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print("[心跳] 部署状态:")
    print(json.dumps(status, ensure_ascii=False, indent=2))

    branch_ok, branch = git(["rev-parse", "--abbrev-ref", "HEAD"], LIVE_DIR)
    branch = branch if branch_ok else "master"
    git(["add", "-A"], LIVE_DIR)
    ok, out = git(["commit", "-m",
                   f"deploy heartbeat {status['hostname']} {status['report_time']}"],
                  LIVE_DIR)
    if not ok and "nothing to commit" not in out:
        print(f"[心跳] commit 失败: {out}")
        return 1
    # 先同步远程，避免与安装期临时通道 _qm_live 的推送互相挡住
    git(["pull", "--no-rebase", "origin", branch], LIVE_DIR, timeout=120)
    ok, out = git(["push", "origin", branch], LIVE_DIR, timeout=120)
    if ok:
        print(f"[心跳] 已上报到 GitHub 数据仓库（{status['hostname']}）")
        return 0
    print(f"[心跳] push 失败: {out}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
