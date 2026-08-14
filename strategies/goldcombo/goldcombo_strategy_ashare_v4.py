#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[2026-08-14 版本管理 v4] v3 已废弃 (小资金严控版),保留文件仅为历史回测兼容。
本文件 v4 = 灵活卖点/回撤控制版 (ATR 自适应 + 阶梯移动止盈 + 时间止损)。

来源: /Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第四版V5.py
来源 sha256: 03162c80dc0ff1a0aff4eb9d5bd089f206cd3ad0e03b0dab51dd3a9fe876acde
RTF 解码:  textutil -convert txt (macOS native, 100% 保真)
解码时间:  2026-08-14 23:00 (subagent 派单)

v4 vs v3 差异 (用户手动优化,subagent 不再改):
- 硬止损 5% → ATR 自适应 (entry_price - ATR(14) * 2.5)
- 移动止盈 固定 8% → 阶梯式 (>20% trail=10%, >10% trail=8%, >0% trail=6%, 未盈利 trail=0)
- 新增 MA10 均线离场 (盈利>3% 且跌破 MA10)
- 新增 时间止损 (持仓 20 天 + 盈利<3% 强制平仓)
- 去掉 MACD 高位死叉离场 (v3 有,v4 简化)
- C7 CCI 阈值 <-80 → <-70 (更敏感)
- C8 -DI 阈值 >25 → >20 (更敏感)
- 滑点 0.001 → 0.003 (3 倍,更保守)
- price_min 保持 3.0 (策略类阈值,数据层 price<2 过滤在 run_backtest 阶段执行)

版本备份链:
- v1 备份: ~/goldcombo_real_backtest/v1_backup/  (git da10a57)
- v2 备份: ~/goldcombo_real_backtest/v2_backup/  (git 57267e1)
- v3 备份: ~/goldcombo_real_backtest/v3_backup/  (本次 v3→v4 前新建,4 文件 + sha256)
- v4 当前: strategies/goldcombo/goldcombo_strategy_ashare_v4.py (本文件)

v4 类名 GoldComboV5Strategy (用户命名混乱:文件名第四版,类名 v5,按 v4 处理)
v4 兜底 (兜底兜底兜底兜底兜底兜底兜底兜底兜底兜底兜底): 改阈值需用户原话驱动,subagent 不擅自修改。

数据层价格过滤: 用户原话"剔除掉股票价格小于 2 块钱以下的所有股票",在 run_backtest 阶段
先按 first_price<2 过滤股票池 (不污染策略类 price_min=3.0)。
"""
import backtrader as bt

class GoldComboV5Strategy(bt.Strategy):
    """
    黄金组合 A - v5 灵活卖点/回撤控制版
    买点：v4 设定 (C3 + 投票 + 价>3)
    卖点：ATR自适应止损 + 阶梯移动止盈 + MA10破位 + CCI超买 + 时间止损
    """
    params = dict(
        # --- 买点参数（冻结 v4） ---
        cci_thresh=-70,
        di_neg_thresh=20,
        di_pos_thresh=15,
        vote_min=2,
        price_min=3.0,
        cash_pct=0.95,
        # --- 卖点灵活参数 ---
        atr_period=14,
        atr_multiplier=2.5,   # ATR 止损倍数（替代死板5%）
        ma_exit_period=10,    # 柔性均线离场
        max_hold=20,          # 时间止损天数
        print_log=True,
    )

    def __init__(self):
        # 买点指标
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        
        # 【新增】卖点/风控指标
        self.atr = bt.ind.ATR(period=self.p.atr_period)
        self.ma_exit = bt.ind.SMA(period=self.p.ma_exit_period)

        self.entry_price = None
        self.highest_since_entry = 0.0
        self.bar_count = 0

    def notify_order(self, order):
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price
            self.bar_count = 0

    def next(self):
        price = self.data.close[0]
        if price < self.p.price_min:  # 仅剔仙股
            return

        # ================= 持仓管理（灵活卖点核心） =================
        if self.position:
            self.bar_count += 1
            if price > self.highest_since_entry:
                self.highest_since_entry = price

            profit_pct = (price - self.entry_price) / self.entry_price

            # 1. ATR 波动率硬止损（自适应，防黑天鹅跳空）
            atr_stop_price = self.entry_price - (self.atr[0] * self.p.atr_multiplier)
            if price < atr_stop_price:
                self.close(); print(f'[ATR止损] {self.data.datetime.date(0)} 触发价:{atr_stop_price:.2f}'); return

            # 2. 阶梯动态移动止盈（随盈利增厚调整回撤容忍度）
            if profit_pct > 0.20:
                trail = 0.10
            elif profit_pct > 0.10:
                trail = 0.08
            elif profit_pct > 0.0:
                trail = 0.06
            else:
                trail = 0.0  # 未盈利时靠 ATR 止损，不重复砍

            if trail > 0 and price < self.highest_since_entry * (1.0 - trail):
                self.close(); print(f'[阶梯止盈-{int(trail*100)}%] {self.data.datetime.date(0)}'); return

            # 3. 柔性均线破位（已盈利且跌破 MA10）
            if profit_pct > 0.03 and price < self.ma_exit[0]:
                self.close(); print(f'[MA10破位离场] {self.data.datetime.date(0)}'); return

            # 4. 极端超买（原 S2）
            if self.cci[0] > 120:
                self.close(); print(f'[超买离场] {self.data.datetime.date(0)}'); return

            # 5. 时间止损（20日微利/平本走）
            if self.bar_count >= self.p.max_hold and profit_pct < 0.03:
                self.close(); print(f'[时间止损] {self.data.datetime.date(0)}'); return

        # ================= 空仓买入（沿用 v4） =================
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
                    print(f'[v5买入] {self.data.datetime.date(0)} 价:{price:.2f} 手:{size//100}')

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV5Strategy)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    print('初始资金: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('最终资金: %.2f' % cerebro.broker.getvalue())