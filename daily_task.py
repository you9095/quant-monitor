#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 端每日自动任务（两段式）
================================
由 Windows 任务计划程序在两个时间点触发：

  09:35  execute 阶段：开盘后按昨日信号真实成交（用实时价≈开盘价）
  15:30  decide   阶段：收盘后更新代码 + 算今日信号 + 上传数据 + 重启面板

时间窗口硬限制：
  execute: 工作日 09:30-10:00
  decide:  工作日 15:00-17:00
周末/夜间/早间一律不跑，绝不 7x24。
"""
import os
import sys
import subprocess
import traceback
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_REPO = BASE_DIR / "live-data"
LOG_DIR = DATA_REPO / "_run_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")
LOG_FILE = LOG_DIR / f"{TODAY}.log"

# Windows 上 venv python
VENV_PY = BASE_DIR / "venv" / "Scripts" / "python.exe"
if not VENV_PY.exists():
    VENV_PY = Path(sys.executable)


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def in_time_window(phase):
    now = datetime.now()
    if now.weekday() >= 5:
        log(f"周末（{now.strftime('%A')}），跳过。")
        return False
    if phase == "execute":
        ok = (9, 30) <= (now.hour, now.minute) < (10, 0)
    else:
        ok = 15 <= now.hour < 17
    if not ok:
        log(f"当前 {now.strftime('%H:%M')} 不在 {phase} 窗口，跳过。")
        return False
    return True


def step_update_code():
    log("更新代码...")
    r = subprocess.run(["git", "fetch", "origin", "main"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"  fetch 失败（沿用本地版本）: {r.stderr.strip()[:200]}")
        return
    r = subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=60)
    log(f"  代码已同步到最新")


def step_install_deps():
    req = BASE_DIR / "requirements.txt"
    if not req.exists():
        return
    log("检查依赖...")
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(req),
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                   cwd=str(BASE_DIR), capture_output=True, timeout=300)


def step_run_engine(phase):
    log(f"运行引擎 [{phase}]...")
    engine = BASE_DIR / "run_daily.py"
    r = subprocess.run([str(VENV_PY), str(engine), phase], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=600)
    log("  引擎输出: " + (r.stdout.strip()[-500:] if r.stdout else "(空)"))
    if r.returncode != 0:
        log("  引擎错误: " + r.stderr.strip()[-500:])


def step_push_data():
    log("上传实盘数据到 GitHub...")
    r = subprocess.run([str(VENV_PY), str(BASE_DIR / "scripts" / "sync_live_data.py"), "push"],
                       cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120)
    log("  " + (r.stdout.strip() or r.stderr.strip())[-300:])


def step_restart_panel():
    log("重启监控面板...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq quant*"],
                       capture_output=True, text=True)
    except Exception:
        pass
    start = BASE_DIR / "run_simulation.py"
    subprocess.Popen(["start", "/min", "", str(VENV_PY), str(start)],
                     cwd=str(BASE_DIR), shell=True)
    log("  面板已重启。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["execute", "decide"])
    args = ap.parse_args()
    phase = args.phase
    log("=" * 50)
    log(f"每日任务启动 [{phase}]（{TODAY}）")
    if not in_time_window(phase):
        return
    try:
        if phase == "decide":
            # 收盘阶段：更新代码 + 装依赖 + 决策 + 上传 + 重启面板
            step_update_code()
            step_install_deps()
            step_run_engine("decide")
            step_push_data()
            step_restart_panel()
        else:
            # 开盘阶段：只执行成交 + 上传数据（不更新代码，避免盘中变动）
            step_run_engine("execute")
            step_push_data()
        log(f"[{phase}] 完成。")
    except Exception as e:
        log(f"任务异常: {e}")
        log(traceback.format_exc())


if __name__ == "__main__":
    main()
