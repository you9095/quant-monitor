"""
T2 单股验证 — 600438 通威股份 (V14_ScaleIn)
- 5 万本金 (用户原话硬约束)
- 验证 left-then-right (首次半仓 + MA10 加仓) 是否触发
- 跟踪 buy/sell 事件, 验证 self.added 状态机
"""
import sys
import os
sys.path.insert(0, '/Users/junze/quant-monitor-local')
import backtrader as bt
import pandas as pd
from strategies.goldcombo.goldcombo_strategy_ashare_v14 import GoldComboV14_ScaleIn


class TrackingStrategy(GoldComboV14_ScaleIn):
    """包装策略类, 跟踪 buy/sell 事件"""
    params = dict(print_log=False)
    def __init__(self):
        super().__init__()
        self.buy_log = []
        self.sell_log = []
        self.added_events = []
        self._last_added_log = False

    def notify_order(self, order):
        super().notify_order(order)
        if order.status in [order.Completed]:
            action = 'BUY' if order.isbuy() else 'SELL'
            log = self.buy_log if order.isbuy() else self.sell_log
            log.append({
                'date': bt.num2date(order.executed.dt).strftime('%Y-%m-%d'),
                'price': float(order.executed.price),
                'size': int(order.executed.size),
                'value': float(order.executed.value),
            })

    def next(self):
        super().next()
        # 记录加仓触发 (after next(), self.added 已更新)
        if self.added and not self._last_added_log:
            bar_date = bt.num2date(self.datas[0].datetime[0]).strftime('%Y-%m-%d')
            self.added_events.append({
                'date': bar_date,
                'price': float(self.data.close[0]),
                'ma10': float(self.ma10[0]),
                'position_size': int(self.position.size) if self.position else 0,
            })
            self._last_added_log = True
        if not self.added:
            self._last_added_log = False


df = pd.read_csv('data/ashare_kline/600438.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
df = df[(df.index >= '2022-01-01') & (df.index <= '2026-08-14')]

cerebro = bt.Cerebro()
cerebro.addstrategy(TrackingStrategy)
cerebro.broker.setcash(50000.0)  # ⚠️ 用户原话硬约束: 5万锁死
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_perc(perc=0.003)
cerebro.adddata(bt.feeds.PandasData(dataname=df))

start_value = cerebro.broker.getvalue()
result = cerebro.run()
final_value = cerebro.broker.getvalue()

strat = result[0]
trades_count = len(strat.buy_log) + len(strat.sell_log)
buy_count = len(strat.buy_log)
sell_count = len(strat.sell_log)
added_count = len(strat.added_events)

print(f'600438 通威股份 2022-2026 测试 (V14_ScaleIn 左试右加):')
print(f'  起始资金: {start_value:.2f}')
print(f'  最终资金: {final_value:.2f}')
print(f'  总收益: {(final_value - start_value) / start_value * 100:.2f}%')
print(f'  总订单数: {trades_count} (BUY: {buy_count}, SELL: {sell_count})')
print(f'  加仓事件数: {added_count} (self.added 状态机触发次数)')
print()

if strat.buy_log:
    print(f'  首次 BUY: {strat.buy_log[0]}')
    if len(strat.buy_log) > 1:
        print(f'  第 2 次 BUY (加仓): {strat.buy_log[1]}')
if strat.sell_log:
    print(f'  首次 SELL: {strat.sell_log[0]}')
print()

if added_count > 0:
    print(f'  ✓ 加仓机制成功触发 ({added_count} 次):')
    for ae in strat.added_events[:5]:
        print(f'    {ae}')
else:
    print(f'  ⚠️ 加仓机制未触发 (但 entry 可能仍有效)')
