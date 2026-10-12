#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 量化监控 —— Windows 一键修复 + 当日收盘价成交 + 启动面板（强自愈 / 全超时 / 逐步上报）
========================================================================================
双击本文件即可。若被 pythonw（无窗口）关联，会自动用 venv 控制台 python 在新窗口重跑自己。

特性：
  · 每一步都有“短超时”，任何联网/子步骤卡住都会自动跳过或换通道，绝不整体卡死；
  · 更新代码三通道自愈：SSH(22) -> SSH(443, ssh.github.com) -> HTTPS；
  · 每完成一步立即写 live-data/_run_logs/oneclick_status.json 并 push，
    助手可远程实时看到进度与卡点（无需用户截图）；
  · 顺序：定位 -> 更新代码 -> 依赖 -> 收盘价成交 -> 上传 -> 起后端(可见窗口) -> 开面板；
  · 控制台末尾暂停，错误清清楚楚，绝不闪退。
本机模拟撮合，不连接任何券商真实账号/资金账号。
"""
import os
import sys
import time
import json
import subprocess
import webbrowser
from pathlib import Path

STAGE_FILE_NAME = Path("_run_logs") / "oneclick_status.json"


def locate_root() -> Path:
    cands = [Path(r"D:\quant-monitor"), Path(__file__).resolve().parent]
    for c in cands:
        if (c / "daily_task.py").exists():
            return c.resolve()
    p = Path(__file__).resolve().parent
    for _ in range(4):
        if (p / "daily_task.py").exists():
            return p.resolve()
        p = p.parent
    return Path(__file__).resolve().parent


def have_console() -> bool:
    try:
        return bool(sys.stdout and sys.stdout.isatty())
    except Exception:
        return False


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else locate_root()
    vpy = root / "venv" / "Scripts" / "python.exe"
    live = root / "live-data"

    # 无控制台：用 venv 控制台 python 在新窗口重跑自己
    if not have_console():
        if not vpy.exists():
            return
        subprocess.Popen(
            ["cmd", "/k", str(vpy), str(Path(__file__).resolve()), str(root)],
            creationflags=0x10, cwd=str(root),
        )
        return

    os.system("chcp 65001 >nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    state = {"host": os.environ.get("COMPUTERNAME", "?"),
             "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "root": str(root), "steps": {}}

    def emit(stage, **kv):
        state["steps"][stage] = {"at": time.strftime("%H:%M:%S"), **kv}
        try:
            live.mkdir(exist_ok=True)
            sf = live / STAGE_FILE_NAME
            sf.parent.mkdir(exist_ok=True)
            sf.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                          encoding="utf-8")
            subprocess.run(["git", "add", str(STAGE_FILE_NAME).replace("\\", "/")],
                           cwd=str(live), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15)
            subprocess.run(["git", "commit", "-m", f"oneclick {stage}"],
                           cwd=str(live), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15)
            subprocess.run(["git", "push", "origin", "master"], cwd=str(live),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=25)
        except Exception:
            pass
        print(f"[{stage}]", kv if kv else "")

    def run(cmd, timeout, cwd=None, visible=True):
        try:
            kw = dict(cwd=str(cwd or root), timeout=timeout)
            if not visible:
                kw.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            r = subprocess.run(cmd, **kw)
            return r.returncode
        except subprocess.TimeoutExpired:
            print(f"   !! 超时({timeout}s)，跳过: {' '.join(map(str, cmd))}")
            return 124
        except Exception as e:
            print(f"   !! 异常: {e}")
            return -1

    print("=" * 64)
    print("  AI Quant - One Click (强自愈版)  本机撮合，不接券商")
    print(f"  工作目录: {root}")
    print("=" * 64)

    emit("locate", vpy_exists=vpy.exists())
    if not vpy.exists():
        print(f"[错误] 未找到 {vpy}")
        emit("fatal", reason="venv python missing")
        input("按回车键关闭...")
        return

    # ---- STEP 1 更新代码（三通道自愈，全部短超时）----
    print("\n===== STEP 1  更新代码 =====")
    updated = False
    channels = [
        ("SSH22", ["git", "fetch", "origin", "master"]),
        ("SSH443", ["git", "-c", "core.sshCommand=ssh -p 443 -o ConnectTimeout=15 ssh.github.com",
                    "fetch", "origin", "master"]),
        ("HTTPS", ["git", "fetch",
                   "https://github.com/you9095/quant-monitor.git", "master"]),
    ]
    used = None
    for name, cmd in channels:
        rc = run(cmd, timeout=45, visible=False)
        print(f"   通道 {name}: rc={rc}")
        if rc == 0:
            used, updated = name, True
            break
    new_commit = None
    if updated:
        run(["git", "reset", "--hard", "FETCH_HEAD"], timeout=30, visible=False)
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(root),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
        new_commit = r.stdout.decode().strip()
    emit("update", ok=updated, channel=used, commit=new_commit)
    print(f"   更新: {'成功 ' + str(new_commit) if updated else '失败，沿用本地代码继续'}")

    # ---- STEP 2 依赖 ----
    print("\n===== STEP 2  检查依赖 =====")
    rc = run([str(vpy), "-m", "pip", "install", "-q", "-r", "requirements.txt",
              "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"], timeout=300)
    emit("deps", rc=rc)

    # ---- STEP 3 收盘价成交 ----
    print("\n===== STEP 3  按今日真实收盘价成交 =====")
    rc = run([str(vpy), "trade_supervisor.py", "--guard"], timeout=300)
    emit("guard", rc=rc)

    # ---- STEP 4 上传实盘数据 ----
    print("\n===== STEP 4  上传实盘数据 =====")
    sync = root / "scripts" / "sync_live_data.py"
    if sync.exists():
        rc = run([str(vpy), str(sync), "push"], timeout=120)
        emit("push", rc=rc)

    # ---- STEP 5 起后端（可见窗口，报错不闪退）----
    print("\n===== STEP 5  启动数据后台（新窗口，可最小化，勿关闭） =====")
    backend_ok = False
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2):
            backend_ok = True
    except Exception:
        pass
    if not backend_ok:
        subprocess.Popen(
            ["cmd", "/k", str(vpy), "-u", "api/real_data_server_v2.py"],
            cwd=str(root), creationflags=0x10,
        )
        for _ in range(40):
            time.sleep(1)
            try:
                import urllib.request
                with urllib.request.urlopen(
                    "http://127.0.0.1:8000/api/v1/health", timeout=2
                ) as r:
                    if r.status == 200:
                        backend_ok = True
                        break
            except Exception:
                pass
    emit("backend", ok=backend_ok)
    print("   后台:", "就绪" if backend_ok else "未就绪，请看后台窗口报错")

    # ---- STEP 6 开实盘面板 ----
    print("\n===== STEP 6  打开实盘面板 =====")
    webbrowser.open("http://localhost:8000/?data_mode=live")
    emit("done", backend_ok=backend_ok, updated=updated, commit=new_commit)

    print("\n" + "=" * 64)
    print("  ALL DONE。面板应已打开；后台窗口可最小化、勿关闭。")
    print("=" * 64)
    input("按回车键关闭本窗口...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[致命错误] {e}")
        try:
            input("按回车键关闭...")
        except Exception:
            pass
