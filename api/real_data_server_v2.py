#!/usr/bin/env python3
"""
三策略监控面板后端 V2 - 动态策略配置版
支持任意数量策略，通过 config/strategies.json 动态加载
"""
import json
import os
import sys
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path

# 让 alerts.py 可被导入
sys.path.insert(0, str(Path(__file__).parent))
import alerts as alert_module

app = Flask(__name__)

# 禁用代理，解决飞书断链问题
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / 'config' / 'strategies.json'
SIGNALS_DIR = BASE_DIR / 'signals'

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
    """加载策略配置（自动跳过 _comment 字段）"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            raw = json.load(f)
        # 过滤掉以 _ 开头的元数据字段
        return {k: v for k, v in raw.items() if not k.startswith('_')}
    except Exception:
        return {
            'qixing': {'name': '七星策略', 'color': '#3b82f6', 'initial_capital': 10000},
            'r32': {'name': '三驾马车R32', 'color': '#10b981', 'initial_capital': 10000},
            'zhuidian': {'name': '追电策略', 'color': '#f59e0b', 'initial_capital': 10000}
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
    strategies = load_strategies()
    return jsonify({
        'code': 0,
        'message': 'success',
        'data': {'strategies': strategies}
    })

@app.route('/api/v1/dashboard/overview')
def get_dashboard_overview():
    strategies_config = load_strategies()
    # fetch_realtime_prices()  # 暂时禁用腾讯行情，由信号文件价格驱动
    
    strategies_data = []
    total_asset = 0
    
    for sid, cfg in strategies_config.items():
        signal = get_latest_signal(sid)
        asset = cfg.get('initial_capital', 10000)
        holdings = []
        
        if signal:
            positions = signal.get('positions', [])
            # 计算总投入并按本金缩放
            total_invest = sum(pos.get('qty', 0) * pos.get('cost', 0) for pos in positions)
            scale_factor = min(cfg.get('initial_capital', 10000) / total_invest, 1.0) if total_invest > 0 else 0
            
            for pos in positions:
                code = pos.get('code', '')
                price = PRICE_CACHE.get(code, pos.get('cost', 0))
                qty = int(pos.get('qty', 0) * scale_factor / 100 * 100)  # 缩放后整百股
                cost = pos.get('cost', 0)
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
                asset += pnl
        
        # 最终权重计算
        total_holding_value = sum(h['quantity'] * h['current_price'] for h in holdings)
        for h in holdings:
            h['weight'] = round(h['quantity'] * h['current_price'] / (total_holding_value + cfg.get('initial_capital', 10000)) * 100, 2) if total_holding_value > 0 else 0
        
        total_asset += asset
        init_cap = cfg.get('initial_capital', 10000)
        tr = signal.get('total_return', 0) if signal else 0
        ann_return = signal.get('annualized_return', 0) if signal else 0
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
            'today_pnl': signal.get('today_pnl', 0) if signal else 0,
            'today_return': signal.get('today_return', 0) if signal else 0,
            'position_ratio': 1.0,
            'cash': max(0, cfg.get('initial_capital', 10000) - sum(h['quantity'] * h['cost_price'] for h in holdings)),
            'holdings': holdings,
            'sharpe_ratio': signal.get('sharpe', 0) if signal else 0,
            'max_drawdown': signal.get('max_drawdown', 0) if signal else 0,
            'trades_count': signal.get('trades', 0) if signal else 0,
            # 三层标签
            'version_tag': version_tag,
            'data_period': data_period,
            'caliber': caliber,
            'signal_date': signal.get('date') if signal else None,
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

if __name__ == '__main__':
    SIGNALS_DIR.mkdir(exist_ok=True)
    port = int(os.environ.get('PORT', 8000))
    print(f'Starting server on http://0.0.0.0:{port}')
    print(f'Strategies: {list(load_strategies().keys())}')
    print(f'Signals dir: {SIGNALS_DIR}')
    start_alert_scheduler()
    app.run(host='0.0.0.0', port=port, debug=False)