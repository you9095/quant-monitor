#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金组合 A —— 跨资产风险调整动量配置（生产版 v1）
=====================================================
本模块是“黄金组合”的正式生产策略，替代此前只做黄金单标的的简单动量版。

核心设计（已通过诚实回测：样本内/样本外切分、参数敏感性、统一1万本金、
生产口径费用滑点；区间 2022-04 ~ 2026-08）：
  1. 长期趋势过滤：仅当收盘价 > 200 日均线（约 10 个月）才允许买入，
     用以过滤 2022 年“慢熊 + 反弹”中 60/120 日均线被反复假突破的问题。
  2. 风险调整动量打分：120 日动量 / 120 日年化波动率，而非只看涨幅，
     避免在高波动品种（如 2025Q4 白银）追高。
  3. 选取得分最高的前 5 个标的（必须趋势向上）。
  4. 逆波动率定权重（1/波动率归一），单只标的上限 40%；
     权重封顶后不重新归一，剩余资金留现金。
  5. 个股止损：从买入后最高收盘回撤 8% 即标记，次日收盘卖出
     （T+1，诚实执行口径，杜绝当日“收盘才知道却按收盘价成交”的偏差）。
  6. 月度调仓：每月最后一个交易日才重新评估；非调仓日维持现有持仓，
     仅执行止损，不做日内再平衡。
  7. 资产缺位（趋势向上的标的不足 5 只）时，本应配置国债/货币；
     但 1 万元本金下国债/货币 1 手即 1 万+ 元，无法作 20% 小仓，
     故缺位资金诚实留为现金（0 收益，避险有效）。

资产池为真正的多资产：A股宽基/行业、海外权益、贵金属商品、利率防御。
全程为模拟盘 / 本机真实撮合，绝不连接任何券商真实账号或资金账号。
"""
from __future__ import annotations

import datetime as _dt
from typing import Callable, Dict, List, Optional

# ---------------- 资产池与类别 ----------------
# 风险资产（参与动量排序）
RISK_POOL = [
    "510300", "510500", "159915", "512880",          # A股：沪深300/中证500/创业板/证券
    "513100", "513500", "513030", "513520", "513130",  # 海外：纳指/标普/德国/日经/恒生科技
    "518880", "161226",                              # 商品：黄金/白银LOF
]
# 防御资产（缺位时的理想归宿；受1万元整手限制，实际多留现金）
BOND_CODE = "511260"   # 十年国债ETF
CASH_CODE = "511880"   # 银华日利（货币）
ALL_POOL = RISK_POOL + [BOND_CODE, CASH_CODE]

ASSET_CATEGORY = {
    "510300": "A股", "510500": "A股", "159915": "A股", "512880": "A股",
    "513100": "海外", "513500": "海外", "513030": "海外", "513520": "海外",
    "513130": "海外", "518880": "商品", "161226": "商品",
    BOND_CODE: "防御", CASH_CODE: "防御",
}

DEFAULT_PARAMS: Dict[str, float] = {
    "trend_w": 200,     # 长期趋势窗口
    "mom_w": 120,       # 动量 / 波动率窗口
    "top_n": 5,         # 持仓标的数
    "stop": -0.08,      # 个股峰值回撤止损阈值
    "cap": 0.40,        # 单只标的最大权重
    "ann_days": 243,    # 年交易日（波动率年化）
}


# ---------------- 日历工具 ----------------
def is_month_end_trade_day(today: str,
                           is_trade_date_fn: Callable[[str], Optional[bool]]) -> bool:
    """today 是否为本月最后一个 A股交易日。
    判定：从明天起直到跨月，若本月内还存在任何交易日，则 False；否则 True。
    日历不可用时退化为“自然月末且为工作日”的保守判断。"""
    d = _dt.date.fromisoformat(today)
    nd = d + _dt.timedelta(days=1)
    checked = False
    while (nd.year, nd.month) == (d.year, d.month):
        try:
            is_td = is_trade_date_fn(nd.isoformat())
        except Exception:
            is_td = None
        if is_td is not None:
            checked = True
            if is_td:
                return False
        else:
            # 日历缺失：退化为工作日判断
            if nd.weekday() < 5:
                return False
        nd += _dt.timedelta(days=1)
    return True


# ---------------- 指标计算 ----------------
def _features(closes: List[float], p: Dict[str, float]):
    """返回 (close, trend_ma, momentum, ann_vol)；数据不足返回 None。"""
    tw = int(p["trend_w"])
    mw = int(p["mom_w"])
    if len(closes) < tw + 1:
        return None
    close = closes[-1]
    trend_ma = sum(closes[-tw:]) / tw                 # 最近 200 日（含今日）均值
    past = closes[-1 - mw]
    momentum = close / past - 1                      # 120 日动量
    rets = [closes[i] / closes[i - 1] - 1
            for i in range(len(closes) - mw, len(closes))]
    vol = _std(rets) * (p["ann_days"] ** 0.5)        # 年化波动率
    if vol <= 0:
        return None
    return close, trend_ma, momentum, vol


def _std(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def _fresh_target(hist: Dict[str, List[float]],
                  p: Dict[str, float]) -> Dict[str, float]:
    """调仓日：趋势过滤 + 风险调整动量排序 + 逆波动率权重。"""
    candidates = []
    for code in RISK_POOL:
        closes = hist.get(code)
        if not closes:
            continue
        f = _features(closes, p)
        if f is None:
            continue
        close, trend_ma, momentum, ann_vol = f
        if close <= trend_ma:                # 长期趋势向下，不买
            continue
        score = momentum / ann_vol           # 风险调整动量
        candidates.append((score, ann_vol, code))
    candidates.sort(key=lambda x: x[0], reverse=True)
    chosen = candidates[: int(p["top_n"])]
    if not chosen:
        return {}
    inv = [(1.0 / v, code) for _, v, code in chosen]
    total_inv = sum(x for x, _ in inv)
    weights = {code: min(p["cap"], x / total_inv) for x, code in inv}
    # 封顶后不重新归一，缺位/被截断资金留现金
    return weights


# ---------------- 主决策入口 ----------------
def decide(hist: Dict[str, List[float]], broker, today: str,
           prices: Dict[str, float],
           is_trade_date_fn: Callable[[str], Optional[bool]],
           params: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """计算今日目标权重 {code: weight}，并更新 broker.strategy_state。
    由 run_daily_engine 在拿到当日真实收盘价后、rebalance 之前调用。

    状态：
      peak          各持仓买入后最高收盘价
      last_rebal    上次调仓日
      pending_stop  上一交易日标记、今日必须卖出的标的
      last_target   上次调仓目标（非调仓日维持）
    """
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)

    st = broker.strategy_state or {}
    peak: Dict[str, float] = dict(st.get("peak", {}))
    pending_stop = set(st.get("pending_stop", []))
    last_target: Dict[str, float] = dict(st.get("last_target", {}))

    rebal_today = is_month_end_trade_day(today, is_trade_date_fn)
    # 冷启动：尚无目标且空仓（如实盘首日），立即建仓；在成功建仓前每日评估
    cold_start = not st.get("last_target") and not broker.positions
    if rebal_today or cold_start:
        base = _fresh_target(hist, p)
        st["last_rebal"] = today
    else:
        # 非调仓日：维持现有持仓的实际权重（允许漂移，不做再平衡）
        base = _hold_weights(broker, prices, set())

    # 今日执行上一交易日标记的止损：剔除（即便调仓日也不买回，冷却1日）
    for code in pending_stop:
        base.pop(code, None)

    target = base

    # 用今日收盘价更新峰值，并判断“明日止损”
    new_pending = set()
    for code in target.keys():
        price = prices.get(code)
        if price is None or price <= 0:
            continue
        if code in peak:
            peak[code] = max(peak[code], price)
        else:
            peak[code] = price              # 今日首次买入，峰值起算
        if price / peak[code] - 1 <= p["stop"]:
            new_pending.add(code)

    # 清理不再持有、也不在止损队列中的峰值，避免状态无限累积
    keep = set(target.keys()) | new_pending
    for code in list(peak.keys()):
        if code not in keep:
            peak.pop(code, None)

    st["peak"] = peak
    st["pending_stop"] = sorted(new_pending)
    st["last_target"] = target
    broker.strategy_state = st
    return target


def _hold_weights(broker, prices: Dict[str, float],
                  exclude: set) -> Dict[str, float]:
    """非调仓日：按当前持仓在当前价下的实际市值占比返回权重，
    使 rebalance 不产生再平衡交易；exclude 中的标的不保留（卖出）。"""
    total_asset = broker.cash + sum(
        pos.qty * prices.get(code, pos.cost_price)
        for code, pos in broker.positions.items()
        if code not in exclude)
    if total_asset <= 0:
        return {}
    weights = {}
    for code, pos in broker.positions.items():
        if code in exclude:
            continue
        price = prices.get(code, pos.cost_price)
        mv = pos.qty * price
        if mv > 0:
            weights[code] = mv / total_asset
    return weights
