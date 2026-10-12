# -*- coding: utf-8 -*-
# ============================================================================
# Quant Monitor 独立解锁器（一次性，纯标准库，不依赖项目任何旧代码）
# 作用：把"代码仓库"通道从被封的 SSH(22) 切到公开匿名的 HTTPS(443)，
#       自动取回最新版 -> 交给最新 launch_panel 补注册 / 起后端 / 开面板。
# 用法：下载本文件到 Windows，双击运行；结束会弹出常驻结果框（不闪退）。
# ============================================================================
import os, sys, time, subprocess, ctypes, traceback

REPO_HTTPS = "https://github.com/you9095/quant-monitor.git"
LOG = []
GIT = None


def log(m):
    line = time.strftime("%H:%M:%S ") + str(m)
    LOG.append(line)
    print(line)


def find_git():
    for exe in ("git", "git.exe"):
        try:
            p = subprocess.run([exe, "--version"], capture_output=True, timeout=10)
            if p.returncode == 0:
                return exe
        except Exception:
            pass
    cands = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def find_root():
    cands = []
    for drive in ("D:", "C:", "E:"):
        base = drive + os.sep
        cands += [os.path.join(base, "quant-monitor"),
                  os.path.join(base, "Quant Monitor"),
                  os.path.join(base, "quant_monitor")]
    cands.append(os.path.expanduser(r"~\quant-monitor"))
    found, seen, out = [], set(), []
    for r in cands:
        if os.path.isdir(os.path.join(r, ".git")):
            found.append(r)
    for r in found:
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


def popup(title, msg):
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        r = tk.Tk()
        r.title(title)
        r.geometry("760x480")
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
    log("=== Quant 解锁器开始 ===")
    global GIT
    GIT = find_git()
    if not GIT:
        return popup("解锁失败", "未找到 git.exe，请确认已安装 Git for Windows。\n\n" + "\n".join(LOG))
    log("git = " + GIT)

    roots = find_root()
    if not roots:
        return popup("解锁失败", "未在 D: / C: / E: 找到含 .git 的 quant-monitor 项目。\n\n" + "\n".join(LOG))
    root = roots[0]
    extra = ("  （另有: " + ", ".join(roots[1:]) + "）") if len(roots) > 1 else ""
    log("项目根 = " + root + extra)

    # 1) 代码仓库 remote 切到公开 HTTPS
    git(root, "remote", "set-url", "origin", REPO_HTTPS)
    # 2) 显式 HTTPS 公开匿名 fetch（绕过任何 SSH 配置 / 22 端口）
    p = git(root, "fetch", "--force", REPO_HTTPS, "master")
    if p.returncode != 0:
        p = git(root, "fetch", "origin", "master")
    if p.returncode != 0:
        return popup("解锁失败：无法从 GitHub 取代码",
                     "请确认 Windows 能打开 github.com（可先用浏览器访问测试），然后重跑本解锁器。\n\n" + "\n".join(LOG))
    # 3) 硬重置到刚取回的最新版
    git(root, "reset", "--hard", "FETCH_HEAD")

    hp = subprocess.run([GIT, "-C", root, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True)
    head = hp.stdout.strip()
    log("当前版本 HEAD = " + head)
    datajs = os.path.join(root, "assets", "data.js")
    ok_new = False
    try:
        ok_new = ("_fetchOnce" in open(datajs, encoding="utf-8", errors="ignore").read())
    except Exception:
        pass
    log("新版取数(重试)逻辑存在 = " + str(ok_new))

    # 4) 交给最新 launch_panel：补注册(QuantTradeGuard) / 起后端 / 开面板
    venv_pyw = os.path.join(root, "venv", "Scripts", "pythonw.exe")
    launch = os.path.join(root, "scripts", "launch_panel.py")
    if os.path.isfile(venv_pyw) and os.path.isfile(launch):
        DETACHED = 0x00000008 | 0x00000200
        subprocess.Popen([venv_pyw, launch, "--open"], cwd=root,
                         creationflags=DETACHED, close_fds=True)
        log("已启动最新 launch_panel（自动补注册 / 起后端 / 开面板）")
    else:
        log("未找到 venv/Scripts/pythonw.exe 或 launch_panel.py，跳过自动启动")

    # 5) 等后端 health 变绿（最多约 60 秒）
    import urllib.request
    health = None
    for i in range(20):
        time.sleep(3)
        try:
            with urllib.request.urlopen("http://localhost:8000/api/v1/health", timeout=4) as r:
                health = r.read().decode()[:140]
            if ('"status":"ok"' in health) or ('"code":0' in health) or ('"code": 0' in health):
                log("后端已就绪: " + health)
                break
        except Exception as e:
            if i % 4 == 0:
                log("等待后端启动... " + str(e)[:80])
    else:
        log("后端在限定时间内未就绪（launch_panel 可能仍在更新，稍后双击桌面“AI量化面板”即可）")

    msg = ("结果：代码已更新到 %s\n新版取数(重试)逻辑：%s\n后端：%s\n\n"
           "通道已切到 HTTPS(443)。若浏览器没自动开面板，双击桌面“AI量化面板”图标即可；"
           "以后每个交易日只需双击该图标，全自动更新 / 成交 / 上传。\n\n日志：\n"
           % (head, ok_new, health or "启动中")) + "\n".join(LOG)
    try:
        lp = os.path.join(os.environ.get("TEMP", "."), "quant_unlock_result.txt")
        open(lp, "w", encoding="utf-8").write(msg)
    except Exception:
        pass
    popup("Quant 解锁完成", msg)


if __name__ == "__main__":
    try:
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
        main()
    except Exception:
        popup("解锁器异常", traceback.format_exc())
