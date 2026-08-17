#!/usr/bin/env python3
"""
quant_data_sync.py - 量化策略数据统一口径同步器 v2.0
功能:
1. 扫描 .hermes/outputs 获取最新棘轮结果
2. 解析 2Y/5Y 年化数据并标记来源周期
3. 自动校正 data.js 中的 mock 数据
4. 生成信号文件 + 飞书推送
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

OUTPUTS_DIR = Path("/Users/junze/.hermes/outputs")
MONITOR_DIR = Path("/Users/junze/quant-monitor-local")
DATAJS_PATH = MONITOR_DIR / "assets" / "data.js"
SIGNALS_DIR = MONITOR_DIR / "signals"

STRATEGY_PATTERNS = {
    "qixing": {"2y": "R120.*年化.*32\\.35", "5y": "R11.*年化.*1\\.92"},
    "r32": {"2y": "R35.*年化.*17\\.16", "5y": "R35.*年化.*23\\.72"},
    "zhuidian": {"2y": "R17.*年化.*103\\.18", "5y": "R39.*年化.*32\\.65"},
    "sanhe": {"2y": "R43.*年化.*35\\.80", "5y": "R44.*年化.*23\\.18"},
    "lightning": {"2y": "R4.*年化.*27\\.34", "5y": "5Y.*未跑"}
}

def extract_annualized_return(text, period="2y"):
    """从报告文本提取年化收益"""
    if "5Y" in text and "未跑" in text:
        return None
    pattern = re.compile(rf"{period.upper()}.*年化.*([+\-]?\d+\.?\d*)%")
    match = pattern.search(text)
    return float(match.group(1)) if match else None

def sync_strategy_data():
    results = {}
    
    for sid in STRATEGY_PATTERNS:
        # 扫描 outputs 目录找最新报告
        latest_report = find_latest_report(sid)
        if latest_report:
            with open(latest_report, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results[sid] = {
                "2y": extract_annualized_return(content, "2y"),
                "5y": extract_annualized_return(content, "5y"),
                "source": latest_report.name
            }
    
    return results

def find_latest_report(strategy_id):
    """找到策略最新棘轮报告"""
    patterns = list(OUTPUTS_DIR.glob(f"**/*{strategy_id}*"))
    if not patterns:
        patterns = list(OUTPUTS_DIR.glob(f"**/*{strategy_id.replace('qixing','七星')}*"))
        patterns += list(OUTPUTS_DIR.glob(f"**/*{strategy_id.replace('r32','三驾')}*"))
        patterns += list(OUTPUTS_DIR.glob(f"**/*{strategy_id.replace('sanhe','三合')}*"))
        patterns += list(OUTPUTS_DIR.glob(f"**/*{strategy_id.replace('lightning','闪电')}*"))
        patterns += list(OUTPUTS_DIR.glob(f"**/*{strategy_id.replace('zhuidian','追电')}*"))
    
    md_files = [p for p in patterns if p.suffix == '.md']
    if md_files:
        return max(md_files, key=lambda p: p.stat().st_mtime)
    return None

if __name__ == "__main__":
    results = sync_strategy_data()
    print(json.dumps(results, ensure_ascii=False, indent=2))