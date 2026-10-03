#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI量化监控系统 - 模拟盘启动脚本
启动 Flask 监控面板，不连接任何真实券商
"""

import sys
import os
import subprocess
from pathlib import Path

# Windows CMD 默认 GBK
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk")
        sys.stderr.reconfigure(encoding="gbk")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent
API_SERVER = BASE_DIR / "api" / "real_data_server_v2.py"


def main():
    print("=" * 55)
    print("  AI量化监控系统 - 模拟盘")
    print("  不连接任何真实券商")
    print("=" * 55)

    if not API_SERVER.exists():
        print(f"\n[错误] 找不到后端文件: {API_SERVER}")
        print("请确认部署包文件完整，重新解压后重试")
        input("\n按回车键退出...")
        return 1

    print(f"\n  启动目录: {BASE_DIR}")
    print("  正在启动监控面板...\n")

    # 以独立子进程方式运行后端，确保 __file__/__name__ 正确
    try:
        proc = subprocess.run(
            [sys.executable, str(API_SERVER)],
            cwd=str(BASE_DIR)
        )
        return proc.returncode
    except KeyboardInterrupt:
        print("\n服务已停止")
        return 0
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")
        input("\n按回车键退出...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
