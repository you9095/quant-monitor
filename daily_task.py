#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 端每日自动任务（现行：单段式，适配"只在交易日 13:00-17:00 开机"）
=====================================================================
由 Windows 任务计划程序触发（2026-10-08 起三触发 + 单实例锁）：

  QuantDailyTrade   onlogon 开机登录后 3 分钟：启动成交监督器（主）
  QuantDailyNoon    工作日 13:05：时间触发双保险（不依赖登录事件，治 onlogon 不触发）
  QuantDailyTradePM 工作日 15:10：收盘兜底（盘后按当日真实收盘价再确保成交一次，幂等）
  QuantBootCheck    onlogon 开机后 1 分钟：只做网络自愈 + 上报，不交易

trade 流程（监督器单实例锁 + 引擎当日幂等，重复触发不会重复成交）：
  更新代码 → 装依赖 → trade_supervisor.py（常驻：行情三源失败按 2/3/5 分钟后
  固定 10 分钟持续重试，直到当日真实价成交完成或 17:00；15:00 后自动转真实收盘价；
  每轮写健康心跳并上传；绝不用历史旧价成交）→ 兜底上传 → 上报心跳 → 重启面板

时间窗口硬限制：trade 仅工作日 13:00-17:00；其余时间一律不交易，绝不 7x24。
旧 execute(09:35)/decide(15:30) 两段式仅保留兼容，不再注册任务。
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
    hm = (now.hour, now.minute)
    if phase == "trade":
        ok = (13, 0) <= hm < (17, 0)
    elif phase == "execute":      # 旧两段式，保留
        ok = (9, 30) <= hm < (10, 0)
    else:                        # decide 旧两段式，保留
        ok = 15 <= now.hour < 17
    if not ok:
        log(f"当前 {now.strftime('%H:%M')} 不在 {phase} 窗口，跳过。")
        return False
    return True


def step_update_code():
    log("更新代码...")
    r = subprocess.run(["git", "fetch", "origin", "master"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"  fetch 失败（沿用本地版本）: {r.stderr.strip()[:200]}")
        return
    r = subprocess.run(["git", "reset", "--hard", "origin/master"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=60)
    log("  代码已同步到最新")


def step_install_deps():
    req = BASE_DIR / "requirements.txt"
    if not req.exists():
        return
    log("检查依赖...")
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(req),
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                   cwd=str(BASE_DIR), capture_output=True, timeout=300)


def step_run_engine(engine_phase):
    log(f"运行引擎 [{engine_phase}]...")
    engine = BASE_DIR / "run_daily.py"
    r = subprocess.run([str(VENV_PY), str(engine), engine_phase], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=600)
    log("  引擎输出: " + (r.stdout.strip()[-800:] if r.stdout else "(空)"))
    if r.returncode != 0:
        log("  引擎错误: " + r.stderr.strip()[-800:])


def step_run_supervisor():
    """跑一次成交周期守护 --guard（幂等、单次即退）。

    计划任务（登录后与工作日下午每 10 分钟的 QuantTradeGuard，外加 onlogon/13:05/15:10）
    会反复唤醒它：非交易日/当日已成交/红标锁定 -> 秒退；交易日 13:00 后未成交 ->
    取当日真实价成交（盘中实时价、收盘后收盘价），三源全失败则写"重试中"心跳，
    等下一次（约 10 分钟后）守护继续，绝不用旧价；跨日发现漏单则按当日真实收盘价
    自动事后补记。只有历史真实价也三源全失败才亮红灯（退出码 2）。
    单次守护限时 15 分钟（取价+撮合足够），周期任务负责"持续重试"，本进程不长驻。
    """
    log("启动成交周期守护 --guard（幂等：跨日补记/当日真实价成交/三源失败10分钟后重试）...")
    sup = BASE_DIR / "trade_supervisor.py"
    try:
        r = subprocess.run([str(VENV_PY), str(sup), "--guard"], cwd=str(BASE_DIR),
                           capture_output=True, text=True, timeout=900)
        log("  守护输出: " + (r.stdout.strip()[-1500:] if r.stdout else "(空)"))
        if r.returncode == 2:
            log("  ⚠️ 守护红灯：真实价三源（含历史收盘价）持续取不到，"
                "见 live-data/_run_logs/trade_health.json，等人工核对。")
        elif r.returncode != 0:
            log("  守护异常退出 code=%s: %s"
                % (r.returncode, (r.stderr or "")[-800:]))
        else:
            log("  守护本次正常结束（已成交/非交易日/等待下午/重试中，周期任务会再来）。")
    except subprocess.TimeoutExpired:
        log("  单次守护超过 15 分钟未退出（异常），下个周期会幂等重试，请查守护日志。")


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


def step_report_heartbeat():
    """上报一次心跳，让 macOS 端能确认定时任务真的在跑"""
    reporter = BASE_DIR / "scripts" / "report_deploy.py"
    if reporter.exists():
        subprocess.run([str(VENV_PY), str(reporter)], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=180)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["trade", "execute", "decide"])
    args = ap.parse_args()
    phase = args.phase
    log("=" * 50)
    log(f"每日任务启动 [{phase}]（{TODAY}）")
    # trade 交由监督器全权判断交易日与 13:00-17:00 窗口（早到会等、晚到退、周末不启动）；
    # 旧 decide/execute 两段式仍沿用固定窗口判断。
    if phase == "trade":
        if datetime.now().weekday() >= 5:
            log("周末，交易监督器不启动。")
            return
    elif not in_time_window(phase):
        return
    try:
        if phase == "trade":
            # 更新代码/依赖只做一次；监督器常驻负责 重试→成交→上传→健康心跳
            step_update_code()
            step_install_deps()
            step_run_supervisor()
            step_push_data()          # 兜底再上传一次（幂等，无变更则跳过）
            step_report_heartbeat()
            step_restart_panel()
        elif phase == "decide":
            # 旧两段式（兼容）
            step_update_code()
            step_install_deps()
            step_run_engine("decide")
            step_push_data()
            step_report_heartbeat()
            step_restart_panel()
        else:
            # 旧 execute（兼容）：只成交 + 上传
            step_run_engine("execute")
            step_push_data()
            step_report_heartbeat()
        log(f"[{phase}] 完成。")
    except Exception as e:
        log(f"任务异常: {e}")
        log(traceback.format_exc())


if __name__ == "__main__":
    main()
