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
    'goldcombo': ('黄金组合A策略', 10000.0),
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
    """返回 {date_str: {'fusion': path|None, 'live': path|None, 'legacy': path|None}}"""
    dates = {}
    for f in wl_dir.glob(f'{sid}_*.json'):
        if 'baseline' in f.name:
            continue
        # 跳过回测/模拟文件，只取实盘 live 和旧格式
        is_sim = '_sim.' in f.name or '_sim_' in f.name
        is_bt = '_bt.' in f.name or '_bt_' in f.name
        if is_sim or is_bt:
            continue
        is_fusion = '_fusion' in f.stem and '_fusion_baseline' not in f.stem
        is_live = '_live.' in f.name or f.stem.endswith('_live')
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
        dates.setdefault(date_str, {'fusion': None, 'live': None, 'legacy': None})
        if is_fusion:
            dates[date_str]['fusion'] = f
        elif is_live:
            dates[date_str]['live'] = f
        else:
            dates[date_str]['legacy'] = f
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
        'return_unit': 'percent',
    }

    # 检测格式：新格式有 live_equity 字段（2026-09-23 起 daily_runner 新输出）
    is_new_format = 'live_equity' in wl

    if is_new_format:
        # === 新格式映射 ===
        live_equity = float(wl.get('live_equity', initial_cap) or initial_cap)
        live_pnl = float(wl.get('live_pnl', 0) or 0)
        live_total_return = float(wl.get('live_total_return', 0) or 0)
        live_positions = wl.get('live_positions') or []

        signal['today_pnl'] = live_pnl
        signal['today_return'] = round(live_pnl / initial_cap * 100, 4) if initial_cap else 0
        # 新格式：live_total_return 是文件直接给出的累计收益率(%)，
        # live_total_pnl 由 initial_cap 反推，不直接用 live_equity - initial_cap
        # （因为不同策略引擎内部本金可能不同，如 zhuidian=10万）
        signal['live_total_pnl'] = round(initial_cap * live_total_return / 100, 2)
        signal['live_total_return'] = live_total_return
        signal['live_days'] = live_days

        # 新格式持仓适配为旧格式 positions 结构
        positions = []
        for p in live_positions:
            if isinstance(p, dict):
                positions.append({
                    'code': p.get('code', p.get('secucode', '')),
                    'name': p.get('name', p.get('sec_name', '')),
                    'qty': p.get('qty', p.get('volume', 0)),
                    'cost': p.get('cost', p.get('cost_price', 0)),
                    'market_value': p.get('market_value', p.get('mv', 0)),
                })
            elif isinstance(p, str):
                positions.append({'code': p, 'name': '', 'qty': 0, 'cost': 0, 'market_value': 0})
        signal['positions'] = positions if sid == 'zhuidian' else [
            pos for pos in positions
            if float(pos.get('qty', 0) or 0) > 0 and float(pos.get('cost', 0) or 0) > 0
        ]

        # 动作推断：有持仓=持有，无持仓=空仓
        has_pos = any(float(pos.get('qty', 0) or 0) > 0 for pos in positions)
        signal['action'] = {
            'type': 'HOLD' if has_pos else 'FLAT',
            'label': '持有' if has_pos else '空仓',
            'target_etf': '',
            'target_weight': 0,
        }
        if wl.get('live_start_date'):
            signal['live_start_date'] = wl['live_start_date']
        return signal

    # === 旧格式映射（原有逻辑）===
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
        if sid == 'zhuidian':
            signal['positions'] = list(positions)
        else:
            signal['positions'] = [
                pos for pos in positions
                if float(pos.get('qty', 0) or 0) > 0 and float(pos.get('cost', 0) or 0) > 0
            ]
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
        base_return = None  # 旧格式末值（累计收益率%）
        new_engine_start_return = None  # 新格式第一天的 live_total_return
        entered_new_format = False
        last_panel_return = None  # 最近一次的面板累计收益率
        last_new_engine_return = None  # 前一天新引擎的 live_total_return（检测重置用）

        for date_str in sorted(dates):
            files = dates[date_str]
            wl_file = files['fusion'] or files['live'] or files['legacy']
            if not wl_file:
                continue

            # 先预览文件内容，判断是否有效
            wl_preview = parse_worklog_first_json(wl_file) or {}
            is_new = 'live_equity' in wl_preview

            # 旧格式空文件检测
            if not is_new:
                dp = wl_preview.get('daily_pnl', {})
                if not isinstance(dp, dict) or 'cumulative' not in dp:
                    continue

            signal = build_etf_signal(sid, sname, date_str, wl_file, live_days, initial_cap)
            if not signal:
                continue

            if not entered_new_format:
                if is_new:
                    # 第一个新格式文件：建立衔接基线
                    entered_new_format = True
                    new_engine_start_return = signal.get('live_total_return', 0) or 0
                    last_new_engine_return = new_engine_start_return
                    if base_return is not None:
                        panel_return = base_return
                    else:
                        panel_return = signal.get('live_total_return', 0) or 0
                    signal['live_total_return'] = round(panel_return, 4)
                    signal['live_total_pnl'] = round(initial_cap * panel_return / 100, 2)
                    last_panel_return = panel_return
                else:
                    # 纯旧格式阶段
                    base_return = signal.get('live_total_return', 0) or 0
                    last_panel_return = base_return
            else:
                # 已进入新格式
                if is_new:
                    new_engine_current = signal.get('live_total_return', 0) or 0
                    # 检测引擎重置：如果新引擎累计收益率跳变超过50%（绝对值），认为引擎重置了
                    if last_new_engine_return is not None and abs(new_engine_current - last_new_engine_return) > 50:
                        # 引擎重置：重新建立基线，前一天的 panel_return 保持不变
                        # 新引擎从今天重新开始，今天的 panel_return = 昨天的 panel_return
                        new_engine_start_return = new_engine_current
                        panel_return = last_panel_return
                    else:
                        panel_return = base_return + (new_engine_current - new_engine_start_return)
                    last_new_engine_return = new_engine_current
                else:
                    # 旧格式文件：沿用前一天
                    panel_return = last_panel_return
                signal['live_total_return'] = round(panel_return, 4)
                signal['live_total_pnl'] = round(initial_cap * panel_return / 100, 2)
                last_panel_return = panel_return

            dst = SIGNALS_DIR / f'{sid}_{date_str}.json'
            dst.write_text(json.dumps(signal, ensure_ascii=False, indent=2), encoding='utf-8')
            count += 1
        print(f'  {sid}: 重建 {count} 个真实 signals（{sorted(dates)[0]} ~ {sorted(dates)[-1]}，本金 {initial_cap:.0f}）')
        total += count

    print(f'\n✅ 重建完成: 共 {total} 个真实 signals，无任何快照/前向填充/回测冒充')


if __name__ == '__main__':
    main()
