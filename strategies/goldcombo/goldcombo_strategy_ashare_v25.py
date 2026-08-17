#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V25 DMA 金叉死叉策略 - 高波动行业 ETF 轮动版
=====================================================
- 标的池：6 只高波动行业 ETF（半导体、军工、5G、光伏、券商、酒）
- 核心：DMA(5,20,5) 金叉买入，死叉卖出
- 过滤：已取消成交量过滤和 RSI 过滤（避免信号过少）
- 风控：硬止损 10%、移动止盈 15%、市场过滤器（只禁开仓不清仓）
- 仓位：最多持有 3 只，单标的最高使用总资金 30%
- 数据源：akshare（需安装）
=====================================================
"""

import backtrader as bt
import pandas as pd
import numpy as np
import math
import akshare as ak
import warnings
warnings.filterwarnings('ignore')


class DMAStrategy(bt.Strategy):
    params = dict(
        # DMA 参数（已放宽）
        dma_short=5,            # 短期均线
        dma_long=20,            # 长期均线
        dma_signal=5,           # AMA 周期

        # 过滤条件（取消）
        use_volume_filter=False,  # 关闭成交量过滤
        vol_period=20,            # 保留但无效
        vol_mult=1.5,             # 保留但无效
        use_rsi_filter=False,     # 关闭 RSI 过滤
        rsi_period=14,            # 保留但无效
        rsi_low=30,               # 保留但无效
        rsi_high=70,              # 保留但无效

        # 风控
        hard_sl=0.10,           # 硬止损：成本价下方 10%
        trail_sl=0.15,          # 移动止盈：最高价回撤 15%
        max_positions=3,        # 最大同时持仓数
        per_pos_pct=0.30,       # 单标的资金比例（总资金）

        # 市场过滤器（保留，但只禁止开仓不清仓）
        use_market_filter=True,
        market_data_name='ETF:510300',  # 使用沪深300ETF作为市场指数
        market_ma_period=200,

        # 交易限制
        cool_days=3,            # 平仓后冷却天数（缩短）
    )

    def __init__(self):
        self.inds = {}
        self.entry_prices = {}
        self.highest = {}
        self.cooldown = {}

        # 为每个数据计算指标
        for d in self.datas:
            name = d._name
            # DMA 指标
            dma = bt.ind.SMA(d.close, period=self.p.dma_short) - bt.ind.SMA(d.close, period=self.p.dma_long)
            ama = bt.ind.SMA(dma, period=self.p.dma_signal)
            cross_up = bt.ind.CrossUp(dma, ama)
            cross_down = bt.ind.CrossDown(dma, ama)

            # 备用指标（即使不用也保留）
            vol_ma = bt.ind.SMA(d.volume, period=self.p.vol_period)
            rsi = bt.ind.RSI(d.close, period=self.p.rsi_period)

            self.inds[name] = {
                'dma': dma,
                'ama': ama,
                'cross_up': cross_up,
                'cross_down': cross_down,
                'vol_ma': vol_ma,
                'rsi': rsi,
            }

            self.entry_prices[d] = None
            self.highest[d] = 0.0
            self.cooldown[d] = 0

        # 市场过滤器数据
        self.market_data = None
        self.ma_market = None
        if self.p.use_market_filter:
            for d in self.datas:
                if d._name == self.p.market_data_name:
                    self.market_data = d
                    self.ma_market = bt.ind.SMA(d.close, period=self.p.market_ma_period)
                    break
            if self.market_data is None:
                print(f"警告：未找到市场过滤器数据 {self.p.market_data_name}，已禁用过滤器")
                self.p.use_market_filter = False

    def next(self):
        # 更新冷却
        for d in self.datas:
            if self.cooldown[d] > 0:
                self.cooldown[d] -= 1

        # 市场过滤器：若市场低于均线，禁止开仓（但不清仓）
        market_bear = False
        if self.p.use_market_filter and self.market_data is not None and self.ma_market is not None:
            if len(self.market_data) > self.p.market_ma_period:
                if self.market_data.close[0] < self.ma_market[0]:
                    market_bear = True

        # 检查持仓的止损/止盈
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                self._check_exit(d)

        # 处理买入信号（仅在市场非空头时开新仓）
        if market_bear:
            return

        for d in self.datas:
            name = d._name
            # 跳过冷却
            if self.cooldown[d] > 0:
                continue
            # 已有持仓则跳过
            if self.getposition(d).size > 0:
                continue
            # 检查最大持仓数
            if self._count_positions() >= self.p.max_positions:
                break

            # 买入信号：金叉
            if self.inds[name]['cross_up'][0]:
                # 过滤条件已关闭，直接买入
                self._buy(d)

    def _check_exit(self, d):
        """检查持仓退出条件"""
        price = d.close[0]
        entry = self.entry_prices.get(d)
        if entry is None:
            self.entry_prices[d] = price
            self.highest[d] = price
            entry = price

        # 更新最高价
        if price > self.highest[d]:
            self.highest[d] = price

        name = d._name
        # 死叉卖出
        if self.inds[name]['cross_down'][0]:
            self.close(data=d)
            self._reset_position(d)
            return

        # 硬止损
        if price < entry * (1.0 - self.p.hard_sl):
            self.close(data=d)
            self._reset_position(d)
            return

        # 移动止盈
        if price < self.highest[d] * (1.0 - self.p.trail_sl):
            self.close(data=d)
            self._reset_position(d)
            return

    def _buy(self, d):
        """执行买入"""
        price = d.close[0]
        cash_to_use = self.broker.getcash() * self.p.per_pos_pct
        lot_size = self._get_lot_size(d)
        size = int(cash_to_use / (price * lot_size)) * lot_size
        if size > 0:
            self.buy(data=d, size=size)
            self.entry_prices[d] = price
            self.highest[d] = price

    def _reset_position(self, d):
        self.entry_prices[d] = None
        self.highest[d] = 0.0
        self.cooldown[d] = self.p.cool_days

    def _count_positions(self):
        count = 0
        for d in self.datas:
            if self.getposition(d).size > 0:
                count += 1
        return count

    def _get_lot_size(self, d):
        # ETF 均为100份一手
        return 100

    def notify_order(self, order):
        if order.status == order.Completed and order.isbuy():
            d = order.data
            self.entry_prices[d] = order.executed.price
            self.highest[d] = order.executed.price


# ==================== 数据获取 ====================
def get_akshare_data(symbol, name_prefix, start_date, end_date):
    """从 akshare 获取 ETF 日线数据"""
    try:
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                 start_date=start_date.replace('-', ''),
                                 end_date=end_date.replace('-', ''))
        df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                           '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except Exception as e:
        print(f"获取 {name_prefix}{symbol} 失败: {e}")
        return None


# ==================== 回测主函数 ====================
def run_backtest():
    # ---------- 配置参数 ----------
    start_date = '2021-08-14'
    end_date = '2026-08-14'
    initial_cash = 80000.0      # 你的实际资金
    commission = 0.0005         # 万5佣金
    slippage = 0.001            # 滑点0.1%

    # 标的池：6只高波动行业ETF + 1只市场指数ETF（用于过滤器）
    symbols = [
        # 高波动行业ETF（交易标的）
        ('512480', 'ETF:'),  # 半导体 ETF
        ('512660', 'ETF:'),  # 军工 ETF
        ('515050', 'ETF:'),  # 5G ETF
        ('515790', 'ETF:'),  # 光伏 ETF
        ('512880', 'ETF:'),  # 证券 ETF
        ('512690', 'ETF:'),  # 酒 ETF
        # 市场指数ETF（仅用于市场过滤器，不参与交易）
        ('510300', 'ETF:'),  # 沪深300ETF
    ]

    # ---------- 创建 cerebro ----------
    cerebro = bt.Cerebro()

    # 加载数据
    loaded_count = 0
    for code, prefix in symbols:
        df = get_akshare_data(code, prefix, start_date, end_date)
        if df is not None and len(df) > 200:
            data = bt.feeds.PandasData(dataname=df, name=f'{prefix}{code}')
            cerebro.adddata(data)
            loaded_count += 1
            print(f"加载成功: {prefix}{code}  数据条数: {len(df)}")
        else:
            print(f"跳过: {prefix}{code}（数据不足或获取失败）")

    if loaded_count == 0:
        print("无可用数据，请检查网络或标的代码")
        return

    print(f"\n成功加载 {loaded_count} 个标的")

    # 添加策略
    cerebro.addstrategy(
        DMAStrategy,
        # DMA 参数
        dma_short=5,
        dma_long=20,
        dma_signal=5,
        # 过滤条件（已关闭）
        use_volume_filter=False,
        use_rsi_filter=False,
        # 风控
        hard_sl=0.10,
        trail_sl=0.15,
        max_positions=3,
        per_pos_pct=0.30,
        # 市场过滤器
        use_market_filter=True,
        market_data_name='ETF:510300',
        market_ma_period=200,
        # 冷却
        cool_days=3,
    )

    # 设置资金和费用
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(perc=slippage)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.TotalValue, _name='TotalValue')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='DrawDown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='Sharpe', timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='TradeAnalyzer')

    # 运行回测
    print("\n开始回测...")
    results = cerebro.run()
    strat = results[0]

    # ---------- 输出结果 ----------
    print("\n================ 回测结果 ================")
    print(f"初始资金: {initial_cash:.2f}")
    print(f"最终资金: {cerebro.broker.getvalue():.2f}")
    print(f"总收益: {(cerebro.broker.getvalue()/initial_cash - 1)*100:.2f}%")

    dd = strat.analyzers.DrawDown.get_analysis()
    print(f"最大回撤: {dd.max.drawdown:.2f}%")

    try:
        sharpe = strat.analyzers.Sharpe.get_analysis()['sharperatio']
        if sharpe is not None:
            print(f"Sharpe比率: {sharpe:.4f}")
    except:
        print("Sharpe比率: N/A")

    ta = strat.analyzers.TradeAnalyzer.get_analysis()
    total_trades = ta.total.closed if 'total' in ta and 'closed' in ta.total else 0
    print(f"总交易笔数（平仓）: {total_trades}")

    # 可选绘制图表（需安装 matplotlib）
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    run_backtest()