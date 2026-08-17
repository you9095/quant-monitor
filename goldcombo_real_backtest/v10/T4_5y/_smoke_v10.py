#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-flight smoke test: V10 + 5 stocks
确认策略类能跑通,不破坏脚本架构"""
import sys
import warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/Users/junze/quant-monitor-local')

import os, json
import backtrader as bt
import pandas as pd
from strategies.goldcombo.goldcombo_strategy_ashare_v10 import GoldComboV10_HighYield

POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
KLINE_DIR = '/Users/junze/quant-monitor-local/data/ashare_kline'

with open(POOL_FILE) as f:
    pool_5y = json.load(f)['pool_5y']['codes']

# Smoke 5 只: 000010, 600000, 000001, 002001, 600519 (含高价股茅台)
test_codes = ['000010', '600000', '000001', '002001', '600519']
START_DATE = '2021-08-14'
END_DATE = '2026-08-14'

for code in test_codes:
    csv_path = os.path.join(KLINE_DIR, f'{code}.csv')
    if not os.path.exists(csv_path):
        print(f'{code}: MISSING csv')
        continue
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.Timestamp(START_DATE)) & (df['date'] <= pd.Timestamp(END_DATE))
    df = df[mask].reset_index(drop=True)
    if len(df) < 60:
        print(f'{code}: {len(df)} rows (skip)')
        continue
    df = df[['date','open','high','low','close','volume']].set_index('date')

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(GoldComboV10_HighYield)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.broker.setcash(500.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')

    try:
        results = cerebro.run()
        strat = results[0]
        final = cerebro.broker.getvalue()
        ret = (final / 500.0 - 1) * 100
        ta = strat.analyzers.ta.get_analysis()
        try:
            n_trades = ta.total.closed
        except:
            n_trades = 0
        dd = strat.analyzers.dd.get_analysis()
        max_dd = dd.drawdown if hasattr(dd,'drawdown') else dd.get('drawdown',0)
        print(f'[{code}] ret={ret:.4f}% trades={n_trades} max_dd={max_dd:.4f}% final={final:.2f}')
    except Exception as e:
        print(f'[{code}] ERROR: {e}')
        import traceback
        traceback.print_exc()
print('--- smoke done ---')
