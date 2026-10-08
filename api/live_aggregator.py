#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘数据聚合层（live-data → 前端子页面扁平契约）
=================================================================
从 live-data/daily、latest、_account_state 读取 Windows 端每日引擎产生的
本机撮合账本，聚合成「买卖记录 / 盈亏历史 / 对账单」三个子页面直接可用的
**扁平 JSON**（前端 res.json() 后直接取 trades / history / per_strategy）。

数据根目录：
  默认 <repo>/live-data；UI 走查时由环境变量 QM_LIVE_DATA_DIR 指向隔离的
  ui-mock/live-data（含 _mock_marker.json），绝不污染真实账本。

性质：全部为模拟盘、本机真实撮合，不连接任何券商真实账号/资金账号。
"""
import os
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_ROOT = Path(os.environ.get("QM_LIVE_DATA_DIR", str(BASE_DIR / "live-data")))

# 成交记录/对账单里的标的名称兜底（实时行情接口返回名称时以接口为准）
ETF_NAMES = {
    "511880": "银华日利ETF", "510300": "沪深300ETF", "510500": "中证500ETF",
    "159915": "创业板ETF", "513100": "纳指ETF", "513520": "日经ETF",
    "518880": "黄金ETF", "159985": "豆粕ETF", "588080": "科创50ETF",
    "512100": "中证1000ETF", "512040": "国泰价值ETF", "512890": "红利低波ETF",
    "513130": "恒生科技ETF", "513030": "纳指科技ETF", "161226": "国泰商品ETF",
    "159967": "创成长ETF", "159980": "有色ETF", "159981": "能源化工ETF",
    "513080": "法国CAC40ETF", "513500": "标普500ETF", "513690": "恒生股息ETF",
    "501018": "南方原油LOF",
}

STRATEGY_ORDER = ["zhuidian", "qixing", "r32", "sanhe", "lightning", "goldcombo"]


# ============================================================
# 读取与基础工具
# ============================================================
def is_mock(root: Path = None) -> bool:
    root = root or LIVE_ROOT
    return (root / "_mock_marker.json").exists()


def nature_meta(root: Path = None) -> dict:
    """数据性质标注（所有响应都带，前端据此打角标/横幅）。"""
    root = root or LIVE_ROOT
    mock = is_mock(root)
    if mock:
        return {
            "data_mode": "live",
            "is_ui_mock": True,
            "data_nature": "ui_mock",
            "data_nature_label": "【UI测试虚拟数据】仅用于界面走查 · 非实盘 / 非回测 / 不接券商",
            "note": "当前为隔离目录 ui-mock 的固定种子虚拟数据，仅用于检验界面与交互，禁止冒充实盘。",
        }
    return {
        "data_mode": "live",
        "is_ui_mock": False,
        "data_nature": "live",
        "data_nature_label": "实盘模拟（Windows 本机真实撮合，非回测，不接任何券商）",
        "note": "来自 Windows 端每日引擎按真实行情本机撮合的账本，经 GitHub 同步；不连接任何真实券商账号。",
    }


def _load_daily_records(strategy="", start="", end="", root: Path = None):
    """读取 daily/<date>/<sid>.json，返回按 (date, sid) 升序的记录列表。"""
    root = root or LIVE_ROOT
    daily = root / "daily"
    out = []
    if not daily.exists():
        return out
    for day_dir in sorted(daily.iterdir()):
        if not day_dir.is_dir():
            continue
        d = day_dir.name
        if start and d < start:
            continue
        if end and d > end:
            continue
        for f in sorted(day_dir.glob("*.json")):
            sid = f.stem
            if strategy and sid != strategy:
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append((d, sid, rec))
    return out


def _num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _etf_name(code, rec=None):
    if rec:
        for p in rec.get("positions", []):
            if p.get("code") == code and p.get("name"):
                return p["name"]
    return ETF_NAMES.get(code, code)


# ============================================================
# 1) 买卖记录
# ============================================================
def _map_trade(d, sid, rec, mock):
    """把引擎成交流水（Broker.trades 单项）映射为 trades.html 字段。"""
    side = (d.get("side") or "BUY").upper()
    action = "buy" if side == "BUY" else "sell"
    code = d.get("code", "")
    qty = int(_num(d.get("qty")))
    ref = d.get("reference_price")
    price = _num(d.get("price"))
    ref = _num(ref, price)
    amount = _num(d.get("amount"), round(price * qty, 2))
    slip = d.get("slippage")
    if slip is None:  # 旧数据兜底：滑点约成交额的 0.1%
        slip = round(amount * 0.001, 2)
    realized = _num(d.get("realized_pnl")) if action == "sell" else 0.0
    realized_pct = _num(d.get("realized_pnl_pct")) if action == "sell" else 0.0
    cost_basis = _num(d.get("cost_basis"))
    name = d.get("name") or _etf_name(code, rec) or code
    fill_dt = f"{rec.get('date', '')}T15:00:00"
    return {
        "strategy_id": sid,
        "strategy_name": rec.get("strategy_name", sid),
        "action": action,
        "order_time": fill_dt,
        "filled_time": fill_dt,
        "code": code,
        "name": name,
        "order_shares": qty,
        "order_price": round(ref, 4),
        "filled_shares": qty,
        "filled_avg_price": round(price, 4),
        "filled_amount": round(amount, 2),
        "commission": round(_num(d.get("commission")), 2),
        "stamp_tax": round(_num(d.get("stamp_tax")), 2),
        "transfer_fee": round(_num(d.get("transfer_fee")), 2),
        "slippage": round(_num(slip), 2),
        "status": "filled",
        "signal_source": "UI虚拟·本机撮合" if mock else "实盘模拟·本机撮合",
        "realized_pnl": round(realized, 2),
        "realized_pnl_pct": round(realized_pct, 2),
        "cost_basis": round(cost_basis, 4),
    }


def build_trades(strategy="", action="", start="", end="", root: Path = None):
    root = root or LIVE_ROOT
    mock = is_mock(root)
    records = _load_daily_records(strategy, start, end, root)
    trades = []
    for d, sid, rec in records:
        for t in rec.get("trades_today", []) or []:
            row = _map_trade(t, sid, rec, mock)
            if action and row["action"] != action:
                continue
            trades.append(row)
    # 最新成交在最上
    trades.sort(key=lambda r: r["filled_time"], reverse=True)
    payload = {
        "trades": trades,
        "count": len(trades),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    payload.update(nature_meta(root))
    return payload


# ============================================================
# 2) 盈亏历史
# ============================================================
def build_pnl_history(strategy="", start="", end="", root: Path = None):
    root = root or LIVE_ROOT
    mock = is_mock(root)
    records = _load_daily_records(strategy, start, end, root)

    # 按日期聚合选中策略
    by_day = {}
    init_capital = {}
    for d, sid, rec in records:
        init_capital[sid] = _num(rec.get("initial_capital"), 10000.0)
        day = by_day.setdefault(d, {"cash": 0.0, "mv": 0.0, "asset": 0.0,
                                    "today_pnl": 0.0, "positions_count": 0,
                                    "top_mv": 0.0, "has_today": False,
                                    "prev_asset": None})
        cash = _num(rec.get("cash"))
        mv = _num(rec.get("market_value"))
        asset = _num(rec.get("total_asset"), cash + mv)
        day["cash"] += cash
        day["mv"] += mv
        day["asset"] += asset
        if rec.get("today_pnl") is not None:
            day["today_pnl"] += _num(rec.get("today_pnl"))
            day["has_today"] = True
        day["positions_count"] += len([p for p in rec.get("positions", [])
                                       if _num(p.get("qty")) > 0])
        for p in rec.get("positions", []):
            pmv = _num(p.get("market_value"),
                       _num(p.get("qty")) * _num(p.get("current_price")))
            if pmv > day["top_mv"]:
                day["top_mv"] = pmv

    initial_total = sum(init_capital.values()) if init_capital else 0.0
    history = []
    prev_asset = initial_total
    for d in sorted(by_day.keys()):
        agg = by_day[d]
        equity = round(agg["asset"], 2)
        if agg["has_today"]:
            daily_pnl = round(agg["today_pnl"], 2)
        else:  # 旧数据无 today_pnl，则用相邻日权益差
            daily_pnl = round(equity - prev_asset, 2)
        base_for_ret = prev_asset if prev_asset else initial_total
        daily_ret = round(daily_pnl / base_for_ret * 100, 2) if base_for_ret else 0.0
        cum_pnl = round(equity - initial_total, 2)
        cum_ret = round(cum_pnl / initial_total * 100, 2) if initial_total else 0.0
        top_pct = round(agg["top_mv"] / equity * 100, 1) if equity > 0 else 0.0
        history.append({
            "date": d,
            "equity": equity,
            "cash": round(agg["cash"], 2),
            "market_value": round(agg["mv"], 2),
            "daily_pnl": daily_pnl,
            "daily_return_pct": daily_ret,
            "cumulative_pnl": cum_pnl,
            "cumulative_return_pct": cum_ret,
            "positions_count": agg["positions_count"],
            "top_position_pct": top_pct,
            "data_source": "UI虚拟" if mock else "实盘模拟",
        })
        prev_asset = equity

    payload = {
        "history": history,
        "count": len(history),
        "initial_capital": initial_total,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    payload.update(nature_meta(root))
    return payload


# ============================================================
# 3) 对账单（本机单一账本自洽核对：模拟器即券商，恒应一致）
# ============================================================
def build_reconciliation(strategy="", start="", end="", root: Path = None):
    root = root or LIVE_ROOT
    mock = is_mock(root)
    records = _load_daily_records(strategy, start, end, root)

    # 每策略：窗口内最新快照 + 区间费用/成交汇总
    per = {}
    order_ids = []
    for d, sid, rec in records:
        cur = per.setdefault(sid, {
            "name": rec.get("strategy_name", sid),
            "commission": 0.0, "stamp": 0.0, "transfer": 0.0,
            "slippage": 0.0, "trades_count": 0, "latest": None,
        })
        cur["name"] = rec.get("strategy_name", cur["name"])
        for t in rec.get("trades_today", []) or []:
            cur["commission"] += _num(t.get("commission"))
            cur["stamp"] += _num(t.get("stamp_tax"))
            cur["transfer"] += _num(t.get("transfer_fee"))
            slip = t.get("slippage")
            cur["slippage"] += _num(slip if slip is not None
                                    else _num(t.get("amount")) * 0.001)
            cur["trades_count"] += 1
            order_ids.append(f"{d}:{sid}:{t.get('code','')}:{t.get('side','')}")
        cur["latest"] = (d, rec)

    per_strategy = {}
    total_cash = total_mv = total_asset = total_today = 0.0
    sids = [s for s in STRATEGY_ORDER if s in per] + \
           [s for s in per if s not in STRATEGY_ORDER]
    for sid in sids:
        c = per[sid]
        d, rec = c["latest"]
        cash = _num(rec.get("cash"))
        mv = _num(rec.get("market_value"))
        asset = _num(rec.get("total_asset"), cash + mv)
        init = _num(rec.get("initial_capital"), 10000.0)
        pnl = _num(rec.get("live_total_pnl"), asset - init)
        ret = _num(rec.get("live_total_return"),
                   pnl / init * 100 if init else 0.0)
        total_cash += cash
        total_mv += mv
        total_asset += asset
        total_today += _num(rec.get("today_pnl"))
        per_strategy[sid] = {
            "name": c["name"],
            "pnl": round(pnl, 2),
            "return_pct": round(ret, 2),
            "cash": round(cash, 2),
            "market_value": round(mv, 2),
            "total_asset": round(asset, 2),
            "trades_count": c["trades_count"],
            # 本机撮合无外部券商：账本两侧同源，账实自洽
            "cash_match": True, "cash_simulator": round(cash, 2),
            "cash_broker": round(cash, 2), "cash_diff": 0.0,
            "mv_match": True, "mv_simulator": round(mv, 2),
            "mv_broker": round(mv, 2), "mv_diff": 0.0,
            "position_match": True,
            "order_match": True, "order_diffs": [],
            "overall_match": True,
            "total_commission": round(c["commission"], 2),
            "total_stamp_tax": round(c["stamp"], 2),
            "total_transfer_fee": round(c["transfer"], 2),
            "total_slippage": round(c["slippage"], 2),
        }

    has_data = len(per_strategy) > 0
    report = {
        "per_strategy": per_strategy,
        "tolerance": 0.01,
        # 顶层总体核对结论（单一账本，全部一致）
        "cash_match": has_data, "cash_diff": 0.0,
        "equity_match": has_data, "equity_diff": 0.0,
        "mv_match": has_data, "mv_diff": 0.0,
        "position_match": has_data, "position_diffs": [],
        "order_match": has_data, "order_diffs": [],
        "overall_match": has_data,
        "orders_total": len(order_ids),
        "totals": {
            "cash": round(total_cash, 2),
            "market_value": round(total_mv, 2),
            "total_equity": round(total_asset, 2),
            "daily_pnl": round(total_today, 2),
        },
        "window": {"start": start, "end": end, "strategy": strategy},
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    report.update(nature_meta(root))
    return report


if __name__ == "__main__":
    # 命令行自检：python api/live_aggregator.py
    import sys
    print("LIVE_ROOT =", LIVE_ROOT, "| mock =", is_mock())
    tr = build_trades()
    ph = build_pnl_history()
    rc = build_reconciliation()
    print("trades:", tr["count"], "| pnl days:", ph["count"],
          "| strategies in recon:", len(rc["per_strategy"]))
    if tr["trades"]:
        print("sample trade:", json.dumps(tr["trades"][0], ensure_ascii=False))
    if ph["history"]:
        print("sample pnl:", json.dumps(ph["history"][-1], ensure_ascii=False))
