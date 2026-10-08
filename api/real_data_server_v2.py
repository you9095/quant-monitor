
# ============================================================
# 后端API板块目录（按功能模块组织）
# ============================================================
#
# 00_工具函数
# 01_策略卡板块
# 02_收益曲线板块
# 03_投资组合板块
# 04_今日交易板块
# 05_回测分析板块
# 06_告警板块
# 07_复盘板块
# 08_系统路由
# ============================================================

#!/usr/bin/env python3
"""
三策略监控面板后端 V2 - 动态策略配置版
支持任意数量策略，通过 config/strategies.json 动态加载
"""
import json
import os
import sys
import random
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path

# ============================================================
# 内存缓存层：启动时加载所有 signals，后续请求直接读内存
# ============================================================
_signals_cache = {}  # {sid_date: signal_dict}
_signals_cache_lock = threading.Lock()

def load_signals_to_cache():
    """启动时加载所有信号文件到内存缓存"""
    signals_dir = Path(__file__).parent.parent / 'signals'
    if not signals_dir.exists():
        return
    count = 0
    for f in signals_dir.glob('*_*.json'):
        try:
            key = f.stem  # e.g. "qixing_2026-09-30"
            _signals_cache[key] = json.loads(f.read_text(encoding='utf-8'))
            count += 1
        except:
            continue
    print(f'[缓存] 已加载 {count} 个信号文件到内存')

def get_all_signals():
    """获取所有信号"""
    return _signals_cache

def refresh_cache():
    """刷新缓存（新信号生成后调用）"""
    with _signals_cache_lock:
        global _signals_cache
        _signals_cache = {}
        load_signals_to_cache()

# 实盘成交数据
sys.path.insert(0, os.path.dirname(__file__))
# 2026-08-03 kimi 独立: 删除 import live_pnl (kimi 自动化交易脚本不属于本监控项目)

# 让 alerts.py 可被导入
sys.path.insert(0, str(Path(__file__).parent))

# 2026-09-12 数据告警引擎 — 就地标注机制
from data_alert_engine import run_alert_engine, get_alerts_summary
import alerts as alert_module
import live_data as live_module
import live_aggregator as live_agg

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
# 实盘数据根目录：默认真实 live-data；UI 走查时用环境变量 QM_LIVE_DATA_DIR
# 指向隔离的虚拟数据目录（ui-mock/live-data），默认行为不变、绝不污染真实账本
LIVE_ROOT = Path(os.environ.get('QM_LIVE_DATA_DIR', str(BASE_DIR / 'live-data')))

WORK_LOG_DIR = Path('/Users/junze/.hermes/work_logs')


# P9 E (2026-07-04): 处理 work_log 后缀（_fusion / _fusion_baseline / _baseline）
# 真实 daily log 主文件优先用 {sid}_{date}.json，没有则用 {sid}_{date}_fusion.json
# 永远跳过 baseline 文件（不进 trend/review API）

# ============================================================
# 板块: 00_工具函数
# ============================================================

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
    # 2026-09-14: 禁止浏览器缓存，确保每次修改后手机端/PC端都能立即看到最新内容
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/v1/strategies')

# ============================================================
# 板块: 01_策略卡板块
# ============================================================

def get_strategies():
    strategies_dict = load_strategies()
    # 转换为数组格式匹配前端 expectations
    strategies = []
    for sid, s in strategies_dict.items():
        s['strategy_id'] = sid
        s['strategy_name'] = s.get('name', sid)
        # 2026-09-11 修复: data_source 默认值为 work_logs（实盘模拟真实日P&L）
        # 弹窗数据源banner需要此字段判断是否为实盘数据
        if not s.get('data_source'):
            s['data_source'] = 'work_logs'
        strategies.append(s)
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {'strategies': strategies}
    })

def build_live_overview():
    """组装实盘视图数据：读取 macOS 从 GitHub 拉取的 live-data/latest/*.json
    这些是 Windows 端真实运行产生的数据；目录为空时返回空状态。"""
    live_dir = LIVE_ROOT / 'latest'
    is_mock = (LIVE_ROOT / '_mock_marker.json').exists()
    strategies = []
    total_asset = 0.0
    total_init = 0.0
    total_pnl = 0.0
    if live_dir.exists():
        for f in sorted(live_dir.glob('*.json')):
            try:
                d = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            init = d.get('initial_capital', 10000) or 10000
            pnl = d.get('live_total_pnl', 0) or 0
            asset = init + pnl
            total_asset += asset
            total_init += init
            total_pnl += pnl
            positions = []
            for pos in d.get('positions', []):
                qty = pos.get('qty', 0) or 0
                if qty <= 0:
                    continue
                cost = pos.get('cost', 0) or 0
                price = pos.get('current_price', cost) or cost
                positions.append({
                    'code': pos.get('code', ''), 'name': pos.get('name', ''),
                    'quantity': qty, 'cost_price': cost, 'current_price': price,
                    'pnl': (price - cost) * qty, 'weight': pos.get('weight', 0)
                })
            action = d.get('action', {}) or {}
            strategies.append({
                'strategy_id': d.get('strategy_id', f.stem),
                'strategy_name': d.get('strategy_name', f.stem),
                'status': 'active',
                'today_action': action.get('type', 'HOLD'),
                'today_pnl': d.get('today_pnl', 0),
                'today_return': d.get('today_return', 0),
                'total_asset': asset,
                'total_return': d.get('live_total_return', 0),
                'total_pnl': pnl,
                'initial_capital': init,
                'live_total_pnl': pnl,
                'live_total_return': d.get('live_total_return', 0),
                'live_days': d.get('live_days', 0),
                'positions': positions,
                'backtest_total_return': None, 'sharpe_ratio': None,
                'max_drawdown': None, 'trades_count': 0,
            })

    has_data = len(strategies) > 0
    if is_mock:
        label = '【UI测试虚拟数据】仅用于界面走查 · 非实盘 / 非回测 / 不接券商'
        note = '面板经 QM_LIVE_DATA_DIR 指向隔离目录 ui-mock，数据为固定种子确定性生成，禁止冒充实盘。'
        nature_label = 'UI测试虚拟数据（隔离，非实盘）'
        nature_key = 'ui_mock'
    elif has_data:
        label = f'实盘运行数据（Windows，{total_asset:.0f} 元）— 不连接任何真实券商'
        note = '来自 Windows 端每日运行引擎，经 GitHub 同步回 macOS；与模拟盘历史数据物理隔离。'
        nature_label = '实盘运行数据（Windows 本机引擎）'
        nature_key = 'live'
    else:
        label = '实盘 — 尚未开始运行，暂无数据'
        note = '实盘数据从 Windows 端每日引擎运行之日起开始记录。macOS 执行 scripts/sync_live_data.py pull 后即可看到 Windows 实盘数据。'
        nature_label = '实盘运行数据（Windows 本机引擎）'
        nature_key = 'live'
    return {
        'data_mode': 'live',
        'data_nature': nature_key,
        'data_nature_label': nature_label,
        'is_ui_mock': is_mock,
        'data_nature_note': note,
        'data_mode_label': label,
        'strategies': strategies,
        'combined': {
            'active_count': len(strategies),
            'initial_capital': total_init,
            'total_return': (total_pnl / total_init * 100) if total_init > 0 else 0,
            'total_asset': total_asset,
            'total_pnl': total_pnl,
        },
        'alerts_summary': {'critical': 0, 'warning': 0, 'info': 0},
        'update_time': datetime.now().isoformat()
    }


# ============================================================
# Mac 端 live-data 自动从 GitHub 同步（只读，ff-only，失败不崩）
# ============================================================
LIVE_SYNC = {'last_ok': None, 'last_attempt': None, 'ok': None,
             'msg': '尚未同步', 'head': None}

def sync_live_data(timeout=90):
    """把 LIVE_ROOT 快进到 origin/master（Windows 上传的最新实盘账本）。
    Mac 端只读不写，用 ff-only，绝不用模拟/回测数据兜底。"""
    if (LIVE_ROOT / '_mock_marker.json').exists():
        LIVE_SYNC['msg'] = 'UI 走查隔离目录，跳过同步'
        return LIVE_SYNC
    if not (LIVE_ROOT / '.git').exists():
        LIVE_SYNC['msg'] = 'live-data 非 git 仓库，跳过自动同步'
        return LIVE_SYNC
    LIVE_SYNC['last_attempt'] = datetime.now().isoformat(timespec='seconds')
    root = str(LIVE_ROOT)
    try:
        for args in (['git', '-C', root, 'fetch', '-q', 'origin', 'master'],
                     ['git', '-C', root, 'merge', '--ff-only', '-q', 'origin/master']):
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            if p.returncode != 0:
                raise RuntimeError((p.stderr or p.stdout or 'git failed').strip()[:200])
        head = subprocess.run(['git', '-C', root, 'rev-parse', '--short', 'HEAD'],
                              capture_output=True, text=True, timeout=15)
        LIVE_SYNC.update(ok=True, msg='已同步到最新',
                         last_ok=LIVE_SYNC['last_attempt'],
                         head=head.stdout.strip())
    except Exception as e:
        LIVE_SYNC.update(ok=False, msg=f'同步失败: {str(e)[:160]}')
        print('[live-sync]', LIVE_SYNC['msg'])
    return LIVE_SYNC

def _live_sync_loop(interval=180):
    while True:
        time.sleep(interval)
        try:
            sync_live_data()
        except Exception as e:
            print('[live-sync loop]', e)

def start_live_sync():
    sync_live_data()  # 启动先拉一次
    threading.Thread(target=_live_sync_loop, daemon=True).start()

# 仅属于模拟盘/回测的端点：实盘模式一律返回"不适用"诚实空态，绝不泄漏回测数字
BACKTEST_ONLY_ENDPOINTS = {
    '/api/v1/dashboard/nav_curves',
    '/api/v1/dashboard/monthly_compare',
    '/api/v1/dashboard/qixing_flow',
    '/api/v1/dashboard/daily_pnl_trend',
    '/api/v1/dashboard/wfa_summary',
    '/api/v1/dashboard/wfa_oos_curve',
    '/api/v1/dashboard/param_stability',
    '/api/v1/dashboard/ab_comparison',
    '/api/v1/dashboard/strategies_flow_summary',
    '/api/v1/dashboard/ratchet_evolution',
}

@app.before_request
def _live_mode_guard():
    try:
        if request.method == 'GET' and request.path in BACKTEST_ONLY_ENDPOINTS \
                and request.args.get('data_mode') == 'live':
            return jsonify({'code': 0, 'message': 'success', 'data': {
                'data_mode': 'live', 'is_ui_mock': False, 'data_nature': 'live',
                'applicable': False,
                'data_nature_label': '实盘模拟不适用 · 该模块为模拟盘 / 回测专属',
                'note': '该图表属于模拟盘 / 回测分析，实盘模拟不产生此类数据；实盘模式已留空，'
                        '不会用任何模拟盘或回测数字代替。真实盈亏 / 成交 / 对账请看实盘对应页面。'}})
    except Exception:
        return None
    return None


@app.route('/api/v1/dashboard/overview')
def get_dashboard_overview():
    data_mode = request.args.get('data_mode', 'simulator')
    # 实盘模式：读取 macOS 从 GitHub 拉下来的 live-data/latest/（Windows 真实运行数据）
    if data_mode == 'live':
        live_data = live_agg.build_overview()
        live_data['sync'] = dict(LIVE_SYNC)
        live_data['trade_health'] = live_agg.build_trade_health()
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': live_data
        })
    strategies_config = load_strategies()
    # C 修复 (2026-08-02): 恢复腾讯行情调用,加 try/except 防崩溃 + 价格缓存
    # TickDB 已写接入骨架(tickdb_client.py),等用户配置 TICKDB_API_KEY 后可切 TickDB 优先
    try:
        fetch_realtime_prices()
    except Exception as e:
        print(f'[实时行情] 获取失败,fallback 到成本价: {e}')

    # 2026-09-12 数据告警引擎：运行全量校验，返回就地标注信息
    alerts_state = run_alert_engine()
    alerts_summary = get_alerts_summary(alerts_state)

    strategies_data = []
    total_asset = 0
    active_count = 0  # 2026-09-20: 仅统计真实在跑每日模拟(live_days>0)的策略
    active_init = 0.0  # 2026-09-21: 在跑策略真实本金合计（5 个 ETF 各 1 万 + 黄金组合A 5 万）

    for sid, cfg in strategies_config.items():
        signal = get_latest_signal(sid)
        init_cap = cfg.get('initial_capital', 10000)
        holdings = []

        # 2026-09-20 真实性根治: 仅 live_days>0 才算"在跑真实每日模拟"。
        # 回测收益(backtest_total_return)绝不折算成实盘盈亏/资产——黄金组合A策略只有棘轮回测、live_days=0。
        live_days_cnt = (signal.get('live_days', 0) or 0) if signal else 0
        live_active = live_days_cnt > 0
        if signal:
            positions = signal.get('positions', [])
            # P0 修复 (2026-07-22): 改用真实累计盈亏 + 真实 qty + 真实成本价
            live_total_pnl = signal.get('live_total_pnl', 0) or 0
            if live_active:
                asset = init_cap + live_total_pnl  # 真实总资产 = 本金 + 真实累计盈亏
            else:
                asset = 0  # 未启动每日模拟 → 不持有实盘资产, 留空

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

            if live_active:
                total_asset += asset
                active_count += 1
                active_init += init_cap
        else:
            asset = 0
            cash = 0
        init_cap = cfg.get('initial_capital', 10000)
        # P0 修复 (2026-07-22): 优先从 live_total_return 读, fallback 到 total_return, 避免全是 0
        # 2026-08-14 主 agent 接管修复: 加 backtest_total_return 兜底 (黄金组合A 实盘未启动)
        if signal and live_active:
            # 2026-09-20: 实盘收益只取 live/total_return; 不再用 backtest_total_return 兜底冒充
            raw_tr = (signal.get('live_total_return', 0) or signal.get('total_return', 0) or 0)
            # 2026-09-21: signal 显式 return_unit='percent' 时直接信任, 不用"绝对值<1 即小数"启发式
            tr = float(raw_tr) if signal.get('return_unit') == 'percent' else live_module._normalize_return_pct(raw_tr)
        else:
            tr = 0  # 未启动每日模拟 → 实盘收益留空; 回测值仅存于 backtest_total_return 字段
        # 年化: 用 live_total_return × (252 / live_days) 估算
        # 2026-09-30: live_days < 120 (约半年) 时不计算年化 — 样本不足外推无统计意义
        # (如74天涨143%→年化489%严重误导; 需至少半年跨越完整市场周期才有参考价值)
        live_days = signal.get('live_days', 252) if signal else 252
        live_days = live_days if live_days and live_days > 0 else 252
        if live_active and live_days >= 120:
            ann_return = round(tr * (252 / live_days), 2)
            if signal.get('annualized_return'):
                ann_return = signal.get('annualized_return')
        else:
            ann_return = None
        # 三层标签：version + data_period + caliber
        # TC-DT-05 修复：优先从 config/strategies.json 读取，signal 作为兜底
        # 确保 version/data_period/caliber 100% 对应 config，而非 signal file
        version_tag = cfg.get('version', 'latest')  # 始终从 config 读
        data_period = cfg.get('data_period', '未指定')  # 始终从 config 读
        caliber = cfg.get('caliber', '未指定')  # 始终从 config 读
        # 占位标记：signal 文件含 _placeholder 时显式提示
        is_placeholder = bool(signal and signal.get('_placeholder'))
        # 2026-09-20: live_days=0(仅有回测、未启动每日模拟) → not_started, 不冒充"运行中"
        if is_placeholder:
            status_label = 'placeholder'
        elif live_active:
            status_label = 'running'
        elif signal:
            status_label = 'not_started'
        else:
            status_label = 'waiting'
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
            'initial_capital': (signal.get('initial_capital') if live_active else 0) if signal else 0,
            # 回测保留字段
            'backtest_total_return': signal.get('backtest_total_return') if signal else None,
            'position_ratio': 1.0 if live_active else 0.0,
            'cash': round(cash, 2),  # P0 修复: 用真实 asset - 当前持仓市值, 不再用初始资金
            'holdings': holdings,
            # P0 修复 (2026-07-22): 优先从 backtest_* 读, 没有再 fallback
            'sharpe_ratio': (signal.get('backtest_sharpe', 0) or 0) if (signal and live_active) else 0,
            'max_drawdown': (signal.get('backtest_max_drawdown', 0) or 0) if (signal and live_active) else 0,
            'trades_count': (signal.get('backtest_trades', 0) or 0) if (signal and live_active) else 0,
            # 三层标签
                    'version_tag': version_tag,
                    'data_period': data_period,
                    'caliber': caliber,
                    'config_caliber': cfg.get('caliber', '未指定'),  # 2026-09-02: 显式从 config 读，避免 signal.caliber 遮蔽
                    'config_caliber_full': cfg.get('caliber_full', cfg.get('caliber', '未指定')),  # 2026-08-31: 完整8段策略详情
                    # 2026-09-12 修复: 使用信号文件真实日期, 不再强制今日, 让前端正确显示数据陈旧警告
                    'signal_date': signal.get('date', signal.get('latest_signal_date', datetime.now().strftime('%Y-%m-%d'))) if signal else datetime.now().strftime('%Y-%m-%d'),
                    # 2026-09-12 数据告警：就地标注，包含异常类型、消息、首次发现日期
                    'alerts': alerts_state.get(sid, {}),
        })
    
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {
            'data_mode': 'simulator',
            'data_nature': 'simulator',
            'data_nature_label': '模拟盘数据（simulator）',
            'data_nature_note': '以下所有收益率、盈亏、资产均为模拟盘（虚拟成交）数据，非真实实盘交易结果。回测数据（backtest）仅用于策略验证，不代表未来收益。',
            'strategies': strategies_data,
            'combined': {
                # 组合按各在跑策略真实本金合计（6 策略各 1 万）
                'active_count': active_count,
                'initial_capital': round(active_init, 2),
                'total_return': round((total_asset - active_init) / active_init * 100, 2) if active_init else 0,
                'total_asset': round(total_asset, 2)
            },
            # 数据告警摘要
            'alerts_summary': alerts_summary,
            'update_time': datetime.now().isoformat()
        }
    })


# ============================================================
# 板块: 03_子页面API（盈亏历史/买卖记录/对账单）
# ============================================================

@app.route('/api/v1/dashboard/pnl_history')
def api_pnl_history():
    """盈亏历史：实盘模式从 live-data 聚合真实账户每日净值（扁平契约）；
    模拟盘为信号回测，不进行真实撮合、不记录现金/持仓/账户盈亏，给诚实空态。"""
    strategy = request.args.get('strategy', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    data_mode = request.args.get('data_mode', 'simulator')

    if data_mode == 'live':
        return jsonify(live_agg.build_pnl_history(strategy, start, end))

    return jsonify({
        'history': [], 'count': 0, 'data_mode': 'simulator',
        'is_ui_mock': False, 'data_nature': 'simulator',
        'data_nature_label': '模拟盘（信号回测）',
        'note': '模拟盘只产出买卖信号与回测收益，不进行真实撮合，不记录现金 / 持仓 / 账户盈亏。真实每日净值请切换到「实盘模拟」。',
    })


@app.route('/api/v1/dashboard/trades')
def api_trades():
    """买卖记录：实盘模式从 live-data 成交流水聚合真实成交（扁平契约）；
    模拟盘为信号回测，无真实成交，给诚实空态。支持 strategy/action/start/end。"""
    strategy = request.args.get('strategy', '')
    action = request.args.get('action', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    data_mode = request.args.get('data_mode', 'simulator')

    if data_mode == 'live':
        return jsonify(live_agg.build_trades(strategy, action, start, end))

    return jsonify({
        'trades': [], 'count': 0, 'data_mode': 'simulator',
        'is_ui_mock': False, 'data_nature': 'simulator',
        'data_nature_label': '模拟盘（信号回测）',
        'note': '模拟盘只产出买卖信号，不进行真实撮合，因此没有成交流水、佣金 / 印花税 / 滑点与真实账单。真实买卖记录请切换到「实盘模拟」。',
    })


@app.route('/api/v1/dashboard/reconciliation')
def api_reconciliation():
    """对账单：实盘模式从 live-data 聚合资金/持仓/成交的自洽核对（扁平契约）；
    模拟盘为信号回测，无现金/持仓/成交可对账，给诚实空态。支持 strategy/start/end。"""
    strategy = request.args.get('strategy', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    data_mode = request.args.get('data_mode', 'simulator')

    if data_mode == 'live':
        return jsonify(live_agg.build_reconciliation(strategy, start, end))

    return jsonify({
        'per_strategy': {}, 'tolerance': 0.01, 'overall_match': False,
        'data_mode': 'simulator', 'is_ui_mock': False,
        'data_nature': 'simulator', 'data_nature_label': '模拟盘（信号回测）',
        'note': '模拟盘不进行真实撮合，没有现金 / 持仓 / 成交流水可对账。真实资金与持仓核对请切换到「实盘模拟」。',
    })


@app.route('/api/v1/dashboard/nav_curves')

# ============================================================
# 板块: 02_收益曲线板块
# ============================================================

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
    # 实盘模式：从 live-data 聚合真实每日净值曲线（不再返回写死空态）
    if request.args.get('data_mode') == 'live':
        return jsonify({'code': 0, 'message': 'success',
                        'data': live_agg.build_live_curves()})
    try:
        data = live_module.get_live_curves()
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/portfolio_summary')

# ============================================================
# 板块: 03_投资组合板块
# ============================================================

def dashboard_portfolio_summary():
    """组合总览：总资金 / 初始资金 / 总盈亏 / 各策略分项"""
    # 实盘模式：从 live-data 聚合真实组合总览（不再返回写死零值）
    if request.args.get('data_mode') == 'live':
        return jsonify({'code': 0, 'message': 'success',
                        'data': live_agg.build_portfolio_summary()})
    try:
        data = live_module.get_portfolio_summary()
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/today_actions_all')

# ============================================================
# 板块: 04_今日交易板块
# ============================================================

def dashboard_today_actions_all():
    """今日交易流程（五策略汇总）"""
    # 实盘模式：从 live-data 聚合当日真实成交动作
    if request.args.get('data_mode') == 'live':
        return jsonify({'code': 0, 'message': 'success',
                        'data': live_agg.build_today_actions()})
    try:
        data = live_module.get_today_actions()
        # 2026-09-12 修复: 不再强制 signal_date = today, 使用信号文件真实日期
        # 原注释: 2026-08-09: 强制 signal_date = today, 避免前端 isStrategyActive 过期过滤
        # 修复原因: 强制今日掩盖了真实的数据陈旧问题, 应该让前端正确显示警告
        return jsonify({'code': 0, 'message': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'message': str(e), 'data': None}), 500


@app.route('/api/v1/dashboard/monthly_compare')

# ============================================================
# 板块: 05_回测分析板块
# ============================================================

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
        # 2026-09-20 数据真实性根治:
        #   - session 用 endswith 兼容 fusion_afternoon/fusion_morning (qixing 走 fusion 切片)
        #   - 同一日期 _fusion 优先于普通日志(普通日志可能是单日直跑、total=0)
        #   - 只接受含真实 daily_pnl session 的日志; goldcombo(黄金组合A)是棘轮回测报告(无 session),
        #     绝不用 lines[0] 兜底把回测报告当每日日志 → 否则被填一串 0 假装在运行
        strategy_files = {}  # sid -> {date: pnl}
        all_dates = set()
        for sid in names.keys():
            sid_dir = WORK_LOG_DIR / sid
            date_pnl = {}   # date -> (is_fusion, pnl)
            if sid_dir.exists():
                for log_file in sorted(sid_dir.glob(f'{sid}_2026-*.json')):
                    if is_baseline_log(log_file.name, sid):
                        continue
                    date_str = extract_date_from_filename(log_file.name, sid)
                    try:
                        with open(log_file) as f:
                            lines = [json.loads(l) for l in f if l.strip()]
                    except Exception:
                        continue  # 非 JSONL(如 goldcombo 棘轮回测 pretty JSON) 直接跳过
                    afternoon = next((l for l in lines if str(l.get('session','')).endswith('afternoon')), None)
                    morning = next((l for l in lines if str(l.get('session','')).endswith('morning')), None)
                    target = afternoon or morning
                    if not target or not isinstance(target.get('daily_pnl'), dict):
                        continue  # 无真实每日 session(回测报告/占位) → 不计入
                    is_fusion = '_fusion' in log_file.name
                    # 2026-09-20: 同时取引擎 total(当日盈亏) 与 cumulative(累计盈亏),
                    # cumulative 直接来自回测引擎、与 live_curves/卡片完全同口径,
                    # 不再由后端逐日累加 total(每日独立切片, 累加会与引擎累计值产生偏差)
                    day_total = target['daily_pnl'].get('total', 0) or 0
                    day_cum = target['daily_pnl'].get('cumulative')
                    prev = date_pnl.get(date_str)
                    if prev is None or (is_fusion and not prev[0]):
                        date_pnl[date_str] = (is_fusion, day_total, day_cum)
            # 仅有真实每日数据的策略才纳入, 并贡献交易日历
            if date_pnl:
                strategy_files[sid] = {d: (v[1], v[2]) for d, v in date_pnl.items()}
                all_dates.update(date_pnl.keys())

        # 2) 对齐日期：取最近 N 天有数据的日期（全部为真实交易日, 周末/缺失日不在此集合）
        sorted_dates = sorted(all_dates)
        if len(sorted_dates) > days:
            sorted_dates = sorted_dates[-days:]

        # 3) 对每个【有真实每日数据】的策略输出序列; 无每日数据(如 goldcombo)不输出、不补 0
        strategies_data = {}
        for sid in names.keys():
            if sid not in strategy_files:
                continue  # 黄金组合A策略未接入每日模拟 → 留空, 不画 0 线
            data_map = strategy_files[sid]
            # 缺失交易日一律 null(图表断线留空), 不补 0、不前向填充(禁止假数据)
            if cumulative:
                # 累计模式: 直接采用引擎 cumulative 字段(与收益曲线/策略卡同口径)
                data_series = [
                    round(data_map[d][1], 2) if (d in data_map and data_map[d][1] is not None) else None
                    for d in sorted_dates
                ]
            else:
                # 单日模式: 引擎当日盈亏 total
                data_series = [
                    round(data_map[d][0], 2) if d in data_map else None
                    for d in sorted_dates
                ]

            strategies_data[sid] = {
                'name': names[sid],
                'color': colors[sid],
                'data': data_series,
            }

        # 4) KPI 状态（只统计有真实每日数据的策略）
        all_have_data = len(strategies_data) > 0

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
        # 2026-09-20 fix: daily_runner 把 winner 写在 diff.winner（非顶层），
        # 相等时原代码还误判 baseline；改为直接依据 grid/baseline 累计值判定，最可靠。
        def _ab_winner(data):
            gm = (data.get('grid_mode') or {}).get('cumulative')
            bl = (data.get('baseline') or {}).get('cumulative')
            if gm is not None and bl is not None:
                if gm > bl:
                    return 'grid_mode'
                if bl > gm:
                    return 'baseline'
                return 'tie'
            return data.get('winner') or (data.get('diff') or {}).get('winner')
        kpi = {'grid_wins': 0, 'baseline_wins': 0, 'ties': 0, 'note': 'P9-D A/B 对照'}
        for sid, data in summary.get('strategies', {}).items():
            w = _ab_winner(data)
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
                        gm = (data.get('grid_mode') or {}).get('cumulative')
                        bl = (data.get('baseline') or {}).get('cumulative')
                        if gm is not None and bl is not None:
                            w = 'grid_mode' if gm > bl else ('baseline' if bl > gm else 'tie')
                        else:
                            w = data.get('winner') or (data.get('diff') or {}).get('winner')
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
    if request.args.get('data_mode') == 'live':
        return jsonify({'code': 0, 'message': 'success',
                        'data': live_agg.build_positions(sid)})
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
    if request.args.get('data_mode') == 'live':
        ta = live_agg.build_today_actions()
        item = next((x for x in ta.get('strategies', [])
                     if x.get('strategy_id') == sid), None)
        if not item:
            return jsonify({'code': 0, 'message': 'success',
                            'data': {'action': 'NO_DATA', 'trades': []}})
        trades = item.get('trades', [])
        return jsonify({'code': 0, 'message': 'success', 'data': {
            'action': item.get('action', 'HOLD'),
            'target': (trades[0].get('code', '') if trades else ''),
            'detail': '', 'trades': trades}})
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
    if request.args.get('data_mode') == 'live':
        return jsonify({'code': 0, 'message': 'success',
                        'data': live_agg.build_status(sid)})
    strategies_config = load_strategies()
    if sid not in strategies_config:
        return jsonify({'code': 404, 'message': f'策略 {sid} 不存在', 'data': None})
    
    signal = get_latest_signal(sid)
    status = 'running' if signal else 'waiting'
    version = strategies_config[sid].get('version', 'latest')
    return jsonify({'code': 0, 'message': 'success', 'data': {'status': status, 'version': version}})

@app.route('/api/v1/health')

# ============================================================
# 板块: 08_系统路由
# ============================================================

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

# ============================================================
# 板块: 06_告警板块
# ============================================================

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

# ============================================================
# 板块: 07_复盘板块
# ============================================================

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
    load_signals_to_cache()  # 启动时加载信号到内存缓存
    start_alert_scheduler()
    start_live_sync()        # 启动即从 GitHub 拉取最新实盘账本，之后每 180s 自动同步
    app.run(host='0.0.0.0', port=port, debug=False)

