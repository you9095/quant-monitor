#!/usr/bin/env python3
"""
AI量化监控系统 - 环境检测脚本
模拟盘模式，不连接任何真实券商
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Windows CMD 默认 GBK
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk")
        sys.stderr.reconfigure(encoding="gbk")
    except Exception:
        pass


def print_step(step, msg):
    print(f"\n{'='*60}")
    print(f"[STEP {step}] {msg}")
    print(f"{'='*60}")


def print_ok(msg):
    print(f"  [OK] {msg}")


def print_warn(msg):
    print(f"  [WARN] {msg}")


def print_error(msg):
    print(f"  [ERROR] {msg}")


def test_python():
    """测试 Python 环境"""
    print_step(1, "Python 环境检测")
    print_ok(f"Python {sys.version.split()[0]}")
    print_ok(f"路径: {sys.executable}")

    if sys.version_info < (3, 9):
        print_error("Python 版本过低，需要 3.9 以上")
        return False
    return True


def test_dependencies():
    """测试依赖包"""
    print_step(2, "Python 依赖检测")
    required = {
        'pandas': 'pandas',
        'numpy': 'numpy',
        'yaml': 'pyyaml',
        'requests': 'requests',
        'flask': 'flask',
        'akshare': 'akshare',
        'apscheduler': 'apscheduler',
    }

    all_ok = True
    for module, package in required.items():
        try:
            __import__(module)
            print_ok(f"{package} 已安装")
        except ImportError:
            print_error(f"{package} 未安装")
            all_ok = False

    return all_ok


def test_config():
    """检测配置文件"""
    print_step(3, "配置文件检测")
    config_path = Path(__file__).parent / "config" / "simulation_config.json"

    if not config_path.exists():
        print_warn("配置文件不存在，将使用默认配置")
        return True

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print_ok("配置文件加载成功")
        print(f"  模式: {config.get('mode', 'simulation')}")
        print(f"  策略数: {len(config.get('strategies', {}))}")
        return True
    except Exception as e:
        print_error(f"配置文件解析失败: {e}")
        return False


def test_network():
    """测试网络连接"""
    print_step(4, "网络连接检测")
    try:
        import requests
        resp = requests.get("https://www.baidu.com", timeout=5)
        if resp.status_code == 200:
            print_ok("网络连接正常")
            return True
        else:
            print_warn(f"网络状态异常: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print_warn(f"网络连接失败: {e}")
        return False


def test_port():
    """检测端口占用"""
    print_step(5, "端口检测 (8000)")
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8000))
    sock.close()

    if result == 0:
        print_warn("端口 8000 已被占用（可能已有服务在运行）")
    else:
        print_ok("端口 8000 可用")
    return True


def main():
    print("=" * 60)
    print("AI量化监控系统 - 环境检测")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("模式: 模拟盘（不连接真实券商）")
    print("=" * 60)

    results = []
    results.append(("Python环境", test_python()))
    results.append(("依赖包", test_dependencies()))
    results.append(("配置文件", test_config()))
    results.append(("网络连接", test_network()))
    results.append(("端口检测", test_port()))

    print("\n" + "=" * 60)
    print("检测结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        icon = "✓" if passed else "✗"
        status = "PASS" if passed else "FAIL"
        print(f"  {icon} {name}: {status}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("✅ 环境检测通过，可以启动模拟盘")
        print("\n启动命令: venv\\Scripts\\python run_simulation.py")
        return 0
    else:
        print("❌ 部分检测失败，请根据提示修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
