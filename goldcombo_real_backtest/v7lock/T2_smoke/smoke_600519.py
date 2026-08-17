#!/usr/local/bin/python3.12
"""T2 smoke test 600519 茅台"""
import sys
sys.path.insert(0, '/Users/junze/quant-monitor-local')
import backtrader as bt
import pandas as pd
from strategies.goldcombo.goldcombo_strategy_ashare_v7lock import GoldComboV7_Locked

df = pd.read_csv('/Users/junze/quant-monitor-local/data/ashare_kline/600519.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
df = df[(df.index >= '2022-01-01') & (df.index <= '2026-08-14')]

cerebro = bt.Cerebro()
cerebro.addstrategy(GoldComboV7_Locked)
cerebro.broker.setcash(10000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_perc(perc=0.003)
cerebro.adddata(bt.feeds.PandasData(dataname=df))

start_value = cerebro.broker.getvalue()
result = cerebro.run()
final_value = cerebro.broker.getvalue()

print('600519 茅台 2022-2026 测试:')
print('  起始资金: %.2f' % start_value)
print('  最终资金: %.2f' % final_value)
print('  总收益: %.2f%%' % ((final_value - start_value) / start_value * 100))
print('  bars 数: %d' % len(df))
print('  价格范围: %.2f ~ %.2f' % (df.close.min(), df.close.max()))