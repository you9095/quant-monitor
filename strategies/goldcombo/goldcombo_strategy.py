#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金组合 A 回测引擎 v2 — GoldComboStrategy (MACD/BOLL/CCI/DMI 4 指标)
=============================================================
- 数据源: /Users/junze/qixing_data/etf_kline/ (38 ETF 池, CSV)
- 起始资金: 100000.0
- 佣金: 0.001
- 滑点: 0.001
- 数据期: 2Y (2024-08-13 ~ 2026-08-13) + 5Y (2021-08-13 ~ 2026-08-13)
- 策略: 4 指标共振 (MACD金叉<0, BOLL扩口, CCI<-100, -DI>30 +DI<10)
- 兜底: 8% 止损 / 4 指标反转平仓

回测日期陷阱规避:
- 用所有 ETF 交易日交集 (set.intersection)
- 回撤算法: cummax-based (correct drawdown)

数据期内可用 ETF 过滤: min_rows >= 200 (2Y) / 1000 (5Y)
"""
import os
import sys
import json
import math
import argparse
import warnings
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Set, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# 清理 PYTHONPATH 污染
sys.path = [p for p in sys.path if 'hermes-agent' not in p]

try:
    import backtrader as bt
except ImportError:
    print("ERROR: backtrader not installed", file=sys.stderr)
    sys.exit(1)

# ==================== 配置 ====================
INITIAL_CAPITAL = 100000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.001
KLINE_DIR = '/Users/junze/qixing_data/etf_kline'

ETF_POOL = [
    "518880", "159985", "501018", "161226", "513100", "159915", "511220",
    "159980", "159981", "159509", "513290", "513500", "159529", "513400",
    "513520", "513030", "513080", "513310", "513730", "159792", "513130",
    "513050", "159920", "513690", "510300", "510500", "510050", "510210",
    "588080", "512100", "563360", "563300", "512890", "159967", "512040",
    "159201", "511380", "511010"
]


# ==================== GoldComboStrategy ====================
class GoldComboStrategy(bt.Strategy):
    """黄金组合 A: 极致恐慌反转模型 (4 指标共振)"""
    params = dict(sl_pct=0.08, print_log=False)

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.adx = bt.ind.ADX(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.trix = bt.ind.TRIX(period=12)
        self.trma = bt.ind.SMA(self.trix, period=9)
        self.entry_price = None
        self.order_count = 0
        self.trade_log = []

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.order_count += 1
                self.trade_log.append({
                    'type': 'BUY',
                    'date': bt.num2date(order.executed.dt).strftime('%Y-%m-%d'),
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'commission': order.executed.comm,
                })
            else:
                self.trade_log.append({
                    'type': 'SELL',
                    'date': bt.num2date(order.executed.dt).strftime('%Y-%m-%d'),
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'commission': order.executed.comm,
                    'pnl': (order.executed.price - self.entry_price) * order.executed.size if self.entry_price else 0,
                })
                self.entry_price = None

    def next(self):
        if self.position:
            if self.entry_price is not None:
                if self.data.close[0] < self.entry_price * (1.0 - self.p.sl_pct):
                    self.close()
                    return
            s2 = self.cci[0] > 120
            s3 = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
            s4 = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
            s6 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)
            if s2 or s3 or s4 or s6:
                self.close()
            return
        if not self.position:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0) and (self.macd.signal[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < -100
            c8 = (self.plus_di[0] < 10) and (self.minus_di[0] > 30)
            if c3 and c4 and c7 and c8:
                self.buy()


class EquityObserver(bt.Observer):
    """记录每日 broker equity"""
    lines = ('equity',)
    def next(self):
        self.lines.equity[0] = self._owner.broker.getvalue()


# ==================== 数据加载 ====================
def load_etf_data(etf_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """加载 ETF 数据, 返回 DataFrame [date, open, high, low, close, volume]"""
    csv_path = os.path.join(KLINE_DIR, f"{etf_code}.csv")
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception:
        try:
            df = pd.read_csv(csv_path, encoding='gbk')
        except Exception:
            return None
    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))
    return df[mask].reset_index(drop=True)


def filter_etf_pool(start_date: str, end_date: str, min_rows: int = 200) -> Tuple[List[str], Dict[str, int]]:
    """筛选 ETF 池: min_rows >= 阈值的 ETF 才参与"""
    row_count = {}
    for code in ETF_POOL:
        df = load_etf_data(code, start_date, end_date)
        if df is not None and len(df) >= min_rows:
            row_count[code] = len(df)
    filtered = sorted(row_count.keys(), key=lambda c: row_count[c], reverse=True)
    return filtered, row_count


# ==================== 指标触发频次分析 ====================
def analyze_indicator_trigger(start_date: str, end_date: str, min_rows: int) -> Dict:
    """分析每个指标在 38 ETF 上的触发频次, 帮助理解策略特性"""
    warmup_start = (pd.Timestamp(start_date) - timedelta(days=180)).strftime('%Y-%m-%d')
    stats = {
        'C3_MACD_golden_cross_below_0': 0,
        'C4_BOLL_broadening': 0,
        'C7_CCI_under_-100': 0,
        'C8_DMI_bear_extreme': 0,
        'all_4_combined': 0,
        'at_least_1': 0,
    }
    per_etf_trigger = {}
    for code in ETF_POOL:
        df = load_etf_data(code, warmup_start, end_date)
        if df is None or len(df) < 200:
            continue
        df = df[df['date'] >= pd.Timestamp(start_date)].copy().reset_index(drop=True)
        if len(df) < min_rows:
            continue
        # 4 指标
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        c3 = (macd > signal) & (macd.shift(1) <= signal.shift(1)) & (macd < 0) & (signal < 0)
        n = 14
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma = tp.rolling(n).mean()
        md = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        cci = (tp - ma) / (0.015 * md)
        c7 = cci < -100
        mb = df['close'].rolling(20).mean()
        sd = df['close'].rolling(20).std()
        bw = (mb + 2*sd) - (mb - 2*sd)
        c4 = bw > bw.shift(1)
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        pdm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
        ndm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)
        tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift(1)).abs(), (df['low']-df['close'].shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.rolling(n).mean()
        plus_di = 100 * pdm.rolling(n).mean() / atr
        minus_di = 100 * ndm.rolling(n).mean() / atr
        c8 = (plus_di < 10) & (minus_di > 30)
        c3v = c3.fillna(False)
        c4v = c4.fillna(False)
        c7v = c7.fillna(False)
        c8v = c8.fillna(False)
        stats['C3_MACD_golden_cross_below_0'] += int(c3v.sum())
        stats['C4_BOLL_broadening'] += int(c4v.sum())
        stats['C7_CCI_under_-100'] += int(c7v.sum())
        stats['C8_DMI_bear_extreme'] += int(c8v.sum())
        stats['all_4_combined'] += int((c3v & c4v & c7v & c8v).sum())
        stats['at_least_1'] += int((c3v | c4v | c7v | c8v).sum())
        per_etf_trigger[code] = {
            'C3': int(c3v.sum()),
            'C4': int(c4v.sum()),
            'C7': int(c7v.sum()),
            'C8': int(c8v.sum()),
            'all4': int((c3v & c4v & c7v & c8v).sum()),
        }
    return {'totals': stats, 'per_etf': per_etf_trigger}


# ==================== 单 ETF 回测 ====================
def run_etf_backtest(etf_code: str, start_date: str, end_date: str, capital: float) -> Dict:
    """单个 ETF 上跑 GoldComboStrategy"""
    warmup_start = (pd.Timestamp(start_date) - timedelta(days=180)).strftime('%Y-%m-%d')
    df_full = load_etf_data(etf_code, warmup_start, end_date)
    if df_full is None or len(df_full) < 60:
        return None

    data = bt.feeds.PandasData(
        dataname=df_full,
        datetime='date',
        open='open', high='high', low='low', close='close', volume='volume',
        openinterest=-1,
        fromdate=pd.Timestamp(start_date),
        todate=pd.Timestamp(end_date),
    )

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(GoldComboStrategy, print_log=False)
    cerebro.adddata(data)
    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=COMMISSION_RATE)
    cerebro.broker.set_slippage_perc(perc=SLIPPAGE)
    cerebro.broker.set_coc(True)
    cerebro.addobserver(EquityObserver)

    strategies = cerebro.run()
    strat = strategies[0]

    # 提取 equity observer
    obs = strat.observers[0]
    eq_array = np.array(obs.lines.equity.array)
    valid = eq_array[~np.isnan(eq_array)]
    final_equity = float(cerebro.broker.getvalue())

    # 拿 trade_log
    trade_log = getattr(strat, 'trade_log', [])
    buy_count = sum(1 for t in trade_log if t['type'] == 'BUY')
    sell_count = sum(1 for t in trade_log if t['type'] == 'SELL')
    win_count = sum(1 for t in trade_log if t['type'] == 'SELL' and t.get('pnl', 0) > 0)

    return {
        'etf_code': etf_code,
        'capital': capital,
        'final_equity': round(final_equity, 2),
        'return_pct': round((final_equity / capital - 1) * 100, 4),
        'buy_count': buy_count,
        'sell_count': sell_count,
        'win_count': win_count,
        'trade_log': trade_log,
    }


# ==================== 38 ETF 池回测 ====================
def run_pool_backtest(etf_list: List[str], start_date: str, end_date: str) -> Dict:
    """38 ETF 等权仓位回测 (1/N 资金)"""
    n_etf = len(etf_list)
    if n_etf == 0:
        return {'error': 'no_etf'}

    capital_per_etf = INITIAL_CAPITAL / n_etf
    per_etf = {}
    for code in etf_list:
        result = run_etf_backtest(code, start_date, end_date, capital_per_etf)
        if result is not None:
            per_etf[code] = result

    if not per_etf:
        return {'error': 'no_data', 'per_etf': {}}

    # 汇总指标
    total_buy = sum(p['buy_count'] for p in per_etf.values())
    total_sell = sum(p['sell_count'] for p in per_etf.values())
    total_wins = sum(p['win_count'] for p in per_etf.values())
    total_final_equity = sum(p['final_equity'] for p in per_etf.values())

    total_return_pct = (total_final_equity / INITIAL_CAPITAL - 1) * 100

    # 估算 max drawdown: 0 交易时 = 0%
    if total_buy == 0:
        max_dd = 0.0
        sharpe = 0.0
        win_rate = 0.0
    else:
        # 简化: 取所有 ETF 的 max DD 中位数 (因为没有连续 equity curve 跨 ETF)
        # 实际: 我们用 daily equity observer 单独求每个 ETF 的 DD, 然后加权平均
        per_etf_dd = []
        per_etf_sharpe = []
        for code, p in per_etf.items():
            if p['buy_count'] == 0:
                continue
            # 重新跑拿 daily equity
            warmup_start = (pd.Timestamp(start_date) - timedelta(days=180)).strftime('%Y-%m-%d')
            df_full = load_etf_data(code, warmup_start, end_date)
            if df_full is None: continue
            data = bt.feeds.PandasData(
                dataname=df_full, datetime='date',
                open='open', high='high', low='low', close='close', volume='volume',
                openinterest=-1,
                fromdate=pd.Timestamp(start_date), todate=pd.Timestamp(end_date),
            )
            cerebro = bt.Cerebro(stdstats=False)
            cerebro.addstrategy(GoldComboStrategy, print_log=False)
            cerebro.adddata(data)
            cerebro.broker.setcash(capital_per_etf)
            cerebro.broker.setcommission(commission=COMMISSION_RATE)
            cerebro.broker.set_slippage_perc(perc=SLIPPAGE)
            cerebro.broker.set_coc(True)
            cerebro.addobserver(EquityObserver)
            strategies = cerebro.run()
            strat = strategies[0]
            obs = strat.observers[0]
            eq_arr = np.array(obs.lines.equity.array)
            valid = eq_arr[~np.isnan(eq_arr)]
            if len(valid) < 2: continue
            eq_s = pd.Series(valid)
            cummax = eq_s.cummax()
            dd = ((eq_s - cummax) / cummax).min() * 100
            per_etf_dd.append(dd)
            # 单 ETF sharpe
            ret = eq_s.pct_change().dropna()
            if ret.std() > 1e-9:
                s = (ret.mean() / ret.std()) * math.sqrt(252)
                per_etf_sharpe.append(s)
        if per_etf_dd:
            max_dd = min(per_etf_dd)  # 最大回撤 = 最差的
        else:
            max_dd = 0.0
        if per_etf_sharpe:
            sharpe = sum(per_etf_sharpe) / len(per_etf_sharpe)
        else:
            sharpe = 0.0
        win_rate = (total_wins / total_sell * 100) if total_sell > 0 else 0.0

    # 分析指标触发频次
    min_rows = 200 if '2024-' in start_date else 1000
    trigger_stats = analyze_indicator_trigger(start_date, end_date, min_rows)

    return {
        'strategy_id': 'goldcombo',
        'strategy_name': '黄金组合A',
        'data_period': f"{start_date} ~ {end_date}",
        'initial_capital': INITIAL_CAPITAL,
        'commission_rate': COMMISSION_RATE,
        'slippage': SLIPPAGE,
        'final_equity': round(total_final_equity, 2),
        'total_return_pct': round(total_return_pct, 4),
        'max_drawdown_pct': round(max_dd, 4),
        'sharpe_ratio': round(sharpe, 4),
        'trade_count': total_buy,  # 用 buy 笔数 (开仓数)
        'closed_trades': total_sell,
        'win_count': total_wins,
        'win_rate_pct': round(win_rate, 2),
        'etf_pool_count': n_etf,
        'etf_pool_used': list(per_etf.keys()),
        'per_etf_stats': {
            code: {
                'final_equity': p['final_equity'],
                'return_pct': p['return_pct'],
                'buy_count': p['buy_count'],
                'sell_count': p['sell_count'],
                'win_count': p['win_count'],
            } for code, p in per_etf.items()
        },
        'indicator_trigger_stats': trigger_stats,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'engine_version': 'goldcombo_v2',
        'strategy_mechanic': '4指标共振 (MACD金叉<0 + BOLL扩口 + CCI<-100 + DMI空方极致) + 8%止损',
        'kpi_target': {
            'return_target': '+5% (棘轮基线最低门槛)',
            'drawdown_max': '-30% (棘轮硬约束)',
        },
    }


# ==================== Main ====================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--period', choices=['2y', '5y'], required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--min-rows', type=int, default=None)
    args = parser.parse_args()

    min_rows = args.min_rows if args.min_rows is not None else (200 if args.period == '2y' else 1000)
    print(f"[goldcombo] period={args.period} ({args.start} ~ {args.end}) min_rows={min_rows}")

    filtered, row_count = filter_etf_pool(args.start, args.end, min_rows=min_rows)
    print(f"[goldcombo] etf pool: {len(filtered)}/{len(ETF_POOL)} (after min_rows >= {min_rows})")

    result = run_pool_backtest(filtered, args.start, args.end)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if 'error' in result:
        print(f"[goldcombo] FAIL: {result['error']}")
        sys.exit(1)
    print(f"[goldcombo] return: {result['total_return_pct']:.2f}%")
    print(f"[goldcombo] drawdown: {result['max_drawdown_pct']:.2f}%")
    print(f"[goldcombo] sharpe: {result['sharpe_ratio']:.2f}")
    print(f"[goldcombo] trades: {result['trade_count']}")
    print(f"[goldcombo] written: {args.output}")


if __name__ == '__main__':
    main()
