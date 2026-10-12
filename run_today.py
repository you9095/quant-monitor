#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 量化监控 —— Windows 一键修复 + 当日收盘价成交 + 启动面板
============================================================
双击本文件即可（.py 默认用 python.exe 控制台打开）。
若被 pythonw（无窗口）关联，本脚本会自动在一个新控制台窗口里重跑自己。

它会按顺序完成：
  1) 更新代码到最新   2) 检查依赖   3) 按今日真实收盘价成交（本机撮合，不接券商）
  4) 上传实盘数据到 GitHub
  5) 在独立窗口启动数据后台   6) 自动打开实盘面板
全程打印、结束暂停，绝不闪退。
"""
import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path


def locate_root() -> Path:
    """定位项目根：优先 D:\\quant-monitor；否则用脚本所在目录向上找含 daily_task.py 的目录。"""
    candidates = [Path(r"D:\quant-monitor"), Path(__file__).resolve().parent]
    for c in candidates:
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

    # 若无控制台（被 pythonw 静默打开），用 venv 的控制台 python 在新窗口重跑自己
    if not have_console():
        if not vpy.exists():
            # 兜底：用当前解释器（pythonw）找不到 venv 时无法弹窗，直接退出
            return
        CREATE_NEW_CONSOLE = 0x00000010
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [str(vpy), str(Path(__file__).resolve()), str(root)],
            creationflags=CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP,
            cwd=str(root),
        )
        return

    # 有控制台：切 UTF-8，避免中文乱码
    os.system("chcp 65001 >nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  AI Quant - One Click Fix and Trade (Simulation)")
    print(f"  工作目录 : {root}")
    print("  本机撮合，不连接任何真实券商账号")
    print("=" * 60)

    if not vpy.exists():
        print(f"[错误] 未找到虚拟环境解释器: {vpy}")
        print("请确认项目位于 D:\\quant-monitor，或重新运行安装器。")
        input("按回车键关闭...")
        return

    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def step(title, cmd):
        print(f"\n===== {title} =====")
        r = subprocess.run(cmd, cwd=str(root), env=env)
        if r.returncode != 0:
            print(f"[警告] 本步骤返回码 = {r.returncode}（请留意上方信息）")
        return r.returncode

    # 1) 更新代码
    step("STEP 1/6  更新代码", ["git", "fetch", "origin", "master"])
    step("STEP 1/6  对齐最新版本", ["git", "reset", "--hard", "origin/master"])

    # 2) 依赖
    step("STEP 2/6  检查依赖", [
        str(vpy), "-m", "pip", "install", "-q", "-r", "requirements.txt",
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
    ])

    # 3) 收盘价成交
    step("STEP 3/6  按今日真实收盘价成交（不接券商）",
         [str(vpy), "trade_supervisor.py", "--guard"])

    # 4) 上传
    step("STEP 4/6  上传实盘数据到 GitHub",
         [str(vpy), "scripts/sync_live_data.py", "push"])

    # 5) 启动后台（独立控制台窗口）
    print("\n===== STEP 5/6  启动数据后台（新窗口，请勿关闭） =====")
    CREATE_NEW_CONSOLE = 0x00000010
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        [str(vpy), "api/real_data_server_v2.py"],
        cwd=str(root), env=env,
        creationflags=CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP,
    )
    print("后台启动中，等待就绪...")
    ok = False
    for _ in range(20):
        time.sleep(1)
        try:
            import urllib.request
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/api/v1/health", timeout=2
            ) as r:
                if r.status == 200:
                    ok = True
                    break
        except Exception:
            pass
    print("后台健康检查:", "通过" if ok else "未就绪（请查看新弹出的后台窗口报错）")

    # 6) 打开实盘面板
    print("\n===== STEP 6/6  打开实盘面板 =====")
    webbrowser.open("http://localhost:8000/?data_mode=live")

    print("\n" + "=" * 60)
    print("  ALL DONE - 面板应已在浏览器打开。")
    print("  若后台窗口有红色报错，请勿关闭该窗口。")
    print("=" * 60)
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
