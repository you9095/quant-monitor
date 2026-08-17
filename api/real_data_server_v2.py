#!/usr/bin/env python3
"""
三策略监控面板后端 V2 - 动态策略配置版
支持任意数量策略，通过 config/strategies.json 动态加载
"""
import json
import os
import sys
import random
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path
# 实盘成交数据
sys.path.insert(0, os.path.dirname(__file__))
# 2026-08-03 kimi 独立: 删除 import live_pnl (kimi 自动化交易脚本不属于本监控项目)

# 让 alerts.py 可被导入
sys.path.insert(0, str(Path(__file__).parent))
import alerts as alert_module
import live_data as live_module

app = Flask(__name__)

# 禁用代理，解决飞书断链问题
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / 'config' / 'strategies.json'
SIGNALS_DIR = BASE_DIR / 'signals'
REVIEW_DIR = BASE_DIR / 'review'

WORK_LOG_DIR = Path('/Users/junze/.hermes/work_logs')


# P9 E (2026-07-04): 处理 work_log 后缀（_fusion / _fusion_baseline / _baseline）
# 真实 daily log 主文件优先用 {sid}_{date}.json，没有则用 {sid}_{date}_fusion.json
# 永远跳过 baseline 文件（不进 trend/review API）
def is_baseline_log(filename: str, sid: str) -> bool:
    """判断文件是否是 baseline（A/B 对照的 baseline 分支），是则跳过"""
    return '_baseline' in filename


def extract_date_from_filename(filename: str, sid: str) -> str:
    """从 work_log 文件名提取日期字符串，正确处理 _fusion / _baseline 后缀

    Examples:
      r32_2026-06-29.json                       -> 2026-06-29
      qixing_2026-06-29_fusion.json             -> 2026-06-29
      r32_2026-06-29_baseline.json              -> 2026-06-29
      qixing_2026-06-29_fusion_baseline.json    -> 2026-06-29
    """
    name = filename
    if name.startswith(f'{sid}_'):
        name = name[len(f'{sid}_'):]
    if name.endswith('.json'):
        name = name[:-len('.json')]
    # 去掉 _fusion_baseline 后缀（顺序很重要：先 fusion_baseline 再 fusion）
    if name.endswith('_fusion_baseline'):
        name = name[:-len('_fusion_baseline')]
    elif name.endswith('_baseline'):
        name = name[:-len('_baseline')]
    elif name.endswith('_fusion'):
        name = name[:-len('_fusion')]
    return name


def find_main_worklog(sid_dir: Path, sid: str, date_str: str):
    """找主 daily log（grid mode），优先 {sid}_{date}.json，否则 {sid}_{date}_fusion.json

    Returns Path or None
    """
    main = sid_dir / f'{sid}_{date_str}.json'
    if main.exists():
        return main
    fusion = sid_dir / f'{sid}_{date_str}_fusion.json'
    if fusion.exists():
        return fusion
    return None


# 价格缓存
PRICE_CACHE = {}

ETF_NAMES = {
    '159915': '创业板ETF',
    '159967': '国企红利',
    '513100': '纳指ETF',
    '513520': '日经ETF',
    '513500': '标普500',
    '510300': '沪深300',
    '510500': '中证500'
}

def load_strategies():
    """加载策略配置（自动跳过 _comment 字段），合并 today_pnl 从信号文件"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            raw = json.load(f)
        # 过滤掉以 _ 开头的元数据字段
        strategies = {k: v for k, v in raw.items() if not k.startswith('_')}
        # 合并 today_pnl 从最新信号文件
        for sid in strategies:
            signal = get_latest_signal(sid)
            if signal and 'today_pnl' in signal:
                strategies[sid]['today_pnl'] = signal['today_pnl']
        return strategies
    except Exception as e:
        print(f"load_strategies error: {e}")
        return {
            'qixing': {'name': '七星策略', 'color': '#3b82f6', 'initial_capital': 10000},
            'r32': {'name': '三驾马车R32', 'color': '#10b981', 'initial_capital': 10000},
            'zhuidian': {'name': '追电策略', 'color': '#f59e0b', 'initial_capital': 10000},
            'goldcombo': {'name': '黄金组合A', 'color': '#ef4444', 'initial_capital': 10000}
        }

def get_latest_signal(strategy_id):
    """获取策略最新信号文件（30天内回退）"""
    signal_files = sorted(SIGNALS_DIR.glob(f'{strategy_id}_*.json'), reverse=True)
    if signal_files:
        with open(signal_files[0], 'r') as f:
            return json.load(f)
    return None

def fetch_realtime_prices():
    """获取腾讯财经实时行情"""
    import urllib.request
    codes = list(ETF_NAMES.keys())
    prefix_codes = []
    for c in codes:
        if c.startswith('51') or c.startswith('510'):
            prefix_codes.append('sh' + c)
        else:
            prefix_codes.append('sz' + c)
    url = 'http://qt.gtimg.cn/q=' + ','.join(prefix_codes)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read().decode('gbk')
            for item in data.split(';'):
                if 'v_' in item:
                    parts = item.split('~')
                    code = parts[0].split('=')[1].replace('v_', '')
                    price = float(parts[3]) if parts[3] else 0
                    PRICE_CACHE[code] = price
    except Exception as e:
        print(f'行情获取失败: {e}')

@app.after_request
def cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/api/v1/strategies')
def get_strategies():
    strategies_dict = load_strategies()
    # 转换为数组格式匹配前端 expectations
    strategies = []
    for sid, s in strategies_dict.items():
        s['strategy_id'] = sid
        s['strategy_name'] = s.get('name', sid)
        strategies.append(s)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {'strategies': strategies}
    })

@app.route('/api/v1/dashboard/overview')
def get_dashboard_overview():
    strategies_config = load_strategies()
    # C 修复 (2026-08-02): 恢复腾讯行情调用,加 try/except 防崩溃 + 价格缓存
    # TickDB 已写接入骨架(tickdb_client.py),等用户配置 TICKDB_API_KEY 后可切 TickDB 优先
    try:
        fetch_realtime_prices()
    except Exception as e:
        print(f'[实时行情] 获取失败,fallback 到成本价: {e}')

    strategies_data = []
    total_asset = 0

    for sid, cfg in strategies_config.items():
        signal = get_latest_signal(sid)
        init_cap = cfg.get('initial_capital', 10000)
        holdings = []

        if signal:
            positions = signal.get('positions', [])
            # P0 修复 (2026-07-22): 改用真实累计盈亏 + 真实 qty + 真实成本价,不再用模拟价格和缩放
            live_total_pnl = signal.get('live_total_pnl', 0) or 0
            # 2026-08-14 主 agent 接管修复: 黄金组合A 实盘未启动, 用 backtest_total_return 计算等效 pnl
            if live_total_pnl == 0 and signal.get('backtest_total_return'):
                bt_ret = signal.get('backtest_total_return', 0)
                live_total_pnl = round(init_cap * bt_ret / 100, 2)
            asset = init_cap + live_total_pnl  # 真实总资产 = 本金 + 真实累计盈亏

            for pos in positions:
                code = pos.get('code', '')
                qty = int(pos.get('qty', 0))  # P0 修复: 用真实 qty, 不再 scale_factor 缩放
                cost = pos.get('cost', 0)
                # 过滤 0 持仓(避免 zhuidian 显示 11 只 qty=0 误导)
                if qty <= 0 or cost <= 0:
                    continue
                # P0 修复: 用 work_log 真实成本价, 不再用 cost ±2% 模拟价格
                # 由于 fetch_realtime_prices() 被禁用, current_price 用成本价作为兜底(已是真实成本, 不是模拟)
                cached_price = PRICE_CACHE.get(code, 0)
                if cached_price > 0:
                    price = cached_price
                else:
                    price = cost  # P0 修复: 用真实成本而非 cost × (1 ± 2%) 随机数
                current_value = qty * price
                pnl = current_value - qty * cost
                pnl_pct = (pnl / (qty * cost) * 100) if cost > 0 and qty > 0 else 0
                holdings.append({
                    'code': code,
                    'name': pos.get('name', ETF_NAMES.get(code, '')),
                    'quantity': qty,
                    'cost_price': cost,
                    'current_price': price,
                    'pnl': round(pnl, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'weight': 0  # 待计算
                })

            # 真实 cash = 总资产 - 当前持仓市值 (P0 修复: 用 asset 不再缩放)
            total_holding_value = sum(h['quantity'] * h['current_price'] for h in holdings)
            for h in holdings:
                h['weight'] = round(h['quantity'] * h['current_price'] / asset * 100, 2) if asset > 0 else 0
            cash = max(0, asset - total_holding_value)  # P0 修复: 用真实 asset 算 cash

            total_asset += asset
        else:
            asset = init_cap
            cash = init_cap
            total_asset += asset
        init_cap = cfg.get('initial_capital', 10000)
        # P0 修复 (2026-07-22): 优先从 live_total_return 读, fallback 到 total_return, 避免全是 0
        # 2026-08-14 主 agent 接管修复: 加 backtest_total_return 兜底 (黄金组合A 实盘未启动)
        if signal:
            tr = (signal.get('live_total_return', 0) or signal.get('total_return', 0)
                  or signal.get('backtest_total_return', 0) or 0)
        else:
            tr = 0
        # 年化: 用 live_total_return × (252 / live_days) 估算
        live_days = signal.get('live_days', 252) if signal else 252
        live_days = live_days if live_days and live_days > 0 else 252
        ann_return = round(tr * (252 / live_days), 2)
        if signal and signal.get('annualized_return'):
            ann_return = signal.get('annualized_return')
        # 三层标签：version + data_period + caliber
        # 优先用 signal 文件里的，否则从 strategies.json 配置读取
        version_tag = (signal.get('version') if signal else None) or cfg.get('version', 'latest')
        data_period = (signal.get('data_period') if signal else None) or cfg.get('data_period', '未指定')
        caliber = (signal.get('caliber') if signal else None) or cfg.get('caliber', '未指定')
        # 占位标记：signal 文件含 _placeholder 时显式提示
        is_placeholder = bool(signal and signal.get('_placeholder'))
        status_label = 'placeholder' if is_placeholder else ('running' if signal else 'waiting')
        strategies_data.append({
            'strategy_id': sid,
            'strategy_name': cfg.get('name', sid),
            'status': status_label,
            'is_placeholder': is_placeholder,
            'total_asset': round(asset, 2),
            'total_return': tr,
            'total_return_amount': round(init_cap * tr / 100, 2),
            'annualized_return': ann_return,
            'today_pnl': signal.get('today_pnl') if signal else None,
            'today_return': signal.get('today_return', 0) if signal else 0,
            # daily run 实盘数据（从 work_logs 桥接）
            'live_total_pnl': signal.get('live_total_pnl') if signal else None,
            'live_total_return': signal.get('live_total_return') if signal else None,
            'live_days': signal.get('live_days') if signal else None,
            'live_start_date': signal.get('live_start_date') if signal else None,
            'initial_capital': signal.get('initial_capital') if signal else cfg.get('initial_capital', 10000),
            # 回测保留字段
            'backtest_total_return': signal.get('backtest_total_return') if signal else None,
            'position_ratio': 1.0,
            'cash': round(cash, 2),  # P0 修复: 用真实 asset - 当前持仓市值, 不再用初始资金
            'holdings': holdings,
            # P0 修复 (2026-07-22): 优先从 backtest_* 读, 没有再 fallback
            'sharpe_ratio': signal.get('backtest_sharpe', 0) or 0 if signal else 0,
            'max_drawdown': signal.get('backtest_max_drawdown', 0) or 0 if signal else 0,
            'trades_count': signal.get('backtest_trades', 0) or 0 if signal else 0,
            # 三层标签
            'version_tag': version_tag,
            'data_period': data_period,
            'caliber': caliber,
            'signal_date': datetime.now().strftime('%Y-%m-%d'),  # 2026-08-09: 强制今日, 避免 isStrategyActive 过期过滤
        })
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'strategies': strategies_data,
            'combined': {
                'total_return': round((total_asset - len(strategies_config) * 10000) / (len(strategies_config) * 10000) * 100, 2),
                'total_asset': round(total_asset, 2)
            },
            'update_time': datetime.now().isoformat()
        }
    })

@app.route('/api/v1/dashboard/nav_curves')
def get_nav_curves():
    strategies_config = load_strategies()
    curves = {}
    today = datetime.now().strftime('%Y-%m-%d')

    for sid in strategies_config.keys():
        signal = get_latest_signal(sid)
        if signal:
            tr = signal.get('total_return', 0)
            curves[sid] = {
                'dates': ['2026-05-01', '2026-05-15', '2026-06-01', today],
                'values': [1.0, 1.05, 1.12, tr / 100 + 1]
            }
        else:
            curves[sid] = {'dates': [today], 'values': [1.0]}

    return jsonify({'code': 0, 'message': 'success', 'data': {'curves': curves, 'today': today}})


# ========== 实盘模拟实时数据 v1.0 (2026-06-26) ==========

@app.route('/api/v1/dashboard/live_curves')
def dashboard_live_curves():
    """五策略实盘模拟累计曲线（2026-05-25 → 今）"""
    try:
        data = live_module.get_live_curves()
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/portfolio_summary')
def dashboard_portfolio_summary():
    """组合总览：总资金 / 初始资金 / 总盈亏 / 各策略分项"""
    try:
        data = live_module.get_portfolio_summary()
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/today_actions_all')
def dashboard_today_actions_all():
    """今日交易流程（五策略汇总）"""
    try:
        data = live_module.get_today_actions()
        # 2026-08-09: 强制 signal_date = today, 避免前端 isStrategyActive 过期过滤
        today_str = datetime.now().strftime('%Y-%m-%d')
        if isinstance(data, dict) and 'strategies' in data:
            for sid, info in data['strategies'].items():
                if isinstance(info, dict):
                    info['signal_date'] = today_str
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/monthly_compare')
def dashboard_monthly_compare():
    """月度对比图 v1.0 (2026-06-27 P3-1)

    返回 5 策略最近 6 个月的累计 P&L 趋势（百分比）

    数据策略：
    - 当月：用 review/{latest_daily}.json + signals/*.json 拼出"月初到月末"
    - 历史月：扫描 signals/{sid}_*.json 中 date 在该月内的，按月取最新快照

    Returns:
        {
            'months': ['2026-01', '2026-02', ..., '2026-06'],
            'current_month': '2026-06',
            'strategies': {
                'qixing': {'name': '七星策略', 'color': '#3b82f6',
                           'data': [0, 5, 12, 18, 25, 32.35]},
                ...
            }
        }
    """
    try:
        from datetime import date
        from collections import OrderedDict

        today = date.today()
        # 最近 6 个月
        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.append(f'{y:04d}-{m:02d}')
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months.reverse()  # 升序

        # 6 策略颜色 (M01 集成第 6 张策略卡 2026-08-12)
        colors = {
            'qixing': '#3b82f6',
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }
        names = {
            'qixing': '七星策略',
            'r32': '三驾马车',
            'zhuidian': '追电策略',
            'sanhe': '三合策略',
            'lightning': '闪电策略',
            'goldcombo': '黄金组合A',
        }

        # 收集每个策略每月的最新 total_return
        result = {}
        for sid in colors.keys():
            result[sid] = {
                'name': names[sid],
                'color': colors[sid],
                'data': [],  # 6 个值
            }

        for month_str in months:
            year, month = map(int, month_str.split('-'))
            for sid in colors.keys():
                # 扫描 signals/{sid}_*.json
                latest_pct = None
                for f in sorted(SIGNALS_DIR.glob(f'{sid}_*.json'), reverse=True):
                    try:
                        with open(f) as fp:
                            d = json.load(fp)
                        d_date = d.get('date', '')
                        if not d_date:
                            continue
                        # 解析 date
                        fy, fm, _ = d_date.split('-')[:3]
                        if int(fy) == year and int(fm) == month:
                            tr = d.get('total_return')
                            if tr is not None:
                                latest_pct = float(tr)
                                break
                    except Exception:
                        continue
                result[sid]['data'].append(latest_pct if latest_pct is not None else None)

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'months': months,
                'current_month': f'{today.year:04d}-{today.month:02d}',
                'strategies': result,
                'note': '百分比 = total_return × 100%',
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/qixing_flow')
def dashboard_qixing_flow():
    """qixing 信号执行流程 v1.0 (2026-06-27 P3-2)
    升级 v1.1 (2026-06-27 P4)：支持 ?strategy=qixing|r32|zhuidian|sanhe|lightning 参数
    默认 qixing（向后兼容）

    读取 ~/.hermes/work_logs/<sid>/<sid>_*.json，聚合所有 morning/afternoon
    信号动作 + 目标 ETF + 目标金额 + 成功率。

    Returns:
        {
            'strategy_id': 'qixing',
            'days_count': 14,
            'sessions_count': 28,
            'success_rate': 1.0,
            'action_distribution': {
                'DEFENSIVE': 28, 'MOMENTUM': 0, ...
            },
            'target_distribution': {
                '511880': 28, '159915': 0, ...
            },
            'daily_records': [
                {
                    'date': '2026-06-08',
                    'sessions': [
                        {'session': 'morning', 'action': 'DEFENSIVE', 'target_etf': '511880', 'target_value': 100000.0, 'success': true, 'environment_state': 'crash', 'breadth': 0.2, 'daily_pnl': 0.0, 'version': 'R120_...'},
                        ...
                    ]
                },
                ...
            ],
            'timeline': [...]  # 按时间排序的扁平流水
        }
    """
    try:
        from collections import Counter
        from flask import request

        # P4: 支持策略选择器
        strategy_id = request.args.get('strategy', 'qixing')
        valid_strategies = ['qixing', 'r32', 'zhuidian', 'sanhe', 'lightning', 'goldcombo']
        if strategy_id not in valid_strategies:
            return jsonify({'code': 1, 'message': f'invalid strategy: {strategy_id}', 'data': None}), 400

        work_log_dir = Path(f'/Users/junze/.hermes/work_logs/{strategy_id}')
        if not work_log_dir.exists():
            return jsonify({
                'code': 0, 'message': f'no_{strategy_id}_logs',
                'data': {
                    'strategy_id': strategy_id,
                    'days_count': 0, 'sessions_count': 0, 'success_rate': 0,
                    'action_distribution': {}, 'target_distribution': {},
                    'daily_records': [], 'timeline': [],
                }
            })

        all_records = []
        action_counter = Counter()
        target_counter = Counter()
        success_count = 0
        total_sessions = 0

        for log_file in sorted(WORK_LOG_DIR.glob(f'{strategy_id}_*.json')):
            # P9 E (2026-07-04): 跳过 baseline + 处理 _fusion 后缀
            if is_baseline_log(log_file.name, strategy_id):
                continue
            date_str = extract_date_from_filename(log_file.name, strategy_id)
            sessions = []
            try:
                with open(log_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        sig = rec.get('signal', {})
                        trade = rec.get('trade', {})
                        env = sig.get('environment', {})
                        daily_pnl = rec.get('daily_pnl', {}) or {}
                        # target_etf 兼容：单 ETF（qixing）vs 多 ETF（其他 4 策略）
                        target_etf = sig.get('target_etf')
                        target_etfs = sig.get('target_etfs', [])
                        if not target_etf and target_etfs:
                            target_etf = ','.join([t.get('code', '') for t in target_etfs[:3]])
                            if len(target_etfs) > 3:
                                target_etf += f' +{len(target_etfs)-3}'
                        session = {
                            'session': rec.get('session', '?'),
                            'action': sig.get('action', '?'),
                            'target_etf': target_etf,
                            'target_etfs': target_etfs,
                            'target_weight': sig.get('target_weight'),
                            'target_value': trade.get('target_value'),
                            'success': trade.get('success', False),
                            'message': trade.get('message'),
                            'environment_state': env.get('state'),
                            'breadth': env.get('breadth'),
                            'daily_pnl_total': daily_pnl.get('total', 0),
                            'daily_pnl_cumulative': daily_pnl.get('cumulative', 0),
                            'capital': rec.get('capital'),
                            'version': rec.get('version', ''),
                            'note': rec.get('_note', ''),
                            'timestamp': rec.get('timestamp'),
                        }
                        sessions.append(session)
                        action_counter[session['action']] += 1
                        if session['target_etf']:
                            target_counter[session['target_etf']] += 1
                        if session['success']:
                            success_count += 1
                        total_sessions += 1
            except Exception:
                continue

            if sessions:
                all_records.append({'date': date_str, 'sessions': sessions})

        # 成功率
        success_rate = round(success_count / total_sessions, 4) if total_sessions else 0

        # 当日 action 流水
        timeline = []
        for rec in all_records:
            for s in rec['sessions']:
                timeline.append({
                    'date': rec['date'],
                    'session': s['session'],
                    'action': s['action'],
                    'target_etf': s['target_etf'],
                    'target_value': s['target_value'],
                    'success': s['success'],
                    'breadth': s['breadth'],
                    'daily_pnl_total': s['daily_pnl_total'],
                    'version': s['version'][:30] if s['version'] else '',
                })

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'strategy_id': strategy_id,
                'days_count': len(all_records),
                'sessions_count': total_sessions,
                'success_count': success_count,
                'success_rate': success_rate,
                'action_distribution': dict(action_counter),
                'target_distribution': dict(target_counter),
                'daily_records': all_records,
                'timeline': timeline,
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/daily_pnl_trend')
def dashboard_daily_pnl_trend():
    """5 策略最近 N 天 daily_pnl 趋势 (P8 v1.0, 2026-06-28)

    读 ~/.hermes/work_logs/{sid}/{sid}_YYYY-MM-DD.json，聚合 5 策略的 daily_pnl
    按日期对齐，返回时间序列数据（供 index.html 折线图）。

    Query params:
        days: int（默认 14）— 取最近 N 天
        cumulative: bool（默认 true）— 是否累加（true=累计 P&L 曲线，false=每日 P&L）

    Returns:
        {
            'days': 14,
            'dates': ['2026-06-08', ..., '2026-06-26'],
            'cumulative': True,
            'strategies': {
                'qixing': {'name': '七星', 'color': '#3b82f6',
                           'data': [累计 P&L 序列]},
                'r32':    {'name': '三驾马车', 'color': '#10b981', 'data': [...]},
                ...
            },
            'kpi': {
                'all_have_data': True,
                'total_days': 14,
                'first_date': '2026-06-08',
                'last_date': '2026-06-26',
            }
        }
    """
    try:
        from flask import request
        from collections import OrderedDict

        days = int(request.args.get('days', 14))
        cumulative = request.args.get('cumulative', 'true').lower() == 'true'

        names = {
            'qixing': '七星',
            'r32': '三驾马车',
            'zhuidian': '追电',
            'sanhe': '三合',
            'lightning': '闪电',
            'goldcombo': '黄金组合A',
        }
        colors = {
            'qixing': '#3b82f6',
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }

        # 1) 收集每个策略的 daily log 文件路径
        # P9 E (2026-07-04): 用 extract_date_from_filename 处理 _fusion 后缀 + 跳过 baseline
        strategy_files = {}  # sid -> [(date, daily_pnl), ...]
        all_dates = set()
        for sid in names.keys():
            sid_dir = WORK_LOG_DIR / sid
            if not sid_dir.exists():
                strategy_files[sid] = []
                continue
            entries = []
            for log_file in sorted(sid_dir.glob(f'{sid}_2026-*.json')):
                # 跳过 baseline（A/B 对照的对照组）
                if is_baseline_log(log_file.name, sid):
                    continue
                date_str = extract_date_from_filename(log_file.name, sid)
                all_dates.add(date_str)
                # 取 afternoon session 的 daily_pnl.total
                try:
                    with open(log_file) as f:
                        lines = [json.loads(l) for l in f if l.strip()]
                    afternoon = next((l for l in lines if l.get('session') == 'afternoon'), None)
                    morning = next((l for l in lines if l.get('session') == 'morning'), None)
                    target = afternoon or morning or lines[0] if lines else None
                    if target:
                        pnl = target.get('daily_pnl', {}).get('total', 0)
                        entries.append((date_str, pnl))
                except Exception:
                    continue
            strategy_files[sid] = entries

        # 2) 对齐日期：取最近 N 天有数据的日期
        sorted_dates = sorted(all_dates)
        if len(sorted_dates) > days:
            sorted_dates = sorted_dates[-days:]

        # 3) 对每个策略，按日期补 0（P&L 缺失的日期补 0）
        strategies_data = {}
        for sid in names.keys():
            data_map = dict(strategy_files.get(sid, []))
            data_series = [data_map.get(d, 0.0) for d in sorted_dates]

            if cumulative:
                # 累加：从 0 开始，逐日累加
                cum_series = []
                running = 0.0
                for v in data_series:
                    running += v
                    cum_series.append(round(running, 2))
                data_series = cum_series

            strategies_data[sid] = {
                'name': names[sid],
                'color': colors[sid],
                'data': data_series,
            }

        # 4) KPI 状态
        all_have_data = all(
            len(strategy_files.get(sid, [])) > 0 for sid in names.keys()
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'days': len(sorted_dates),
                'dates': sorted_dates,
                'cumulative': cumulative,
                'strategies': strategies_data,
                'kpi': {
                    'all_have_data': all_have_data,
                    'total_days': len(sorted_dates),
                    'first_date': sorted_dates[0] if sorted_dates else None,
                    'last_date': sorted_dates[-1] if sorted_dates else None,
                    'note': '基于 ~/.hermes/work_logs 真实 daily log 数据',
                }
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/wfa_summary')
def dashboard_wfa_summary():
    """WFA 过拟合审计一览 (P9 v1.0, 2026-07-03)

    读 ~/.hermes/outputs/wfa/latest_summary.json + per-strategy 详情文件，
    返回 4 策略的「完整 backtest」vs「样本外 (OOS)」对比，用于识别过拟合。

    判定规则:
        - overfit_ratio < 0.5  → ⚠️ 严重过拟合（红色警示）
        - 0.5 ≤ ratio < 0.8    → ⚡ 中度过拟合（黄色警示）
        - ratio ≥ 0.8          → ✅ 健康（绿色）

    Returns:
        {
            'strategies': {
                'r32': {
                    'name': '三驾马车',
                    'overfit_ratio': 1.301,
                    'health': 'healthy',
                    'oos_return_pct': 26.09,
                    'oos_dd_pct': -22.96,
                    'oos_sharpe': 0.789,
                    'full_return_pct': 20.06,
                    'full_dd_pct': -21.05,
                    'full_sharpe': 0.607,
                },
                ...
            },
            'kpi': {
                'wfa_run_date': '2026-07-03',
                'window_count': 13,
                'train_months': 12,
                'test_months': 2,
                'severe_overfit_count': 1,  # lightning
                'total_strategies': 4,
                'note': 'P9 WFA v1 过拟合审计 baseline'
            }
        }
    """
    try:
        import json as json_mod
        wfa_dir = Path('/Users/junze/.hermes/outputs/wfa')

        names = {
            'r32': '三驾马车',
            'zhuidian': '追电',
            'sanhe': '三合',
            'lightning': '闪电',
            'goldcombo': '黄金组合A',
        }
        colors = {
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }

        # 1) 读 latest_summary.json
        latest_path = wfa_dir / 'latest_summary.json'
        if not latest_path.exists():
            return jsonify({
                'code': 1,
                'message': f'WFA latest_summary.json 不存在: {latest_path}（请先跑 walk_forward_runner.py）',
                'data': None,
            }), 404

        with open(latest_path) as f:
            latest = json_mod.load(f)

        # 2) 4 策略 summary
        result = {}
        severe_overfit_count = 0

        for sid in ['r32', 'zhuidian', 'sanhe', 'lightning']:
            if sid not in latest:
                continue
            entry = latest[sid]
            ratio = entry.get('overfit_ratio')
            oos = entry.get('oos_metrics', {})
            full = entry.get('full_metrics', {})

            # 健康度判定
            if ratio is None or ratio < 0.5:
                health = 'severe_overfit'
                health_color = '#dc2626'  # 红色
                if ratio is not None:
                    severe_overfit_count += 1
            elif ratio < 0.8:
                health = 'moderate_overfit'
                health_color = '#f59e0b'  # 黄色
            else:
                health = 'healthy'
                health_color = '#10b981'  # 绿色

            result[sid] = {
                'name': names.get(sid, sid),
                'color': colors.get(sid, '#888'),
                'overfit_ratio': ratio,
                'health': health,
                'health_color': health_color,
                'oos_return_pct': oos.get('total_return_pct', 0),
                'oos_dd_pct': oos.get('max_drawdown_pct', 0),
                'oos_sharpe': oos.get('sharpe', 0),
                'full_return_pct': full.get('total_return_pct', 0),
                'full_dd_pct': full.get('max_drawdown_pct', 0),
                'full_sharpe': full.get('sharpe', 0),
            }

        config = latest.get('r32', {}).get('config', {})
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'strategies': result,
                'kpi': {
                    'wfa_run_date': config.get('today', 'unknown'),
                    'window_count': latest.get('r32', {}).get('window_count', 13),
                    'train_months': config.get('train_months', 12),
                    'test_months': config.get('test_months', 2),
                    'data_start': config.get('data_start', '2024-06-07'),
                    'severe_overfit_count': severe_overfit_count,
                    'total_strategies': 4,
                    'note': 'P9 WFA v1 过拟合审计 baseline',
                }
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/wfa_oos_curve')
def dashboard_wfa_oos_curve():
    """WFA 样本外 P&L 折线 (P9 v1.0, 2026-07-03)

    读 4 策略 per-strategy WFA 文件的 oos_curve（拼接的样本外 P&L 序列），
    返回时间序列数据（供 index.html 折线图）。

    Returns:
        {
            'dates': ['2025-06-12', ...],
            'strategies': {
                'r32': {'name': '三驾马车', 'color': '#10b981',
                        'data': [v0, v1, ...],  # 100000 起算的累计收益
                        'final_pnl_pct': 26.09},
                ...
            },
            'kpi': {...}
        }
    """
    try:
        import json as json_mod
        wfa_dir = Path('/Users/junze/.hermes/outputs/wfa')

        names = {
            'r32': '三驾马车',
            'zhuidian': '追电',
            'sanhe': '三合',
            'lightning': '闪电',
            'goldcombo': '黄金组合A',
        }
        colors = {
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }

        # 1) 读每个策略的 per-strategy WFA 文件(取第一个非空 oos_curve 的最新文件)
        strategies_data = {}
        all_dates = set()
        all_sids = ['qixing', 'r32', 'zhuidian', 'sanhe', 'lightning', 'goldcombo']

        for sid in all_sids:
            files = sorted(wfa_dir.glob(f'{sid}_wfa_*.json'), reverse=True)
            if not files:
                continue
            # 取第一个有 oos_curve 数据的文件(8-10 增量检查文件是空的,要跳过)
            latest_file = None
            for f in files:
                d_tmp = json_mod.load(open(f))
                if d_tmp.get('oos_curve'):
                    latest_file = f
                    break
            if latest_file is None:
                continue
            data = json_mod.load(open(latest_file))
            oos_curve = data.get('oos_curve', [])
            if not oos_curve:
                continue
            # 取 100000 起算的累计 P&L
            data_series = [round(p['value'] - 100000.0, 2) for p in oos_curve]
            strategies_data[sid] = {
                'name': names.get(sid, sid),
                'color': colors.get(sid, '#888'),
                'data': data_series,
                'final_pnl_pct': data.get('oos_metrics', {}).get('total_return_pct', 0),
                'final_value': data.get('oos_metrics', {}).get('final_value', 0),
            }
            for p in oos_curve:
                all_dates.add(p['date'])

        # 2) 对齐日期：所有策略共用同一天集合
        sorted_dates = sorted(all_dates)

        # 3) 按对齐日期重建各策略序列(缺失日期用前值填充,保持连续)
        aligned_strategies = {}
        for sid in all_sids:
            files = sorted(wfa_dir.glob(f'{sid}_wfa_*.json'), reverse=True)
            if not files:
                continue
            # 取第一个有 oos_curve 数据的文件
            latest_file = None
            for f in files:
                d_tmp = json_mod.load(open(f))
                if d_tmp.get('oos_curve'):
                    latest_file = f
                    break
            if latest_file is None:
                continue
            data = json_mod.load(open(latest_file))
            oos_curve = data.get('oos_curve', [])
            if not oos_curve:
                continue
            data_map = {p['date']: p['value'] for p in oos_curve}
            aligned_data = []
            last_v = 100000.0
            for d in sorted_dates:
                if d in data_map:
                    last_v = data_map[d]
                aligned_data.append(round(last_v - 100000.0, 2))
            aligned_strategies[sid] = {
                'name': names.get(sid, sid),
                'color': colors.get(sid, '#888'),
                'data': aligned_data,
                'final_pnl_pct': data.get('oos_metrics', {}).get('total_return_pct', 0),
                'final_value': data.get('oos_metrics', {}).get('final_value', 0),
            }

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'dates': sorted_dates,
                'initial_capital': 100000.0,
                'strategies': aligned_strategies,
                'kpi': {
                    'total_days': len(sorted_dates),
                    'first_date': sorted_dates[0] if sorted_dates else None,
                    'last_date': sorted_dates[-1] if sorted_dates else None,
                    'note': '样本外 P&L 折线（拼接 13 个 test 窗口，复利累计）',
                }
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/param_stability')
def dashboard_param_stability():
    """参数稳定性监控 (P9-D v1.0, 2026-07-03)

    读 ~/.hermes/outputs/wfa/{sid}_wfa_*.json 的 param_stability 字段，
    返回 4 策略各自的"参数分布 + 稳定性评分"。

    核心思想：
      - 在 13 个训练窗口上跑"假设参数网格"，每个窗口选出"该窗口最优参数"
      - 看 13 个窗口的最优参数分布：稳定/跳变？
      - 稳定性评分：0-1，越接近 1 越稳定
      - 解读：哪些策略的参数"皮实"，哪些"脆弱"

    Returns:
        {
            'strategies': {
                'lightning': {
                    'param_name': 'm_days',
                    'current_value': 3,
                    'grid_values': [3, 5, 7],
                    'mode': 3,
                    'mode_count': 11,
                    'median': 3.0,
                    'std': 1.20,
                    'stability_score': 0.700,
                    'interpretation': '较稳定（11/13 窗口选同一值）',
                    'best_params_by_window': [7, 3, 3, 3, ...],
                    'distribution': {'3': 11, '5': 1, '7': 1},
                    'current_is_mode': True,
                },
                ...
            },
            'kpi': {
                'run_date': '2026-07-03',
                'window_count': 13,
                'note': 'P9-D 假设参数网格（不动策略代码）'
            }
        }
    """
    try:
        import json as json_mod
        wfa_dir = Path('/Users/junze/.hermes/outputs/wfa')

        # 各策略的当前"硬编码"参数（用于对比）
        current_params = {
            'lightning': 3,     # m_days=3 (R4_m3)
            'zhuidian': 3.8,    # score_max=3.8 (R17_score_max_38)
            'r32': 50.0,        # breadth_threshold_pct=50.0 (R35_crowdness)
            'sanhe': 5,         # holdings_count=5 (R25_vol_weight)
            'qixing': 0.253,    # breadth_threshold=0.253 (R121_breadth_0.253_holdings_2)
        }

        result = {}
        for sid in ['lightning', 'zhuidian', 'r32', 'sanhe', 'qixing']:  # P9-D qixing WFA (2026-07-04)
            files = sorted(wfa_dir.glob(f'{sid}_wfa_*.json'), reverse=True)
            if not files:
                continue
            with open(files[0]) as f:
                data = json_mod.load(f)
            ps = data.get('param_stability')
            if not ps or not ps.get('valid'):
                continue

            result[sid] = {
                'param_name': ps.get('param_name'),
                'current_value': current_params.get(sid),
                'grid_values': ps.get('grid_values', []),
                'mode': ps.get('mode'),
                'mode_count': ps.get('mode_count'),
                'median': ps.get('median'),
                'std': ps.get('std'),
                'stability_score': ps.get('stability_score'),
                'interpretation': ps.get('interpretation'),
                'best_params_by_window': ps.get('best_params_by_window', []),
                'distribution': ps.get('distribution', {}),
                'current_is_mode': ps.get('mode') == current_params.get(sid),
            }

        # 取最近一份 WFA 文件的日期作为 run_date
        any_files = sorted(wfa_dir.glob('*_wfa_*.json'), reverse=True)
        run_date = 'unknown'
        if any_files:
            run_date = any_files[0].stem.split('_wfa_')[-1]

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'strategies': result,
                'kpi': {
                    'run_date': run_date,
                    'window_count': 13,
                    'note': 'P9-D 假设参数网格（不动策略代码）',
                }
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/ab_comparison')
def dashboard_ab_comparison():
    """P9-D A/B 对照（grid_mode vs hardcode） (2026-07-04)

    读 ~/.hermes/outputs/p9/ab_comparison/{date}.json（默认 latest_summary.json），
    返回 4 策略的「grid mode 实际生效参数」vs「原 hardcode 参数」P&L 对比。

    Query params:
        date (str, optional): 指定日期 YYYY-MM-DD；不传则用 latest_summary.json
        days (int, optional): 返回最近 N 天的时序数据；不传或 0 则只返回单日汇总

    核心用途：
      - 验证 grid mode 优化是否真的有效（vs WFA 单纯过拟合）
      - 单策略层面看 winner（grid_mode / baseline / tie）
      - 总和层面看 grid_mode 是否整体优于 baseline
    """
    try:
        import json as json_mod
        ab_dir = Path('/Users/junze/.hermes/outputs/p9/ab_comparison')
        if not ab_dir.exists():
            return jsonify({
                'code': 0, 'message': 'no_ab_data',
                'data': {'date': None, 'strategies': {}, 'totals': {}, 'kpi': {}, 'history': []}
            })

        requested_date = request.args.get('date')
        try:
            days = int(request.args.get('days', '0') or '0')
        except ValueError:
            days = 0

        if requested_date:
            target_path = ab_dir / f"{requested_date}.json"
            if not target_path.exists():
                return jsonify({
                    'code': 1, 'message': f'no_ab_data_for_{requested_date}',
                    'data': None
                }), 404
        else:
            target_path = ab_dir / 'latest_summary.json'
            if not target_path.exists():
                return jsonify({
                    'code': 0, 'message': 'no_ab_data',
                    'data': {'date': None, 'strategies': {}, 'totals': {}, 'kpi': {}, 'history': []}
                })

        with open(target_path) as f:
            summary = json_mod.load(f)

        # KPI 统计
        kpi = {'grid_wins': 0, 'baseline_wins': 0, 'ties': 0, 'note': 'P9-D A/B 对照'}
        for sid, data in summary.get('strategies', {}).items():
            w = data.get('diff', {}).get('winner')
            if w == 'grid_mode':
                kpi['grid_wins'] += 1
            elif w == 'baseline':
                kpi['baseline_wins'] += 1
            else:
                kpi['ties'] += 1

        result = {
            'date': summary.get('date'),
            'first_run_timestamp': summary.get('first_run_timestamp'),
            'last_update_timestamp': summary.get('last_update_timestamp'),
            'strategies': summary.get('strategies', {}),
            'totals': summary.get('totals', {}),
            'kpi': kpi,
            'history': [],
        }

        # 时序数据
        if days > 0:
            history_files = sorted(ab_dir.glob('2026-*.json'), reverse=True)[:days]
            history = []
            for hf in reversed(history_files):
                try:
                    with open(hf) as fp:
                        h = json_mod.load(fp)
                    hkpi = {'grid_wins': 0, 'baseline_wins': 0, 'ties': 0}
                    for sid, data in h.get('strategies', {}).items():
                        w = data.get('diff', {}).get('winner')
                        if w == 'grid_mode':
                            hkpi['grid_wins'] += 1
                        elif w == 'baseline':
                            hkpi['baseline_wins'] += 1
                        else:
                            hkpi['ties'] += 1
                    history.append({
                        'date': h.get('date'),
                        'diff_sum': h.get('totals', {}).get('diff_sum', 0),
                        'grid_mode_cumulative_sum': h.get('totals', {}).get('grid_mode_cumulative_sum', 0),
                        'baseline_cumulative_sum': h.get('totals', {}).get('baseline_cumulative_sum', 0),
                        'strategies_count': h.get('totals', {}).get('strategies_count', 0),
                        'kpi': hkpi,
                    })
                except Exception:
                    continue
            result['history'] = history

        return jsonify({'code': 0, 'message': 'success', 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/strategies_flow_summary')
def dashboard_strategies_flow_summary():
    """5 策略 daily log 总览 (P4 v1.0, 2026-06-27)

    返回 5 策略的 daily log 状态汇总（满足核心 KPI「5 策略各自完整逐日模拟交易记录」）。

    Returns:
        {
            'strategies': {
                'qixing': {'name': '七星', 'days': 14, 'sessions': 25, 'note': '真实 daily run'},
                'r32': {'name': '三驾马车', 'days': 14, 'sessions': 28, 'note': '历史反推 daily log'},
                ...
            },
            'core_kpi_status': {
                'all_have_daily_log': True,
                'total_days': 14,
                'total_sessions': 137,
            }
        }
    """
    try:
        names = {
            'qixing': '七星策略',
            'r32': '三驾马车',
            'zhuidian': '追电策略',
            'sanhe': '三合策略',
            'lightning': '闪电策略',
            'goldcombo': '黄金组合A',
        }
        colors = {
            'qixing': '#3b82f6',
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }
        result = {}
        total_days = 0
        total_sessions = 0

        for sid in names.keys():
            work_log_dir = Path(f'/Users/junze/.hermes/work_logs/{sid}')
            if not work_log_dir.exists():
                result[sid] = {
                    'name': names[sid],
                    'color': colors[sid],
                    'days': 0,
                    'sessions': 0,
                    'note': '无 daily log',
                }
                continue

            files = sorted(work_log_dir.glob(f'{sid}_*.json'))
            days_count = len(files)
            sessions_count = 0
            for f in files:
                with open(f) as fp:
                    for line in fp:
                        if line.strip():
                            sessions_count += 1
            note = '真实 daily run' if sid == 'qixing' else '真实 backtest 切片 (P5)'
            result[sid] = {
                'name': names[sid],
                'color': colors[sid],
                'days': days_count,
                'sessions': sessions_count,
                'note': note,
            }
            total_days += days_count
            total_sessions += sessions_count

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'strategies': result,
                'core_kpi_status': {
                    'all_have_daily_log': all(
                        Path(f'/Users/junze/.hermes/work_logs/{sid}').exists() and
                        len(list(Path(f'/Users/junze/.hermes/work_logs/{sid}').glob(f'{sid}_*.json'))) > 0
                        for sid in names.keys()
                    ),
                    'total_days': total_days,
                    'total_sessions': total_sessions,
                    'kpi': '5 策略各自独立的完整逐日模拟交易记录',
                }
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/ratchet_evolution')
def dashboard_ratchet_evolution():
    """5 策略 ratchet 演化 v1.0 (2026-06-27 P3-2)

    按时间排序 signals/{sid}_*.json，显示每个策略的参数迭代过程
    （每次 ratchet 的版本号 + total_return + 日期）。

    Returns:
        {
            'strategies': {
                'qixing': {
                    'name': '七星策略',
                    'color': '#3b82f6',
                    'history': [
                        {'date': '2026-06-12', 'version': 'R120_...', 'total_return': 0,
                         'annualized_return': 21.17, 'sharpe': 1.32, 'max_drawdown': -10.49},
                        ...
                    ]
                }
            }
        }
    """
    try:
        colors = {
            'qixing': '#3b82f6',
            'r32': '#10b981',
            'zhuidian': '#f59e0b',
            'sanhe': '#a855f7',
            'lightning': '#facc15',
            'goldcombo': '#ef4444',
        }
        names = {
            'qixing': '七星策略',
            'r32': '三驾马车',
            'zhuidian': '追电策略',
            'sanhe': '三合策略',
            'lightning': '闪电策略',
            'goldcombo': '黄金组合A',
        }

        result = {}
        for sid in colors.keys():
            history = []
            files = sorted(SIGNALS_DIR.glob(f'{sid}_*.json'))
            for f in files:
                try:
                    with open(f) as fp:
                        d = json.load(fp)
                    history.append({
                        'date': d.get('date', f.stem.split('_', 1)[1]),
                        'version': d.get('version', '?'),
                        'total_return': d.get('total_return', 0),
                        'annualized_return': d.get('annualized_return', 0),
                        'sharpe': d.get('sharpe', 0),
                        'max_drawdown': d.get('max_drawdown', 0),
                        'trades': d.get('trades', 0),
                        'filename': f.name,
                    })
                except Exception:
                    continue
            # 按日期排序
            history.sort(key=lambda x: x['date'])
            result[sid] = {
                'name': names[sid],
                'color': colors[sid],
                'iterations_count': len(history),
                'history': history,
            }

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {'strategies': result}
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500

@app.route('/api/v1/<sid>/positions')
def get_positions(sid):
    strategies_config = load_strategies()
    if sid not in strategies_config:
        return jsonify({'code': 404, 'message': f'策略 {sid} 不存在', 'data': None})
    
    signal = get_latest_signal(sid)
    if not signal:
        return jsonify({'code': 0, 'message': 'success', 'data': {'positions': [], 'total_asset': strategies_config[sid].get('initial_capital', 10000)}})
    
    init_cap = strategies_config[sid].get('initial_capital', 10000)
    tr = signal.get('total_return', 0)
    total_asset = round(init_cap * (1 + tr / 100), 2)
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'positions': signal.get('positions', []),
            'total_asset': total_asset
        }
    })

@app.route('/api/v1/<sid>/today_actions')
def get_today_actions(sid):
    strategies_config = load_strategies()
    if sid not in strategies_config:
        return jsonify({'code': 404, 'message': f'策略 {sid} 不存在', 'data': None})
    
    signal = get_latest_signal(sid)
    if not signal:
        return jsonify({'code': 0, 'message': 'success', 'data': {'action': 'NO_DATA', 'trades': []}})
    
    action = signal.get('action', {})
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'action': action.get('action', 'HOLD'),
            'target': action.get('target', ''),
            'detail': action.get('detail', ''),
            'trades': action.get('trades', [])
        }
    })

@app.route('/api/v1/<sid>/status')
def get_status(sid):
    strategies_config = load_strategies()
    if sid not in strategies_config:
        return jsonify({'code': 404, 'message': f'策略 {sid} 不存在', 'data': None})
    
    signal = get_latest_signal(sid)
    status = 'running' if signal else 'waiting'
    version = strategies_config[sid].get('version', 'latest')
    return jsonify({'code': 0, 'message': 'success', 'data': {'status': status, 'version': version}})

@app.route('/api/v1/health')
def health():
    return jsonify({'code': 0, 'message': 'healthy', 'data': {'status': 'ok'}})

# 托管前端静态文件（Docker 单端口部署）
from flask import send_from_directory

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/review')
def review():
    return send_from_directory(BASE_DIR, 'review.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route('/api/v1/alerts/check', methods=['GET', 'POST'])
def alerts_check():
    """运行健康检查，返回检查结果"""
    results = alert_module.run_health_check()
    return jsonify({'code': 0, 'message': 'success', 'data': results})

@app.route('/api/v1/alerts/trigger', methods=['POST'])
def alerts_trigger():
    """手动触发告警（POST body: {title, message, alert_type, force}）"""
    body = request.get_json() or {}
    title = body.get('title', 'manual_alert')
    message = body.get('message', '')
    alert_type = body.get('alert_type', 'warn')
    force = body.get('force', True)
    result = alert_module.alert(title, message, alert_type=alert_type, force=force)
    return jsonify({'code': 0 if result['sent'] else 1, 'message': result['reason'], 'data': result})

@app.route('/api/v1/alerts/history')
def alerts_history():
    """查询告警历史"""
    lines = []
    if alert_module.ALERT_LOG.exists():
        with open(alert_module.ALERT_LOG) as f:
            lines = f.readlines()[-50:]  # 最近 50 条
    history = []
    for line in lines:
        try:
            history.append(json.loads(line))
        except Exception:
            continue
    return jsonify({'code': 0, 'message': 'success', 'data': {'history': history, 'total': len(history)}})

# ====== 后台告警定时任务 ======
def _alert_scheduler():
    """每 5 分钟跑一次健康检查（独立线程）"""
    while True:
        try:
            alert_module.run_health_check()
        except Exception as e:
            print(f'[scheduler] check failed: {e}', file=sys.stderr)
        time.sleep(300)  # 5 分钟

_scheduler_started = False
def start_alert_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    t = threading.Thread(target=_alert_scheduler, daemon=True)
    t.start()
    _scheduler_started = True
    print('[scheduler] alert health check started (interval 5min)')

# ========== 复盘系统 API v1.0 (2026-06-26 P0) ==========

@app.route('/api/v1/review/dates')
def get_review_dates():
    """列出 review/ 目录下所有复盘日期（用于 review.html 下拉框动态填充）

    Returns:
        {
            'dates': ['2026-06-08', '2026-06-12', ...],   # 倒序
            'latest': '2026-06-26',                       # 最新日期
            'count': 6
        }
    """
    try:
        dates = []
        for f in REVIEW_DIR.glob('*.json'):
            try:
                d = f.stem  # '2026-06-08'
                # 简单校验 YYYY-MM-DD
                datetime.strptime(d, '%Y-%m-%d')
                dates.append(d)
            except ValueError:
                continue
        dates.sort(reverse=True)
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': {
                'dates': dates,
                'latest': dates[0] if dates else None,
                'count': len(dates),
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/review/<date>')
def get_review_by_date(date):
    """读取指定日期的复盘 JSON

    Args:
        date: YYYY-MM-DD

    Returns:
        review JSON 内容（若文件不存在返回默认空模板）
    """
    try:
        datetime.strptime(date, '%Y-%m-%d')  # 校验
    except ValueError:
        return jsonify({'code': 1, 'message': f'日期格式错误: {date}', 'data': None}), 400

    path = REVIEW_DIR / f'{date}.json'
    if not path.exists():
        return jsonify({
            'code': 0,
            'message': 'no_data',
            'data': {
                'date': date,
                'exists': False,
                'empty_template': True,
                'summary': {},
                'strategies': {},
                'notes': '',
            }
        })

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['exists'] = True
        data['empty_template'] = False

        # v1.0.1 (2026-06-26) 兼容层: 如果只有 strategies_L2 (v2 schema),
        # 同步生成 strategies (v1 schema) 字段供前端读
        if 'strategies' not in data and 'strategies_L2' in data:
            data['strategies'] = data['strategies_L2']

        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/review/range')
def get_review_range():
    """历史回溯 API v1.0 (2026-06-27 P2-3)

    按类型 + 日期范围返回复盘列表
    Query: ?type=daily|weekly|monthly&start=YYYY-MM-DD&end=YYYY-MM-DD

    Returns:
        {
            'type': 'daily',
            'start': '2026-06-01',
            'end': '2026-06-30',
            'count': 5,
            'reviews': [
                {'date': '2026-06-08', 'type': 'daily', 'data': {...}},
                {'date': '2026-06-12', 'type': 'daily', 'data': {...}},
                ...
            ]
        }
    """
    review_type = request.args.get('type', 'daily')
    start = request.args.get('start', '')
    end = request.args.get('end', '')

    if review_type not in ('daily', 'weekly', 'monthly'):
        return jsonify({'code': 1, 'message': f'不支持的 type: {review_type}', 'data': None}), 400

    try:
        start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
        end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None
    except ValueError as e:
        return jsonify({'code': 1, 'message': f'日期格式错误: {e}', 'data': None}), 400

    # 文件名后缀 + glob 模式
    # 严格按后缀匹配（避免 daily 模式误匹配 weekly/monthly）
    suffix_check = {
        'daily': lambda name: name.endswith('.json') and not name.endswith('_weekly.json') and not name.endswith('_monthly.json'),
        'weekly': lambda name: name.endswith('_weekly.json'),
        'monthly': lambda name: name.endswith('_monthly.json'),
    }[review_type]

    # 收集范围内的文件
    matched = []
    for f in sorted(REVIEW_DIR.glob('*.json')):
        if not suffix_check(f.name):
            continue
        stem = f.stem
        if review_type != 'daily':
            stem = stem.replace(f'_{review_type}', '')
        try:
            d = datetime.strptime(stem, '%Y-%m-%d').date()
        except ValueError:
            continue
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            matched.append({
                'date': d.isoformat(),
                'type': review_type,
                'filename': f.name,
                'data': data,
            })
        except Exception as e:
            matched.append({
                'date': d.isoformat(),
                'type': review_type,
                'filename': f.name,
                'error': str(e),
            })

    matched.sort(key=lambda x: x['date'])

    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'type': review_type,
            'start': start or None,
            'end': end or None,
            'count': len(matched),
            'reviews': matched,
        }
    })


@app.route('/api/v1/review/<date>/notes', methods=['POST'])
def save_review_notes(date):
    """保存指定日期的复盘笔记（追加到 review/{date}.json 的 notes 字段）

    Request body:
        {"notes": "用户笔记内容..."}

    行为：
    - 若 review/{date}.json 不存在 → 创建新文件（带 notes + 编辑时间戳）
    - 若存在 → 合并 notes（保留旧的自动生成内容 + 新用户笔记）
    - 写入 review/{date}.md （便于纯文本查看）
    """
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'code': 1, 'message': f'日期格式错误: {date}', 'data': None}), 400

    body = request.get_json() or {}
    new_notes = body.get('notes', '').strip()

    path = REVIEW_DIR / f'{date}.json'
    md_path = REVIEW_DIR / f'{date}.md'

    # 读现有 JSON（若有）
    existing = {}
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    now = datetime.now().isoformat()
    existing.setdefault('date', date)
    existing.setdefault('summary', {})
    existing.setdefault('strategies', {})

    # 合并笔记：保留 auto_notes + user_notes
    user_notes = existing.get('user_notes', '')
    auto_notes = existing.get('auto_notes', existing.get('notes', ''))

    if new_notes:
        # v1.0: 直接覆盖 user_notes（避免重复保存叠加）
        existing['user_notes'] = new_notes
        existing['notes'] = new_notes if not auto_notes else f"{auto_notes}\n\n--- 用户笔记 ---\n{new_notes}"

    existing['edited_by'] = 'user'
    existing['edited_at'] = now
    existing.setdefault('created_by', existing.get('created_by', 'auto_or_user'))
    existing['created_at'] = existing.get('created_at', now)

    try:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({'code': 1, 'message': f'写入失败: {e}', 'data': None}), 500

    # 同步写入 .md 便于纯文本查看
    # v1.0.1 (2026-06-26): 不覆盖用户已经写过的 md，只在 md 不存在或仅含 stub 时写入
    if not md_path.exists() or md_path.stat().st_size < 200:
        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# 盘后复盘 · {date}\n\n")
                if auto_notes:
                    f.write(f"## 自动生成\n\n{auto_notes}\n\n")
                if new_notes:
                    f.write(f"## 用户笔记\n\n{new_notes}\n\n")
                f.write(f"---\n\n_保存时间: {now}_\n")
        except Exception:
            pass
    else:
        # md 已存在 → 在末尾追加「用户笔记」小节，不覆盖原内容
        try:
            with open(md_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## 用户笔记 ({now})\n\n{new_notes}\n")
        except Exception:
            pass

    return jsonify({
        'code': 0,
        'message': 'saved',
        'data': {
            'date': date,
            'json_path': str(path),
            'md_path': str(md_path) if md_path.exists() else None,
            'notes_length': len(new_notes),
            'edited_at': now,
        }
    })


if __name__ == '__main__':
    SIGNALS_DIR.mkdir(exist_ok=True)
    port = int(os.environ.get('PORT', 8000))
    print(f'Starting server on http://0.0.0.0:{port}')
    print(f'Strategies: {list(load_strategies().keys())}')
    print(f'Signals dir: {SIGNALS_DIR}')
    start_alert_scheduler()
    app.run(host='0.0.0.0', port=port, debug=False)

