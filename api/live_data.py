#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控面板实时数据聚合层 (v1.1.1 - 2026-06-26)
============================================
为 quant-monitor-local 监控面板聚合 5 个策略的实盘模拟数据。

监控面板的 5 个策略（仅以下 5 个，不含其他独立项目）：
  - qixing    七星策略
  - r32       三驾马车
  - zhuidian  追电策略
  - sanhe     三合策略
  - lightning 闪电策略

数据源：
  - signals/{sid}_*.json   策略配置(棘轮迭代结果仅用于回测展示, 不进入实盘曲线)
  - config/strategies.json 每个策略的本金 + 元数据

对外 3 个接口：
  1. get_live_curves()       5 策略 2026-05-25 → 今的累计收益率曲线
  2. get_portfolio_summary() 总资金 / 初始 / 总盈亏 / 各策略分项
  3. get_today_actions()     5 策略今日交易流程

注意（v1.1.1 修正）：
- 不接入外部独立项目的数据（2026-08-03: kimi 自动化交易脚本已从本项目删除，独立项目）
- 不接入 ~/.hermes/stock_trader/ 项目的数据（独立项目，不属于本面板）
- 5 策略的实盘交易处于"信号驱动调仓"模式，没有日级 P&L 序列
  → 曲线完全由 work_logs 真实每日日志逐点构建, 无快照/无插值/无前向填充, 无数据则留空
"""
import json
import os
import re
import glob
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ==================== 路径常量 ====================
BASE_DIR = Path(__file__).parent.parent
SIGNALS_DIR = BASE_DIR / 'signals'
# 2026-08-21 v2: 实盘模拟 真实日 P&L 数据源
WORK_LOG_DIR = Path('/Users/junze/.hermes/work_logs')
CONFIG_FILE = BASE_DIR / 'config' / 'strategies.json'

# 实盘模拟起始日（所有 5 策略统一基准日）
LIVE_START_DATE = '2026-05-25'

# 每个策略的本金（来自 strategies.json）
DEFAULT_INITIAL_CAPITAL = 10000


def _normalize_return_pct(val) -> float:
    """收益率格式自动校验（2026-09-10 修复）。

    历史问题：8-31 模拟模式把 live_total_return 写成小数形式（如 -0.002243），
    而正常信号文件是百分比形式（如 270.31）。后端按百分比计算
    current_value = init_cap * (1 + tr/100)，导致小数形式的收益率
    被除以100后几乎为0，市值接近本金。

    自动检测规则：
      - 绝对值 < 1 且 != 0 → 判定为小数形式，×100 转百分比
      - 绝对值 >= 1 或 == 0 → 判定为百分比形式，保持原样
    """
    if val is None:
        return 0.0
    try:
        v = float(val)
    except (TypeError, ValueError):
        return 0.0
    if v != 0 and abs(v) < 1:
        return round(v * 100, 4)
    return v


#==============================================================================
# _load_latest_worklog - 从 work_logs 读取最新策略数据
#==============================================================================
def _load_latest_worklog(strategy_id: str) -> Optional[Dict[str, Any]]:
    """从 work_logs 目录读取策略的最新每日日志数据。

    返回格式与 _load_latest_signal 兼容，优先返回真实执行数据。
    支持两种格式：
    1. 旧格式: daily_pnl.cumulative, trade.securities
    2. 新格式 (live_runner): live_pnl, live_equity, live_positions 等 live_ 前缀字段
    """
    work_log_dir = Path(f'/Users/junze/.hermes/work_logs/{strategy_id}')
    if not work_log_dir.exists():
        return None

    # 查找非baseline的日志文件
    all_files = sorted(work_log_dir.glob(f'{strategy_id}_*.json'))
    # 过滤掉 baseline 文件
    non_baseline = [f for f in all_files if '_baseline' not in f.name]

    if not non_baseline:
        return None

    # 优先读取 _fusion 文件 (更接近真实 daily_runner 口径)
    # 按文件名日期排序，取最新的
    fusion_files = [f for f in non_baseline if '_fusion' in f.stem]
    regular_files = [f for f in non_baseline if '_fusion' not in f.stem]

    # 取最新的 fusion 文件，如果没有则取最新的 regular 文件
    target_file = fusion_files[-1] if fusion_files else regular_files[-1]

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if not lines:
            return None

        # 取最后一条记录 (最新的交易日)
        last_line = lines[-1]
        try:
            data = json.loads(last_line)
        except json.JSONDecodeError:
            # 不是 JSONL 格式（如 goldcombo 的大 JSON 报告），跳过
            return None

        # ===== 检测格式：新格式有 live_ 前缀字段 =====
        is_new_format = any(k.startswith('live_') for k in data.keys())

        if is_new_format:
            # ===== 新格式解析 (live_runner 输出) =====
            live_pnl = data.get('live_pnl', 0) or 0
            live_equity = data.get('live_equity', 0) or 0
            live_cash = data.get('live_cash', 0) or 0
            live_total_return = data.get('live_total_return', 0) or 0
            live_trade_count = data.get('live_trade_count', 0) or 0
            live_positions = data.get('live_positions', []) or []
            live_per_etf_pnl = data.get('live_per_etf_pnl', {}) or {}

            # 判断是否有真实成交：有持仓或有成交笔数
            has_real_trades = live_trade_count > 0 or len(live_positions) > 0

            # 解析持仓
            positions = []
            for pos in live_positions:
                code = pos.get('code') or pos.get('name') or ''
                qty = pos.get('live_qty', pos.get('qty', 0)) or 0
                cost = pos.get('live_cost', pos.get('cost', 0)) or 0
                if qty > 0:
                    positions.append({
                        'code': code,
                        'name': code,
                        'qty': qty,
                        'cost': cost,
                    })

            result = {
                'date': data.get('date', ''),
                'live_total_pnl': live_pnl,  # 始终读取 live_pnl，不因无持仓归零
                'live_total_return': live_total_return,
                'live_days': len(non_baseline),
                'today_pnl': live_pnl,
                'today_return': live_total_return,
                'action': 'TRADE' if live_trade_count > 0 else 'HOLD',
                'target': '',
                'positions': positions,
                'return_unit': 'percent',
                'version': data.get('version', ''),
                'initial_capital': None,
                # 新增：完整字段透传给前端
                'live_equity': live_equity,
                'live_cash': live_cash,
                'live_trade_count': live_trade_count,
                'live_per_etf_pnl': live_per_etf_pnl,
            }
        else:
            # ===== 旧格式解析 (兼容旧版 daily_runner) =====
            trade_securities = data.get('trade', {}).get('securities', []) or []
            daily_pnl = data.get('daily_pnl', {}) or {}
            trade_count = daily_pnl.get('trade_count', 0) or 0
            has_real_trades = len(trade_securities) > 0 or trade_count > 0

            result = {
                'date': data.get('trade_status', {}).get('date') or '',
                'live_total_pnl': daily_pnl.get('cumulative', 0) if has_real_trades else 0,
                'live_total_return': daily_pnl.get('return_pct', 0) if has_real_trades else 0,
                'live_days': len(non_baseline),
                'today_pnl': data.get('daily_pnl', {}).get('total', 0) or 0,
                'today_return': data.get('daily_pnl', {}).get('return_pct', 0) or 0,
                'action': data.get('signal', {}).get('action', 'HOLD') if 'signal' in data else 'HOLD',
                'target': data.get('signal', {}).get('target_etf', '') if 'signal' in data else '',
                'positions': [],
                'return_unit': 'percent',
                'version': data.get('version', ''),
                'initial_capital': None,
            }

            # 尝试从 _position_state.json 读取当前持仓信息
            pstate_file = work_log_dir / '_position_state.json'
            if pstate_file.exists():
                with open(pstate_file, 'r', encoding='utf-8') as f:
                    pstate = json.load(f)
                result['positions'] = [{
                    'code': pstate.get('security', ''),
                    'name': ETF_NAMES.get(pstate.get('security', ''), ''),
                    'qty': pstate.get('qty', 0),
                    'cost': 0,
                }]
                result['initial_capital'] = pstate.get('qty', 0) * pstate.get('last_price', 0) or 10000

            # 从 latest record 的 capital 字段
            if result['initial_capital'] is None and 'capital' in data:
                result['initial_capital'] = data['capital']

            # 如果 positions 为空但有 daily_pnl，尝试从 per_etf 计算
            if not result['positions'] and 'per_etf' in data.get('daily_pnl', {}):
                for etf_code, etf_pnl in data['daily_pnl']['per_etf'].items():
                    result['positions'].append({
                        'code': etf_code,
                        'name': ETF_NAMES.get(etf_code, ''),
                        'qty': 0,
                        'cost': 0,
                    })

        return result

    except Exception as e:
        print(f"Error loading worklog for {strategy_id}: {e}")
        return None


ETF_NAMES = {
    '159915': '创业板ETF',
    '159967': '国企红利',
    '513100': '纳指ETF',
    '513520': '日经ETF',
    '513500': '标普500',
    '510300': '沪深300',
    '510500': '中证500'


}
def _load_strategies_config() -> Dict:
    """加载策略配置（含 initial_capital）"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if not k.startswith('_')}
    except Exception:
        return {}


def _build_live_curve_from_worklogs(strategy_id: str, start_date: str, end_date: str,
                                       initial_capital: float) -> Dict:
    """
    2026-08-23 v6 江予白 V12 重构 (按 §6.5 必须修数据不只告警):
    - points 存金额 (不再转 %) → 保留真实数据
    - _build_curve 计算 current_value = actual_capital_used + cum_pnl (不再用 initial_capital %)
    - 暴露 actual_capital_used 字段 → 前端透明化
    """
    points = []  # [(date_str, cum_amount_yuan)]

    # 数据源 1: work_logs/{strategy_id}/*.json
    # 2026-09-20 修复: 同一天若存在 _fusion 文件(daily_runner_v2 切片实盘口径)则优先,
    # 普通文件(策略脚本单日直跑, 不累计)不用于曲线; session 用 endswith 兼容 fusion_*。
    work_log_dir = WORK_LOG_DIR / strategy_id
    if work_log_dir.exists():
        date_files = {}
        for f in sorted(work_log_dir.glob(f'{strategy_id}_*.json')):
            if '_baseline' in f.name:
                continue
            date_in_name = None
            for part in f.stem.split('_'):
                if len(part) == 10 and part[4] == '-' and part[7] == '-':
                    date_in_name = part
                    break
            if not date_in_name:
                continue
            is_fusion = '_fusion' in f.stem
            prev = date_files.get(date_in_name)
            if prev is None or (is_fusion and not prev[1]):
                date_files[date_in_name] = (f, is_fusion)

        for date_in_name, (f, _is_fusion) in sorted(date_files.items()):
            try:
                text = f.read_text()
                afternoon = None
                morning = None
                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except:
                        continue
                    sess = str(obj.get('session', ''))
                    if sess.endswith('afternoon') and obj.get('daily_pnl'):
                        afternoon = obj
                    elif sess.endswith('morning') and obj.get('daily_pnl'):
                        morning = obj
                target = afternoon or morning
                if target:
                    daily_pnl = target.get('daily_pnl', {})
                    cum_amount = daily_pnl.get('cumulative')
                    date = target.get('trade_status', {}).get('date', date_in_name)
                    actual_capital = target.get('capital')
                    if cum_amount is not None and date:
                        points.append((date, round(cum_amount, 2), actual_capital or initial_capital))
            except Exception:
                continue
    
    data_source = 'work_logs'

    # 2026-09-20 永久禁止快照/插值: work_logs 无真实每日数据时直接返回 empty(留空),
    # 不再从 signals 的 total_return 反推插值(快照机制; 当前 signals 由 work_logs 重建, 本就无该字段)。

    if not points:
        # 2026-09-20 无任何真实每日数据 → 一律空着(null), 不画本金平线假装"在运行"
        return {
            'dates': [start_date, end_date],
            'values': [None, None],
            'returns': [None, None],
            'real_trading_days': 0,
            'data_source': 'empty',
            'data_start': start_date,
            'data_end': end_date,
            'is_interpolated': [False, False],
            'actual_capital_used': initial_capital,
        }

    points.sort(key=lambda x: x[0])

    # 2026-09-20 永久禁止快照/前向填充: 不补齐 start 前、不延长 end 后、缺失日期留 null
    points = [s for s in points if start_date <= s[0] <= end_date]
    if not points:
        return {
            'dates': [start_date, end_date],
            'values': [None, None],
            'returns': [None, None],
            'real_trading_days': 0,
            'data_source': 'empty',
            'data_start': start_date,
            'data_end': end_date,
            'is_interpolated': [False, False],
            'actual_capital_used': initial_capital,
        }

    # 2026-09-20 禁止快照: 曲线只输出真实交易日数据点。
    # 周末/节假日/断更日一律不生成点（不补 null、不前向填充、不延长到今天），
    # 曲线自然终止于最后一个真实交易日 data_end。
    dates: List[str] = []
    values: List = []
    returns: List = []
    is_interpolated: List[bool] = []

    actual_capital_used = points[0][2]
    for s_date, s_val, s_cap in points:
        dates.append(s_date)
        values.append(round(s_cap + s_val, 2))
        returns.append(round((s_val / s_cap) * 100, 2) if s_cap > 0 else 0.0)
        is_interpolated.append(False)

    data_start = points[0][0]
    data_end = points[-1][0]
    
    return {
        'dates': dates,
        'values': values,
        'returns': returns,
        'real_trading_days': len([s for s in points if start_date <= s[0] <= end_date]),
        'data_source': data_source,
        'data_start': data_start,
        'data_end': data_end,
        'is_interpolated': is_interpolated,
        'actual_capital_used': actual_capital_used,  # v8: 从 work_logs 实际读
        'initial_capital_config': initial_capital,    # v8: config 里的初始本金 (参考)
    }


def get_live_curves(end_date: Optional[str] = None) -> Dict:
    """
    获取五策略的实盘累计曲线

    Returns:
        {
            'start_date': '2026-05-25',
            'end_date': '2026-06-26',
            'days': 32,
            'curves': {
                'qixing':  {'dates': [...], 'values': [...], 'returns': [...]},
                'r32':     {...},
                ...
            },
            'strategy_ids': ['qixing', 'r32', 'zhuidian', 'sanhe', 'lightning']
        }
    """
    cfg = _load_strategies_config()
    if end_date is None:
        end_date = date.today().isoformat()

    curves = {}
    for sid in cfg.keys():
        init_cap = cfg[sid].get('initial_capital', DEFAULT_INITIAL_CAPITAL)
        # 2026-09-20 数据真实性根治: goldcombo(黄金组合A策略)只有棘轮回测、没有每日模拟信号,
        # 按用户最高原则"无真实每日数据就空着, 回测净值不许混入实盘模拟曲线",
        # 不再用 evidence 回测净值(2021~2026)冒充实盘曲线 —— 那会把 X 轴拉到 5 年、压缩真实盘曲线。
        # 统一走标准 builder: 无 work_logs 每日数据即返回 empty, 曲线留空, 待接入每日信号后再显示。
        curves[sid] = _build_live_curve_from_worklogs(sid, LIVE_START_DATE, end_date, init_cap)

    # 2026-08-23 v4 江予白 V12 漏洞修复: 数据完整性 validation
    validation_warnings = []
    for sid, c in curves.items():
        if c.get('data_source') == 'work_logs' and len(c.get('values', [])) > 1:
            values = c['values']
            for i in range(1, len(values)):
                if values[i-1] > 0:
                    pct_change = abs((values[i] - values[i-1]) / values[i-1])
                    if pct_change > 0.5:
                        validation_warnings.append({
                            'sid': sid,
                            'idx': i,
                            'date': c['dates'][i],
                            'pct_change': round(pct_change * 100, 2),
                            'value_before': values[i-1],
                            'value_after': values[i],
                            'is_interpolated': c.get('is_interpolated', [])[i] if i < len(c.get('is_interpolated', [])) else None
                        })

    return {
        'start_date': LIVE_START_DATE,
        'end_date': end_date,
        'days': (datetime.strptime(end_date, '%Y-%m-%d') -
                 datetime.strptime(LIVE_START_DATE, '%Y-%m-%d')).days + 1,
        'curves': curves,
        'strategy_ids': list(cfg.keys()),
        'validation_warnings': validation_warnings,
        'validation_note': f'检测到 {len(validation_warnings)} 个异常跳变 (>50%), 通常为 daily run 系统 capital 重置或插值, 非真实盈亏' if validation_warnings else '数据完整性校验通过',
    }


def get_portfolio_summary() -> Dict:
    """
    获取组合总览（实盘模拟至今）

    Returns:
        {
            'total_value':      当前总资产,
            'initial_capital':  初始总资金,
            'total_pnl':        累计盈亏金额,
            'total_return_pct': 累计收益率,
            'per_strategy': {
                'qixing': {
                    'initial_capital': 10000,
                    'current_value': 17400.00,
                    'pnl': +7400.00,
                    'return_pct': 74.00,
                    'latest_signal_date': '2026-06-30',
                },
                ...
            }
        }
    """
    cfg = _load_strategies_config()
    initial_total = 0
    current_total = 0
    per_strategy = {}

    for sid, c in cfg.items():
        # 读取最新 worklog（实盘执行数据优先）
        wl = _load_latest_worklog(sid)
        # 回退到 signal（用于策略配置信息）
        sig = _load_latest_signal(sid) if not wl else None

        # 2026-09-20 真实性根治: 仅 live_days>0 的真实每日模拟策略计入实盘组合。
        # 黄金组合A策略(goldcombo)只有棘轮回测、live_days=0, 回测收益不得计入实盘组合,
        # 因此直接跳过(不计入初始资金/当前资产/分项), 无真实数据就空着。
        live_days = (wl or sig or {}).get('live_days', 0) or 0
        if live_days <= 0:
            continue

        init_cap = c.get('initial_capital', DEFAULT_INITIAL_CAPITAL)
        initial_total += init_cap

        # 优先使用 worklog 数据，回退到 signal
        source = wl if wl else sig
        if source:
            # 实盘收益率只取 live_total_return/total_return; 不再用 backtest_total_return 兜底冒充
            raw_tr = (source.get('live_total_return', 0) or source.get('total_return', 0) or 0)
            # 2026-09-21: signal 显式声明 return_unit='percent' 时直接信任,
            # 不再用"绝对值<1 即小数"的启发式猜测(会把真实的 -0.364% 误放大成 -36.4%)
            tr = float(raw_tr) if source.get('return_unit') == 'percent' else _normalize_return_pct(raw_tr)
            current_value = round(init_cap * (1 + tr / 100), 2)
            pnl = round(current_value - init_cap, 2)
        else:
            tr = 0
            current_value = init_cap
            pnl = 0

        current_total += current_value
        per_strategy[sid] = {
            'strategy_id': sid,
            'name': c.get('name', sid),
            'initial_capital': init_cap,
            'current_value': current_value,
            'pnl': pnl,
            'return_pct': round(tr, 2),
            'latest_signal_date': source.get('date') if source else None,
            'version': source.get('version') if source else c.get('version', 'N/A'),
        }

    return {
        'total_value': round(current_total, 2),
        'initial_capital': initial_total,
        'total_pnl': round(current_total - initial_total, 2),
        'total_return_pct': round((current_total - initial_total) / initial_total * 100, 2),
        'per_strategy': per_strategy,
        'live_start_date': LIVE_START_DATE,
        'update_time': datetime.now().isoformat(),
    }


def _load_latest_signal(strategy_id: str) -> Optional[Dict]:
    """读取策略最新信号文件"""
    files = sorted(glob.glob(str(SIGNALS_DIR / f'{strategy_id}_*.json')), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def get_today_actions() -> Dict:
    """
    获取每个策略今日交易流程

    Returns:
        {
            'date': '2026-06-26',
            'strategies': {
                'qixing': {
                    'action': 'REBALANCE' / 'BUY' / 'SELL' / 'HOLD',
                    'target': '159915',
                    'detail': 'R120 默认参数...',
                    'positions': [...]
                },
                ...
            }
        }
    """
    today = date.today().isoformat()
    cfg = _load_strategies_config()
    strategies = {}

    for sid in cfg.keys():
        sig = _load_latest_signal(sid)
        if not sig:
            strategies[sid] = {
                'strategy_id': sid,
                'name': cfg[sid].get('name', sid),
                'action': 'NO_DATA',
                'target': None,
                'detail': '暂无信号数据',
                'positions': [],
                'signal_date': None,
            }
            continue

        action_obj = sig.get('action', {}) or {}
        strategies[sid] = {
            'strategy_id': sid,
            'name': cfg[sid].get('name', sid),
            'action': action_obj.get('action', 'HOLD') if isinstance(action_obj, dict) else 'HOLD',
            'target': action_obj.get('target') if isinstance(action_obj, dict) else None,
            'detail': action_obj.get('detail', '') if isinstance(action_obj, dict) else '',
            'positions': sig.get('positions', []),
            'signal_date': sig.get('date'),
            # P0 修复 (2026-08-03): 同文件多端点扫描 — signals 只有 live_total_return,
            # 与 L93 曲线 / L234 portfolio_summary 保持同一字段溯源
            # 2026-08-14 主 agent 接管修复: 加 backtest_total_return 兜底
            'total_return': (sig.get('live_total_return', 0) or sig.get('total_return', 0)
                             or sig.get('backtest_total_return', 0) or 0),
            'today_pnl': sig.get('today_pnl', 0),
            'today_return': sig.get('today_return', 0),
            'version': sig.get('version', cfg[sid].get('version', 'N/A')),
        }

    return {
        'date': today,
        'strategies': strategies,
    }


if __name__ == '__main__':
    # 自检
    print('===== portfolio_summary =====')
    print(json.dumps(get_portfolio_summary(), ensure_ascii=False, indent=2))
    print('\n===== live_curves (前5天) =====')
    curves = get_live_curves()
    for sid in curves['strategy_ids']:
        c = curves['curves'][sid]
        print(f"  {sid}: {c['real_trading_days']} points, "
              f"first 3 returns: {c['returns'][:3]}, "
              f"last 3 returns: {c['returns'][-3:]}")
    print('\n===== today_actions =====')
    print(json.dumps(get_today_actions(), ensure_ascii=False, indent=2))