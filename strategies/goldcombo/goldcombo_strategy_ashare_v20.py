import backtrader as bt
import math

class GoldComboV20_NoMA(bt.Strategy):
    """
    =========================================================================
    V20 零均线数值化版 (用户指令: 卖点剔除所有MA, 用具体数值/ATR/CCI)
    -------------------------------------------------------------------------
    【硬性规则 - 全策略无 bt.ind.SMA / MA 】
    1. 买点: 收盘 > 60日最高价 (通道突破, 非均线) 
    2. 卖A: 成本 -15% (数值硬止损)
    3. 卖B: 峰值回撤 -35% (数值止盈, 包容洗盘)
    4. 卖C: 价格 < 峰值 - 3*ATR(14) (波动率断裂, 替代破线)
    5. 卖D: CCI 前5日>100 现<80 (动量泡沫破灭)
    6. 冷却: 卖后 60日禁买
    =========================================================================
    """
    params = dict(
        break_n=60, atr_period=14, atr_multi=3.0,
        cci_peak=100.0, cci_fall=80.0,
        trail_sl=0.35, hard_sl=0.15,
        price_min=1.0, cash_pct=0.95, cool_days=60,
    )
    def __init__(self):
        # 仅用通道(Highest)和波动率/动量, 无 SMA
        self.high_n = bt.ind.Highest(self.data.high, period=self.p.break_n)
        self.atr = bt.ind.ATR(period=self.p.atr_period)
        self.cci = bt.ind.CCI(period=14)
        self.entry_price = None
        self.highest = 0.0
        self.cooldown = 0

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min: return
        if math.isnan(self.atr[0]) or math.isnan(self.cci[0]): return

        if self.position:
            if price > self.highest: self.highest = price
            # 卖A: 成本-15%
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); self._reset(); return
            # 卖B: 峰值-35%
            if price < self.highest * (1.0 - self.p.trail_sl):
                self.close(); self._reset(); return
            # 卖C: ATR断裂 (非均线)
            if price < self.highest - (self.atr[0] * self.p.atr_multi):
                self.close(); self._reset(); return
            # 卖D: CCI泡沫破灭 (非均线)
            if self.cci[-5] > self.p.cci_peak and self.cci[0] < self.p.cci_fall:
                self.close(); self._reset(); return
        else:
            if self.cooldown > 0:
                self.cooldown -= 1; return
            # 买: 纯通道突破
            if price > self.high_n[-1]:
                cash = self.broker.getcash() * self.p.cash_pct
                size = int(cash / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = price; self.highest = price

    def _reset(self):
        self.entry_price = None; self.cooldown = self.p.cool_days

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV20_NoMA)
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()
