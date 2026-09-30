#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据告警引擎 — 就地标注机制
2026-09-12 实现

核心逻辑：
1. 每次API请求时运行全量数据校验
2. 发现异常 → 检查是否已记录 → 未记录则添加（first_seen=今天）
3. 异常已修复 → 从状态文件中移除
4. 返回每个策略每个字段的告警状态，前端就地标注

告警状态持久化：data/alerts_state.json
格式：{
  "strategy_id": {
    "field_name": {
      "type": "accounting_identity" | "capital_mismatch" | "zero_pnl" | "stale_signal" | "negative_cash" | "simulated_data",
      "message": "异常描述",
      "first_seen": "2026-09-12",
      "last_seen": "2026-09-12",
      "severity": "error" | "warning"
    }
  }
}
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path('/Users/junze/quant-monitor-local')
SIGNALS_DIR = ROOT / 'signals'
CONFIG_FILE = ROOT / 'config' / 'strategies.json'
ALERTS_STATE_FILE = ROOT / 'data' / 'alerts_state.json'

# 告警阈值
STALE_DAYS = 5
ZERO_PNL_DAYS = 7


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_alerts_state():
    """加载告警状态文件"""
    if ALERTS_STATE_FILE.exists():
        with open(ALERTS_STATE_FILE) as f:
            return json.load(f)
    return {}


def save_alerts_state(state):
    """保存告警状态文件"""
    ALERTS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_latest_signal(sid):
    """获取最新的信号文件"""
    files = sorted(SIGNALS_DIR.glob(f'{sid}_*.json'), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def check_strategy(sid, config):
    """校验单个策略，返回异常列表"""
    alerts = []
    today = datetime.now().strftime('%Y-%m-%d')

    signal = get_latest_signal(sid)
    if signal is None:
        alerts.append({
            'field': 'signal_file',
            'type': 'missing_signal',
            'message': f'信号文件不存在',
            'severity': 'error'
        })
        return alerts

    # 提取字段
    initial_capital = signal.get('initial_capital', 0)
    live_total_pnl = signal.get('live_total_pnl', 0) or 0
    cash = signal.get('cash', 0) or 0
    positions = signal.get('positions', [])
    signal_date = signal.get('date', signal.get('signal_date', ''))
    data_source = signal.get('data_source', '')

    total_mv = sum(p.get('market_value', 0) for p in positions)
    total_asset = cash + total_mv
    expected_asset = initial_capital + live_total_pnl

    # === 校验1：会计恒等式 ===
    diff = abs(total_asset - expected_asset)
    if diff > 1.0:
        alerts.append({
            'field': 'total_asset',
            'type': 'accounting_identity',
            'message': f'会计恒等式不成立: 现金({cash:.2f})+持仓({total_mv:.2f})={total_asset:.2f} ≠ 本金({initial_capital:.2f})+累计({live_total_pnl:.2f})={expected_asset:.2f}, 差异{diff:.2f}',
            'severity': 'error'
        })

    # === 校验2：本金一致性 ===
    config_capital = config.get(sid, {}).get('initial_capital', 0)
    if config_capital > 0 and abs(initial_capital - config_capital) > 0.01:
        alerts.append({
            'field': 'initial_capital',
            'type': 'capital_mismatch',
            'message': f'本金不一致: 信号文件={initial_capital}, 配置文件={config_capital}',
            'severity': 'error'
        })

    # === 校验3：累计长期为0 ===
    if abs(live_total_pnl) < 0.01:
        try:
            sig_date = datetime.strptime(signal_date, '%Y-%m-%d')
            days_zero = (datetime.now() - sig_date).days
            if days_zero > ZERO_PNL_DAYS:
                alerts.append({
                    'field': 'live_total_pnl',
                    'type': 'zero_pnl',
                    'message': f'累计盈亏为0超过{days_zero}天（{signal_date}至今），可能是未接入真实回测',
                    'severity': 'warning'
                })
        except:
            pass

    # === 校验4：信号文件陈旧 ===
    try:
        sig_date = datetime.strptime(signal_date, '%Y-%m-%d')
        days_stale = (datetime.now() - sig_date).days
        if days_stale > STALE_DAYS:
            alerts.append({
                'field': 'signal_date',
                'type': 'stale_signal',
                'message': f'信号文件陈旧: {signal_date}（{days_stale}天前）',
                'severity': 'warning'
            })
    except:
        alerts.append({
            'field': 'signal_date',
            'type': 'invalid_date',
            'message': f'信号日期格式异常: {signal_date}',
            'severity': 'warning'
        })

    # === 校验5：现金为负 ===
    if cash < 0:
        alerts.append({
            'field': 'cash',
            'type': 'negative_cash',
            'message': f'现金为负: {cash:.2f}（持仓市值可能超过本金+累计）',
            'severity': 'error'
        })

    # === 校验6：数据源模拟模式 ===
    if 'simulated' in data_source.lower() or '模拟' in data_source:
        alerts.append({
            'field': 'data_source',
            'type': 'simulated_data',
            'message': f'数据源包含模拟模式: {data_source}',
            'severity': 'error'
        })

    return alerts


def run_alert_engine():
    """
    运行告警引擎，返回所有策略的告警状态
    
    返回格式：
    {
        "strategy_id": {
            "field_name": {
                "type": "...",
                "message": "...",
                "first_seen": "2026-09-12",
                "last_seen": "2026-09-12",
                "severity": "error" | "warning"
            }
        }
    }
    """
    config = load_config()
    strategies = [k for k in config.keys() if not k.startswith('_')]
    today = datetime.now().strftime('%Y-%m-%d')

    # 加载已有告警状态
    state = load_alerts_state()
    new_state = {}

    for sid in strategies:
        current_alerts = check_strategy(sid, config)
        old_strategy_alerts = state.get(sid, {})
        new_strategy_alerts = {}

        for alert in current_alerts:
            field = alert['field']
            alert_type = alert['type']

            # 检查是否已有同类型告警
            existing = old_strategy_alerts.get(field, {})
            if existing.get('type') == alert_type:
                # 已有告警，保留first_seen，更新last_seen
                first_seen = existing.get('first_seen', today)
            else:
                # 新告警
                first_seen = today

            new_strategy_alerts[field] = {
                'type': alert_type,
                'message': alert['message'],
                'first_seen': first_seen,
                'last_seen': today,
                'severity': alert['severity']
            }

        if new_strategy_alerts:
            new_state[sid] = new_strategy_alerts

    # 保存新状态
    save_alerts_state(new_state)

    return new_state


def get_alerts_summary(alerts_state):
    """获取告警摘要，用于前端展示"""
    summary = {
        'total_errors': 0,
        'total_warnings': 0,
        'strategies_with_alerts': [],
        'by_strategy': {}
    }

    for sid, fields in alerts_state.items():
        strategy_alerts = []
        for field, alert in fields.items():
            strategy_alerts.append({
                'field': field,
                'type': alert['type'],
                'message': alert['message'],
                'first_seen': alert['first_seen'],
                'severity': alert['severity']
            })
            if alert['severity'] == 'error':
                summary['total_errors'] += 1
            else:
                summary['total_warnings'] += 1

        if strategy_alerts:
            summary['strategies_with_alerts'].append(sid)
            summary['by_strategy'][sid] = strategy_alerts

    return summary


if __name__ == '__main__':
    # 命令行运行：打印所有告警
    alerts = run_alert_engine()
    summary = get_alerts_summary(alerts)

    print('=' * 70)
    print('数据告警引擎运行结果')
    print(f'运行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    print(f'错误: {summary["total_errors"]}, 警告: {summary["total_warnings"]}')
    print(f'有告警的策略: {", ".join(summary["strategies_with_alerts"]) or "无"}')
    print()

    for sid, fields in alerts.items():
        print(f'--- {sid} ---')
        for field, alert in fields.items():
            icon = '❌' if alert['severity'] == 'error' else '⚠️'
            print(f'  {icon} [{field}] {alert["message"]}')
            print(f'     首次发现: {alert["first_seen"]}, 最近发现: {alert["last_seen"]}')
        print()
