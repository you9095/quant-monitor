# -*- coding: utf-8 -*-
"""
黄金组合 A 策略 v6 - 严控回撤去错杀版
==================================================================
来源: /Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V6版本.py
来源 sha256: 3fc45cd06f57f654bfc78ed9ba82cf53b42c8290fb88fee49a6b37c3fe245726
解 RTF 时间: 2026-08-15 13:31 (textutil -convert txt 解码成功)
备份链: v1 → v2 → v3 → v4 → v6 (v5 用户跳过)

策略类名: GoldComboV6Strategy
v6 vs v4 关键差异:
  - 5% 硬止损回归 (v3 → v4 删除, v6 拿回) hard_sl=0.05
  - 新增保本移动止损: breakeven_pct=0.05 + be_stop_pct=0.01
  - MACD 高位死叉离场回归 (DIFF 下穿 DEA 且都在零轴上)
  - 彻底删除: ATR 自适应止损 / 阶梯移动止盈 / MA10 跌破 / 时间止损
  - 保留: CCI>120 离场
  - 入场核心 (C3+C4/C7/C8) 和 C7/C8/price_min/cash_pct/滑点 与 v4 一致
==================================================================
"""

import backtrader as bt

class GoldComboV6Strategy(bt.Strategy):
    """
    黄金组合 A - v6 严控回撤去错杀版
    买点：v4 有效设定 (C3 + 投票 + 价>3, CCI<-70)
    卖点：5%铁律硬止损 + 保本移损(浮盈>5%后成本+1%离场) + CCI>120 + MACD水上死叉
          【彻底删除】时间止损、MA10破位、ATR宽止损（避免错杀与回撤放大）
    """
    params = dict(
        # 买点（冻结 v4）
        cci_thresh=-70,
        di_neg_thresh=20,
        di_pos_thresh=15,
        vote_min=2,
        price_min=3.0,
        cash_pct=0.95,
        # 卖点（v6 重构）
        hard_sl=0.05,         # 铁律：成本下 5% 必砍（压住 worst DD）
        breakeven_pct=0.05,   # 浮盈超 5% 启动保本
        be_stop_pct=0.01,     # 保本止损：成本上 1%
        print_log=True,
    )

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)

        self.entry_price = None

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min:
            return

        # ================= 持仓管理（v6 极简刚性卖点） =================
        if self.position:
            # 1. 铁律硬止损（未盈利或微利时的最大防线）
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); print(f'[硬止损-5%] {self.data.datetime.date(0)}'); return

            # 2. 保本移动止损（浮盈 >5% 后，底线提到成本+1%，绝对不容许赚钱变亏钱）
            if price > self.entry_price * (1.0 + self.p.breakeven_pct):
                if price < self.entry_price * (1.0 + self.p.be_stop_pct):
                    self.close(); print(f'[保本离场] {self.data.datetime.date(0)}'); return

            # 3. 极端超买离场（原 S2，吃尽情绪泡沫）
            if self.cci[0] > 120:
                self.close(); print(f'[超买离场] {self.data.datetime.date(0)}'); return

            # 4. MACD 高位死叉（零轴上 DIFF 下穿 DEA，确认主升浪终结）
            if (self.macd.macd[0] < self.macd.signal[0]) and \
               (self.macd.macd[-1] >= self.macd.signal[-1]) and \
               (self.macd.macd[0] > 0):
                self.close(); print(f'[高死离场] {self.data.datetime.date(0)}'); return

        # ================= 空仓买入（沿用 v4 买点） =================
        if not self.position:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0)
            c4 = bw > bw_prev
            c7 = self.cci[0] < self.p.cci_thresh
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and (self.minus_di[0] > self.p.di_neg_thresh)

            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                cash_to_use = self.broker.getcash() * self.p.cash_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)
                    print(f'[v6买入] {self.data.datetime.date(0)} 价:{price:.2f} 手:{size//100}')

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV6Strategy)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    print('初始资金: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('最终资金: %.2f' % cerebro.broker.getvalue())