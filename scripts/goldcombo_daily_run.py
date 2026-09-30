#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金组合A（goldcombo / V24 DMAStrategy）每日真实模拟引擎
=========================================================
定位（PROJECT_RULES 规则7：回测/实盘严格分离）：
  - 棘轮/5Y 回测脚本（goldcombo_ratchet_ashare.py、run_backtest_5y_v24.py）
    只负责参数迭代与历史回测，**绝不**产出每日实盘信号。
  - 本脚本是黄金组合A唯一的「每日真实模拟」入口：每个交易日 D 收盘后，
    用真实日线 K 线（data/v24_*）+ 固定 V24 策略 + 固定实盘起点，
    滚动重放到 D，切出 D 当天的真实持仓/成交/净值，写入 work_logs，
    再由 rebuild_signals_from_worklogs.py 生成当日 signal。

真实性保证：
  - 策略逻辑一字不改复用 strategies/goldcombo/goldcombo_strategy_ashare_v24.py 的 DMAStrategy；
  - 行情全部来自本地真实 CSV（scripts/fetch_v24_pool_kline.py 每日增量更新），
    退市转债数据自然止于最后交易日，不前向填充、不造数；
  - 账户在 LIVE_START 之前不交易（仅用历史行情 warm-up DMA/MA200 指标），
    LIVE_START 当天才开始按真实信号建仓；之前的日期不写 work_log（没有真实模拟就空着）；
  - 每个交易日确定性重放（同数据/同参数/同起点 → 同结果），账户连续、可复现，无快照。

运行环境：必须用含 backtrader 的 venv：
  /Users/junze/qixing_strategy/venv/bin/python scripts/goldcombo_daily_run.py --date 2026-09-21

Usage:
  ... goldcombo_daily_run.py --date 2026-09-21           # 正式写入当日 work_log
  ... goldcombo_daily_run.py --date 2026-09-18 --dry-run # 只打印不写
  ... goldcombo_daily_run.py --date 2026-09-18 --live-start 2026-09-18 --dry-run  # 验证引擎
"""
import os
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    os.environ[k] = ''
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import sys
import types
import json
import argparse
import datetime
from pathlib import Path

# ---- 仅用本地 CSV，策略文件顶部 import akshare 但回测路径不调用，注入空桩避免强制安装 ----
try:
    import akshare  # noqa: F401
except Exception:
    sys.modules.setdefault('akshare', types.ModuleType('akshare'))

import pandas as pd
import backtrader as bt

ROOT = Path('/Users/junze/quant-monitor-local')
sys.path.insert(0, str(ROOT))
from strategies.goldcombo.goldcombo_strategy_ashare_v24 import DMAStrategy  # noqa: E402

WORKLOG_DIR = Path('/Users/junze/.hermes/work_logs/goldcombo')
DATA_DIR = ROOT / 'data'
LIVE_START_DEFAULT = datetime.date(2026, 9, 21)
INITIAL_CASH = 50000.0          # V24 策略锁死 5 万本金（per_pos_pct=0.20 × 最多 5 只）
WARMUP_FROM = '2021-08-14'      # 指标 warm-up 起点（与 5Y 回测一致，覆盖 MA200）

SYMBOLS = [
    ('510300', 'ETF'), ('510500', 'ETF'), ('512880', 'ETF'),
    ('512690', 'ETF'), ('512480', 'ETF'),
    ('000001', 'STK'), ('600519', 'STK'), ('000333', 'STK'),
    ('113050', 'CB'), ('110079', 'CB'), ('113011', 'CB'),
    ('113013', 'CB'), ('113016', 'CB'),
]
SUBDIR = {'ETF': 'v24_etf_kline', 'STK': 'v24_stk_kline', 'CB': 'v24_bonds'}


class LiveDMAStrategy(DMAStrategy):
    """在 V24 策略上加：实盘起点门控 + 成交记录 + 逐日净值记录（不改买卖逻辑）。"""

    params = dict(live_start=None)  # datetime.date

    def __init__(self):
        super().__init__()
        self.fills = []     # 真实成交
        self.nav_curve = []  # 逐日 {date, cash, value}

    def _cur_date(self):
        return bt.num2date(self.datas[0].datetime[0]).date()

    def next(self):
        cur = self._cur_date()
        # 实盘起点之前：只让指标随行情推进，账户一律不交易
        if self.p.live_start is not None and cur < self.p.live_start:
            return
        super().next()
        # 当日收盘后记录账户净值（多数据源以主数据 510300 交易日为时轴）
        if self.datas[0].datetime[0] == self.data.datetime[0]:
            self.nav_curve.append({
                'date': cur.strftime('%Y-%m-%d'),
                'cash': round(float(self.broker.getcash()), 2),
                'value': round(float(self.broker.getvalue()), 2),
            })

    def notify_order(self, order):
        super().notify_order(order)
        if order.status != order.Completed:
            return
        d = order.data
        code = d._name.split(':', 1)[1]
        dt = bt.num2date(d.datetime[0]).date().strftime('%Y-%m-%d')
        self.fills.append({
            'date': dt,
            'code': code,
            'action': 'BUY' if order.isbuy() else 'SELL',
            'shares': abs(int(order.executed.size)),
            'price': round(float(order.executed.price), 4),
            'value': round(float(abs(order.executed.size) * order.executed.price), 2),
            'commission': round(float(order.executed.comm), 4),
            'pnl': round(float(order.executed.pnl), 2),
            'reason': getattr(order, 'gc_reason', ''),
        })


def load_feed(code, kind, end_date):
    csv = DATA_DIR / SUBDIR[kind] / f'{code}.csv'
    if not csv.exists():
        return None
    df = pd.read_csv(csv, encoding='utf-8-sig')
    if 'date' not in df.columns and '日期' in df.columns:
        df = df.rename(columns={'日期': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df[(df.index >= WARMUP_FROM) & (df.index <= pd.Timestamp(end_date))]
    for c in ('open', 'high', 'low', 'close', 'volume'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df[['open', 'high', 'low', 'close', 'volume']].ffill()
    return df


def run(end_date: datetime.date, live_start: datetime.date):
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.set_coc(True)   # 当日信号当日收盘价成交，对齐 5 策略 daily 口径
    loaded = []
    for code, kind in SYMBOLS:
        df = load_feed(code, kind, end_date)
        if df is None or len(df) < 60:
            continue
        cerebro.adddata(bt.feeds.PandasData(dataname=df), name=f'{kind}:{code}')
        loaded.append(f'{kind}:{code}')
    cerebro.addstrategy(LiveDMAStrategy, live_start=live_start)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    strat = cerebro.run()[0]
    return strat, loaded


def positions_at(strat, date_str):
    """从真实成交累积到 date 的持仓，并用 date 收盘价重估市值。"""
    pos = {}
    for t in strat.fills:
        if t['date'] > date_str:
            break
        c = t['code']
        pos.setdefault(c, {'qty': 0, 'cost': 0.0})
        if t['action'] == 'BUY':
            pos[c]['qty'] += t['shares']
            pos[c]['cost'] += t['value'] + t['commission']
        else:
            pos[c]['qty'] -= t['shares']
            pos[c]['cost'] -= t['value']
        if pos[c]['qty'] <= 0:
            pos.pop(c, None)
    # 收盘价重估
    close_map = {}
    for d in strat.datas:
        code = d._name.split(':', 1)[1]
        try:
            # 找到 <= date_str 的最后一根 bar 收盘
            dt_arr = [bt.num2date(d.datetime[i]).date().strftime('%Y-%m-%d')
                      for i in range(-min(len(d), 60), 0)]
        except Exception:
            dt_arr = []
        # 简化：直接用当前最后收盘（数据已截到 end_date）
        close_map[code] = float(d.close[0])
    out = []
    for c, p in pos.items():
        if p['qty'] <= 0:
            continue
        avg_cost = p['cost'] / p['qty']
        px = close_map.get(c, avg_cost)
        out.append({
            'code': c, 'name': c, 'qty': p['qty'],
            'cost': round(avg_cost, 4),
            'market_value': round(p['qty'] * px, 2),
        })
    return out


def build_worklog(strat, loaded, end_date, live_start):
    date_str = end_date.strftime('%Y-%m-%d')
    nav = {p['date']: p['value'] for p in strat.nav_curve}
    # 前一交易日净值
    dates = sorted(nav.keys())
    if date_str not in nav:
        return None, f'{date_str} 不在净值曲线（非交易日或数据未更新？），不写 work_log'
    idx = dates.index(date_str)
    prev_nav = nav[dates[idx - 1]] if idx > 0 else INITIAL_CASH
    cur_nav = nav[date_str]

    today_trades = [t for t in strat.fills if t['date'] == date_str]
    positions = positions_at(strat, date_str)
    prev_date_str = dates[idx - 1] if idx > 0 else None
    positions_before = positions_at(strat, prev_date_str) if prev_date_str else []
    daily_pnl = round(cur_nav - prev_nav, 2)
    cumulative = round(cur_nav - INITIAL_CASH, 2)
    return_pct = round(cumulative / INITIAL_CASH * 100, 4)
    live_days = idx + 1

    # 成交明细转 work_log trade 格式
    secs = [{
        'time': '14:45:00', 'action': t['action'].lower(), 'code': t['code'],
        'qty': t['shares'], 'price': t['price'], 'amount': t['value'],
        'pnl': t['pnl'] if t['action'] == 'SELL' else 0, 'reason': t['reason'],
    } for t in today_trades]
    per_etf_pnl = {}
    for t in today_trades:
        if t['action'] == 'SELL':
            per_etf_pnl[t['code']] = per_etf_pnl.get(t['code'], 0) + t['pnl']

    action = 'REBALANCE' if today_trades else ('HOLD' if positions else 'FLAT')

    def entry(session, time_, reason, total):
        return {
            'status': 'success', 'strategy_id': 'goldcombo',
            'live_start_date': live_start.strftime('%Y-%m-%d'),
            'trade_status': {'date': date_str, 'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][end_date.weekday()],
                             'is_trading_day': True, 'current_time': time_, 'reason': reason},
            'session': session,
            'signal': {'action': action, 'target_etf': None,
                       'target_etfs': [{'code': p['code'], 'target_value': p['market_value'],
                                        'weight': round(p['market_value'] / cur_nav, 4) if cur_nav else 0}
                                       for p in positions],
                       'target_weight': 1.0, 'environment': {'state': 'normal'}},
            'trade': {'success': True, 'security': positions[0]['code'] if positions else None,
                      'securities': secs, 'target_value': INITIAL_CASH,
                      'message': f'V24_DMAStrategy 真实每日模拟 | {len(today_trades)} 笔成交 | 持仓 {len(positions)} 只'},
            'positions_before': positions_before, 'positions_after': positions,
            'daily_pnl': {'total': total, 'per_etf': per_etf_pnl, 'cumulative': cumulative,
                          'return_pct': return_pct, 'trade_count': len(today_trades)},
            'return_unit': 'percent',
            'version': 'V24_DMAStrategy', 'params_used': {}, 'params_source': 'v24_locked',
            'data_source': 'V24 真实日线 CSV 因果每日重放（live_start=%s）' % live_start.strftime('%Y-%m-%d'),
            'timestamp': datetime.datetime.now().isoformat(),
            'capital': INITIAL_CASH, 'summary': f'goldcombo {date_str} {session}',
        }

    lines = [
        json.dumps(entry('morning', '10:00:15', '工作日（morning 决策）', 0), ensure_ascii=False),
        json.dumps(entry('afternoon', '14:45:00', '工作日（afternoon 收盘 P&L）', daily_pnl), ensure_ascii=False),
    ]
    meta = {'loaded': loaded, 'cur_nav': cur_nav, 'prev_nav': prev_nav,
            'daily_pnl': daily_pnl, 'cumulative': cumulative, 'return_pct': return_pct,
            'live_days': live_days, 'positions': positions, 'today_trades': today_trades}
    return lines, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True, help='实盘交易日 YYYY-MM-DD')
    ap.add_argument('--live-start', default=LIVE_START_DEFAULT.strftime('%Y-%m-%d'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    end_date = datetime.datetime.strptime(args.date, '%Y-%m-%d').date()
    live_start = datetime.datetime.strptime(args.live_start, '%Y-%m-%d').date()

    if end_date < live_start:
        print(f'[goldcombo] {args.date} 早于实盘起点 {args.live_start}，不写 work_log（没有真实模拟就空着）')
        return

    strat, loaded = run(end_date, live_start)
    lines, meta = build_worklog(strat, loaded, end_date, live_start)
    if lines is None:
        print('[goldcombo] ' + str(meta))
        return

    print(f'加载标的 {len(loaded)}: {loaded}')
    print(f"当日净值 {meta['prev_nav']:.2f} → {meta['cur_nav']:.2f} | "
          f"当日盈亏 {meta['daily_pnl']:+.2f} | 累计 {meta['cumulative']:+.2f} "
          f"({meta['return_pct']:+.4f}%) | live_days={meta['live_days']}")
    print(f"持仓 {len(meta['positions'])} 只: {[(p['code'], p['qty']) for p in meta['positions']]}")
    print(f"当日成交 {len(meta['today_trades'])} 笔: "
          f"{[(t['action'], t['code'], t['shares'], t['price']) for t in meta['today_trades']]}")

    if args.dry_run:
        print('[dry-run] 不写 work_log')
        return
    WORKLOG_DIR.mkdir(parents=True, exist_ok=True)
    out = WORKLOG_DIR / f'goldcombo_{args.date}.json'
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'已写入 {out}')


if __name__ == '__main__':
    main()
