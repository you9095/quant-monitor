# -*- coding: utf-8 -*-
"""
=============================================================================
黄金组合 V8 终版策略 (GoldComboV8_Final) - 沪深 A 股版本
=============================================================================
来源: 用户上传 (RTF 包裹), 解 RTF 后真 Python
原文件: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化V8final.py
原文件 sha256: 8d66c5841183bcd54861767490c1c7be42933c80663301a5a8eb0bfc92cda8c4
原文件大小: 8918B (122 行, RTF 包裹)
解 RTF 方法: textutil -convert txt -inputencoding UTF-8 -encoding UTF-8
解 RTF 时间: 2026-08-15
解出 Python: 115 行 (5530B)

与之前 v8 EatTheBody 逻辑完全相同:
- 入场: C3 (MACD 零轴下金叉) 必选 + [C4/C7/C8] ≥ 2 投票
- 离场 3 机制: 硬止损 10% (hard_sl) + 移动止盈 15% (trail_sl) + CCI>120 (cci_exit)
- 价格过滤: price_min=3.0
- 仓位: cash_pct=0.95, 按 100 股手数
- 硬性规则 7: MACD 死叉卖点彻底禁用

唯一区别:
- 类名: GoldComboV8_EatTheBody → GoldComboV8_Final
- 注释更详细
- 独立 cci_exit 参数 (v8 中 CCI 阈值固定 120, V8final 通过 params 可调)

参数 (硬性规则, 不可随意改动):
- cci_thresh = -70.0   (CCI 超卖)
- di_neg_thresh = 20.0 (-DI 空方)
- di_pos_thresh = 15.0 (+DI 多方)
- vote_min = 2         (辅助条件至少满足个数)
- price_min = 3.0      (最低股价过滤)
- hard_sl = 0.10       (未盈利硬止损 10%)
- trail_sl = 0.15      (盈利后峰值回撤 15% 离场)
- cci_exit = 120.0     (CCI 极端超买离场)
- cash_pct = 0.95      (单笔仓位 95%)

commit SHA (待 T2 写入): 见 ~/goldcombo_real_backtest/v8final/T2_commit/conclusion.md
=============================================================================
"""

import backtrader as bt

class GoldComboV8_Final(bt.Strategy):
    """
    =========================================================================
    黄金组合 V8 终版策略 (完全自包含 / 硬性规则内嵌)
    -------------------------------------------------------------------------
    【硬性规则清单 - 全部在下方代码中强制生效】
    1. 价格过滤: 仅交易收盘价 > 3.0 元的股票 (剔除仙股/退市风险)
    2. 仓位管理: 单笔使用 95% 可用现金, 按 100 股整数倍买入
    3. 买入触发: C3(MACD零轴下金叉) 必选 + [C4(BOLL开口), C7(CCI<-70), C8(DMI空方)] 至少满足 2 个
    4. 卖出规则 A (硬止损): 成本价下方 10% 必须平仓 (防黑天鹅)
    5. 卖出规则 B (移动止盈): 持仓期间最高价回撤 15% 必须平仓 (吃主升浪, 控回撤)
    6. 卖出规则 C (极端超买): CCI > 120 必须平仓 (情绪顶部)
    7. 卖出规则 D (MACD禁售): 彻底删除 MACD 死叉卖点, 不允许以此信号下车
    =========================================================================
    """
    # 所有阈值参数集中声明，回测时不可随意改动
    params = dict(
        # --- 买点参数 ---
        cci_thresh=-70.0,     # 硬性规则: CCI 超卖阈值
        di_neg_thresh=20.0,   # 硬性规则: -DI 空方阈值
        di_pos_thresh=15.0,   # 硬性规则: +DI 多方阈值
        vote_min=2,           # 硬性规则: 辅助条件至少满足个数
        price_min=3.0,        # 硬性规则: 最低股价过滤
        # --- 卖点参数 ---
        hard_sl=0.10,         # 硬性规则: 未盈利硬止损 10%
        trail_sl=0.15,        # 硬性规则: 盈利后峰值回撤 15% 离场
        cci_exit=120.0,       # 硬性规则: CCI 极端超买离场线
        # --- 仓位参数 ---
        cash_pct=0.95,        # 硬性规则: 单笔仓位 95%
    )

    def __init__(self):
        # ========== 指标计算 (仅用于信号, 不含任何隐藏逻辑) ==========
        self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(period=14)
        self.plus_di = bt.ind.PlusDI(period=14)
        self.minus_di = bt.ind.MinusDI(period=14)
        self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
        
        # 持仓状态跟踪变量
        self.entry_price = None
        self.highest_since_entry = 0.0

    def notify_order(self, order):
        """订单成交后记录真实成本价与最高价"""
        if order.status in [order.Completed] and order.isbuy():
            self.entry_price = order.executed.price
            self.highest_since_entry = order.executed.price

    def next(self):
        # ========== 硬性规则 1: 价格过滤器 ==========
        price = self.data.close[0]
        if price < self.p.price_min:
            return  # 低于 3 元直接跳过, 不交易

        # ========== 持仓状态: 检查卖出 ==========
        if self.position:
            # 更新持仓期间最高价 (用于移动止盈计算)
            if price > self.highest_since_entry:
                self.highest_since_entry = price

            # ========== 硬性规则 4: 10% 硬止损 ==========
            if price < self.entry_price * (1.0 - self.p.hard_sl):
                self.close()
                return

            # ========== 硬性规则 5: 15% 峰值回撤止盈 ==========
            if price < self.highest_since_entry * (1.0 - self.p.trail_sl):
                self.close()
                return

            # ========== 硬性规则 6: CCI>120 极端超买离场 ==========
            if self.cci[0] > self.p.cci_exit:
                self.close()
                return

            # ========== 硬性规则 7: MACD 卖点已彻底禁用, 此处无任何 MACD 平仓代码 ==========

        # ========== 空仓状态: 检查买入 ==========
        if not self.position:
            # BOLL 带宽计算
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]

            # --- 硬性规则 3 分解: C3 必选条件 --
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and \
                 (self.macd.macd[0] < 0)

            # --- 硬性规则 3 分解: 辅助投票条件 ---
            c4 = bw > bw_prev  # BOLL 开口放大
            c7 = self.cci[0] < self.p.cci_thresh  # CCI 极端超卖
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and \
                 (self.minus_di[0] > self.p.di_neg_thresh)  # DMI 空方极致

            # --- 硬性规则 3 执行: C3 且 辅助>=2 ---
            if c3 and (sum([c4, c7, c8]) >= self.p.vote_min):
                # ========== 硬性规则 2: 仓位管理 ==========
                cash_to_use = self.broker.getcash() * self.p.cash_pct
                size = int(cash_to_use / (price * 100)) * 100
                if size > 0:
                    self.buy(size=size)

# ========== 回测引擎独立启动入口 (可直接 python 运行) ==========
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV8_Final)
    # 硬性规则: 统一 1 万本金测试基准
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    print('V8 初始资金: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('V8 最终资金: %.2f' % cerebro.broker.getvalue())