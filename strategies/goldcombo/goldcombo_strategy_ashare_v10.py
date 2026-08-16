import backtrader as bt
import math

class GoldComboV10_PathB(bt.Strategy):
    """
    =========================================================================
    V10 激进左翼高收益版 (用户军令状: 死磕左侧, 追求高收益)
    -------------------------------------------------------------------------
    【硬性规则 - 全部内嵌】
    1. 价格过滤: 仅交易收盘价 > 3.0 元 (防爆雷)
    2. 买入触发: C3(MACD零轴下金叉) 必选 + [C4/C7/C8] 至少满足 1 个 (vote_min=1, 极敏感)
    3. 卖出规则 A (仅防退市): 成本价下方 30% 才砍 (容忍主跌浪, 不早下车)
    4. 卖出规则 B (泡沫离场): CCI > 200 必平 (吃尽超级主升浪)
    5. 卖出规则 C (回撤锁利): 持仓峰值回撤 25% 平 (防止坐过山车)
    6. 仓位: 共享资金池, 单票 20% 现金 (允许同时持有多只, 资金不留闲置)
    =========================================================================
    """
    params = dict(
        cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
        vote_min=1, price_min=3.0, per_pos_pct=0.20,  # 单票占20%总资
        hard_sl=0.30, trail_sl=0.25, cci_bubble=200.0,
    )

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.macd.macd[0]) or math.isnan(self.cci[0]) or \
           math.isnan(self.plus_di[0]) or math.isnan(self.minus_di[0]): return

        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            # 规则3: 30% 防退市硬止损
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            # 规则5: 25% 峰值回撤
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            # 规则4: CCI>200 泡沫顶
            if self.cci[0] > self.p.cci_bubble:
                self.close(); return
        else:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)
            # 规则2: 极敏感买点
            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                # 规则6: 组合分仓, 单票20%
                cash_to_use = self.broker.getcash() * self.p.per_pos_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV10_PathB)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()