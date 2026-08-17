"""V10 信号诊断脚本 (T2 smoke test) - 不修改 V10 策略类, 仅复制其逻辑做信号收集."""
import backtrader as bt
import pandas as pd
import math
import sys

class V10SignalCollector(bt.Strategy):
    params = dict(cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
                  vote_min=1, price_min=3.0, per_pos_pct=0.20,
                  hard_sl=0.30, trail_sl=0.25, cci_bubble=200.0)
    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.signals = []
        self.entry_price = None
        self.highest_since_entry = 0.0
    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price
    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.macd.macd[0]) or math.isnan(self.cci[0]) or math.isnan(self.plus_di[0]) or math.isnan(self.minus_di[0]): return
        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            if price < self.entry_price * (1.0 - self.p.hard_sl): self.close(); return
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl): self.close(); return
            if self.cci[0] > self.p.cci_bubble: self.close(); return
        else:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)
            self.signals.append({'date': str(self.data.datetime.date(0)), 'price': price, 'c3': c3, 'c4': c4, 'c7': c7, 'c8': c8})
            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                cash_to_use = self.broker.getcash() * self.p.per_pos_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

for code, label in [("600519", "茅台"), ("002415", "海康"), ("600438", "通威股份"), ("000001", "平安银行"), ("000333", "美的集团")]:
    csv_path = f'/Users/junze/quant-monitor-local/data/ashare_kline/{code}.csv'
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df[(df.index >= '2022-01-01') & (df.index <= '2026-08-14')]

    cerebro = bt.Cerebro()
    cerebro.addstrategy(V10SignalCollector)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    result = cerebro.run()
    strat = result[0]
    sigs = strat.signals
    n_complete = sum(1 for o in strat.broker.orders if o.status == o.Completed)
    final = cerebro.broker.getvalue()
    c3 = sum(1 for s in sigs if s['c3'])
    c4 = sum(1 for s in sigs if s['c4'])
    c7 = sum(1 for s in sigs if s['c7'])
    c8 = sum(1 for s in sigs if s['c8'])
    combined = sum(1 for s in sigs if s['c3'] and (s['c4']+s['c7']+s['c8']) >= 1)
    print(f'=== {code} {label} ===')
    print(f'  价格范围: {df.close.min():.1f}~{df.close.max():.1f}, 数据 {len(df)} 行')
    print(f'  C3:{c3}  C4:{c4}  C7:{c7}  C8:{c8}  Combined(C3+>=1):{combined}')
    print(f'  已完成订单: {n_complete}, 最终资金: {final:.2f}')
    if combined > 0 and combined <= 5:
        for s in [x for x in sigs if x['c3'] and (x['c4']+x['c7']+x['c8']) >= 1]:
            print(f'    Signal: {s["date"]} px={s["price"]:.2f} c4={s["c4"]} c7={s["c7"]} c8={s["c8"]}')
    print()