import backtrader as bt
import math

class GoldComboV14_ScaleIn(bt.Strategy):
    """
    =========================================================================
    V14 左试右加版 (用户观点落地: 左侧金叉半仓 + MA10加仓 + 快卖)
    -------------------------------------------------------------------------
    【硬性规则】
    1. 价格过滤: >3.0 元
    2. 首次买入(左试): C3(MACD零轴下金叉)+[C4/C7/C8]≥1 -> 买半仓(总资10%)
    3. 加仓(右确认): 持仓中且未加过 + 价格>MA10 -> 买另半仓(总资10%)
    4. 卖出 A: 破 MA10 (快速离场, 控回撤)
    5. 卖出 B: MACD 高位死叉 (DIFF下穿DEA)
    6. 卖出 C: 峰值回撤 25% (trail_sl)
    7. 硬止损: 成本 -20% (宽容, 复刻V10精神)
    =========================================================================
    """
    params = dict(
        cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
        vote_min=1, price_min=3.0,
        half_pct=0.10,   # 半仓=总资10%, 加满=20%
        hard_sl=0.20, trail_sl=0.25,
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
        self.added = False  # 加仓状态机

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            if self.entry_price is None:
                self.entry_price = order.executed.price
            self.highest_since_entry = max(self.highest_since_entry, order.executed.price)

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.macd.macd[0]) or math.isnan(self.ma10[0]): return

        # ========== 持仓管理 ==========
        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            
            # 规则7: 20% 硬止损
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); self.added=False; self.entry_price=None; return
            # 规则6: 25% 回撤
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); self.added=False; self.entry_price=None; return
            # 规则4: 破 MA10 快离场
            if price < self.ma10[0]:
                self.close(); self.added=False; self.entry_price=None; return
            # 规则5: MACD 死叉
            if (self.macd.macd[0] < self.macd.signal[0]) and \
               (self.macd.macd[-1] >= self.macd.signal[-1]):
                self.close(); self.added=False; self.entry_price=None; return

            # 规则3: 右侧加仓 (未加过 + 站上MA10)
            if not self.added and price > self.ma10[0]:
                cash_to_use = self.broker.getcash() * self.p.half_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    self.added = True  # 锁定，不重复加

        # ========== 首次买入 (左试) ==========
        else:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)
            
            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                cash_to_use = self.broker.getcash() * self.p.half_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    # added 保持 False，等 next -bar MA10 确认再加

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV14_ScaleIn)
    cerebro.broker.setcash(50000.0)  # 锁死 5 万
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()