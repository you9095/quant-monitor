import backtrader as bt
import math

class GoldComboV16_ChannelBreakout(bt.Strategy):
    """
    =========================================================================
    V16 范式革命版 (摒弃 MACD/CCI, 改用通道突破 + ATR 头寸)
    -------------------------------------------------------------------------
    【突破性规则】
    1. 买点: 收盘价突破 20日 最高价 (唐奇安入场) -> 全仓干
    2. 卖点: 收盘价跌破 10日 最低价 (唐奇安离场) 或 ATR 止损
    3. 仓位: ATR 波动率定仓 (波动小多买, 波动大多买少)
    4. 过滤: 仅做价格 > 3 元, 且 50日MA 向上 (多头市才参与)
    =========================================================================
    """
    params = dict(
        break_out=20, break_down=10, ma_filter=50,
        atr_period=14, risk_pct=0.02,  # 单笔风险 2% 总资
    )

    def __init__(self):
        self.highest20 = bt.ind.Highest(self.data.high, period=self.p.break_out)
        self.lowest10 = bt.ind.Lowest(self.data.low, period=self.p.break_down)
        self.atr = bt.ind.ATR(period=self.p.atr_period)
        self.ma50 = bt.ind.SMA(period=self.p.ma_filter)
        self.entry_price = None

    def next(self):
        price = self.data.close[0]
        if price < 3.0 or math.isnan(self.atr[0]): return
        
        if not self.position:
            # 突破 20日高 + 50MA 向上 = 趋势启动
            if price > self.highest20[-1] and price > self.ma50[0]:
                # ATR 定仓: 用 2% 风险算size
                risk_cash = self.broker.getcash() * self.p.risk_pct
                size = int(risk_cash / (self.atr[0] * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = price
        else:
            # 破 10日低 或 成本回撤 2*ATR 离场
            if price < self.lowest10[-1] or price < self.entry_price - 2 * self.atr[0]:
                self.close()
                self.entry_price = None

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV16_ChannelBreakout)
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.run()