#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI量化面板 · 统一启动器（模拟盘，本机真实撮合，绝不连接任何券商真实账号/资金账号）。

quant:// 页面按钮、Windows 计划任务 QuantPanelGuard、启动器 .bat/.command
全部调用本文件，负责确保本机 8000 端口的 Flask 后台在运行：
  - 后台已在运行：直接退出（幂等）；
  - 未运行：以后台/无窗口方式拉起 api/real_data_server_v2.py，
    启动输出与报错全部追加到 logs/backend_boot.log；
  - 轮询健康端点，就绪即退出；超时未就绪则在 Windows 弹出明确错误框并指向日志，
    绝不“黑窗一闪、没有任何提示”。
自带文件锁，避免按钮点击与计划任务并发拉起多个后台。
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
    """拿到锁返回文件句柄；已有另一个启动器在跑则返回 None。"""
    try:
        fh = open(LOCKFILE, "w")
    except Exception:
        return True  # 锁文件都建不了时不阻塞启动
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
    """协议处理器通常是 pythonw.exe（无控制台）；启动后端改用同目录 python.exe。"""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return cand
    return exe


def spawn_backend():
    py = console_python()
    logf = open(BOOTLOG, "a", encoding="utf-8")
    logf.write("\n" + "=" * 28 + f" launch @ {time.strftime('%Y-%m-%d %H:%M:%S')} "
               f"py={py} " + "=" * 28 + "\n")
    kw = dict(cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
              stdin=subprocess.DEVNULL, close_fds=True)
    if sys.platform == "win32":
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                               | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen([str(py), "-u", str(SERVER)], **kw)
    log(f"spawned backend pid={proc.pid}")
    return proc


def report_heartbeat():
    """后端就绪后 best-effort 触发一次部署心跳上报（含当前 git 版本号），便于远程确认。"""
    try:
        rep = ROOT / "scripts" / "report_deploy.py"
        if not rep.exists():
            return
        py = console_python()
        kw = dict(cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  stdin=subprocess.DEVNULL, close_fds=True)
        if sys.platform == "win32":
            kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            kw["start_new_session"] = True
        subprocess.Popen([str(py), str(rep)], **kw)
        log("heartbeat reporter triggered")
    except Exception as exc:
        log(f"heartbeat reporter skipped: {exc}")


def alert(msg):
    log("ALERT: " + msg)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "AI量化面板启动器", 0x40)
        except Exception:
            pass


def open_in_browser():
    """用系统默认浏览器打开面板（同源 http，绕开 file:// 的一切限制）。"""
    url = f"http://localhost:{PORT}/"
    try:
        if sys.platform == "win32":
            os.startfile(url)  # Windows 最可靠，pythonw 无控制台也生效
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        log(f"browser opened: {url}")
        return
    except Exception as exc:
        log(f"open via os/startfile failed: {exc}")
    try:
        import webbrowser
        webbrowser.open(url, new=2)
        log(f"browser opened via webbrowser: {url}")
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
    lock = acquire_lock()

    # 另一个启动器（如开机守护）正在拉起后台：本进程不重复 spawn，
    # 但若是用户双击（--open），仍等后台就绪后把面板打开。
    if lock is None:
        log("another launcher holds the lock; waiting only" if open_browser
            else "another launcher is starting backend; exit")
        if open_browser and wait_healthy():
            open_in_browser()
        return 0

    say("启动器：正在检查数据后台是否已在运行…")
    if healthy():
        say("数据后台已在运行，无需重复启动。")
        if open_browser:
            open_in_browser()
        return 0

    say("数据后台未运行，正在启动（首次约需 30-90 秒，含数据同步）…")
    try:
        spawn_backend()
    except Exception as exc:
        alert(f"启动数据后台失败：{exc}\n\n请把日志文件发给助手排查：\n{BOOTLOG}")
        return 2

    if wait_healthy():
        say(f"数据后台已就绪：http://localhost:{PORT}/")
        report_heartbeat()
        if open_browser:
            open_in_browser()
        return 0

    alert(f"数据后台在 {WAIT_SECONDS} 秒内仍未就绪。\n\n"
          f"请把下面的日志文件发给助手排查：\n{BOOTLOG}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
