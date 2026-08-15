#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[2026-08-15 v8 · 黄金组合 EatTheBody 防暴跌50%严控版]
====================================================================
本文件 = 用户手动上传的 v8 严控回撤策略,经 subagent 解 RTF 后落地到项目位置。

来源 (source of truth):
    ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化V8.PY
来源 sha256:
    3a6d34879c8ab59cc3e927aacf261fe4992b9a3e69b02417c78bb1f2c1aeb75b
来源文件类型:
    Rich Text Format (RTF), 5585 bytes
解码方式:
    textutil -convert txt -inputencoding UTF-8 -encoding UTF-8
解码时间:
    2026-08-15 19:38 (Asia/Shanghai)
解码产物 (RTF-cleaned Python) 已存档:
    ~/goldcombo_real_backtest/v8/T1_extract/goldcombo_strategy_v8_clean.txt (3834 bytes)

类名: GoldComboV8_EatTheBody (bt.Strategy)

用户原话 (2026-08-15): "这是更新后的黄金组合策略,替换掉原先的 V6 版本,针对的还是沪深股市。
现在跑一次最近 5 年的回测,并把结果发给我。"

v6 → v8 关键差异 (用户手动优化, subagent 未改任何阈值):
| 维度              | v6 (严控回撤去错杀)        | v8 (EatTheBody 防暴跌50%)     |
|-------------------|----------------------------|-------------------------------|
| 硬止损            | 5%                         | 10% (放宽, 给反弹单空间)      |
| 保本移动止损      | breakeven_pct=0.05/be_stop | 删除 (v6 独有)                |
| 移动止盈          | 无                         | trail_sl=0.15 (15% 回撤锁利)  |
| MACD 高位死叉离场 | 有                         | 删除 (v6 独有)                |
| CCI>120 离场      | 保留                       | 保留                          |
| 离场机制数        | 4 个                       | 3 个 (精简)                   |
| 入场核心 (C3+投票)| 与 v6 一致                 | 与 v6 一致                    |
| C7/C8/price_min/  | 与 v6 一致                 | 与 v6 一致                    |
| cash_pct/滑点     |                            |                               |

v8 核心思路 (用户原话"优化"):
- 防"暴跌50%行情被5%硬止损震出" — v6 5% 硬止损在暴跌行情里可能在大底前止损, 错过反弹
- v8 给单笔交易足够空间 (10% 硬止损), 同时 15% 移动止盈锁利润
- 离场机制精简到 3 个 (从 v6 的 4 个减 1 个): 硬止损 / 移动止盈 / CCI

版本备份链 (沿用 v1→v2→v3→v4→v6 规矩):
- v1 备份: ~/goldcombo_real_backtest/v1_backup/                (git da10a57)
- v2 备份: ~/goldcombo_real_backtest/v2_backup/                (git 57267e1)
- v3 备份: ~/goldcombo_real_backtest/v3_backup/
- v4 备份: ~/goldcombo_real_backtest/v4_backup/
- v6 备份: ~/goldcombo_real_backtest/v8/v6_integration_backup/ (本次新建,6 文件 + sha256)
- v6 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v6.py (未删, 仅 alias 切到 v8)
- v8 新文件: strategies/goldcombo/goldcombo_strategy_ashare_v8.py (本文件)
- alias 文件: strategies/goldcombo/goldcombo_strategy_ashare.py (已改 import 指向 v8)

本任务无额外 price 过滤层要求 (v4 任务特有), 直接用 v8 策略类 price_min=3.0 自身过滤。
====================================================================
"""
import backtrader as bt

class GoldComboV8_EatTheBody(bt.Strategy):
    """
    黄金组合 - v8 左侧吃鱼身版 (落实用户诊断)
    买点：完全沿用 v6 (C3 + 投票 + 价>3, CCI<-70)
    卖点：【删除MACD死叉】 + CCI>120 极端超买离场 + 硬止损10% + 最高点回撤15%锁利
    """
    params = dict(
        # 买点（冻结 v6）
        cci_thresh=-70,
        di_neg_thresh=20,
        di_pos_thresh=15,
        vote_min=2,
        price_min=3.0,
        cash_pct=0.95,
        # 卖点（用户改良：去 MACD，控 15% 回撤）
        hard_sl=0.10,        # 成本下 10% 必砍（防黑天鹅，比 15% 更紧一点）
        trail_sl=0.15,       # 从持仓最高价回撤 15% 离场（吃主升浪）
        print_log=True,
    )

    def __init__(self):
        # 买点指标
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
        if price < self.p.price_min:
            return

        # ================= 持仓管理（v8 去 MACD 卖点） =================
        if self.position:
            if price > self.highest_since_entry:
                self.highest_since_entry = price

            # 1. 铁律硬止损（成本下 10%，防退市断层）
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close(); print(f'[硬止损-10%] {self.data.datetime.date(0)}'); return

            # 2. 最高点回撤 15% 移动止盈（核心：让利润奔跑，不早下车）
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close(); print(f'[回撤15%离场] {self.data.datetime.date(0)}'); return

            # 3. 极端超买离场（原 S2，唯一保留的技術离场，吃尽泡沫）
            if self.cci[0] > 120:
                self.close(); print(f'[超买离场] {self.data.datetime.date(0)}'); return

            # 【注意：原 MACD 高位死叉离场已彻底删除，不再截断主升浪】

        # ================= 空仓买入（v6 买点） =================
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
                    print(f'[v8买入] {self.data.datetime.date(0)} 价:{price:.2f} 手:{size//100}')
