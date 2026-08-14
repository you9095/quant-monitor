# -*- coding: utf-8 -*-
"""
黄金组合 A — 沪深 A 股 (排除科创+创业) · v3 小资金严控版
================================================================
用户上传日期: 2026-08-14
用户原始文件: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第三版.py
用户原始 sha256: 8cf94157d1db91367a657c2e414a287bd08c75817a3ecb6d973e754bfc28c0de
解 RTF 后 raw sha256: 45af259a1ebae70760d7cd27ded47130daaa7c5b330e3ed7c6df459efd7f9f7e
解 RTF 时间: 2026-08-14T14:29:33Z
解 RTF 方法: macOS 系统工具 `textutil -convert txt` (相比 python re.sub 更稳, 中文注释不丢)

策略类: GoldComboV3_1Strategy (v3 用户版 vs v2 的 GoldComboRelaxedStrategy)

v2 → v3 关键变化 (用户手动优化):
- 仓位管理: cash_pct=0.95 (1万本金打 9500) + size=按手取整 int(cash/price/100)*100
- 价格过滤: 剔除 price>90 高价股 + price<3 仙股
- 风控改严: hard_sl 8% → 5%
- 风控新增: trail_sl=0.08 (从最高点回撤 8% 走)
- 离场精简: 去掉 S3 (DMI 多方) + S4 (TRIX 水上), 只保留 CCI>120 + MACD 高位死叉
- 指标精简: 去掉 TRIX/TRMA/ADX (不需要了)
- 初始资金: 100000 → 10000

备份链:
- v1 备份: ~/goldcombo_real_backtest/v1_backup/
- v2 备份: ~/goldcombo_real_backtest/v2_backup/  (sha256 a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1)

以下为 v3 用户上传文件的真 Python 内容 (经 textutil 解 RTF 后):
================================================================
"""

import backtrader as bt

class GoldComboV3_1Strategy(bt.Strategy):
    """
    黄金组合 A - v3.1 小资金严控版
    买入：C3(必选) + [C4, C7, C8] 至少满足2个 + 价格过滤(3~90元)
    卖出：CCI>120 极端超买 或 MACD高位死叉 或 移动止盈(-8%回撤) 或 硬止损(-5%未盈利)
    仓位：单笔 95% 现金（几乎满仓干）
    本金：回测统一 1 万
    """
    params = dict(
        cci_thresh=-80,
        di_neg_thresh=25,
        di_pos_thresh=15,
        vote_min=2,
        price_max=90.0,
        price_min=3.0,
        cash_pct=0.95,       # 仓位打满 (1万本金即用9500)
        hard_sl=0.05,        # 【改】未盈利硬止损 5%
        trail_sl=0.08,       # 【改】盈利后移动止盈回撤阈值 8%
        print_log=True,
    )

    def __init__(self):
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        self.entry_price = None
        self.highest_since_entry = 0.0  # 记录持仓期间最高价

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        price = self.data.close[0]
        # 0. 价格闸门
        if price > self.p.price_max or price < self.p.price_min:
            return

        # 1. 持仓管理（卖点逻辑）
        if self.position:
            # 更新持仓最高价（用于移动止盈）
            if price > self.highest_since_entry:
                self.highest_since_entry = price

            # 风控 A：买入成本下方 5% 硬止损（防黑天鹅，严控磨损）
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close()
                if self.p.print_log: print(f'[硬止损-5%] {self.data.datetime.date(0)}')
                return

            # 风控 B：盈利后移动止盈（从最高点回撤 8% 才走）
            if price > self.entry_price and price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close()
                if self.p.print_log: print(f'[移动止盈-8%] {self.data.datetime.date(0)}')
                return

            # 止盈 C：CCI 极端超买（原 S2）
            if self.cci[0] > 120:
                self.close()
                if self.p.print_log: print(f'[超买离场] {self.data.datetime.date(0)}')
                return

            # 止盈 D：MACD 高位死叉（DIFF 下穿 DEA 且均在零轴上）
            if (self.macd.macd[0] < self.macd.signal[0]) and \
               (self.macd.macd[-1] >= self.macd.signal[-1]) and \
               (self.macd.macd[0] > 0):
                self.close()
                if self.p.print_log: print(f'[高位死叉离场] {self.data.datetime.date(0)}')
                return

        # 2. 空仓买入（Gated Voting 保留）
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
                    if self.p.print_log: print(f'[v3.1买入] {self.data.datetime.date(0)} 价:{price:.2f} 手:{size//100}')

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV3_1Strategy)
    # 【改】统一使用 1 万本金进行回测
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.001)
    print('初始资金: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('最终资金: %.2f' % cerebro.broker.getvalue())
    cerebro.plot()