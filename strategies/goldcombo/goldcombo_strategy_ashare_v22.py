import backtrader as bt
import math
from collections import defaultdict

class MultiAssetRotation(bt.Strategy):
    """
    多资产轮动策略（股票/ETF/可转债混合）
    ============================================================
    - 核心：60日动量排序 + 60日高点突破确认
    - 调仓：每 rebalance_days 个交易日检查一次
    - 持有 top_n 只最强标的（默认3）
    - 资金：总资金 * invest_pct 用于持仓，等权分配
    - 风控：硬止损、峰值回撤、ATR止损、CCI衰竭
    - 市场过滤：可选，若启用且市场指数低于MA200则空仓
    ============================================================
    """
    params = dict(
        momentum_period=60,      # 动量计算窗口
        break_period=60,         # 突破窗口
        top_n=3,                 # 持有标的数量
        rebalance_days=20,       # 调仓频率（交易日）
        invest_pct=0.90,         # 总资金用于持仓的比例
        hard_sl=0.15,            # 硬止损（成本价下方）
        trail_sl=0.20,           # 峰值回撤止损
        atr_period=14,
        atr_multi=3.0,
        cci_peak=100.0,
        cci_fall=80.0,
        cool_days=60,            # 平仓后冷却天数
        use_market_filter=False, # 是否启用市场过滤器
        market_data_name='ETF:510300',  # 市场指数数据名称
        ma_period=200,           # 市场过滤器均线
    )

    def __init__(self):
        # 为每个数据计算指标
        self.inds = {}
        self.entry_prices = {}    # data -> entry price
        self.highest = {}         # data -> highest since entry
        self.cooldown = defaultdict(int)  # data -> remaining cooldown days

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

        # 市场过滤器（若启用）
        self.market_data = None
        if self.p.use_market_filter:
            for d in self.datas:
                if d._name == self.p.market_data_name:
                    self.market_data = d
                    self.ma_market = bt.ind.SMA(d.close, period=self.p.ma_period)
                    break
            if self.market_data is None:
                print(f"警告: 未找到市场过滤器数据 {self.p.market_data_name}，已禁用过滤器")
                self.p.use_market_filter = False

        self.day_count = 0

    def next(self):
        self.day_count += 1

        # 更新冷却计数
        for d in self.datas:
            if self.cooldown[d] > 0:
                self.cooldown[d] -= 1

        # 市场过滤器：若市场低于均线，清仓并禁止开仓
        if self.p.use_market_filter and self.market_data is not None:
            if len(self.market_data) > self.p.ma_period:
                if self.market_data.close[0] < self.ma_market[0]:
                    # 清仓所有
                    for d in self.datas:
                        pos = self.getposition(d)
                        if pos.size > 0:
                            self.close(d)
                            self._reset_position(d)
                    return  # 当日不再开仓

        # 处理已有持仓的止损和退出
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                self._check_exit(d)

        # 调仓日检查轮动
        if self.day_count % self.p.rebalance_days != 0:
            return

        # 市场过滤器再次确认
        if self.p.use_market_filter and self.market_data is not None:
            if len(self.market_data) > self.p.ma_period:
                if self.market_data.close[0] < self.ma_market[0]:
                    return  # 禁止开仓

        # 计算所有标的的动量并排序
        candidates = []
        for d in self.datas:
            name = d._name
            # 跳过冷却中的标的
            if self.cooldown[d] > 0:
                continue
            # 需要足够数据
            if len(d) < self.p.momentum_period + 1:
                continue
            # 检查指标是否有效
            roc_val = self.inds[name]['roc'][0]
            high_n_prev = self.inds[name]['high_n'][-1]
            if math.isnan(roc_val) or math.isnan(high_n_prev):
                continue
            # 必须动量>0且价格突破60日高点
            if roc_val > 0 and d.close[0] > high_n_prev:
                candidates.append((d, roc_val))

        # 按动量降序排列，取前top_n
        candidates.sort(key=lambda x: x[1], reverse=True)
        target_datas = [d for d, _ in candidates[:self.p.top_n]]

        # 卖出不在目标列表中的持仓
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0 and d not in target_datas:
                self.close(d)
                self._reset_position(d)

        # 为目标持仓分配资金
        if len(target_datas) > 0:
            # 总可用资金（现金）
            total_cash = self.broker.getcash()
            # 目标总投入资金 = 总账户价值 * invest_pct
            target_total_value = self.broker.getvalue() * self.p.invest_pct
            # 每只标的分配资金 = 目标总价值 / 目标数量
            per_alloc = target_total_value / len(target_datas)

            for d in target_datas:
                pos = self.getposition(d)
                if pos.size == 0:
                    price = d.close[0]
                    # 根据数据类型确定每手数量
                    lot_size = self._get_lot_size(d)
                    # 可买数量（向下取整到整手）
                    size = int(per_alloc / (price * lot_size)) * lot_size
                    if size > 0:
                        self.buy(data=d, size=size)
                        self.entry_prices[d] = price
                        self.highest[d] = price

    def _check_exit(self, d):
        """检查持仓的退出条件"""
        price = d.close[0]
        entry = self.entry_prices.get(d)
        if entry is None:
            # 如果缺少入场价，用当前价近似（安全处理）
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

        # 峰值回撤
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
        """平仓后重置该标的的状态，并设置冷却"""
        self.entry_prices[d] = None
        self.highest[d] = 0.0
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
            # 记录实际成交价作为入场价（更准确）
            d = order.data
            self.entry_prices[d] = order.executed.price
            self.highest[d] = order.executed.price