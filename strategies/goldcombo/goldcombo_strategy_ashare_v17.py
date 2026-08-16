import backtrader as bt
import math

class GoldComboV17_LowFreqBreakout(bt.Strategy):
    """
    =========================================================================
    V17 极低频突破版 (用户底线: 年化>30% & 5年<1000笔)
    -------------------------------------------------------------------------
    【突破性规则 - 抛弃所有短周期振荡指标】
    1. 价格过滤: >3.0 元
    2. 买点(极严): 收盘价 > 120日最高价(半年突破) 且 MA20>MA60>MA120(多头序)
       -> 全仓单只 (集中火力, 不复用10%分仓)
    3. 卖点: 收盘价 < MA20(短期生命线) 或 峰值回撤 20%
    4. 硬止损: 成本 -15%
    5. 周期: 日线但参数拉长, 天然低频
    =========================================================================
    """
    params = dict(
        break_n=120, ma_short=20, ma_mid=60, ma_long=120,
        trail_sl=0.20, hard_sl=0.15,
        per_pos_pct=0.95,  # 集中持仓, 不全散
    )

    def __init__(self):
        self.highest_n = bt.ind.Highest(self.data.high, period=self.p.break_n)
        self.ma_s = bt.ind.SMA(period=self.p.ma_short)
        self.ma_m = bt.ind.SMA(period=self.p.ma_mid)
        self.ma_l = bt.ind.SMA(period=self.p.ma_long)
        self.entry_price = None
        self.highest_since_entry = 0.0

    def next(self):
        price = self.data.close[0]
        if price < 3.0: return
        if math.isnan(self.ma_l[0]) or math.isnan(self.highest_n[0]): return

        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); self._reset(); return
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); self._reset(); return
            if price < self.ma_s[0]:  # 破20日线走
                self.close(); self._reset(); return
        else:
            # 规则2: 半年突破 + 均线多头
            breakout = price > self.highest_n[-1]
            bull_seq = (self.ma_s[0] > self.ma_m[0]) and (self.ma_m[0] > self.ma_l[0])
            if breakout and bull_seq:
                cash = self.broker.getcash() * self.p.per_pos_pct
                size = int(cash / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = price
                    self.highest_since_entry = price

    def _reset(self):
        self.entry_price = None

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV17_LowFreqBreakout)
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()