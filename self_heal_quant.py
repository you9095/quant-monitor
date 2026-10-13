# -*- coding: utf-8 -*-
# ============================================================================
# Quant Monitor 强力自愈器（一次性，纯标准库，不依赖项目任何旧代码）
# 在"独立解锁器"基础上增加：
#   1) 枚举并杀掉所有卡住的项目 Python 进程（含后端、启动器、守护，自愈器自身除外），
#      彻底释放文件锁；
#   2) 删除本地锁文件；
#   3) 代码通道切公开 HTTPS -> 取回最新 -> 硬重置；
#   4) 把"进程枚举/杀了谁/锁/git 结果"写到数据仓库 _run_logs/self_heal.json 并 push；
#   5) 启动最新 launch_panel（自动起后端、补注册、开面板），等待 health 变绿；
#   6) 常驻结果框，不闪退。
# 用法：双击运行（无需管理员；普通权限即可杀当前用户自己的进程）。
# ============================================================================
import os, sys, time, subprocess, ctypes, traceback, json

REPO_HTTPS = "https://github.com/you9095/quant-monitor.git"
LOG = []
GIT = None
SELF_PID = os.getpid()
MARKERS = ("launch_panel.py", "real_data_server", "run_simulation.py",
           "trade_supervisor.py", "daily_task.py", "run_daily.py",
           "unlock_quant.py", "self_heal_quant")


def log(m):
    line = time.strftime("%H:%M:%S ") + str(m)
    LOG.append(line)
    print(line)


def find_git():
    for exe in ("git", "git.exe"):
        try:
            if subprocess.run([exe, "--version"], capture_output=True,
                              timeout=10).returncode == 0:
                return exe
        except Exception:
            pass
    for c in (r"C:\Program Files\Git\cmd\git.exe",
              r"C:\Program Files\Git\bin\git.exe",
              r"C:\Program Files (x86)\Git\cmd\git.exe",
              os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe")):
        if os.path.isfile(c):
            return c
    return None


def find_root():
    cands = []
    for drive in ("D:", "C:", "E:"):
        cands += [os.path.join(drive + os.sep, n) for n in
                  ("quant-monitor", "Quant Monitor", "quant_monitor")]
    cands.append(os.path.expanduser(r"~\quant-monitor"))
    out, seen = [], set()
    for r in cands:
        if os.path.isdir(os.path.join(r, ".git")):
            k = os.path.normcase(os.path.abspath(r))
            if k not in seen:
                seen.add(k)
                out.append(r)
    return out


def git(root, *args, timeout=180):
    p = subprocess.run([GIT] + list(args), cwd=root,
                       capture_output=True, text=True, timeout=timeout)
    if p.stdout:
        log("  > " + p.stdout.strip()[:300])
    if p.returncode != 0:
        log("  ! " + (p.stderr or p.stdout or "").strip()[:400])
    return p


def list_project_python(root):
    """枚举项目相关 python/pythonw 进程，返回 [(pid, cmdline)]（不含自愈器自己）。"""
    ps_script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='python.exe' OR Name='pythonw.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)||$($_.CommandLine)\" }"
    )
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                           capture_output=True, timeout=45)
        out = p.stdout.decode("utf-8", errors="ignore")
    except Exception as e:
        log("进程枚举失败: " + str(e)[:120])
        return []
    root_l = os.path.normcase(os.path.abspath(root)).lower()
    hits = []
    for line in out.splitlines():
        line = line.strip()
        if "||" not in line:
            continue
        pid_s, cmd = line.split("||", 1)
        try:
            pid = int(pid_s.strip())
        except Exception:
            continue
        if pid == SELF_PID:
            continue
        cl = cmd.lower().replace("/", os.sep)
        is_proj = (root_l in cl) or any(m in cl for m in MARKERS)
        if is_proj:
            hits.append((pid, cmd.strip()))
    return hits


def kill_them(hits):
    killed = []
    for pid, cmd in hits:
        r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, text=True, timeout=20)
        rec = {"pid": pid, "cmd": cmd[:160], "killed": r.returncode == 0,
               "msg": (r.stderr or r.stdout or "").strip()[:160]}
        killed.append(rec)
        log(("已杀 " if rec["killed"] else "杀失败 ") + str(pid) + "  " + cmd[:70])
    return killed


def clear_locks(root):
    removed = []
    for rel in ("logs/launch_panel.lock", "live-data/_run_logs/supervisor.lock"):
        fp = os.path.join(root, rel.replace("/", os.sep))
        try:
            if os.path.exists(fp):
                os.remove(fp)
                removed.append(fp)
                log("删锁 " + fp)
        except Exception as e:
            log("删锁失败 " + fp + ": " + str(e)[:80])
    return removed


def write_report(root, payload):
    d = os.path.join(root, "live-data", "_run_logs")
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "self_heal.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return fp


def push_report(root):
    live = os.path.join(root, "live-data")
    subprocess.run([GIT, "-C", live, "add", "-A"], capture_output=True, timeout=60)
    subprocess.run([GIT, "-C", live, "commit", "-m",
                    "self-heal report " + time.strftime("%Y-%m-%d %H:%M")],
                   capture_output=True, text=True, timeout=60)
    p = subprocess.run([GIT, "-C", live, "push", "origin", "master"],
                       capture_output=True, text=True, timeout=120)
    return p.returncode == 0, (p.stderr or p.stdout or "").strip()


def popup(title, msg):
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        r = tk.Tk()
        r.title(title)
        r.geometry("820x520")
        st = scrolledtext.ScrolledText(r, wrap=tk.WORD, font=("Consolas", 10))
        st.insert("1.0", msg)
        st.configure(state="disabled")
        st.pack(fill="both", expand=True)
        tk.Button(r, text="关闭", command=r.destroy).pack(pady=6)
        r.lift()
        r.attributes("-topmost", True)
        r.mainloop()
    except Exception:
        try:
            ctypes.windll.user32.MessageBoxW(0, msg[:1800], title, 0x40)
        except Exception:
            pass


def main():
    log("=== Quant 强力自愈器开始 ===")
    global GIT
    GIT = find_git()
    if not GIT:
        return popup("自愈失败", "未找到 git.exe。\n\n" + "\n".join(LOG))
    log("git = " + GIT)

    roots = find_root()
    if not roots:
        return popup("自愈失败", "未找到含 .git 的 quant-monitor 项目。\n\n" + "\n".join(LOG))
    root = roots[0]
    log("项目根 = " + root + (("  （另有: " + ", ".join(roots[1:]) + "）")
                              if len(roots) > 1 else ""))

    # 1) 枚举并杀掉卡住的项目进程（释放所有锁）
    hits = list_project_python(root)
    log("发现项目 Python 进程 %d 个（不含自愈器自己）" % len(hits))
    killed = kill_them(hits)
    time.sleep(2)

    # 2) 清理锁文件
    locks = clear_locks(root)

    # 3) 通道切公开 HTTPS、取回最新、硬重置
    git(root, "remote", "set-url", "origin", REPO_HTTPS)
    p = git(root, "fetch", "--force", REPO_HTTPS, "master")
    if p.returncode != 0:
        git(root, "fetch", "origin", "master")
    git(root, "reset", "--hard", "FETCH_HEAD")
    hp = subprocess.run([GIT, "-C", root, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True)
    head = hp.stdout.strip()
    log("当前版本 HEAD = " + head)

    # 4) 写自愈报告并 push（数据仓库凭据已缓存，独立 git 完成，不依赖后端）
    payload = {"report_time": time.strftime("%Y-%m-%d %H:%M:%S"),
               "head": head, "found_processes": len(hits),
               "killed": killed, "locks_removed": locks,
               "is_admin": bool(ctypes.windll.shell32.IsUserAnAdmin())}
    write_report(root, payload)
    ok_push, push_msg = push_report(root)
    log("自愈报告 push = " + str(ok_push) + "  " + push_msg[:120])

    # 5) 启动最新 launch_panel（自动起后端 / 补注册 / 开面板）
    venv_pyw = os.path.join(root, "venv", "Scripts", "pythonw.exe")
    launch = os.path.join(root, "scripts", "launch_panel.py")
    if os.path.isfile(venv_pyw) and os.path.isfile(launch):
        DETACHED = 0x00000008 | 0x00000200
        subprocess.Popen([venv_pyw, launch, "--open"], cwd=root,
                         creationflags=DETACHED, close_fds=True)
        log("已启动最新 launch_panel")
    else:
        log("未找到 venv pythonw 或 launch_panel，跳过自动启动")

    # 6) 等后端 health 变绿
    import urllib.request
    health = None
    for i in range(24):
        time.sleep(3)
        try:
            with urllib.request.urlopen(
                    "http://localhost:8000/api/v1/health", timeout=4) as r:
                health = r.read().decode()[:140]
            if '"status":"ok"' in health or '"code":0' in health:
                log("后端已就绪: " + health)
                break
        except Exception as e:
            if i % 5 == 0:
                log("等待后端启动... " + str(e)[:70])
    else:
        log("后端在限定时间内未就绪，可稍后双击桌面“AI量化面板”图标")

    # 7) 补最终报告并再 push
    payload["health"] = health
    payload["report_push_ok"] = ok_push
    write_report(root, payload)
    push_report(root)

    msg = ("结果：卡住进程已清理（发现 %d、已杀 %d）、锁 %d 个、代码更新到 %s\n"
           "自愈报告上传：%s\n后端：%s\n\n以后每个交易日只需双击桌面“AI量化面板”图标，"
           "15:10 自动按收盘价成交、失败进程内每 10 分钟重试到 17:00。\n\n日志：\n"
           % (len(hits), sum(1 for k in killed if k["killed"]),
              len(locks), head, ok_push, health or "启动中")) + "\n".join(LOG)
    try:
        rp = os.path.join(os.environ.get("TEMP", "."), "quant_self_heal_result.txt")
        open(rp, "w", encoding="utf-8").write(msg)
    except Exception:
        pass
    popup("Quant 强力自愈完成", msg)


if __name__ == "__main__":
    try:
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
        main()
    except Exception:
        popup("自愈器异常", traceback.format_exc())
