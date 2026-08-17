"""T3 单股验证 — 600438 通威股份 (锂电/光伏龙头).

用户原话: '先挑 1 只已知强势股(如 2022 年后的锂电/光伏龙头)手动验证能打出买入信号,再批量跑'
V10 沿用 V7LOCK 单股验证要求.

策略: V10_HighYield (GoldComboV10_HighYield), 一字不差, 不加任何外部 hold/lock
"""
import backtrader as bt
import pandas as pd
import json
import sys
import os

# 路径设置: 让脚本可独立运行
PROJECT_ROOT = '/Users/junze/quant-monitor-local'
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# 直接 import 用户原版, 不修改任何一行
from strategies.goldcombo.goldcombo_strategy_ashare_v10 import GoldComboV10_HighYield

CSV_PATH = '/Users/junze/quant-monitor-local/data/ashare_kline/600438.csv'

df = pd.read_csv(CSV_PATH)
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
df = df[(df.index >= '2022-01-01') & (df.index <= '2026-08-14')]

print(f'600438 通威股份 2022-01-01 ~ 2026-08-14')
print(f'数据: {len(df)} 行, 价格 {df.close.min():.2f} ~ {df.close.max():.2f}, 起始价 {df.iloc[0]["close"]:.2f}')

cerebro = bt.Cerebro()
cerebro.addstrategy(GoldComboV10_HighYield)  # 一字不差, 不加参数
cerebro.broker.setcash(10000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_perc(perc=0.003)

# 加 backtrader Analyzers
cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='tradeanalyzer')

cerebro.adddata(bt.feeds.PandasData(dataname=df))

start_value = cerebro.broker.getvalue()
results = cerebro.run()
final_value = cerebro.broker.getvalue()

strat = results[0]

n_completed = sum(1 for o in strat.broker.orders if o.status == o.Completed)
completed_trades = [o for o in strat.broker.orders if o.status == o.Completed]
buys = [o for o in completed_trades if o.isbuy()]
sells = [o for o in completed_trades if o.issell()]

dd = strat.analyzers.drawdown.get_analysis()
sharpe = strat.analyzers.sharpe.get_analysis()
ta = strat.analyzers.tradeanalyzer.get_analysis()

print(f'\n=== 600438 通威股份 单股回测 ===')
print(f'起始资金: {start_value:.2f}')
print(f'最终资金: {final_value:.2f}')
print(f'总收益: {(final_value - start_value) / start_value * 100:.4f}%')
print(f'买入笔数: {len(buys)}, 卖出笔数: {len(sells)}')
print(f'最大回撤: {dd.max.drawdown:.2f}%')
print(f'Sharpe: {sharpe.get("sharperatio", 0):.4f}')

# TradeAnalyzer
total_trades = ta.get('total', {}).get('total', 0) if 'total' in ta else 0
won = ta.get('won', {}).get('total', 0) if 'won' in ta else 0
lost = ta.get('lost', {}).get('total', 0) if 'lost' in ta else 0
print(f'完成交易轮次: {total_trades} (win {won}, loss {lost})')

# 详细成交
print(f'\n详细成交:')
for i, buy in enumerate(buys):
    print(f'  #{i+1} BUY  @ {buy.executed.price:.2f} size={buy.executed.size}')
for i, sell in enumerate(sells):
    print(f'  #{i+1} SELL @ {sell.executed.price:.2f} size={sell.executed.size}')

result = {
    'code': '600438',
    'name': '通威股份',
    'period': '2022-01-01 ~ 2026-08-14',
    'start_value': start_value,
    'final_value': final_value,
    'return_pct': (final_value - start_value) / start_value * 100,
    'n_completed_orders': n_completed,
    'n_buys': len(buys),
    'n_sells': len(sells),
    'max_drawdown_pct': dd.max.drawdown,
    'sharpe': sharpe.get('sharperatio', 0),
    'trade_total': total_trades,
    'trade_won': won,
    'trade_lost': lost,
    'verification': 'PASS' if n_completed >= 1 else 'FAIL',
}

OUT = '/Users/junze/goldcombo_real_backtest/v10/T3_single_stock/600438_result.json'
with open(OUT, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f'\n→ {result["verification"]}: 已完成订单 {n_completed} 笔 (>=1 笔要求)')
print(f'→ 结果落盘: {OUT}')

sys.exit(0 if result['verification'] == 'PASS' else 1)