import backtrader as bt
import math

class GoldComboV8_Final(bt.Strategy):
    """
    =========================================================================
    V8 终版 (防错纯净版) - 买点与 V6 完全一致, 仅改卖点
    硬性规则: 价格>3 | C3必选+辅助≥2 | 硬止损10% | 回撤15% | CCI>120离场
    【严禁】任何外部脚本添加 20天hold / 50%lock / 4指标AND
    =========================================================================
    """
    params = dict(
        cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
        vote_min=2, price_min=3.0, cash_pct=0.95,
        hard_sl=0.10, trail_sl=0.15, cci_exit=120.0,
        debug=False,  # 设 True 可打印信号变量, 查 0 触发原因
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
        # 硬性规则1: 价格过滤
        if price < self.p.price_min:
            return

        # ===== 数据防火墙: 防止 CSV 缺量导致 DMI=NaN 静默 0 触发 =====
        if math.isnan(self.macd.macd[0]) or math.isnan(self.cci[0]) or \
           math.isnan(self.plus_di[0]) or math.isnan(self.minus_di[0]):
            if self.p.debug: print(f'[数据缺失] {self.data.datetime.date(0)} 跳过')
            return

        # ===== 持仓卖出 =====
        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            if self.cci[0] > self.p.cci_exit:
                self.close(); return
            # 无 MACD 卖点
        # ===== 空仓买入 (与 V6 完全相同逻辑) =====
        else:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)

            if self.p.debug:
                print(f'[信号] {self.data.datetime.date(0)} C3:{c3} C4:{c4} C7:{c7} C8:{c8}')

            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                cash_to_use = self.broker.getcash() * self.p.cash_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV8_Final)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()