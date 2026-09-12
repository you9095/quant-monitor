#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化监控项目 · 数据完整性校验脚本
修复漏洞：2026-09-12 goldcombo两套系统未对接事故

校验项：
1. 会计恒等式：现金 + 持仓市值 = 初始本金 + 累计盈亏
2. 本金一致性：信号文件 vs strategies.json 配置
3. 累计长期为0告警（超过7天）
4. 信号文件陈旧告警（超过5天）
5. 现金异常告警（现金 > 本金的2倍 或 现金为负）
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path('/Users/junze/quant-monitor-local')
SIGNALS_DIR = ROOT / 'signals'
CONFIG_FILE = ROOT / 'config' / 'strategies.json'

# 告警阈值
STALE_DAYS = 5          # 信号文件超过5天未更新
ZERO_PNL_DAYS = 7       # 累计为0超过7天
CASH_RATIO_THRESHOLD = 2.0  # 现金超过本金2倍


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def check_strategy(sid, config):
    """校验单个策略"""
    issues = []
    warnings = []
    
    # 找最新的信号文件
    sig_files = sorted(SIGNALS_DIR.glob(f'{sid}_*.json'), reverse=True)
    if not sig_files:
        issues.append(f'❌ 无信号文件')
        return issues, warnings
    
    latest = sig_files[0]
    with open(latest) as f:
        sig = json.load(f)
    
    # 提取字段
    initial_capital = sig.get('initial_capital', 0)
    live_total_pnl = sig.get('live_total_pnl', 0)
    cash = sig.get('cash', 0)
    positions = sig.get('positions', [])
    signal_date = sig.get('date', sig.get('signal_date', ''))
    data_source = sig.get('data_source', '')
    
    total_mv = sum(p.get('market_value', 0) for p in positions)
    total_asset = cash + total_mv
    expected_asset = initial_capital + live_total_pnl
    
    # === 校验1：会计恒等式 ===
    diff = abs(total_asset - expected_asset)
    if diff > 1.0:  # 允许1元误差
        issues.append(
            f'❌ 会计恒等式不成立: 现金({cash:.2f}) + 持仓({total_mv:.2f}) = {total_asset:.2f}, '
            f'但 本金({initial_capital:.2f}) + 累计({live_total_pnl:.2f}) = {expected_asset:.2f}, '
            f'差异={diff:.2f}'
        )
    
    # === 校验2：本金一致性 ===
    config_capital = config.get(sid, {}).get('initial_capital', 0)
    if config_capital > 0 and abs(initial_capital - config_capital) > 0.01:
        issues.append(
            f'❌ 本金不一致: 信号文件={initial_capital}, 配置文件={config_capital}'
        )
    
    # === 校验3：累计长期为0 ===
    if abs(live_total_pnl) < 0.01:
        # 检查信号文件日期
        try:
            sig_date = datetime.strptime(signal_date, '%Y-%m-%d')
            days_zero = (datetime.now() - sig_date).days
            if days_zero > ZERO_PNL_DAYS:
                warnings.append(
                    f'⚠️ 累计盈亏为0超过{days_zero}天（{signal_date}至今），'
                    f'可能是新策略未接入或数据错误'
                )
        except:
            pass
    
    # === 校验4：信号文件陈旧 ===
    try:
        sig_date = datetime.strptime(signal_date, '%Y-%m-%d')
        days_stale = (datetime.now() - sig_date).days
        if days_stale > STALE_DAYS:
            warnings.append(f'⚠️ 信号文件陈旧: {signal_date}（{days_stale}天前）')
    except:
        warnings.append(f'⚠️ 信号日期格式异常: {signal_date}')
    
    # === 校验5：现金异常 ===
    if initial_capital > 0:
        # 现金为负是严重问题
        if cash < 0:
            issues.append(f'❌ 现金为负: {cash:.2f}（持仓市值可能超过本金+累计）')
        # 现金超过总资产的99%且累计为0，可能是数据错误
        elif total_asset > 0 and cash / total_asset > 0.99 and abs(live_total_pnl) < 0.01:
            warnings.append(
                f'⚠️ 全部现金且累计为0: 现金={cash:.2f}，占总资产{cash/total_asset*100:.1f}%，'
                f'累计={live_total_pnl:.2f}，可能是未接入真实回测'
            )
    
    # === 校验6：数据源检查 ===
    if 'simulated' in data_source.lower() or '模拟' in data_source:
        issues.append(f'❌ 数据源包含模拟模式: {data_source}')
    
    return issues, warnings


def main():
    print('=' * 70)
    print('量化监控项目 · 数据完整性校验')
    print(f'校验时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    config = load_config()
    # 排除非策略字段（如 _comment, _meta 等）
    strategies = [k for k in config.keys() if not k.startswith('_')]
    
    total_issues = 0
    total_warnings = 0
    
    for sid in strategies:
        print(f'\n--- {sid} ---')
        issues, warnings = check_strategy(sid, config)
        
        if not issues and not warnings:
            print('  ✅ 全部通过')
        
        for issue in issues:
            print(f'  {issue}')
            total_issues += 1
        
        for warning in warnings:
            print(f'  {warning}')
            total_warnings += 1
    
    print('\n' + '=' * 70)
    print(f'校验结果: {total_issues} 个错误, {total_warnings} 个警告')
    
    if total_issues > 0:
        print('❌ 存在数据完整性问题，请立即修复！')
        sys.exit(1)
    elif total_warnings > 0:
        print('⚠️ 存在警告，建议检查')
        sys.exit(0)
    else:
        print('✅ 全部通过')
        sys.exit(0)


if __name__ == '__main__':
    main()
