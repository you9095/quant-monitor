#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 拉取后远程确认（在 macOS 端运行）。
=====================================================
当 Windows 双击桌面"AI量化面板"图标、自动更新并上报心跳后，在 Mac 上跑本脚本，
自动完成以下核对并给出 PASS/FAIL，不需要临时拼命令：

  1. 拉取数据仓库最新心跳；
  2. 确认 Windows 心跳里的 code_commit 与 Mac 当前代码版本一致（即已自动更新到最新）；
  3. 确认心跳是"刚刚"上报的（新鲜度，默认 10 分钟内，可用 --fresh-min 改）；
  4. 确认虚拟环境、关键依赖、live-data 仓库、计划任务（QuantTradeGuard / QuantPanelGuard）；
  5. 确认旧两段式任务已删除；
  6. 读取六策略账本，确认能正常解析、且与数据仓库一致。

用法：
  python3 scripts/verify_windows_sync.py            # 正常核对
  python3 scripts/verify_windows_sync.py --fresh-min 5
退出码：0 = 全部 PASS；1 = 有 FAIL；2 = 环境/读取问题。
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "live-data"
SIX = ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]
REQUIRED_TASKS = ["QuantTradeGuard", "QuantPanelGuard", "QuantWakeResume"]
REQUIRED_DEPS = ["flask", "akshare", "pandas", "numpy", "requests"]


def run(cmd, cwd, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as exc:
        return -1, str(exc)


def latest_windows_heartbeat():
    """返回 (文件名, 状态dict)，取 win32 中 report_time 最新的。"""
    hb_dir = LIVE / "_deploy_status"
    if not hb_dir.exists():
        return None
    best = None
    for f in hb_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("platform") != "win32":
            continue
        if best is None or d.get("report_time", "") > best[1].get("report_time", ""):
            best = (f.name, d)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh-min", type=int, default=10,
                    help="心跳新鲜度阈值（分钟），默认 10")
    args = ap.parse_args()

    results = []  # (PASS/FAIL, 项, 说明)

    def check(name, ok, detail=""):
        results.append(("PASS" if ok else "FAIL", name, detail))

    # 0. 环境检查
    if not LIVE.exists():
        print("[错误] live-data 目录不存在，无法远程确认。")
        return 2

    # 1. 拉数据仓库最新
    rc, out = run(["git", "pull", "origin", "master"], LIVE)
    check("拉取数据仓库最新", rc == 0, "Already up to date 或已更新" if rc == 0 else out)

    # 2. 期望代码版本 = Mac 当前 HEAD
    rc, exp_code = run(["git", "rev-parse", "--short", "HEAD"], ROOT)
    if rc != 0:
        print("[错误] 无法读取 Mac 当前代码版本。")
        return 2
    exp_code = exp_code.strip()

    # 3. 读取 Windows 心跳
    hb = latest_windows_heartbeat()
    check("存在 Windows 心跳", hb is not None,
          hb[0] if hb else "_deploy_status 下无 win32 心跳")
    if not hb:
        report(results, exp_code, None)
        return 1
    fname, st = hb

    # 4. 代码版本一致
    win_code = st.get("code_commit", "?")
    check("Windows 已更新到最新代码", win_code == exp_code,
          f"Windows={win_code}，期望={exp_code}")

    # 5. 心跳新鲜度
    try:
        rt = datetime.fromisoformat(st.get("report_time", ""))
        age = (datetime.now() - rt).total_seconds() / 60.0
        check("心跳为刚上报（%d 分钟内）" % args.fresh_min,
              age <= args.fresh_min, f"{age:.1f} 分钟前 @ {st.get('report_time')}")
    except Exception:
        check("心跳为刚上报（%d 分钟内）" % args.fresh_min, False,
              f"report_time 无法解析: {st.get('report_time')}")

    # 6. 虚拟环境
    check("Windows 虚拟环境存在", st.get("venv_exists") is True,
          "venv_exists=true" if st.get("venv_exists") else "venv_exists=false")

    # 7. 关键依赖
    deps = st.get("dependencies", {})
    missing = [m for m in REQUIRED_DEPS if deps.get(m, "MISSING") == "MISSING"]
    check("关键依赖齐全", not missing,
          "全部正常" if not missing else f"缺失: {missing}")

    # 8. live-data 仓库
    check("live-data 为 Git 仓库", st.get("live_data_is_repo") is True,
          st.get("live_data_remote", ""))

    # 9. 计划任务
    tasks = st.get("tasks_all_Quant", [])
    if isinstance(tasks, str):
        tasks = []
    miss_tasks = [t for t in REQUIRED_TASKS if t not in tasks]
    check("计划任务齐全（QuantTradeGuard/QuantPanelGuard）",
          not miss_tasks, f"现有: {sorted(tasks)}" if not miss_tasks
          else f"缺少: {miss_tasks}")

    # 10. 旧任务已删除
    legacy_bad = [k for k, v in st.items()
                  if k.startswith("legacy_") and v != "MISSING"]
    check("旧两段式任务已删除", not legacy_bad,
          "旧任务均 MISSING" if not legacy_bad else f"残留: {legacy_bad}")

    # 11. 六策略账本可解析
    acc_dir = LIVE / "_account_state"
    parsed = {}
    for sid in SIX:
        p = acc_dir / f"{sid}.json"
        if not p.exists():
            check(f"账本 {sid}", False, "文件不存在")
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            parsed[sid] = d
            check(f"账本 {sid}", True,
                  f"现金 {round(float(d.get('cash', 0)), 2)}，"
                  f"持仓 {len(d.get('positions', {}))}，"
                  f"成交 {len(d.get('trades', []))}")
        except Exception as exc:
            check(f"账本 {sid}", False, f"解析失败: {exc}")

    # 12. 数据仓库无未推送（本地与远程一致）
    rc, local = run(["git", "rev-parse", "HEAD"], LIVE)
    rc2, remote = run(["git", "rev-parse", "origin/master"], LIVE)
    check("数据本地与远程一致",
          local.strip() == remote.strip(),
          f"{local.strip()[:7]} == {remote.strip()[:7]}")

    report(results, exp_code, st)
    return 0 if all(s == "PASS" for s, _, _ in results) else 1


def report(results, exp_code, st):
    print("\n" + "=" * 60)
    print(" Windows 远程确认结果（期望代码版本 %s）" % exp_code)
    print("=" * 60)
    if st:
        print("主机: %s | 平台: %s | 上报时间: %s" % (
            st.get("hostname"), st.get("platform"), st.get("report_time")))
        print("代码版本: %s | Python: %s" % (
            st.get("code_commit"), st.get("python")))
        print("-" * 60)
    for status, name, detail in results:
        mark = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"{mark} {name}")
        if detail:
            print(f"       {detail}")
    print("=" * 60)
    fails = [n for s, n, _ in results if s == "FAIL"]
    if not fails:
        print("结论: 全部通过，Windows 已自动拉取最新版并正常同步。")
    else:
        print(f"结论: {len(fails)} 项未通过 -> {fails}")


if __name__ == "__main__":
    sys.exit(main())
