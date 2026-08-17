import backtrader as bt
import math

class GoldComboV11_EnergyPeak(bt.Strategy):
    params = dict(
        cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
        vote_min=1, price_min=3.0, per_pos_pct=0.20,
        hard_sl=0.15, trail_sl=0.20,
        cci_peak=100.0, cci_fall=80.0,
    )
    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.ma10 = bt.ind.SMA(period=10)
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.macd.macd[0]) or math.isnan(self.cci[0]) or math.isnan(self.ma10[0]): return

        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            # 能量衰竭离场：CCI曾>100现<80 且 破MA10
            if (self.cci[-5] > self.p.cci_peak) and (self.cci[0] < self.p.cci_fall) and (price < self.ma10[0]):
                self.close(); return
        else:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)
            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                cash_to_use = self.broker.getcash() * self.p.per_pos_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV11_EnergyPeak)
    # 硬性规则：本金 5 万，不准改回 1 万，否则重演 V10 sizing bug
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()