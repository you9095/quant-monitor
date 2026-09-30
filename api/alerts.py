#!/usr/bin/env python3
"""
三策略监控面板 · 告警模块
功能：
  - 策略异常检测（无信号/数据滞后/回撤超阈值）
  - 服务健康异常检测（行情拉取失败/磁盘满）
  - 飞书告警推送（带 5 分钟频控）
  - 告警审计日志（logs/alerts.log）

用法（独立脚本）：
  python3 alerts.py check           # 单次健康检查
  python3 alerts.py test            # 发送测试告警
  python3 alerts.py alert <title> <msg>  # 手动触发告警
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ====== 配置 ======
BASE_DIR = Path(__file__).parent.parent
SIGNALS_DIR = BASE_DIR / 'signals'
LOGS_DIR = BASE_DIR / 'logs'
ALERT_LOG = LOGS_DIR / 'alerts.log'
STATE_FILE = LOGS_DIR / '.alert_state.json'

# 告警阈值（可在 config/alerts.json 中覆盖）
DEFAULT_CONFIG = {
    'signal_stale_hours': 24,         # 信号文件超过 N 小时视为滞后
    'drawdown_threshold': -0.10,      # 最大回撤超过 -10% 告警
    'price_cache_empty': True,        # 行情缓存为空时告警
    'cooldown_minutes': 5,            # 同类型告警冷却时间
    'disk_usage_threshold': 0.90,     # 磁盘使用率超 90% 告警
}

# ====== 频控状态 ======
def _load_state():
    """加载告警状态（每个告警类型上次推送时间）"""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(state):
    """保存告警状态"""
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def _should_alert(alert_key, cooldown_min):
    """检查是否在冷却期内"""
    state = _load_state()
    last = state.get(alert_key)
    if not last:
        return True
    last_time = datetime.fromisoformat(last)
    return datetime.now() - last_time > timedelta(minutes=cooldown_min)

def _mark_alerted(alert_key):
    """标记告警已推送"""
    state = _load_state()
    state[alert_key] = datetime.now().isoformat()
    _save_state(state)

# ====== 飞书推送 ======
def _send_feishu(title, content, alert_type='info'):
    """DISABLED 2026-06-28: 禁止自动飞书推送"""
    print("[飞书推送已禁用]")
    return False

# ====== 审计日志 ======
def _log_alert(alert_key, title, message, sent_to_feishu):
    """记录告警到审计日志"""
    LOGS_DIR.mkdir(exist_ok=True)
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'alert_key': alert_key,
        'title': title,
        'message': message,
        'sent_to_feishu': sent_to_feishu,
    }
    with open(ALERT_LOG, 'a') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

# ====== 公开 API ======
def alert(title, message, alert_type='warn', alert_key=None, force=False):
    """
    触发告警
    :param title: 告警标题
    :param message: 告警详情
    :param alert_type: info | warn | error
    :param alert_key: 用于频控的唯一 key，默认基于 title
    :param force: True 跳过冷却强制推送
    :return: dict {sent: bool, reason: str}
    """
    config = _load_config()
    cooldown = config.get('cooldown_minutes', 5)
    key = alert_key or title

    if not force and not _should_alert(key, cooldown):
        return {'sent': False, 'reason': 'cooldown'}

    sent = _send_feishu(title, message, alert_type)
    _mark_alerted(key)
    _log_alert(key, title, message, sent)
    return {'sent': sent, 'reason': 'sent' if sent else 'feishu_failed'}

def _load_config():
    """加载告警配置（可被 config/alerts.json 覆盖）"""
    config_file = BASE_DIR / 'config' / 'alerts.json'
    if config_file.exists():
        try:
            with open(config_file) as f:
                user_cfg = json.load(f)
            return {**DEFAULT_CONFIG, **user_cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG

# ====== 健康检查器 ======
def check_signal_freshness(config):
    """检查所有策略的信号文件新鲜度

    增强 (2026-06-20): stale 超过 72h 自动尝试从最近 result JSON 同步一次
    """
    signals = list(SIGNALS_DIR.glob('*.json'))
    if not signals:
        alert(
            '⚠️ 监控面板信号缺失',
            f'目录 {SIGNALS_DIR} 下没有任何信号文件，请确认棘轮迭代任务正常运行。',
            alert_type='error',
            alert_key='signals_missing'
        )
        return False

    stale_hours = config.get('signal_stale_hours', 24)
    auto_sync_hours = config.get('auto_sync_threshold_hours', 72)  # 72h 后自动尝试 sync
    stale_strategies = []
    auto_sync_candidates = []
    now = datetime.now()
    for f in signals:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = now - mtime
        age_hours = age.total_seconds() / 3600
        if age > timedelta(hours=stale_hours):
            stale_strategies.append(f"{f.stem} ({age_hours:.1f}h)")
            # 超过 auto_sync_hours 触发自动 sync 尝试
            if age_hours > auto_sync_hours:
                strategy_id = f.stem.split('_')[0]
                auto_sync_candidates.append((strategy_id, f, age_hours))

    # 自动同步尝试 (P2-1 增强)
    if auto_sync_candidates:
        auto_sync_results = _try_auto_sync(auto_sync_candidates, config)
        if auto_sync_results['synced']:
            alert(
                '🔄 自动同步已执行',
                f'以下策略超过 {auto_sync_hours}h 未更新，已自动尝试同步：\n' +
                '\n'.join('→ ' + s for s in auto_sync_results['synced']),
                alert_type='info',
                alert_key='auto_sync_executed'
            )
        if auto_sync_results['failed']:
            alert(
                '❌ 自动同步失败',
                f'以下策略自动同步失败（缺少最近 result JSON）：\n' +
                '\n'.join('→ ' + s for s in auto_sync_results['failed']),
                alert_type='warn',
                alert_key='auto_sync_failed'
            )

    if stale_strategies:
        alert(
            '⚠️ 策略信号滞后',
            f'以下策略信号文件超过 {stale_hours}h 未更新：\n' + '\n'.join('→ ' + s for s in stale_strategies),
            alert_type='warn',
            alert_key='signals_stale'
        )
        return False
    return True


def _try_auto_sync(candidates, config):
    """尝试从最近的 result JSON 自动同步信号文件

    Args:
        candidates: [(strategy_id, current_signal_file, age_hours), ...]
        config: alerts.json 配置

    Returns:
        {'synced': [...], 'failed': [...]}
    """
    import subprocess
    from pathlib import Path as P

    # 候选 result JSON 搜索路径
    result_search_dirs = [
        P.home() / 'ratchet_results',
        P.home() / 'qixing_strategy',
        P.home() / '三策略监控面板_项目档案',
        P.home() / 'qixing_backtest',
        P.home() / 'zhuidian_results',
    ]
    # 自定义路径
    custom_dirs = config.get('auto_sync_search_dirs', [])
    result_search_dirs.extend(P(d) for d in custom_dirs)

    synced = []
    failed = []

    for strategy_id, signal_file, age_hours in candidates:
        # 找该 strategy 的最新 result JSON
        latest_result = None
        latest_mtime = 0
        for d in result_search_dirs:
            if not d.exists():
                continue
            for pattern in [f'*{strategy_id}*', '*']:
                for f in d.glob(f'{pattern}.json'):
                    try:
                        mt = f.stat().st_mtime
                        if mt > latest_mtime:
                            latest_result = f
                            latest_mtime = mt
                    except Exception:
                        continue

        if not latest_result:
            failed.append(f"{strategy_id} (无 result JSON)")
            continue

        # 检查 result JSON 是否比当前 signal 新
        result_age_hours = (datetime.now().timestamp() - latest_mtime) / 3600
        if result_age_hours >= age_hours:
            failed.append(f"{strategy_id} (最新 result 也比 signal 旧 {result_age_hours:.1f}h)")
            continue

        # 调用 sync 脚本
        sync_script = BASE_DIR / 'scripts' / 'update_strategy_to_monitor.sh'
        if not sync_script.exists():
            failed.append(f"{strategy_id} (sync 脚本不存在)")
            continue

        try:
            result = subprocess.run(
                ['bash', str(sync_script), strategy_id, str(latest_result)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                synced.append(f"{strategy_id} (result={latest_result.name})")
            else:
                failed.append(f"{strategy_id} (sync 退出码 {result.returncode})")
        except subprocess.TimeoutExpired:
            failed.append(f"{strategy_id} (sync 超时)")
        except Exception as e:
            failed.append(f"{strategy_id} (sync 异常: {e})")

    return {'synced': synced, 'failed': failed}

def check_drawdown(config):
    """检查回撤超阈值"""
    threshold = config.get('drawdown_threshold', -0.10)
    breached = []
    for f in SIGNALS_DIR.glob('*.json'):
        try:
            with open(f) as fp:
                signal = json.load(fp)
            dd = signal.get('max_drawdown', 0)
            if dd and dd <= threshold * 100:  # signal 中存的是百分比
                breached.append(f"{f.stem.split('_')[0]}: 回撤 {dd}%")
        except Exception:
            continue

    if breached:
        alert(
            '🚨 回撤超阈值',
            f'回撤超过 {threshold*100}% 阈值的策略：\n' + '\n'.join('→ ' + b for b in breached),
            alert_type='error',
            alert_key='drawdown_breach'
        )
        return False
    return True

def check_disk_usage(config):
    """检查磁盘使用率"""
    threshold = config.get('disk_usage_threshold', 0.90)
    try:
        import shutil
        usage = shutil.disk_usage(str(BASE_DIR))
        used_ratio = usage.used / usage.total
        if used_ratio > threshold:
            alert(
                '💾 磁盘空间不足',
                f'当前使用率 {used_ratio*100:.1f}%，超过 {threshold*100}% 阈值。\n剩余：{usage.free / (1024**3):.1f} GB',
                alert_type='warn',
                alert_key='disk_full'
            )
            return False
    except Exception:
        pass
    return True

def run_health_check():
    """运行所有健康检查"""
    config = _load_config()
    results = {
        'signal_freshness': check_signal_freshness(config),
        'drawdown': check_drawdown(config),
        'disk_usage': check_disk_usage(config),
    }
    return results

# ====== CLI 入口 ======
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python alerts.py [check|test|alert <title> <msg>]')
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'check':
        results = run_health_check()
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif cmd == 'test':
        result = alert(
            '🟢 监控面板告警测试',
            f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n这是一条测试告警，验证飞书通道连通性。',
            alert_type='info',
            alert_key='test_alert',
            force=True
        )
        print(json.dumps(result, ensure_ascii=False))
    elif cmd == 'alert':
        if len(sys.argv) < 4:
            print('Usage: python alerts.py alert <title> <msg>')
            sys.exit(1)
        title = sys.argv[2]
        msg = sys.argv[3]
        result = alert(title, msg, force=True)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f'Unknown command: {cmd}')
        sys.exit(1)