#!/usr/bin/env python3
"""T3 smoke test - v6 策略 import + 双股 smoke 跑批"""
import sys
import os

# 设置 quant-monitor-local 为工作目录
project_dir = '/Users/junze/quant-monitor-local'
os.chdir(project_dir)
sys.path.insert(0, project_dir)

# 1. import 测试
print('=== 1. import 测试 ===')
from strategies.goldcombo.goldcombo_strategy_ashare_v6 import GoldComboV6Strategy
print(f'import OK: {GoldComboV6Strategy.__name__}')

# 验证 alias 也指向 v6
from strategies.goldcombo.goldcombo_strategy_ashare import GoldComboStrategy
print(f'alias GoldComboStrategy → {GoldComboStrategy.__name__}')
assert GoldComboStrategy is GoldComboV6Strategy, 'alias 指向不对!'
print('✅ alias 正确指向 v6')

# 2. smoke test 600519 (茅台, ~1400 元, 应触发 price_min=3.0 过滤, 0 交易)
print()
print('=== 2. smoke test 600519 (茅台, 价 ~1400) ===')
import backtrader as bt
import pandas as pd

df = pd.read_csv('data/ashare_kline/600519.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')

cerebro = bt.Cerebro()
cerebro.addstrategy(GoldComboV6Strategy, print_log=False)
cerebro.broker.setcash(10000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_perc(perc=0.003)
cerebro.adddata(bt.feeds.PandasData(dataname=df))

print(f'起始资金: {cerebro.broker.getvalue():.2f}')
print(f'数据期: {df.index.min()} ~ {df.index.max()} ({len(df)} 行)')
print(f'价格范围: {df["close"].min():.2f} ~ {df["close"].max():.2f}')
print(f'当前价: {df["close"].iloc[-1]:.2f}')

result_600519 = cerebro.run()
final_600519 = cerebro.broker.getvalue()
print(f'最终资金: {final_600519:.2f}')
print(f'价格 < 3 元触发过滤 → 茅台价远高于 3.0, 应该正常跑 (但需要触发 C3+C4/C7/C8 才会有交易)')

# 3. smoke test 002415 (海康威视, 价 ~30)
print()
print('=== 3. smoke test 002415 (海康威视, 价 ~30) ===')

df2 = pd.read_csv('data/ashare_kline/002415.csv')
df2['date'] = pd.to_datetime(df2['date'])
df2 = df2.set_index('date')

cerebro2 = bt.Cerebro()
cerebro2.addstrategy(GoldComboV6Strategy, print_log=False)
cerebro2.broker.setcash(10000.0)
cerebro2.broker.setcommission(commission=0.001)
cerebro2.broker.set_slippage_perc(perc=0.003)
cerebro2.adddata(bt.feeds.PandasData(dataname=df2))

print(f'起始资金: {cerebro2.broker.getvalue():.2f}')
print(f'数据期: {df2.index.min()} ~ {df2.index.max()} ({len(df2)} 行)')
print(f'价格范围: {df2["close"].min():.2f} ~ {df2["close"].max():.2f}')
print(f'当前价: {df2["close"].iloc[-1]:.2f}')

result_002415 = cerebro2.run()
final_002415 = cerebro2.broker.getvalue()
print(f'最终资金: {final_002415:.2f}')

# 4. 验证策略参数
print()
print('=== 4. 验证 v6 策略参数 ===')
print(f'cci_thresh: {GoldComboV6Strategy.params.cci_thresh}')
print(f'hard_sl: {GoldComboV6Strategy.params.hard_sl}')
print(f'breakeven_pct: {GoldComboV6Strategy.params.breakeven_pct}')
print(f'be_stop_pct: {GoldComboV6Strategy.params.be_stop_pct}')
print(f'di_neg_thresh: {GoldComboV6Strategy.params.di_neg_thresh}')
print(f'di_pos_thresh: {GoldComboV6Strategy.params.di_pos_thresh}')
print(f'vote_min: {GoldComboV6Strategy.params.vote_min}')
print(f'price_min: {GoldComboV6Strategy.params.price_min}')
print(f'cash_pct: {GoldComboV6Strategy.params.cash_pct}')

print()
print('=== smoke test PASS ===')