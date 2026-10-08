#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实买卖撮合引擎内核（A股模拟盘，不连接任何券商）
=====================================================
规则（贴近真实A股）：
  - 买入：100股整数倍；佣金 max(5元, 成交额×0.00025)；无印花税；滑点 +0.1%
  - 卖出：100股整数倍；佣金 max(5元, 成交额×0.00025)；印花税 成交额×0.0005；滑点 -0.1%
  - T+1：当日买入的股份次日才可卖
  - 持仓成本：加权平均成本法
  - 每日结算：按当日收盘价 mark-to-market

状态持久化：account_state.json（现金、持仓、已实现盈亏、成交流水）
"""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ---- 费用参数 ----
COMMISSION_RATE = 0.00025   # 佣金万2.5
MIN_COMMISSION = 5.0        # 最低佣金5元
STAMP_TAX_RATE = 0.0005     # 印花税千0.5（仅卖出）
SLIPPAGE = 0.001            # 滑点0.1%
LOT = 100                   # A股整手100股


def _commission(amount: float) -> float:
    return max(MIN_COMMISSION, amount * COMMISSION_RATE)


@dataclass
class Position:
    code: str
    name: str = ""
    qty: int = 0              # 总持仓
    avail_qty: int = 0        # 可卖（T+1，今日买入计入 qty 但不计 avail）
    cost_price: float = 0.0   # 加权平均成本价

    def market_value(self, price: float) -> float:
        return self.qty * price


class Broker:
    """模拟券商账户：现金 + 持仓 + 成交流水"""

    def __init__(self, initial_capital: float = 10000.0, strategy_id: str = ""):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions: Dict[str, Position] = {}
        self.trades: List[dict] = []          # 成交流水
        self.realized_pnl: float = 0.0
        self.strategy_id = strategy_id
        self.pending_target: Dict[str, float] = {}   # 明日目标持仓 {code: weight}

    # ---------- 买入 ----------
    def buy(self, code: str, price: float, amount_yuan: float, name: str = "",
            date: str = "") -> Optional[dict]:
        """用 amount_yuan 元买入 code，按收盘价+滑点成交。返回成交记录或None"""
        if price <= 0 or amount_yuan <= 0:
            return None
        exec_price = price * (1 + SLIPPAGE)
        # 整手取整
        qty = int(amount_yuan / exec_price / LOT) * LOT
        if qty <= 0:
            return None
        gross = qty * exec_price
        commission = _commission(gross)
        slip_amount = qty * (exec_price - price)   # 买入滑点金额（高价买入的额外成本）
        total_cost = gross + commission
        if total_cost > self.cash:
            # 现金不足，按可买金额重算
            qty = int((self.cash - MIN_COMMISSION) / exec_price / LOT) * LOT
            if qty <= 0:
                return None
            gross = qty * exec_price
            commission = _commission(gross)
            slip_amount = qty * (exec_price - price)
            total_cost = gross + commission
        self.cash -= total_cost

        # 加权平均成本
        if code in self.positions:
            pos = self.positions[code]
            old_cost = pos.cost_price * pos.qty
            pos.qty += qty
            pos.avail_qty += 0          # T+1：今日买入不可卖
            pos.cost_price = (old_cost + gross) / pos.qty if pos.qty > 0 else 0
            pos.name = name or pos.name
        else:
            self.positions[code] = Position(
                code=code, name=name, qty=qty, avail_qty=0,
                cost_price=exec_price)

        trade = {
            "date": date, "side": "BUY", "code": code,
            "name": name or self.positions[code].name,
            "reference_price": round(price, 4),   # 委托参考价（未含滑点）
            "price": round(exec_price, 4), "qty": qty,
            "amount": round(gross, 2), "commission": round(commission, 2),
            "stamp_tax": 0.0, "transfer_fee": 0.0,
            "slippage": round(slip_amount, 2),    # 滑点金额
            "realized_pnl": 0.0, "realized_pnl_pct": 0.0,
            "cost_basis": round(self.positions[code].cost_price, 4),  # 每股持仓成本
            "cash_after": round(self.cash, 2),
        }
        self.trades.append(trade)
        return trade

    # ---------- 卖出 ----------
    def sell(self, code: str, price: float, qty: Optional[int] = None,
             name: str = "", date: str = "") -> Optional[dict]:
        """卖出 code，默认卖出全部可卖持仓"""
        if code not in self.positions:
            return None
        pos = self.positions[code]
        avail = pos.avail_qty
        if avail <= 0:
            return None  # T+1，今天买的不能卖
        sell_qty = avail if qty is None else min(qty, avail)
        if sell_qty <= 0:
            return None
        exec_price = price * (1 - SLIPPAGE)
        gross = sell_qty * exec_price
        commission = _commission(gross)
        stamp = gross * STAMP_TAX_RATE
        slip_amount = sell_qty * (price - exec_price)   # 卖出滑点金额（低价卖出的少收）
        net_cash = gross - commission - stamp
        self.cash += net_cash

        # 实现盈亏（单笔，扣费后相对持仓成本）
        pos_name = name or pos.name
        cost_price = pos.cost_price
        cost_basis_total = cost_price * sell_qty
        realized = gross - commission - stamp - cost_basis_total
        realized_pct = realized / cost_basis_total * 100 if cost_basis_total > 0 else 0.0
        self.realized_pnl += realized

        pos.qty -= sell_qty
        pos.avail_qty -= sell_qty
        if pos.qty <= 0:
            del self.positions[code]

        trade = {
            "date": date, "side": "SELL", "code": code, "name": pos_name,
            "reference_price": round(price, 4),   # 委托参考价（未含滑点）
            "price": round(exec_price, 4), "qty": sell_qty,
            "amount": round(gross, 2), "commission": round(commission, 2),
            "stamp_tax": round(stamp, 2), "transfer_fee": 0.0,
            "slippage": round(slip_amount, 2),    # 滑点金额
            "realized_pnl": round(realized, 2),
            "realized_pnl_pct": round(realized_pct, 2),
            "cost_basis": round(cost_price, 4),   # 卖出部分的每股成本
            "cash_after": round(self.cash, 2),
        }
        self.trades.append(trade)
        return trade

    # ---------- 每日结算 ----------
    def settle(self, prices: Dict[str, float]) -> dict:
        """按当日收盘价重估，返回当日账户快照"""
        market_value = 0.0
        positions_out = []
        for code, pos in self.positions.items():
            price = prices.get(code, pos.cost_price)
            mv = pos.qty * price
            market_value += mv
            positions_out.append({
                "code": code, "name": pos.name, "qty": pos.qty,
                "avail_qty": pos.avail_qty, "cost_price": round(pos.cost_price, 4),
                "current_price": round(price, 4),
                "market_value": round(mv, 2),
                "pnl": round((price - pos.cost_price) * pos.qty, 2),
                "pnl_pct": round((price / pos.cost_price - 1) * 100, 2) if pos.cost_price > 0 else 0,
            })
        total_asset = self.cash + market_value
        total_pnl = total_asset - self.initial_capital
        return {
            "cash": round(self.cash, 2),
            "market_value": round(market_value, 2),
            "total_asset": round(total_asset, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return": round(total_pnl / self.initial_capital * 100, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "positions": positions_out,
        }

    def end_of_day(self):
        """收盘后：今日买入转为可卖（T+1 跨过一天）"""
        for pos in self.positions.values():
            pos.avail_qty = pos.qty

    def rebalance(self, target: Dict[str, float], prices: Dict[str, float],
                  date: str = "", names: Optional[Dict[str, str]] = None) -> List[dict]:
        """按目标持仓 {code: weight} 调仓，用 prices 成交。返回当天所有成交。

        先卖不在目标里的持仓，再按权重买入目标标的。
        weight 占总资产比例（0~1）。names 为 {code: 标的名}，写入成交记录。
        """
        names = names or {}
        all_trades = []
        total_asset = self.cash + sum(
            p.qty * prices.get(c, p.cost_price) for c, p in self.positions.items())

        # 1. 卖出：当前持仓但不在目标里的，全卖
        for code in list(self.positions.keys()):
            if code not in target and code in self.positions:
                price = prices.get(code)
                if price and price > 0:
                    t = self.sell(code, price, date=date, name=names.get(code, ""))
                    if t:
                        all_trades.append(t)

        # 2. 买入：目标持仓，按权重分配总资产
        for code, weight in target.items():
            price = prices.get(code)
            if not price or price <= 0:
                continue
            # 重新算总资产（卖出后现金变了）
            total_asset = self.cash + sum(
                p.qty * prices.get(c, p.cost_price) for c, p in self.positions.items())
            target_amount = total_asset * weight
            # 如果已经持有这只，只补差额
            held_qty = self.positions.get(code).qty if code in self.positions else 0
            held_value = held_qty * price
            buy_amount = target_amount - held_value
            if buy_amount > 0:
                t = self.buy(code, price, buy_amount, date=date,
                             name=names.get(code, ""))
                if t:
                    all_trades.append(t)
        return all_trades

    # ---------- 持久化 ----------
    def save(self, path: Path):
        data = {
            "strategy_id": self.strategy_id,
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "positions": {c: asdict(p) for c, p in self.positions.items()},
            "trades": self.trades[-500:],   # 只留最近500条
            "pending_target": self.pending_target,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Broker":
        d = json.loads(path.read_text(encoding="utf-8"))
        b = cls(initial_capital=d["initial_capital"], strategy_id=d.get("strategy_id", ""))
        b.cash = d["cash"]
        b.realized_pnl = d.get("realized_pnl", 0.0)
        for code, pd in d.get("positions", {}).items():
            b.positions[code] = Position(**pd)
        b.trades = d.get("trades", [])
        b.pending_target = d.get("pending_target", {})
        return b

    @classmethod
    def load_or_new(cls, path: Path, capital: float, sid: str) -> "Broker":
        if path.exists():
            return cls.load(path)
        return cls(initial_capital=capital, strategy_id=sid)
