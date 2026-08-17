import backtrader as bt
import math

class GoldComboV7_Locked(bt.Strategy):
    """
    =========================================================================
    V7 锁死版 (右侧主升浪追击 - 将用户原始卖点组转为买入共振)
    -------------------------------------------------------------------------
    【硬性规则 - 全部内嵌, 严禁外部添加 hold/lock/时间止损】
    1. 价格过滤: 仅交易收盘价 > 3.0 元
    2. 买入触发: 以下 5 个强势信号中至少满足 3 个 (vote_min=3):
       - DMI多方: +DI>30, -DI<20, ADX>32 (原卖点S3)
       - MACD水上: DIFF>DEA 且 DIFF>0 且 DEA>0 (原卖点S6)
       - TRIX零上: TRIX>TRMA 且 TRIX>0 (原卖点S4)
       - OBV强势: OBV > MAOBV (原卖点S7)
       - CCI强势: CCI > 120 (原卖点S2)
    3. 卖出规则 A (硬止损): 成本价下方 8% 平仓 (右侧假突破防御)
    4. 卖出规则 B (移动止盈): 持仓峰值回撤 15% 平仓 (让利润奔跑)
    5. 卖出规则 C (趋势终结): MACD 高位死叉 (DIFF下穿DEA) 平仓
    6. 仓位管理: 单笔 95% 现金, 100股整数倍
    =========================================================================
    """
    params = dict(
        vote_min=3, price_min=3.0, cash_pct=0.95,
        hard_sl=0.08, trail_sl=0.15,
    )

    def __init__(self):
        # 指标初始化 (完全对应您原始卖点描述)
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.adx = bt.ind.ADX(period=14)
        self.trix = bt.ind.TRIX(period=12)
        self.trma = bt.ind.SMA(self.trix, period=9)
        self.obv = bt.ind.OBV()
        self.maobv = bt.ind.SMA(self.obv, period=30)
        
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        # 规则1: 价格过滤
        if price < self.p.price_min:
            return
        
        # 数据防火墙: 防 CSV 缺量导致指标 NaN 静默失效
        if math.isnan(self.macd.macd[0]) or math.isnan(self.plus_di[0]) or math.isnan(self.obv[0]):
            return

        # ========== 持仓卖出 ==========
        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price
            
            # 规则3a: 8% 硬止损
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); return
            
            # 规则4: 15% 峰值回撤止盈
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); return
            
            # 规则5: MACD 高位死叉 (右侧趋势终结信号, 与左侧不同此处保留)
            if (self.macd.macd[0] < self.macd.signal[0]) and \
               (self.macd.macd[-1] >= self.macd.signal[-1]):
                self.close(); return

        # ========== 空仓买入 (原卖点转买点) ==========
        else:
            # 规则2 分解
            s_dmi = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
            s_macd = (self.macd.macd[0] > self.macd.signal[0]) and \
                     (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)
            s_trix = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
            s_obv = (self.obv[0] > self.maobv[0])
            s_cci = (self.cci[0] > 120)

            if sum([s_dmi, s_macd, s_trix, s_obv, s_cci]) >= self.p.vote_min:
                # 规则6: 仓位管理
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