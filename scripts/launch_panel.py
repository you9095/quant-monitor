#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI量化面板 · 全自动总控（模拟盘，本机真实撮合，绝不连接任何券商真实账号/资金账号）。

桌面“AI量化面板”图标、quant:// 按钮、计划任务 QuantPanelGuard 都调用本文件。
双击后无需任何其它操作，自动按顺序完成：
  STEP 1  更新代码（git fetch + reset --hard origin/master）。
           若更新确实拉到了新版本，自动“重启自己”一次以执行最新逻辑（用户仍只双击一次）。
  STEP 2  确保数据后台在运行（未运行则静默拉起）。
  STEP 2.5 幂等补注册计划任务（含 QuantTradeGuard，注册自愈降级，不依赖后端重启）。
  STEP 3  成交周期守护 trade_supervisor --guard
            · 非交易日 / 当日已成交：秒退
            · 盘中 13-15：秒退，由 QuantTradeGuard 收盘后按真实收盘价自动成交
            · 收盘后：立即按当日真实收盘价成交（三源全失败则持续重试，不用旧价）
  STEP 4  上传实盘数据到 GitHub
  STEP 5  上报部署心跳（含代码版本，便于远程自动核查）
  STEP 6  用默认浏览器直接打开“实盘”面板
全程静默、输出写入 logs/backend_boot.log；致命错误弹出明确提示框，绝不闪退无提示。
自带文件锁，避免并发重复执行。
"""

import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGDIR = ROOT / "logs"
LOGDIR.mkdir(exist_ok=True)
BOOTLOG = LOGDIR / "backend_boot.log"
LOCKFILE = LOGDIR / "launch_panel.lock"
SERVER = ROOT / "api" / "real_data_server_v2.py"
PORT = int(os.environ.get("PORT", "8000"))
WAIT_SECONDS = 90
IS_WIN = sys.platform == "win32"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0


def log(msg):
    try:
        with open(BOOTLOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


def say(msg):
    print(msg, flush=True)
    log(msg)


def healthy(timeout=1.5):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/v1/health", timeout=timeout
        ) as r:
            return r.status == 200
    except Exception:
        return False


def acquire_lock():
    """拿到锁返回文件句柄；已有另一个总控在跑则返回 None。"""
    try:
        fh = open(LOCKFILE, "w")
    except Exception:
        return True
    try:
        import msvcrt  # Windows
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return fh
        except OSError:
            return None
    except ImportError:
        try:
            import fcntl  # macOS / Linux
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except Exception:
            return None


def console_python():
    """协议处理器常为 pythonw.exe（无控制台）；需要控制台 python.exe 时用同目录版本。"""
    exe = Path(sys.executable)
    if IS_WIN and exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return cand
    return exe


def project_py():
    """项目子步骤统一用项目虚拟环境 python（优先），保证依赖一致。"""
    cand = ROOT / "venv" / "Scripts" / "python.exe"
    if cand.exists():
        return cand
    cand = ROOT / "api" / "venv" / "bin" / "python"
    if cand.exists():
        return cand
    return console_python()


def _banner(lf, title):
    lf.write("\n" + "=" * 24 + f" {title} @ {time.strftime('%H:%M:%S')} "
             + "=" * 24 + "\n")


def _git_env():
    env = os.environ.copy()
    # SSH 连接短超时，避免国内网络挂起整体卡死
    env.setdefault("GIT_SSH_COMMAND", "ssh -o ConnectTimeout=15")
    return env


def run_git(args, timeout=120):
    """静默执行 git，输出进日志；返回返回码。"""
    try:
        with open(BOOTLOG, "a", encoding="utf-8") as lf:
            _banner(lf, "git " + " ".join(args))
            kw = dict(cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT,
                      stdin=subprocess.DEVNULL, env=_git_env())
            if IS_WIN:
                kw["creationflags"] = NO_WINDOW
            r = subprocess.run(["git", *args], timeout=timeout, **kw)
            return r.returncode
    except Exception as exc:
        log(f"git {' '.join(args)} 异常: {exc}")
        return -1


def git_head():
    try:
        kw = dict(cwd=str(ROOT), capture_output=True, text=True,
                  timeout=20, env=_git_env())
        if IS_WIN:
            kw["creationflags"] = NO_WINDOW
        r = subprocess.run(["git", "rev-parse", "HEAD"], **kw)
        return r.stdout.strip()
    except Exception:
        return ""


def run_py(script_args, timeout=600):
    """用项目 venv python 静默运行脚本，输出进日志；返回返回码。"""
    py = project_py()
    try:
        with open(BOOTLOG, "a", encoding="utf-8") as lf:
            _banner(lf, str(py.name) + " " + " ".join(map(str, script_args)))
            kw = dict(cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT,
                      stdin=subprocess.DEVNULL)
            if IS_WIN:
                kw["creationflags"] = NO_WINDOW
            r = subprocess.run([str(py), *map(str, script_args)],
                               timeout=timeout, **kw)
            return r.returncode
    except Exception as exc:
        log(f"运行 {script_args} 异常: {exc}")
        return -1


def spawn_backend():
    py = project_py()
    logf = open(BOOTLOG, "a", encoding="utf-8")
    _banner(logf, f"spawn backend py={py}")
    kw = dict(cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
              stdin=subprocess.DEVNULL, close_fds=True)
    if IS_WIN:
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                               | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | NO_WINDOW)
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen([str(py), "-u", str(SERVER)], **kw)
    log(f"spawned backend pid={proc.pid}")
    return proc


def relaunch_self():
    """以当前解释器（保持 pythonw 静默）重新启动本文件，标记 --restarted。"""
    args = [sys.executable, str(Path(__file__).resolve()),
            "--open", "--restarted"]
    try:
        if IS_WIN:
            flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                     | NO_WINDOW)
            subprocess.Popen(args, creationflags=flags, close_fds=True,
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(args, start_new_session=True,
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        log("relaunched self (--restarted)")
    except Exception as exc:
        log(f"relaunch failed: {exc}")


def report_heartbeat():
    """best-effort 触发部署心跳上报（含当前 git 版本号）。"""
    try:
        rep = ROOT / "scripts" / "report_deploy.py"
        if rep.exists():
            run_py([rep], timeout=60)
            log("heartbeat reporter triggered")
    except Exception as exc:
        log(f"heartbeat reporter skipped: {exc}")


def alert(msg):
    log("ALERT: " + msg)
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "AI量化面板", 0x40)
        except Exception:
            pass


def panel_url():
    return f"http://localhost:{PORT}/?data_mode=live"


def open_in_browser():
    url = panel_url()
    try:
        if IS_WIN:
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        log(f"browser opened: {url}")
        return
    except Exception as exc:
        log(f"open failed: {exc}")
    try:
        import webbrowser
        webbrowser.open(url, new=2)
    except Exception as exc:
        log(f"open_in_browser failed: {exc}")


def wait_healthy():
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        time.sleep(2)
        if healthy():
            return True
    return False


def main():
    open_browser = "--open" in sys.argv
    restarted = "--restarted" in sys.argv
    if restarted:
        time.sleep(2)  # 等上一个实例退出、释放文件锁

    lock = acquire_lock()
    if lock is None:
        log("another launcher holds the lock" + ("；wait only" if open_browser else "；exit"))
        if open_browser and wait_healthy():
            open_in_browser()
        return 0

    # STEP 1：自更新；若确实拉到新版本则重启自己（只重启一次，--restarted 后不再重启）
    say("STEP 1/6 更新代码…")
    before = git_head()
    run_git(["fetch", "origin", "master"], timeout=120)
    run_git(["reset", "--hard", "origin/master"], timeout=90)
    after = git_head()
    if not restarted and before and after and before != after:
        log(f"代码已更新 {before[:7]} -> {after[:7]}，自动重启以执行最新逻辑")
        relaunch_self()
        return 0  # 锁随本进程退出释放；--restarted 新实例会跑完整个流程

    # STEP 2：确保后台在运行
    say("STEP 2/6 检查数据后台…")
    if not healthy():
        say("后台未运行，正在静默启动…")
        try:
            spawn_backend()
        except Exception as exc:
            alert(f"启动数据后台失败：{exc}\n\n日志：\n{BOOTLOG}")
            return 2
        if not wait_healthy():
            alert(f"数据后台在 {WAIT_SECONDS} 秒内未就绪。\n\n日志：\n{BOOTLOG}")
            return 1
    say("数据后台已就绪。")

    # STEP 2.5：幂等补注册计划任务（QuantTradeGuard 注册自愈降级；不阻断）
    say("STEP 2.5 补注册计划任务…")
    reg = ROOT / "scripts" / "win_self_register.py"
    if reg.exists():
        run_py([reg], timeout=90)

    # STEP 3：成交守护（盘中秒退、收盘后按收盘价成交、已成交/非交易日秒退）
    say("STEP 3/6 成交周期守护…")
    rc = run_py(["trade_supervisor.py", "--guard"], timeout=600)
    if rc == 2:
        log("guard 红灯：真实价三源持续失败，等下次守护/人工核对。")

    # STEP 4：上传实盘数据
    say("STEP 4/6 上传实盘数据…")
    sync = ROOT / "scripts" / "sync_live_data.py"
    if sync.exists():
        run_py([sync, "push"], timeout=180)

    # STEP 5：心跳
    say("STEP 5/6 上报心跳…")
    report_heartbeat()

    # STEP 6：打开实盘面板
    say("STEP 6/6 打开实盘面板…")
    if open_browser:
        open_in_browser()

    say("全自动流程结束。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        alert(f"总控发生错误：{exc}\n\n日志：\n{BOOTLOG}")
        sys.exit(1)
