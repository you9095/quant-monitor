#!/usr/bin/env python3
"""
update_monitor_data.py - 实时更新监控面板 data.js
功能: 从 signals/*.json 读取最新数据，自动更新 mockData
"""

import json
import re
from pathlib import Path

MONITOR_DIR = Path("/Users/junze/quant-monitor-local")
SIGNALS_DIR = MONITOR_DIR / "signals"
DATAJS_PATH = MONITOR_DIR / "assets" / "data.js"

def update_datajs():
    # 读取所有信号文件
    signals = {}
    for sf in SIGNALS_DIR.glob("*.json"):
        with open(sf, 'r') as f:
            data = json.load(f)
            signals[data['strategy_id']] = data
    
    # 读取 data.js
    with open(DATAJS_PATH, 'r') as f:
        datajs = f.read()
    
    # 更新每个策略的 metrics
    for sid, signal in signals.items():
        annualized = signal.get('annualized_return', 'null')
        max_dd = signal.get('max_drawdown', 'null')
        
        # 查找并替换 metrics 块
        pattern = rf"(id: '{sid}',.*?metrics: {{[^}}]+}})"
        # 这里需要更精确的替换逻辑
        
    print("信号数据已读取，准备更新 data.js")

if __name__ == "__main__":
    update_datajs()