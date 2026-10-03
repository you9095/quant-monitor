#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键修复 git 关联并上报部署状态（Windows 双击 fix_and_report.bat 调用）

处理三种常见部署残留：
  1. zip 部署导致代码目录不是 git 仓库 / remote 缺失 → 自动 init+关联+同步
  2. live-data 数据仓库没 clone 或 remote 错 → 自动 clone/修复
  3. 修复后上报心跳到数据仓库，macOS 端即可远程看到结果

全程打印 [OK]/[FAIL]，结束时把结果写入 fix_result.txt。
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = BASE_DIR / "live-data"
CODE_REPO = "git@github.com:you9095/quant-monitor.git"
DATA_REPO = "git@github.com:you9095/quant-monitor-live-data.git"

result = {"steps": [], "ok": True}


def log(ok, msg):
    tag = "[OK]  " if ok else "[FAIL]"
    line = f"{tag} {msg}"
    print(line, flush=True)
    result["steps"].append({"ok": ok, "msg": msg})
    if not ok:
        result["ok"] = False


def run(args, cwd, timeout=180):
    try:
        r = subprocess.run(args, cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def is_git_repo(path):
    ok, out = run(["git", "rev-parse", "--is-inside-work-tree"], path)
    return ok and "true" in out


def fix_code_repo():
    print("=== 1. 检查代码仓库 ===", flush=True)
    if not is_git_repo(BASE_DIR):
        log(True, "代码目录还不是 git 仓库，正在初始化关联...")
        run(["git", "init"], BASE_DIR)
        run(["git", "remote", "remove", "origin"], BASE_DIR)
        run(["git", "remote", "add", "origin", CODE_REPO], BASE_DIR)
    else:
        # 确保 remote 正确
        ok, url = run(["git", "remote", "get-url", "origin"], BASE_DIR)
        if not ok or "quant-monitor.git" not in url:
            run(["git", "remote", "remove", "origin"], BASE_DIR)
            run(["git", "remote", "add", "origin", CODE_REPO], BASE_DIR)
        log(True, "代码目录已是 git 仓库")

    ok, out = run(["git", "fetch", "origin", "master"], BASE_DIR, timeout=300)
    if not ok:
        log(False, f"拉取代码失败（检查 SSH）: {out[-200:]}")
        return
    run(["git", "checkout", "-B", "master"], BASE_DIR)
    ok, out = run(["git", "reset", "--hard", "origin/master"], BASE_DIR)
    log(ok, "代码已同步到 GitHub 最新版" if ok else f"代码同步失败: {out[-200:]}")


def fix_data_repo():
    print("=== 2. 检查数据仓库 live-data ===", flush=True)
    need_clone = (not LIVE_DIR.exists()) or (not is_git_repo(LIVE_DIR))
    if need_clone:
        if LIVE_DIR.exists():
            # 保留可能存在的本地数据，改名备份后 clone
            backup = LIVE_DIR.parent / f"live-data-backup-{datetime.now():%H%M%S}"
            try:
                LIVE_DIR.rename(backup)
                log(True, f"旧 live-data 已备份为 {backup.name}")
            except Exception:
                pass
        ok, out = run(["git", "clone", DATA_REPO, "live-data"], BASE_DIR, timeout=300)
        log(ok, "数据仓库已 clone 到 live-data/" if ok else f"数据仓库 clone 失败: {out[-200:]}")
    else:
        ok, url = run(["git", "remote", "get-url", "origin"], LIVE_DIR)
        if not ok or "quant-monitor-live-data" not in url:
            run(["git", "remote", "set-url", "origin", DATA_REPO], LIVE_DIR)
        okb, _ = run(["git", "pull", "origin", "master"], LIVE_DIR, timeout=180)
        log(okb, "数据仓库已存在并拉取最新" if okb else "数据仓库存在但 pull 失败（继续尝试上报）")


def report():
    print("=== 3. 上报部署状态 ===", flush=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import report_deploy
        rc = report_deploy.main()
        log(rc == 0, "部署状态已上报 GitHub" if rc == 0 else "上报失败（见上方日志）")
    except Exception as e:
        log(False, f"上报脚本异常: {e}")


def main():
    print("=" * 55, flush=True)
    print("  Fix git linkage and report deploy status", flush=True)
    print("=" * 55, flush=True)
    try:
        fix_code_repo()
        fix_data_repo()
        report()
    except Exception as e:
        log(False, f"修复过程异常: {e}")

    (BASE_DIR / "fix_result.txt").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 55, flush=True)
    print("  ALL DONE. Result written to fix_result.txt", flush=True)
    print("=" * 55, flush=True)


if __name__ == "__main__":
    main()
