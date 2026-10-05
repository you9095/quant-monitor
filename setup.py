#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI量化监控系统 - 模拟盘环境安装脚本
由 deploy_all.bat 调用，不连接任何真实券商
"""

import os
import sys
import json
import shutil
import subprocess
import venv
from pathlib import Path

# Windows CMD 默认 GBK，需要设置 Python 输出编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk")
        sys.stderr.reconfigure(encoding="gbk")
    except Exception:
        pass


BASE_DIR = Path(__file__).parent
VENV_DIR = BASE_DIR / "venv"
CONFIG_DIR = BASE_DIR / "config"

# 全程日志落盘：即使黑窗口闪退，D:\quant-monitor\install_setup.log 也有完整错误
class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def reconfigure(self, **kw):
        for st in self._streams:
            try:
                st.reconfigure(**kw)
            except Exception:
                pass


try:
    import datetime as _dt
    _logf = open(BASE_DIR / "install_setup.log", "a", encoding="utf-8", errors="replace")
    _logf.write("\n\n===== setup.py run %s (v4) =====\n" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    sys.stdout = _Tee(sys.stdout, _logf)
    sys.stderr = _Tee(sys.stderr, _logf)
except Exception:
    _logf = None


# 连接自愈：SSH22 → SSH443(ssh.github.com) → HTTPS 三通道自动选择
sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    import github_connect as gh
except Exception as _e:
    gh = None
    print(f"[警告] 无法加载 github_connect 连接自愈模块: {_e}")

PACKAGES = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
    "flask>=2.0.0",
    "akshare>=1.12.0",
    "apscheduler>=3.10.0",
]

DEFAULT_CONFIG = {
    "mode": "simulation",
    "note": "模拟盘，不连接任何真实券商，所有买卖/对账单/盈亏均为模拟盘真实运行数据",
    "server": {"host": "0.0.0.0", "port": 8000},
    "strategies": {
        "qixing": {"enabled": True, "name": "七星策略", "initial_capital": 10000},
        "r32": {"enabled": True, "name": "三驾马车", "initial_capital": 10000},
        "zhuidian": {"enabled": True, "name": "追电策略", "initial_capital": 10000},
        "sanhe": {"enabled": True, "name": "三合策略", "initial_capital": 10000},
        "lightning": {"enabled": True, "name": "闪电策略", "initial_capital": 10000},
        "goldcombo": {"enabled": True, "name": "黄金组合A", "initial_capital": 10000},
    },
}


def step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")
    print("-" * 50)


def ok(msg):
    print(f"  [OK] {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def fail(msg):
    print(f"  [ERROR] {msg}")


def get_venv_python():
    """获取 venv 中的 python 路径"""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def get_venv_pip():
    """获取 venv 中的 pip 路径"""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def create_venv():
    """创建虚拟环境；已存在但损坏（python 无法运行）则删除重建。"""
    venv_python = get_venv_python()
    if venv_python.exists():
        # 验证现有 venv 是否真的可用，避免半安装的坏 venv 卡住后续
        probe = subprocess.run([str(venv_python), "--version"],
                               capture_output=True, text=True, timeout=30)
        if probe.returncode == 0:
            ok("虚拟环境已存在且可用，跳过创建")
            return True
        warn("检测到损坏的虚拟环境，删除后重建 ...")
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    print("  正在创建虚拟环境（约30秒）...")
    try:
        venv.create(str(VENV_DIR), with_pip=True)
        if venv_python.exists():
            ok("虚拟环境创建成功")
            return True
        else:
            fail("虚拟环境创建后未找到 python")
            return False
    except Exception as e:
        fail(f"虚拟环境创建失败: {e}")
        return False


def install_packages():
    """安装 Python 依赖；多镜像轮换 + 官方兜底，单镜像失败自动换下一个。"""
    venv_python = get_venv_python()
    venv_pip = get_venv_pip()

    # (镜像URL, trusted-host)，按国内速度排序；最后用官方源兜底
    mirrors = [
        ("https://pypi.tuna.tsinghua.edu.cn/simple", "pypi.tuna.tsinghua.edu.cn"),
        ("https://mirrors.aliyun.com/pypi/simple/", "mirrors.aliyun.com"),
        ("https://pypi.mirrors.ustc.edu.cn/simple/", "pypi.mirrors.ustc.edu.cn"),
        (None, None),  # 官方源
    ]
    common = ["--timeout", "60", "--retries", "3"]

    def pip(args, index=None, host=None):
        cmd = [str(venv_python), "-m", "pip"] + args + common
        if index:
            cmd += ["-i", index, "--trusted-host", host]
        return subprocess.run(cmd, capture_output=True, text=True)

    print("  正在升级 pip（多镜像自动轮换）...")
    for index, host in mirrors:
        if pip(["install", "--upgrade", "pip"], index, host).returncode == 0:
            break

    print(f"  开始安装 {len(PACKAGES)} 个依赖包，请耐心等待，勿关闭窗口 ...")
    print()

    failed = []
    for i, pkg in enumerate(PACKAGES, 1):
        print(f"  [{i}/{len(PACKAGES)}] 安装 {pkg} ...")
        ok_flag = False
        last_err = ""
        for index, host in mirrors:
            r = pip(["install", pkg], index, host)
            if r.returncode == 0:
                tag = "官方源" if not index else "镜像源"
                ok(f"{pkg} 安装成功（{tag}）")
                ok_flag = True
                break
            last_err = (r.stderr or r.stdout or "")[-200:]
        if not ok_flag:
            fail(f"{pkg} 安装失败：{last_err}")
            failed.append(pkg)
        print()

    if failed:
        warn(f"以下 {len(failed)} 个包安装失败: {', '.join(failed)}")
        warn("核心面板/引擎不依赖全部包，可稍后补装；akshare 仅影响每日行情")
        return False
    ok("全部依赖安装完成")
    return True


def create_config():
    """检查项目配置文件"""
    CONFIG_DIR.mkdir(exist_ok=True)
    config_path = CONFIG_DIR / "strategies.json"

    if config_path.exists():
        ok("策略配置文件就绪 (config/strategies.json)")
        return True

    warn("未找到 config/strategies.json，部署包可能不完整")
    return False


def verify():
    """验证安装结果。核心模块硬性检查（带超时）；akshare 为行情源，软验证不阻断。"""
    venv_python = get_venv_python()
    print("  正在验证依赖导入...")

    all_ok = True
    # 面板/引擎启动必需的核心模块
    for mod in ["pandas", "numpy", "yaml", "requests", "flask"]:
        try:
            r = subprocess.run(
                [str(venv_python), "-c", f"import {mod}; print('{mod} OK')"],
                capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                ok(mod)
            else:
                fail(f"{mod} 导入失败")
                all_ok = False
        except subprocess.TimeoutExpired:
            fail(f"{mod} 导入超时(60s)")
            all_ok = False

    # akshare 只是每日行情源，首次导入可能很慢，给 120s；任何结果都不阻断安装
    try:
        r = subprocess.run(
            [str(venv_python), "-c", "import akshare; print('akshare OK')"],
            capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            ok("akshare（行情源就绪）")
        else:
            warn("akshare 导入异常，但不影响安装；每日行情运行前会自动补装/重试")
    except subprocess.TimeoutExpired:
        warn("akshare 首次导入超时(120s)，不阻断安装（多为首次初始化慢，稍后重试即可）")
    return all_ok


def setup_git_auto_update():
    """步骤5: 关联 GitHub 仓库，启用自动更新 + 注册每日任务"""
    print("  检测 Git...")
    r = subprocess.run(["git", "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        warn("未检测到 Git。自动更新需先安装 Git for Windows:")
        print("     下载 https://git-scm.com/download/win 安装后重新运行本脚本")
        return False

    ok("Git 已就绪")

    # 配置 git 凭据管理器 / SSH443 自愈
    if gh:
        gh.configure_git()

    # 把当前目录关联到代码仓库（自动在 SSH22/SSH443/HTTPS 中选可用通道）
    if not (BASE_DIR / ".git").exists():
        print("  关联代码仓库（自动探测可用通道）...")
        subprocess.run(["git", "init"], cwd=str(BASE_DIR), capture_output=True)
        url, mode = (gh.best_url(gh.CODE_SSH, gh.CODE_HTTPS) if gh else (None, "none"))
        if url:
            subprocess.run(["git", "remote", "remove", "origin"],
                           cwd=str(BASE_DIR), capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", url],
                           cwd=str(BASE_DIR), capture_output=True)
            r = subprocess.run(["git", "fetch", "origin", "master"],
                               cwd=str(BASE_DIR), capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                subprocess.run(["git", "reset", "--hard", "origin/master"],
                               cwd=str(BASE_DIR), capture_output=True)
                ok(f"已关联代码仓库（{mode}），以后可自动更新")
            else:
                warn("代码仓库 fetch 失败")
        else:
            warn("代码仓库连接失败：SSH22/SSH443/HTTPS 三种通道均不通")

    # clone 数据仓库（三通道自愈）
    live_data = BASE_DIR / "live-data"
    if not (live_data / ".git").exists():
        print("  拉取实盘数据仓库（自动探测可用通道）...")
        mode = gh.clone_fallback(gh.DATA_SSH, gh.DATA_HTTPS, "live-data", BASE_DIR) if gh else None
        if mode:
            ok(f"实盘数据仓库就绪（{mode}）")
        else:
            warn("数据仓库连接失败：三种通道均不通，实盘数据暂无法回传")

    # ===== 计划任务（2026-10-04 改单段式，适配只在交易日 13:00-17:00 开机）=====
    venv_py = get_venv_python()
    task_base = f'"\\"{venv_py}\\" \\"{BASE_DIR / "daily_task.py"}\\""'

    is_admin = True
    if sys.platform == "win32":
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = True
    if not is_admin:
        warn("当前不是管理员权限，可能无法删除旧任务/注册开机任务！")
        print("     如下方任务迁移未完成，请关闭窗口后右键 install_v9.bat → 以管理员身份运行。")

    def sch(args, label):
        r = subprocess.run(["schtasks"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            ok(label)
        else:
            warn(f"{label} 失败: {r.stderr.strip()[:200]}")
        return r.returncode == 0

    # 先删除旧两段式任务（09:35 execute / 15:30 decide），"不存在"属正常
    for _old in ("QuantExecuteTask", "QuantDecideTask"):
        r = subprocess.run(["schtasks", "/delete", "/tn", _old, "/f"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            ok(f"已删除旧任务 {_old}")
        else:
            print(f"  旧任务 {_old} 不存在或无需删除")

    # 1) 开机即交易：登录后 3 分钟跑 trade（窗口 13:00-17:00，窗口外自行跳过）
    sch(["/create", "/tn", "QuantDailyTrade", "/tr", task_base + " trade",
         "/sc", "onlogon", "/delay", "0003:00", "/f"],
        "开机交易任务已注册：交易日开机后自动 决策+成交+上传")

    # 2) 下午兜底：工作日 15:10 再跑一次（引擎当日幂等，已成交则跳过）
    sch(["/create", "/tn", "QuantDailyTradePM", "/tr", task_base + " trade",
         "/sc", "weekly", "/d", "MON,TUE,WED,THU,FRI", "/st", "15:10", "/f"],
        "下午兜底任务已注册：工作日15:10确保收盘后成交一次（幂等）")

    # 3) 开机网络自检：登录后 1 分钟，只更新代码+自愈数据仓库+上报，不交易
    fix_cmd = f'"\\"{venv_py}\\" \\"{BASE_DIR / "scripts" / "fix_and_report.py"}\\""'
    sch(["/create", "/tn", "QuantBootCheck", "/tr", fix_cmd,
         "/sc", "onlogon", "/delay", "0001:00", "/f"],
        "开机自检已注册：登录后先自愈网络并上报，3分钟后交易任务再跑")

    # 回查：新任务必须齐全、旧任务必须消失
    if sys.platform == "win32":
        def _exists(t):
            return subprocess.run(["schtasks", "/query", "/tn", t],
                                  capture_output=True, text=True).returncode == 0
        new_ok = all(_exists(t) for t in
                     ("QuantDailyTrade", "QuantDailyTradePM", "QuantBootCheck"))
        old_gone = all(not _exists(t) for t in
                       ("QuantExecuteTask", "QuantDecideTask"))
        if new_ok and old_gone:
            ok("计划任务迁移完成：新任务齐全、旧 09:35/15:30 任务已删除")
        else:
            warn(f"计划任务迁移未完全生效（新任务齐全={new_ok}，旧任务已删={old_gone}）")
            print("     >>> 请右键 install_v9.bat → 以管理员身份运行，再跑一次。")


def step0_connect():
    """最优先：打通 GitHub（SSH22→SSH443→HTTPS 自愈），clone 数据仓库并立即上线报心跳。"""
    print("  正在连接 GitHub（自动尝试 SSH22 / SSH443 / HTTPS，可能需1-2分钟）...")
    if not gh:
        warn("连接自愈模块缺失，跳过联网步骤")
        return False
    gh.configure_git()
    mode = gh.clone_fallback(gh.DATA_SSH, gh.DATA_HTTPS, "live-data", BASE_DIR)
    if mode:
        ok(f"GitHub 已连通，数据仓库就绪（{mode}）")
        try:
            subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "report_deploy.py")],
                           cwd=str(BASE_DIR), capture_output=True, text=True, timeout=180)
            print("  已上报上线状态")
        except Exception:
            pass
        return True
    warn("GitHub 暂未连通（SSH22/SSH443/HTTPS 均失败）")
    print("     将先完成本地安装；开机自检任务会在网络恢复后自动重连并补报。")
    return False


def main():
    print("=" * 55)
    print("  AI量化监控系统 - 模拟盘环境安装  (setup v4)")
    print("  模式: 模拟盘（不连接任何真实券商）")
    print("=" * 55)
    print(f"  安装目录: {BASE_DIR}")
    print(f"  Python: {sys.version.split()[0]} ({sys.executable})")

    # 步骤0：最先打通 GitHub 连接（失败不阻断本地安装，开机后自动重试）
    print("\n[步骤 0/5] 连接 GitHub 并建立数据回传通道")
    try:
        step0_connect()
    except Exception as e:
        warn(f"连接步骤异常（不阻断本地安装）: {e}")

    total = 5

    # 步骤1: 创建虚拟环境（唯一硬依赖，失败才终止）
    step(1, total, "创建 Python 虚拟环境")
    try:
        venv_ok = create_venv()
    except Exception as e:
        venv_ok = False
        fail(f"创建虚拟环境异常: {e}")
    if not venv_ok:
        print("\n安装失败：无法创建虚拟环境，请检查 Python 是否正确安装")
        input("按回车键退出...")
        return 1

    # 步骤2: 安装依赖（失败不阻断，verify 会复核，缺包开机任务可补装）
    step(2, total, "安装 Python 依赖包")
    try:
        install_packages()
    except Exception as e:
        warn(f"依赖安装阶段异常（继续）: {e}")

    # 步骤3: 检查配置
    step(3, total, "检查项目配置文件")
    try:
        create_config()
    except Exception as e:
        warn(f"配置检查异常（继续）: {e}")

    # 步骤4: 验证（akshare 软验证，绝不卡死整个安装）
    step(4, total, "验证安装结果")
    try:
        verify()
    except Exception as e:
        warn(f"验证阶段异常（继续）: {e}")

    # 步骤5: 关联 GitHub + clone 数据仓库 + 注册每日任务（关键收尾，必须执行）
    step(5, total, "关联 GitHub（自动更新 + 每日定时运行上传）")
    try:
        setup_git_auto_update()
    except Exception as e:
        warn(f"关联/注册任务阶段异常: {e}")

    # 完成
    print("\n" + "=" * 55)
    print("  安装流程已走完")
    print("=" * 55)
    print()
    print("  下一步（双击即可，不用敲命令）:")
    print()
    print("    1. 双击 start.bat  启动监控面板")
    print("    2. 浏览器打开 http://localhost:8000")
    print()
    print("  自动化说明:")
    print("    每个交易日开机后自动 决策+成交+上传（窗口13:00-17:00），15:10 兜底")
    print("    macOS 端 push 新版本后，Windows 开机自动更新，无需再打包拷贝")
    print()
    print("  注意: 本系统为模拟盘，不连接任何真实券商")
    print("=" * 55)
    print()

    # 最终部署心跳（无论前面有无警告都尝试上报，让 macOS 端能看到结果）
    try:
        import subprocess as _sp
        print("正在上报部署状态到 GitHub ...")
        py = str(VENV_DIR / "Scripts" / "python.exe") if (VENV_DIR / "Scripts" / "python.exe").exists() else sys.executable
        r = _sp.run([py, str(BASE_DIR / "scripts" / "report_deploy.py")],
                    cwd=str(BASE_DIR), capture_output=True, text=True, timeout=180)
        print(r.stdout[-600:] if r.stdout else "")
        if r.returncode != 0:
            print(r.stderr[-400:] if r.stderr else "")
            warn("部署心跳上报失败（不影响本地运行，开机自检会补报）")
    except Exception as e:
        warn(f"部署心跳上报异常: {e}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 兜底：任何未预料的异常都打印出来并停住，绝不静默闪退
        import traceback
        print("\n[安装器异常] 安装过程中出现未预料的错误：")
        traceback.print_exc()
        print(f"\n错误摘要: {e}")
        input("按回车键退出（请把上方红色/英文错误反馈）...")
        sys.exit(1)
