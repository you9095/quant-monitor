import backtrader as bt
import math

class GoldComboV21b_AssetRot(bt.Strategy):
    """
    =========================================================================
    V21b 资产轮动修正版 (ETF5只+转债; 峰值回撤改20%; 零均线)
    -------------------------------------------------------------------------
    1. 标的: ETF(5只) + 可转债(价>100) 混合, 无个股
    2. 买: 收盘>60日最高(通道突破)
    3. 卖A: 成本-15% | 卖B: 峰值-20%(用户改保守) | 卖C: 峰值-3ATR | 卖D: CCI破灭
    4. 冷却: 60日
    =========================================================================
    """
    params = dict(
        break_n=60, atr_period=14, atr_multi=3.0,
        cci_peak=100.0, cci_fall=80.0,
        trail_sl=0.20,  # ← 用户指令: 35%改20%
        hard_sl=0.15,
        price_min=1.0, per_pos_pct=0.20, cool_days=60,
    )
    def __init__(self):
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
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); self._reset(); return
            if price < self.highest * (1.0 - self.p.trail_sl):  # 20%回撤
                self.close(); self._reset(); return
            if price < self.highest - (self.atr[0] * self.p.atr_multi):
                self.close(); self._reset(); return
            if self.cci[-5] > self.p.cci_peak and self.cci[0] < self.p.cci_fall:
                self.close(); self._reset(); return
        else:
            if self.cooldown > 0:
                self.cooldown -= 1; return
            if price > self.high_n[-1]:
                cash = self.broker.getcash() * self.p.per_pos_pct
                size = int(cash / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = price; self.highest = price

    def _reset(self):
        self.entry_price = None; self.cooldown = self.p.cool_days

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV21b_AssetRot)
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()