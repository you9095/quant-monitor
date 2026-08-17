#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V23 多资产轮动策略（股票/ETF/可转债混合） - 修复版
=====================================================
修复要点：
1. 入场条件从 60日突破+60日动量 放宽为 20日突破+20日动量，提高触发率
2. 调仓频率从每20日改为每日检查，但设置最小持有期5日防止频繁换仓
3. 取消全局冷却期，改为平仓后10天不重新买入同一标的
4. 保留多重止损：硬止损、峰值回撤、ATR止损、CCI衰竭
5. 支持股票/ETF/可转债自动识别每手数量（转债10张，其他100股/份）
6. 所有代码集中在本文件，数据获取使用 akshare（需安装）或本地CSV
=====================================================
"""

import backtrader as bt
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta
import akshare as ak  # 需要 pip install akshare
import warnings
warnings.filterwarnings('ignore')

# ==================== 策略类 ====================
class MultiAssetRotation(bt.Strategy):
    """
    多资产轮动策略（股票/ETF/可转债混合）
    """
    params = dict(
        # 入场条件
        momentum_period=20,      # 动量窗口（原60 → 20）
        break_period=20,         # 突破窗口（原60 → 20）
        # 持仓管理
        top_n=3,                 # 最多持有标的数量
        min_hold_days=5,         # 最小持有交易日（防止频繁换仓）
        # 资金管理
        invest_pct=0.95,         # 总资金用于持仓的比例
        # 止损
        hard_sl=0.15,            # 硬止损：成本价下方15%
        trail_sl=0.20,           # 峰值回撤止损：最高价回撤20%
        atr_period=14,
        atr_multi=3.0,
        cci_peak=100.0,
        cci_fall=80.0,
        # 冷却
        cool_days=10,            # 平仓后冷却天数（原60 → 10）
        # 市场过滤器（默认关闭，避免过度限制）
        use_market_filter=False,
        market_data_name='ETF:510300',
        ma_period=200,
    )

    def __init__(self):
        self.inds = {}
        self.entry_prices = {}
        self.highest = {}
        self.hold_days = {}          # 记录持仓天数
        self.cooldown = {}           # 记录每个标的冷却剩余天数

        # 为每个数据计算指标
        for d in self.datas:
            name = d._name
            self.inds[name] = {
                'roc': bt.ind.ROC(d.close, period=self.p.momentum_period),
                'high_n': bt.ind.Highest(d.high, period=self.p.break_period),
                'atr': bt.ind.ATR(d, period=self.p.atr_period),
                'cci': bt.ind.CCI(d, period=14),
            }
            self.entry_prices[d] = None
            self.highest[d] = 0.0
            self.hold_days[d] = 0
            self.cooldown[d] = 0

        # 市场过滤器（若启用）
        self.market_data = None
        if self.p.use_market_filter:
            for d in self.datas:
                if d._name == self.p.market_data_name:
                    self.market_data = d
                    self.ma_market = bt.ind.SMA(d.close, period=self.p.ma_period)
                    break

    def next(self):
        # 更新冷却计数
        for d in self.datas:
            if self.cooldown[d] > 0:
                self.cooldown[d] -= 1

        # 市场过滤器：若市场低于均线，清仓并禁止开仓
        if self.p.use_market_filter and self.market_data is not None:
            if len(self.market_data) > self.p.ma_period:
                if self.market_data.close[0] < self.ma_market[0]:
                    for d in self.datas:
                        pos = self.getposition(d)
                        if pos.size > 0:
                            self.close(data=d)
                            self._reset_position(d)
                    return

        # 处理已有持仓的止损和退出
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                self.hold_days[d] += 1
                self._check_exit(d)

        # 每日检查轮动（原先每20日检查）
        # 计算所有标的的动量并排序，选择满足条件的标的
        candidates = []
        for d in self.datas:
            name = d._name
            # 跳过冷却中的标的
            if self.cooldown[d] > 0:
                continue
            # 需要足够数据
            if len(d) < self.p.momentum_period + 1:
                continue
            roc_val = self.inds[name]['roc'][0]
            high_n_prev = self.inds[name]['high_n'][-1]
            if math.isnan(roc_val) or math.isnan(high_n_prev):
                continue
            # 入场条件：动量>0 且 收盘价突破20日最高
            if roc_val > 0 and d.close[0] > high_n_prev:
                candidates.append((d, roc_val))

        # 按动量降序排列，取前top_n
        candidates.sort(key=lambda x: x[1], reverse=True)
        target_datas = [d for d, _ in candidates[:self.p.top_n]]

        # 卖出不在目标列表中的持仓（但需满足最小持有期）
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0 and d not in target_datas:
                # 若未达到最小持有期，暂不卖出（除非已触发止损）
                if self.hold_days[d] >= self.p.min_hold_days:
                    self.close(data=d)
                    self._reset_position(d)

        # 为目标持仓分配资金（等权）
        if len(target_datas) > 0:
            # 总目标投入资金 = 总账户价值 * invest_pct
            target_total_value = self.broker.getvalue() * self.p.invest_pct
            per_alloc = target_total_value / len(target_datas)

            for d in target_datas:
                pos = self.getposition(d)
                if pos.size == 0:
                    price = d.close[0]
                    lot_size = self._get_lot_size(d)
                    size = int(per_alloc / (price * lot_size)) * lot_size
                    if size > 0:
                        self.buy(data=d, size=size)
                        self.entry_prices[d] = price
                        self.highest[d] = price
                        self.hold_days[d] = 0

    def _check_exit(self, d):
        """检查持仓的退出条件"""
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
        atr = self.inds[name]['atr'][0]
        cci = self.inds[name]['cci'][0]
        cci_prev5 = self.inds[name]['cci'][-5]

        # 硬止损
        if price < entry * (1.0 - self.p.hard_sl):
            self.close(data=d)
            self._reset_position(d)
            return

        # 峰值回撤止损
        if price < self.highest[d] * (1.0 - self.p.trail_sl):
            self.close(data=d)
            self._reset_position(d)
            return

        # ATR动态止损
        if not math.isnan(atr) and price < self.highest[d] - (atr * self.p.atr_multi):
            self.close(data=d)
            self._reset_position(d)
            return

        # CCI衰竭
        if not math.isnan(cci) and not math.isnan(cci_prev5):
            if cci_prev5 > self.p.cci_peak and cci < self.p.cci_fall:
                self.close(data=d)
                self._reset_position(d)
                return

    def _reset_position(self, d):
        """平仓后重置状态，并设置冷却"""
        self.entry_prices[d] = None
        self.highest[d] = 0.0
        self.hold_days[d] = 0
        self.cooldown[d] = self.p.cool_days

    def _get_lot_size(self, d):
        """根据数据名称判断每手数量"""
        name = d._name
        if name.startswith('CB:'):   # 可转债，每手10张
            return 10
        else:                        # 股票和ETF，每手100股/份
            return 100

    def notify_order(self, order):
        if order.status == order.Completed and order.isbuy():
            d = order.data
            self.entry_prices[d] = order.executed.price
            self.highest[d] = order.executed.price


# ==================== 数据获取函数 ====================
def get_akshare_data(symbol, name_prefix, start_date, end_date):
    """
    从 akshare 获取日线数据，返回 DataFrame
    symbol: 代码（如 '510300' 或 '113050'）
    name_prefix: 'ETF:' 或 'CB:' 或 'STK:'
    """
    try:
        if name_prefix == 'ETF:':
            # 获取ETF日线
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                     start_date=start_date.replace('-', ''),
                                     end_date=end_date.replace('-', ''))
            df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                               '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        elif name_prefix == 'CB:':
            # 获取可转债日线
            df = ak.bond_zh_hs_cov_daily(symbol=symbol)
            df.rename(columns={'date': 'date', 'open': 'open', 'close': 'close',
                               'high': 'high', 'low': 'low', 'volume': 'volume'}, inplace=True)
        else:  # 股票（主板）
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
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


# ==================== 主程序 ====================
def run_backtest():
    # ---------- 配置参数 ----------
    start_date = '2021-08-14'
    end_date = '2026-08-14'
    initial_cash = 50000.0
    commission = 0.0005  # 万5佣金
    slippage = 0.001     # 滑点0.1%

    # 标的池配置
    # ETF池（5只）
    etf_codes = ['510300', '510500', '512880', '512800', '512690']  # 沪深300、中证500、证券、银行、酒
    etf_names = [f'ETF:{code}' for code in etf_codes]

    # 可转债池（50只，价格>100，这里列出常见转债代码，可按需替换）
    cb_codes = [
        '113050', '110079', '113011', '113013', '113016', '113021', '113024', '113025',
        '113027', '113030', '113037', '113043', '113044', '113046', '113047', '113049',
        '113051', '113052', '113053', '113056', '113057', '113058', '113059', '113061',
        '113062', '113063', '113064', '113065', '113066', '113067', '113068', '113069',
        '113070', '113071', '113072', '113073', '113074', '113075', '113076', '113077',
        '113078', '113079', '113081', '113082', '113083', '113084', '113085', '113086',
        '113087', '113088'
    ]
    cb_names = [f'CB:{code}' for code in cb_codes]

    # 可添加股票，例如：
    # stock_codes = ['000001', '600519', '000333']
    # stock_names = [f'STK:{code}' for code in stock_codes]

    # 组合所有标的名称
    all_names = etf_names + cb_names  # + stock_names

    # ---------- 创建 cerebro ----------
    cerebro = bt.Cerebro()

    # 加载数据
    loaded_count = 0
    for full_name in all_names:
        prefix, code = full_name.split(':')
        df = get_akshare_data(code, prefix + ':', start_date, end_date)
        if df is not None and len(df) > 200:  # 过滤数据太短的标的
            data = bt.feeds.PandasData(dataname=df, name=full_name)
            cerebro.adddata(data)
            loaded_count += 1
            print(f"加载成功: {full_name} 数据条数: {len(df)}")
        else:
            print(f"跳过: {full_name}（数据不足或获取失败）")

    print(f"成功加载 {loaded_count} 个标的")

    if loaded_count == 0:
        print("无可用数据，请检查网络或标的代码")
        return

    # 添加策略
    cerebro.addstrategy(
        MultiAssetRotation,
        top_n=3,
        momentum_period=20,
        break_period=20,
        min_hold_days=5,
        hard_sl=0.15,
        trail_sl=0.20,
        use_market_filter=False,   # 默认关闭市场过滤器，避免过度限制
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

    # 最大回撤
    dd = strat.analyzers.DrawDown.get_analysis()
    print(f"最大回撤: {dd.max.drawdown:.2f}%")

    # Sharpe
    try:
        sharpe = strat.analyzers.Sharpe.get_analysis()['sharperatio']
        if sharpe is not None:
            print(f"Sharpe比率: {sharpe:.4f}")
    except:
        print("Sharpe比率: N/A")

    # 交易统计
    ta = strat.analyzers.TradeAnalyzer.get_analysis()
    total_trades = ta.total.closed if 'total' in ta and 'closed' in ta.total else 0
    print(f"总交易笔数（平仓）: {total_trades}")

    # 打印每笔交易细节（可选）
    # for trade in strat.trades:
    #     print(f"标的: {trade.data._name}, 方向: {'多' if trade.islong else '空'}, "
    #           f"开仓价: {trade.price:.2f}, 平仓价: {trade.price:.2f}, 盈亏: {trade.pnlcomm:.2f}")

    # 绘制图表（可选，需安装 matplotlib）
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    run_backtest()