#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 work_logs 全量重建 signals（禁止快照版，2026-09-20）
======================================================
铁律:
  1. signals 只能由真实 work_logs 逐日生成, 禁止任何复制/前向填充/快照
  2. 某日没有真实 work_logs → 该日不生成 signal 文件（没有真实数据就空着）
  3. qixing 优先使用 _fusion 版本（融合策略实盘口径）
  4. goldcombo(黄金组合A策略) 自 2026-09-21 起接入真实每日模拟
     （scripts/goldcombo_daily_run.py，venv+backtrader，V24 锁死、实盘起点前不交易），
     与 5 个 ETF 策略走同一条逐日 work_logs → signals 链路；
     棘轮回测结果一律不得进入 work_logs/signals（规则7：回测/实盘严格分离）。

用法:
  python3 rebuild_signals_from_worklogs.py            # 全量重建
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

SIGNALS_DIR = Path('/Users/junze/quant-monitor-local/signals')
WORKLOGS_DIR = Path('/Users/junze/.hermes/work_logs')

# 每日真实模拟策略 → 初始本金（goldcombo V24 策略锁死 5 万，其余各 1 万）
STRATEGIES = {
    'qixing': ('七星策略', 10000.0),
    'r32': ('三驾马车策略', 10000.0),
    'zhuidian': ('追电策略', 10000.0),
    'sanhe': ('三合策略', 10000.0),
    'lightning': ('闪电策略', 10000.0),
    'goldcombo': ('黄金组合A策略', 50000.0),
}

ACTION_MAP = {
    'DEFENSIVE': '防御', 'HOLD': '持有', 'REBALANCE': '调仓',
    'FLAT': '空仓', 'BUY': '买入', 'SELL': '卖出',
    'EMPTY': '空仓', 'OBSERVE': '观望', 'NONE': '无信号',
}


def parse_worklog_first_json(wl_path: Path):
    """work_logs 是 JSONL, 取第一行（或含 daily_pnl 的 afternoon 行）"""
    try:
        text = wl_path.read_text(encoding='utf-8')
    except Exception:
        return None
    afternoon = None
    morning = None
    first = None
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if first is None:
            first = obj
        if str(obj.get('session', '')).endswith('afternoon') and obj.get('daily_pnl'):
            afternoon = obj
        elif str(obj.get('session', '')).endswith('morning') and obj.get('daily_pnl'):
            morning = obj
    return afternoon or morning or first


def collect_dates(wl_dir: Path, sid: str):
    """返回 {date_str: {'fusion': path|None, 'normal': path|None}}"""
    dates = {}
    for f in wl_dir.glob(f'{sid}_*.json'):
        if 'baseline' in f.name:
            continue
        is_fusion = '_fusion' in f.stem
        date_str = None
        for part in f.stem.split('_'):
            if len(part) == 10 and part[4] == '-' and part[7] == '-':
                try:
                    datetime.strptime(part, '%Y-%m-%d')
                    date_str = part
                    break
                except ValueError:
                    continue
        if not date_str:
            continue
        dates.setdefault(date_str, {'fusion': None, 'normal': None})
        if is_fusion:
            dates[date_str]['fusion'] = f
        else:
            dates[date_str]['normal'] = f
    return dates


def build_etf_signal(sid, sname, date_str, wl_file, live_days, initial_cap):
    wl = parse_worklog_first_json(wl_file)
    if not wl:
        return None

    signal = {
        'date': date_str,
        'strategy_id': sid,
        'strategy_name': sname,
        'initial_capital': initial_cap,
        'data_source': 'work_logs（真实每日信号）',
        # 2026-09-21: 显式声明收益率单位为百分数(如 -0.364 表示 -0.364%),
        # 后端不得再用"绝对值<1 即小数"的启发式猜测(会把真实的 -0.364% 放大成 -36.4%)
        'return_unit': 'percent',
    }

    sig = wl.get('signal') if isinstance(wl.get('signal'), dict) else {}
    action_en = sig.get('action', '')
    signal['action'] = {
        'type': action_en,
        'label': ACTION_MAP.get(action_en, action_en),
        'target_etf': sig.get('target_etf', ''),
        'target_weight': sig.get('target_weight', 0),
    }

    dp = wl.get('daily_pnl') if isinstance(wl.get('daily_pnl'), dict) else {}
    signal['today_pnl'] = float(dp.get('total', 0) or 0)
    if 'return_pct' in dp:
        signal['today_return'] = float(dp['return_pct'])
    if 'cumulative' in dp:
        signal['live_total_pnl'] = float(dp['cumulative'])
    if 'return_pct' in dp:
        signal['live_total_return'] = float(dp['return_pct'])
    if 'trade_count' in dp:
        signal['trade_count'] = int(dp['trade_count'])
    # 实盘起点（goldcombo 每日引擎在 work_log 写 live_start_date；ETF 无此字段则为 None）
    if wl.get('live_start_date'):
        signal['live_start_date'] = wl['live_start_date']

    positions = wl.get('positions_after') or wl.get('positions') or wl.get('holdings') or []
    if isinstance(positions, list):
        # 过滤规则：若策略为 zhuidian，保留所有 positions（含 qty=0），
        # 这是追电策略的正常状态（轮动策略常为空仓/观察），不应被过滤掉。
        # 对其他策略（qixing/r32/sanhe/lightning），仅保留 qty>0 且 cost>0 的真实持仓。
        if sid == 'zhuidian':
            signal['positions'] = list(positions)
        else:
            signal['positions'] = [
                pos for pos in positions
                if float(pos.get('qty', 0) or 0) > 0 and float(pos.get('cost', 0) or 0) > 0
            ]
    # 2026-09-21 修复：当无 ETF 通过动量筛选时，清空 target_etfs
    # 避免前端显示虚高收益（target_value=0 导致的虚假抬高）
    sig = signal.get('action', {})
    if sid == 'zhuidian' and isinstance(sig, dict):
        target_etfs = sig.get('target_etfs', [])
        if target_etfs and all(t.get('target_value', 0) == 0 for t in target_etfs):
            signal['target_etfs'] = []
            signal['target_weight'] = 0
            signal['action'] = {**sig, 'type': 'HOLD', 'target_etf': '', 'target_weight': 0}

    signal['live_days'] = live_days
    return signal


def main():
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    for sid, (sname, initial_cap) in STRATEGIES.items():
        wl_dir = WORKLOGS_DIR / sid
        if not wl_dir.exists():
            print(f'  {sid}: work_logs 目录不存在, 跳过')
            continue
        dates = collect_dates(wl_dir, sid)
        live_days = len(dates)

        # 清空该策略旧 signals（禁止旧快照/回测占位残留）
        for f in SIGNALS_DIR.glob(f'{sid}_*.json'):
            f.unlink()

        if live_days == 0:
            print(f'  {sid}: 无真实每日 work_logs，不生成 signal（没有真实模拟就空着）')
            continue

        count = 0
        for date_str in sorted(dates):
            files = dates[date_str]
            wl_file = files['fusion'] or files['normal']
            if not wl_file:
                continue
            signal = build_etf_signal(sid, sname, date_str, wl_file, live_days, initial_cap)
            if not signal:
                continue
            dst = SIGNALS_DIR / f'{sid}_{date_str}.json'
            dst.write_text(json.dumps(signal, ensure_ascii=False, indent=2), encoding='utf-8')
            count += 1
        print(f'  {sid}: 重建 {count} 个真实 signals（{sorted(dates)[0]} ~ {sorted(dates)[-1]}，本金 {initial_cap:.0f}）')
        total += count

    print(f'\n✅ 重建完成: 共 {total} 个真实 signals，无任何快照/前向填充/回测冒充')


if __name__ == '__main__':
    main()
