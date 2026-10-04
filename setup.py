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
    """创建虚拟环境"""
    venv_python = get_venv_python()
    if venv_python.exists():
        ok("虚拟环境已存在，跳过创建")
        return True

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
    """安装 Python 依赖"""
    venv_python = get_venv_python()
    venv_pip = get_venv_pip()

    # 国内镜像源（清华），大幅加快下载速度
    mirror = ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]

    print("  正在升级 pip...")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"] + mirror,
        shell=False
    )

    print(f"  开始安装 {len(PACKAGES)} 个依赖包（显示下载进度，请耐心等待）...")
    print("  如果某个包下载慢，会自动继续，请勿关闭窗口")
    print()

    # 逐个安装，实时显示进度，失败不影响其他包
    failed = []
    for i, pkg in enumerate(PACKAGES, 1):
        print(f"  [{i}/{len(PACKAGES)}] 安装 {pkg} ...")
        r = subprocess.run(
            [str(venv_pip), "install", pkg] + mirror,
            capture_output=True, text=True
        )
        if r.returncode == 0:
            ok(f"{pkg} 安装成功")
        else:
            # 清华源失败则尝试官方源
            print(f"       清华源失败，尝试官方源...")
            r2 = subprocess.run(
                [str(venv_pip), "install", pkg],
                capture_output=True, text=True
            )
            if r2.returncode == 0:
                ok(f"{pkg} 安装成功（官方源）")
            else:
                fail(f"{pkg} 安装失败")
                failed.append(pkg)
        print()

    if failed:
        warn(f"以下 {len(failed)} 个包安装失败: {', '.join(failed)}")
        warn("不影响核心功能，可稍后在 start.bat 报错时再补装")
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
    """验证安装结果"""
    venv_python = get_venv_python()
    print("  正在验证依赖导入...")

    check_modules = ["pandas", "numpy", "yaml", "requests", "flask", "akshare"]
    all_ok = True
    for mod in check_modules:
        r = subprocess.run(
            [str(venv_python), "-c", f"import {mod}; print('{mod} OK')"],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            ok(f"{mod}")
        else:
            fail(f"{mod} 导入失败")
            all_ok = False

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

    # 注册 Windows 计划任务：两段式
    #   工作日 09:35 execute：开盘后按昨日信号真实成交
    #   工作日 15:30 decide：收盘后更新代码+算今日信号+上传数据+重启面板
    venv_py = get_venv_python()
    task_base = f'"\\"{venv_py}\\" \\"{BASE_DIR / "daily_task.py"}\\""'

    print("  注册开盘执行任务（工作日 09:35）...")
    r1 = subprocess.run(
        ["schtasks", "/create", "/tn", "QuantExecuteTask", "/tr",
         task_base + " execute",
         "/sc", "weekly", "/d", "MON,TUE,WED,THU,FRI", "/st", "09:35", "/f"],
        capture_output=True, text=True)
    if r1.returncode == 0:
        ok("开盘任务已注册：工作日 09:35 自动按昨日信号真实成交")
    else:
        warn(f"开盘任务注册失败: {r1.stderr.strip()}")

    print("  注册收盘决策任务（工作日 15:30）...")
    r2 = subprocess.run(
        ["schtasks", "/create", "/tn", "QuantDecideTask", "/tr",
         task_base + " decide",
         "/sc", "weekly", "/d", "MON,TUE,WED,THU,FRI", "/st", "15:30", "/f"],
        capture_output=True, text=True)
    if r2.returncode == 0:
        ok("收盘任务已注册：工作日 15:30 自动 更新代码+算信号+上传+重启面板")
    else:
        warn(f"收盘任务注册失败: {r2.stderr.strip()}")

    # 开机自检：登录 Windows 2 分钟后自动更新代码+确保数据仓库+上报心跳（不交易）
    fix_cmd = f'"\\"{venv_py}\\" \\"{BASE_DIR / "scripts" / "fix_and_report.py"}\\""'
    print("  注册开机自检任务（登录后2分钟）...")
    r3 = subprocess.run(
        ["schtasks", "/create", "/tn", "QuantBootCheck", "/tr", fix_cmd,
         "/sc", "onlogon", "/delay", "0002:00", "/f"],
        capture_output=True, text=True)
    if r3.returncode == 0:
        ok("开机自检已注册：每次开机登录后自动更新并上报状态")
    else:
        warn(f"开机自检注册失败: {r3.stderr.strip()}")


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
    print("  AI量化监控系统 - 模拟盘环境安装")
    print("  模式: 模拟盘（不连接任何真实券商）")
    print("=" * 55)
    print(f"  安装目录: {BASE_DIR}")
    print(f"  Python: {sys.version.split()[0]} ({sys.executable})")

    # 步骤0：最先打通 GitHub 连接（失败不阻断本地安装，开机后自动重试）
    print("\n[步骤 0/5] 连接 GitHub 并建立数据回传通道")
    step0_connect()

    total = 5

    # 步骤1: 创建虚拟环境
    step(1, total, "创建 Python 虚拟环境")
    if not create_venv():
        print("\n安装失败，请检查 Python 是否正确安装")
        input("按回车键退出...")
        return 1

    # 步骤2: 安装依赖
    step(2, total, "安装 Python 依赖包")
    install_packages()

    # 步骤3: 检查配置
    step(3, total, "检查项目配置文件")
    create_config()

    # 步骤4: 验证
    step(4, total, "验证安装结果")
    verify()

    # 步骤5: 关联 GitHub 自动更新 + 注册每日任务
    step(5, total, "关联 GitHub（自动更新 + 每日 15:30 自动运行上传）")
    setup_git_auto_update()

    # 完成
    print("\n" + "=" * 55)
    print("  安装完成")
    print("=" * 55)
    print()
    print("  下一步（双击即可，不用敲命令）:")
    print()
    print("    1. 双击 start.bat  启动监控面板")
    print("    2. 浏览器打开 http://localhost:8000")
    print()
    print("  自动化说明:")
    print("    每个工作日 15:30 自动：拉最新代码→跑实盘→上传GitHub→重启")
    print("    macOS 端 push 新版本后，第二天 Windows 自动更新，无需再打包拷贝")
    print()
    print("  注意: 本系统为模拟盘，不连接任何真实券商")
    print("=" * 55)
    print()

    # 部署心跳上报：让 macOS 端能远程判断 Windows 是否部署成功
    try:
        import subprocess as _sp
        print("正在上报部署状态到 GitHub ...")
        py = str(VENV_DIR / "Scripts" / "python.exe") if (VENV_DIR / "Scripts" / "python.exe").exists() else sys.executable
        r = _sp.run([py, str(BASE_DIR / "scripts" / "report_deploy.py")],
                    cwd=str(BASE_DIR), capture_output=True, text=True, timeout=180)
        print(r.stdout[-600:] if r.stdout else "")
        if r.returncode != 0:
            print(r.stderr[-400:] if r.stderr else "")
            warn("部署心跳上报失败（不影响本地运行，可稍后手动跑 scripts/report_deploy.py）")
    except Exception as e:
        warn(f"部署心跳上报异常: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
