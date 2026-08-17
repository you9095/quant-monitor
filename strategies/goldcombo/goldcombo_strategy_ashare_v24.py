#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMA 金叉死叉策略（多品种版）
================================
- 核心：DMA 上穿 AMA 买入，下穿 AMA 卖出
- 过滤：成交量放大 + RSI 合理区间（可选）
- 风控：硬止损、移动止盈、市场过滤器
- 支持股票、ETF、可转债（自动识别每手数量）
- 数据源：akshare（需安装），或替换为本地 CSV
"""

import backtrader as bt
import pandas as pd
import numpy as np
import math
from datetime import datetime
import akshare as ak
import warnings
warnings.filterwarnings('ignore')


# ==================== 策略类 ====================
class DMAStrategy(bt.Strategy):
    params = dict(
        # DMA 参数
        dma_short=10,           # 短期均线
        dma_long=50,            # 长期均线
        dma_signal=10,          # AMA 周期

        # 过滤条件
        use_volume_filter=True, # 是否启用成交量过滤
        vol_period=20,          # 成交量均线周期
        vol_mult=1.5,           # 买入时成交量需大于均量*倍数
        use_rsi_filter=True,    # 是否启用 RSI 过滤
        rsi_period=14,
        rsi_low=30,             # RSI 下限
        rsi_high=70,            # RSI 上限

        # 风控
        hard_sl=0.10,           # 硬止损比例
        trail_sl=0.15,          # 移动止盈回撤比例
        max_positions=5,        # 最大同时持仓数
        per_pos_pct=0.20,       # 单标的资金比例（总资金）

        # 市场过滤器
        use_market_filter=True, # 是否启用市场过滤
        market_data_name='ETF:510300',  # 市场指数数据名称
        market_ma_period=200,

        # 交易限制
        cool_days=10,           # 平仓后冷却天数
    )

    def __init__(self):
        self.inds = {}
        self.entry_prices = {}
        self.highest = {}
        self.cooldown = {}
        self.order = None

        # 为每个数据计算指标
        for d in self.datas:
            name = d._name
            # DMA 指标
            dma = bt.ind.SMA(d.close, period=self.p.dma_short) - bt.ind.SMA(d.close, period=self.p.dma_long)
            ama = bt.ind.SMA(dma, period=self.p.dma_signal)
            # 交叉信号
            cross_up = bt.ind.CrossUp(dma, ama)
            cross_down = bt.ind.CrossDown(dma, ama)

            # 成交量均线
            vol_ma = bt.ind.SMA(d.volume, period=self.p.vol_period)

            # RSI
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

    def next(self):
        # 更新冷却
        for d in self.datas:
            if self.cooldown[d] > 0:
                self.cooldown[d] -= 1

        # 市场过滤器：若市场低于均线，清仓所有
        if self.p.use_market_filter and self.market_data is not None and self.ma_market is not None:
            if len(self.market_data) > self.p.market_ma_period:
                if self.market_data.close[0] < self.ma_market[0]:
                    for d in self.datas:
                        if self.getposition(d).size > 0:
                            self.close(data=d)
                            self._reset_position(d)
                    return  # 当日不再开仓

        # 检查持仓的止损/止盈
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                self._check_exit(d)

        # 处理买入信号
        for d in self.datas:
            name = d._name
            # 跳过冷却
            if self.cooldown[d] > 0:
                continue
            # 已经有持仓则跳过
            if self.getposition(d).size > 0:
                continue
            # 检查最大持仓数
            if self._count_positions() >= self.p.max_positions:
                break

            # 买入信号：金叉 + 过滤条件
            if self.inds[name]['cross_up'][0]:
                # 过滤条件检查
                if self.p.use_volume_filter:
                    if d.volume[0] < self.inds[name]['vol_ma'][0] * self.p.vol_mult:
                        continue
                if self.p.use_rsi_filter:
                    rsi_val = self.inds[name]['rsi'][0]
                    if math.isnan(rsi_val) or rsi_val < self.p.rsi_low or rsi_val > self.p.rsi_high:
                        continue

                # 执行买入
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
        # 计算可买数量
        price = d.close[0]
        cash_to_use = self.broker.getcash() * self.p.per_pos_pct
        lot_size = self._get_lot_size(d)
        size = int(cash_to_use / (price * lot_size)) * lot_size
        if size > 0:
            self.buy(data=d, size=size)
            self.entry_prices[d] = price
            self.highest[d] = price

    def _reset_position(self, d):
        """重置状态并设置冷却"""
        self.entry_prices[d] = None
        self.highest[d] = 0.0
        self.cooldown[d] = self.p.cool_days

    def _count_positions(self):
        """当前持仓数量"""
        count = 0
        for d in self.datas:
            if self.getposition(d).size > 0:
                count += 1
        return count

    def _get_lot_size(self, d):
        """根据名称前缀判断每手数量"""
        name = d._name
        if name.startswith('CB:'):
            return 10       # 可转债一手10张
        else:
            return 100      # 股票和ETF一手100股/份

    def notify_order(self, order):
        if order.status == order.Completed and order.isbuy():
            d = order.data
            self.entry_prices[d] = order.executed.price
            self.highest[d] = order.executed.price


# ==================== 数据获取 ====================
def get_akshare_data(symbol, name_prefix, start_date, end_date):
    """
    从 akshare 获取日线数据
    symbol: 代码（如 '510300'）
    name_prefix: 'ETF:' 或 'STK:' 或 'CB:'
    """
    try:
        if name_prefix == 'ETF:':
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                     start_date=start_date.replace('-', ''),
                                     end_date=end_date.replace('-', ''))
            df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                               '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        elif name_prefix == 'STK:':
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                    start_date=start_date.replace('-', ''),
                                    end_date=end_date.replace('-', ''))
            df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                               '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        elif name_prefix == 'CB:':
            df = ak.bond_zh_hs_cov_daily(symbol=symbol)
            df.rename(columns={'date': 'date', 'open': 'open', 'close': 'close',
                               'high': 'high', 'low': 'low', 'volume': 'volume'}, inplace=True)
        else:
            return None

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
    initial_cash = 50000.0
    commission = 0.0005      # 万5佣金
    slippage = 0.001         # 滑点0.1%

    # 标的池（示例：5只ETF + 3只主板股票 + 5只可转债，可按需修改）
    symbols = [
        # ETF
        ('510300', 'ETF:'),
        ('510500', 'ETF:'),
        ('512880', 'ETF:'),
        ('512690', 'ETF:'),
        ('512480', 'ETF:'),
        # 主板股票
        ('000001', 'STK:'),  # 平安银行
        ('600519', 'STK:'),  # 贵州茅台
        ('000333', 'STK:'),  # 美的集团
        # 可转债（示例代码）
        ('113050', 'CB:'),
        ('110079', 'CB:'),
        ('113011', 'CB:'),
        ('113013', 'CB:'),
        ('113016', 'CB:'),
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
        dma_short=10,
        dma_long=50,
        dma_signal=10,
        use_volume_filter=True,
        vol_period=20,
        vol_mult=1.5,
        use_rsi_filter=True,
        rsi_low=30,
        rsi_high=70,
        hard_sl=0.10,
        trail_sl=0.15,
        max_positions=5,
        per_pos_pct=0.20,
        use_market_filter=True,
        market_data_name='ETF:510300',  # 确保池中包含该标的
        market_ma_period=200,
        cool_days=10,
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