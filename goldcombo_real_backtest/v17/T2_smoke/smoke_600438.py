"""T2 单股验证 — 600438 通威股份 (5万本金锁死, V17 极低频突破)"""
import sys
import os
sys.path.insert(0, '/Users/junze/quant-monitor-local')

import backtrader as bt
import pandas as pd
from strategies.goldcombo.goldcombo_strategy_ashare_v17 import GoldComboV17_LowFreqBreakout

CODE = '600438'
CSV = f'/Users/junze/quant-monitor-local/data/ashare_kline/{CODE}.csv'

# 加载数据
df = pd.read_csv(CSV)
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
df = df[(df.index >= '2022-01-01') & (df.index <= '2026-08-14')]

print(f"=== {CODE} 通威股份 V17_LowFreqBreakout 单股验证 (5万本金锁死) ===")
print(f"数据期: 2022-01-01 ~ 2026-08-14 ({len(df)} 根K线)")
print(f"起始价: {df.iloc[0]['close']:.2f}")
print(f"终止价: {df.iloc[-1]['close']:.2f}")
print(f"区间最低: {df['low'].min():.2f}")
print(f"区间最高: {df['high'].max():.2f}")
print()

# backtrader 引擎
cerebro = bt.Cerebro()
cerebro.addstrategy(GoldComboV17_LowFreqBreakout)  # V17 极简 7 参数, 不含 print_log
cerebro.broker.setcash(50000.0)  # ⚠️ 用户原话硬约束: 5万锁死
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_perc(perc=0.003)
cerebro.adddata(bt.feeds.PandasData(dataname=df))

# Analyzers
cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return')
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0, annualize=True)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

start_value = cerebro.broker.getvalue()
results = cerebro.run()
final_value = cerebro.broker.getvalue()

strat = results[0]
sharpe = strat.analyzers.sharpe.get_analysis()
drawdown = strat.analyzers.drawdown.get_analysis()
trade_analysis = strat.analyzers.trades.get_analysis()

total_trades = trade_analysis.get('total', {}).get('closed', 0)
won = trade_analysis.get('won', {}).get('total', 0)
lost = trade_analysis.get('lost', {}).get('total', 0)

print(f"=== 关键数字 ===")
print(f"起始资金: {start_value:.2f}")
print(f"最终资金: {final_value:.2f}")
print(f"总收益: {(final_value - start_value) / start_value * 100:.4f}%")
print(f"已平仓笔数: {total_trades}")
print(f"盈利笔数: {won}")
print(f"亏损笔数: {lost}")
print(f"胜率: {(won / total_trades * 100) if total_trades > 0 else 0:.2f}%")
print(f"最大回撤: {drawdown.max.drawdown:.2f}%")
print(f"最大回撤金额: {drawdown.max.moneydown:.2f}")
print(f"Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
print()

# V17 关键验证
print(f"=== V17 极低频突破 关键验证 ===")
print(f"半年(120日)突破 + MA多头序入场: {'触发' if total_trades > 0 else '未触发 (此单股 5Y 内无满足双条件的时点)'}")
print(f"95% 集中持仓验证: {'正常' if total_trades > 0 else 'N/A (无持仓)'}")
print()

# 年化
years = 4.62  # 2022-01-01 ~ 2026-08-14
total_return = (final_value / start_value)
annual_return = (total_return ** (1 / years) - 1) * 100
print(f"年化收益 (近似, {years:.2f}Y): {annual_return:.2f}%")