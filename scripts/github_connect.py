#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 连接自愈模块（Windows 一键安装 / 每日任务共用）

国内网络连 GitHub 常见三道坎，本模块按"国内最可靠优先"自动尝试、选第一条通的：
  1. SSH over 443 （ssh.github.com:443，绕过 22 端口封锁与 HTTPS 重置，首选）
  2. SSH over 22 （标准端口，常被阻断）
  3. HTTPS over 443（Git Credential Manager 首次弹一次浏览器登录，之后永久缓存）

纯标准库，无第三方依赖。任何 git 失败都返回 (False, 报错文本)，不抛异常。
"""
import os
import sys
import subprocess
from pathlib import Path

CODE_SSH = "git@github.com:you9095/quant-monitor.git"
CODE_HTTPS = "https://github.com/you9095/quant-monitor.git"
DATA_SSH = "git@github.com:you9095/quant-monitor-live-data.git"
DATA_HTTPS = "https://github.com/you9095/quant-monitor-live-data.git"

_SSH443_BLOCK = (
    "Host github.com\n"
    "\tHostName ssh.github.com\n"
    "\tPort 443\n"
    "\tUser git\n"
)


def log(msg):
    print(msg, flush=True)


def run(args, cwd=None, timeout=60, env=None):
    """执行命令，返回 (ok, 合并输出)。永不抛异常。"""
    try:
        r = subprocess.run(args, cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return False, "git 命令不存在（未安装 Git for Windows）"
    except subprocess.TimeoutExpired:
        return False, f"命令超时({timeout}s): {' '.join(args[:3])}"
    except Exception as e:
        return False, f"命令异常: {e}"


def _ssh_env():
    """SSH(22) 专用环境：自动信任主机指纹、禁用交互卡死、15s 连接超时。"""
    env = dict(os.environ)
    env["GIT_SSH_COMMAND"] = (
        "ssh -o StrictHostKeyChecking=accept-new "
        "-o BatchMode=yes -o ConnectTimeout=15"
    )
    return env


def _ssh443_env():
    """SSH over 443 专用环境：显式连 ssh.github.com:443（国内首选，最可靠）。"""
    env = dict(os.environ)
    env["GIT_SSH_COMMAND"] = (
        "ssh -p 443 -o HostName=ssh.github.com "
        "-o StrictHostKeyChecking=accept-new "
        "-o BatchMode=yes -o ConnectTimeout=20"
    )
    return env


def configure_git():
    """配置凭据管理器（HTTPS 首次弹窗授权后永久缓存）。跨平台幂等。"""
    if sys.platform == "win32":
        run(["git", "config", "--global", "credential.helper", "manager"])
    elif sys.platform == "darwin":
        run(["git", "config", "--global", "credential.helper", "osxkeychain"])
    run(["git", "config", "--global", "http.version", "HTTP/1.1"])
    run(["git", "config", "--global", "http.postBuffer", "524288000"])
    # 提交身份：全新 Git 若缺失会导致 commit 失败、心跳 push 不上来
    ok_name, _ = run(["git", "config", "--global", "--get", "user.name"])
    if not ok_name:
        run(["git", "config", "--global", "user.name", "quant-windows"])
    ok_email, _ = run(["git", "config", "--global", "--get", "user.email"])
    if not ok_email:
        run(["git", "config", "--global", "user.email", "quant@local"])


def _ssh_config_path():
    return Path.home() / ".ssh" / "config"


def enable_ssh_over_443():
    """在 ~/.ssh/config 写入 github.com 走 ssh.github.com:443（幂等）。"""
    cfg = _ssh_config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    existing = cfg.read_text(encoding="utf-8", errors="ignore") if cfg.exists() else ""
    if "ssh.github.com" in existing:
        return
    with cfg.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n# Added by AI Quant installer: route GitHub SSH over port 443\n")
        f.write(_SSH443_BLOCK)


def _probe(url, env=None, timeout=45):
    """用 ls-remote 轻量探测某 URL 是否可读（私有仓库也能验证权限）。"""
    ok, _ = run(["git", "ls-remote", url, "HEAD"], timeout=timeout, env=env)
    return ok


def best_url(ssh_url, https_url, verbose=True):
    """依次探测 SSH443 → SSH22 → HTTPS，返回 (可用URL, 模式名) 或 (None, 'none')。

    副作用：自动写好 ssh 443 配置、git 凭据管理器。
    HTTPS 首次会弹 GitHub 登录窗，给 240s 让用户完成授权。
    """
    def p(m):
        if verbose:
            log(m)

    # 1) SSH over 443（国内首选，显式指定 ssh.github.com:443，不依赖隐式配置）
    enable_ssh_over_443()
    p("  探测 GitHub SSH over 443 (ssh.github.com:443，国内首选) ...")
    if _probe(ssh_url, env=_ssh443_env(), timeout=30):
        p("  [通] SSH 端口443 可用")
        return ssh_url, "ssh443"

    # 2) SSH over 22
    p("  SSH443 不通，尝试 SSH 端口22 ...")
    if _probe(ssh_url, env=_ssh_env(), timeout=25):
        p("  [通] SSH 端口22 可用")
        return ssh_url, "ssh22"

    # 3) HTTPS（可能弹登录窗，给足时间）
    p("  SSH 均不通，改用 HTTPS。若弹出 GitHub 登录/授权窗口，请在浏览器完成一次登录 ...")
    configure_git()
    if _probe(https_url, env=None, timeout=240):
        p("  [通] HTTPS 可用")
        return https_url, "https"

    p("  [失败] SSH443 / SSH22 / HTTPS 三种方式均无法连接 GitHub")
    return None, "none"


def clone_fallback(ssh_url, https_url, dir_name, cwd, verbose=True, timeout=600):
    """把仓库克隆到 cwd/dir_name；已存在且是 git 仓库则跳过。

    返回模式名 'ssh22'/'ssh443'/'https'/'existing'，失败返回 None。
    """
    cwd = Path(cwd)
    target = cwd / dir_name
    if (target / ".git").exists():
        if verbose:
            log(f"  {dir_name} 已存在，跳过克隆")
        return "existing"

    url, mode = best_url(ssh_url, https_url, verbose=verbose)
    if not url:
        return None
    if target.exists():
        # 非 git 的同名目录，备份而不是删除
        backup = cwd / f"{dir_name}-old"
        i = 1
        while backup.exists():
            backup = cwd / f"{dir_name}-old{i}"
            i += 1
        try:
            target.rename(backup)
            if verbose:
                log(f"  旧目录已备份为 {backup.name}")
        except Exception as e:
            log(f"  无法备份旧目录 {target}: {e}")
    if url.startswith("git@"):
        env = _ssh443_env() if mode == "ssh443" else _ssh_env()
    else:
        env = None
    ok, out = run(["git", "clone", url, dir_name], cwd=cwd, timeout=timeout, env=env)
    if ok:
        if verbose:
            log(f"  [通] 已克隆 {dir_name}（{mode}）")
        return mode
    if target.exists():
        import shutil
        shutil.rmtree(target, ignore_errors=True)
    log(f"  [失败] 克隆 {dir_name} 出错: {out[-300:]}")
    return None


def hard_update(repo_dir, timeout=300):
    """对已克隆的代码仓库强制同步到远程 master（自动更新）。SSH443 优先，22 回退。"""
    repo_dir = Path(repo_dir)
    if not (repo_dir / ".git").exists():
        return False, "not a git repo"
    enable_ssh_over_443()
    ok, out = run(["git", "fetch", "origin", "master"], cwd=repo_dir, timeout=timeout, env=_ssh443_env())
    if not ok:
        ok, out = run(["git", "fetch", "origin", "master"], cwd=repo_dir, timeout=timeout, env=_ssh_env())
    if not ok:
        return False, out
    return run(["git", "reset", "--hard", "origin/master"], cwd=repo_dir, timeout=60)


if __name__ == "__main__":
    # 自测：探测当前机器到两个仓库的连接
    print("=== GitHub 连接自测 ===")
    configure_git()
    u1, m1 = best_url(CODE_SSH, CODE_HTTPS)
    print(f"代码仓库: {m1}  {u1 or ''}")
    u2, m2 = best_url(DATA_SSH, DATA_HTTPS)
    print(f"数据仓库: {m2}  {u2 or ''}")
    sys.exit(0 if (u1 and u2) else 1)
