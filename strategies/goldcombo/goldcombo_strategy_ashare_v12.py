import backtrader as bt
import math

class GoldComboV12_LeftBuyRightSell(bt.Strategy):
    """
    =========================================================================
    V12 左买右卖混合版 (执行用户方向1: 卖点进一步右移 + 复刻V10路径B资金)
    -------------------------------------------------------------------------
    【硬性规则】
    1. 价格过滤: >3.0 元
    2. 买入: C3(MACD零轴下金叉) + [C4/C7/C8] 选≥1 (极敏左侧)
    3. 卖出 A (防退市): 成本 -30% 砍 (宽容)
    4. 卖出 B (回撤): 峰值回撤 25% 离场 (吃主升浪)
    5. 卖出 C (能量终结): 价格破 MA20 且 DMI空方反扑(+DI<10,-DI>25) -> 确认右侧顶部离场
    6. 仓位: 单票 10% 总资 (5万本金=5000/只, 复刻V10路径B)
    =========================================================================
    """
    params = dict(
        cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
        vote_min=1, price_min=3.0, per_pos_pct=0.10,
        hard_sl=0.30, trail_sl=0.25,
    )

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.ma20 = bt.ind.SMA(period=20)  # 右移生命线
        
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.macd.macd[0]) or math.isnan(self.ma20[0]): return

        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            # 规则3: 30% 硬止损
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            # 规则4: 25% 回撤
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            # 规则5: 能量终结 (右移卖点: 破MA20 + 空方反扑)
            if price < self.ma20[0] and (self.plus_di[0] < 10) and (self.minus_di[0] > 25):
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
    cerebro.addstrategy(GoldComboV12_LeftBuyRightSell)
    # 锁死 5 万本金，单票 10% = 5000，复刻 V10 路径 B 最优配置
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()
