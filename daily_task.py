#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 端每日自动任务（工作日 15:30 由任务计划程序触发）

流程：
  1. 时间窗口校验（仅工作日 15:00-17:00，其余时间直接退出，绝不 7x24）
  2. git pull 代码仓库最新版（自动升级，无需手动拷文件）
  3. 如有新依赖则重装
  4. 跑当日实盘引擎，生成 live-data/daily/<今天>/
  5. git push 实盘数据到 GitHub
  6. 重启监控面板

日志写入 live-data/_run_logs/<日期>.log
"""
import os
import sys
import subprocess
import traceback
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


def in_time_window():
    now = datetime.now()
    if now.weekday() >= 5:   # 周末
        log(f"周末（{now.strftime('%A')}），跳过。")
        return False
    if not (15 <= now.hour < 17):
        log(f"当前 {now.strftime('%H:%M')} 不在 15:00-17:00 窗口，跳过。")
        return False
    return True


def already_run_today():
    manifest = DATA_REPO / "_manifest.json"
    if not manifest.exists():
        return False
    try:
        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data.get("last_run_date") == TODAY
    except Exception:
        return False


def step_update_code():
    """从 GitHub 拉取最新代码版本"""
    log("步骤1/5：从 GitHub 更新代码...")
    r = subprocess.run(["git", "fetch", "origin", "main"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"  fetch 失败（可能无网络，沿用本地版本）: {r.stderr.strip()}")
        return
    r = subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=60)
    log(f"  代码已同步到最新: {r.stdout.strip() or r.stderr.strip()}")


def step_install_deps():
    """如有 requirements 变化则重装"""
    req = BASE_DIR / "requirements.txt"
    if not req.exists():
        return
    log("步骤2/5：检查依赖...")
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(req),
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                   cwd=str(BASE_DIR), capture_output=True, timeout=300)


def step_run_engine():
    """跑当日实盘引擎，生成 live-data/daily/<今天>/"""
    log("步骤3/5：运行当日实盘引擎...")
    engine = BASE_DIR / "run_daily.py"
    if not engine.exists():
        log("  （未找到 run_daily.py，跳过引擎，仅记录运行心跳）")
        return
    r = subprocess.run([str(VENV_PY), str(engine)], cwd=str(BASE_DIR),
                       capture_output=True, text=True, timeout=600)
    log("  引擎输出: " + (r.stdout.strip()[-500:] if r.stdout else "(空)"))
    if r.returncode != 0:
        log("  引擎错误: " + r.stderr.strip()[-500:])


def step_push_data():
    """同步数据到 GitHub"""
    log("步骤4/5：上传实盘数据到 GitHub...")
    r = subprocess.run([str(VENV_PY), str(BASE_DIR / "scripts" / "sync_live_data.py"), "push"],
                       cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120)
    log("  " + (r.stdout.strip() or r.stderr.strip())[-300:])


def step_restart_panel():
    """重启监控面板"""
    log("步骤5/5：重启监控面板...")
    # Windows: 杀掉占用8000的进程，再后台启动
    try:
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq quant*"],
                       capture_output=True, text=True)
    except Exception:
        pass
    start = BASE_DIR / "run_simulation.py"
    subprocess.Popen(["start", "/min", "", str(VENV_PY), str(start)],
                     cwd=str(BASE_DIR), shell=True)
    log("  面板已重启。")


def mark_manifest():
    import json
    manifest = DATA_REPO / "_manifest.json"
    data = {"last_run_date": TODAY, "last_run_time": datetime.now().isoformat()}
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    log("=" * 50)
    log(f"每日任务启动（{TODAY}）")
    if not in_time_window():
        return
    if already_run_today():
        log("今天已运行过，跳过。")
        return
    try:
        step_update_code()
        step_install_deps()
        step_run_engine()
        mark_manifest()
        step_push_data()
        step_restart_panel()
        log("每日任务完成。")
    except Exception as e:
        log(f"任务异常: {e}")
        log(traceback.format_exc())


if __name__ == "__main__":
    main()
