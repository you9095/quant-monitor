import backtrader as bt

class GoldComboRelaxedStrategy(bt.Strategy):
    """
    黄金组合 A - 改良共振版 (Gated Voting)
    买入：C3(MACD低位金叉) 必选 + [C4(BOLL开口), C7(CCI<-80), C8(DMI空方:-DI>25,+DI<15)] 至少满足2个
    卖点：硬止损 8% + CCI>120 + DMI多方 + TRIX水上 + MACD水上
    """
    params = dict(
        sl_pct=0.08,           # 硬止损 8%
        cci_thresh=-80,        # CCI 超卖阈值放宽
        di_neg_thresh=25,      # -DI 阈值放宽
        di_pos_thresh=15,      # +DI 阈值放宽
        vote_min=2,            # 辅助条件至少满足个数
        print_log=True,
    )

    def __init__(self):
        # 指标初始化
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.adx = bt.ind.ADX(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.trix = bt.ind.TRIX(period=12)
        self.trma = bt.ind.SMA(self.trix, period=9)
        self.entry_price = None

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price

    def next(self):
        # ================= 持仓管理 =================
        if self.position:
            # 1. 硬止损
            if self.entry_price is not None:
                if self.data.close[0] < self.entry_price * (1.0 - self.p.sl_pct):
                    self.close()
                    if self.p.print_log: print(f'[止损] {self.data.datetime.date(0)}')
                    return

            # 2. 卖点（任一满足即离场）
            s2 = self.cci[0] > 120
            s3 = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
            s4 = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
            s6 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)

            if s2 or s3 or s4 or s6:
                self.close()
                if self.p.print_log: print(f'[信号离场] {self.data.datetime.date(0)}')
            return

        # ================= 空仓买入 =================
        if not self.position:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]

            # 核心条件 C3：MACD 低位金叉（必选）
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and \
                 (self.macd.macd[0] < 0)

            # 辅助条件组
            c4 = bw > bw_prev  # BOLL开口
            c7 = self.cci[0] < self.p.cci_thresh  # CCI超卖（放宽）
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and \
                 (self.minus_di[0] > self.p.di_neg_thresh)  # DMI空方（放宽）

            # 投票计数：辅助条件满足几个？
            aux_votes = sum([c4, c7, c8])

            # 核心门控 + 投票买入
            if c3 and (aux_votes >= self.p.vote_min):
                self.buy()
                if self.p.print_log:
                    print(f'[改良买入] {self.data.datetime.date(0)} 辅助触发数:{aux_votes}')

# ================= 回测启动示例 =================
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboRelaxedStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.001)
    print('初始资金: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('最终资金: %.2f' % cerebro.broker.getvalue())
    cerebro.plot()