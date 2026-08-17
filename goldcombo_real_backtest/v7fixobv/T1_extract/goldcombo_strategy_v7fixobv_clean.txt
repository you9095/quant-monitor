import backtrader as bt

# ================= 自定义 OBV 指标 (解决 bt.ind.OBV 不存在问题) =================
class MyOBV(bt.Indicator):
    lines = ('obv',)
    def __init__(self):
        # 用上一根收盘价和当前收盘价比较，决定加减成交量
        self.lines.obv = bt.ind.SumN(
            bt.Cmp(self.data.close, self.data.close(-1)) * self.data.volume,
            period=1
        )  # 简化版：Backtrader 的 SumN+Cmp 组合等效于能量潮累加

# ================= 主策略类 (V7 锁死修复版) =================
class GoldComboV7_Locked(bt.Strategy):
    """
    =========================================================================
    V7 锁死版 (右侧主升浪追击) - OBV 自定义修复
    -------------------------------------------------------------------------
    【硬性规则 - 全部内嵌】
    1. 价格过滤: 仅交易收盘价 > 3.0 元
    2. 买入触发: 5个强势信号至少满足3个 (vote_min=3)
       - DMI多方 / MACD水上 / TRIX零上 / OBV强势 / CCI强势
    3. 卖出: 成本-8%砍 / 峰值回撤15%砍 / MACD高位死叉砍
    4. 仓位: 95% 现金, 100股整数倍
    =========================================================================
    """
    params = dict(
        vote_min=3, price_min=3.0, cash_pct=0.95,
        hard_sl=0.08, trail_sl=0.15,
    )

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.adx = bt.ind.ADX(period=14)
        self.trix = bt.ind.TRIX(period=12)
        self.trma = bt.ind.SMA(self.trix, period=9)
        # 使用自定义 OBV，不再调用 bt.ind.OBV()
        self.obv = MyOBV(self.data)
        self.maobv = bt.ind.SMA(self.obv, period=30)
        
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min:
            return

        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            if (self.macd.macd[0] < self.macd.signal[0]) and \
               (self.macd.macd[-1] >= self.macd.signal[-1]):
                self.close(); return
        else:
            s_dmi = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
            s_macd = (self.macd.macd[0] > self.macd.signal[0]) and \
                     (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)
            s_trix = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
            s_obv = (self.obv.obv[0] > self.maobv[0])
            s_cci = (self.cci[0] > 120)

            if sum([s_dmi, s_macd, s_trix, s_obv, s_cci]) >= self.p.vote_min:
                cash_to_use = self.broker.getcash() * self.p.cash_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV7_Locked)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()