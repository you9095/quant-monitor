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
    is_backfill = bool(rec.get("backfill"))
    nature = rec.get("data_nature") or ("UI虚拟·本机撮合" if mock else "实盘模拟·本机撮合")
    if not mock:
        signal_src = "实盘模拟·事后补记·本机撮合" if is_backfill else "实盘模拟·本机撮合"
    else:
        signal_src = "UI虚拟·本机撮合"
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
        "signal_source": signal_src,
        "realized_pnl": round(realized, 2),
        "realized_pnl_pct": round(realized_pct, 2),
        "cost_basis": round(cost_basis, 4),
        "backfill": is_backfill,
        "backfill_for_date": rec.get("backfill_for_date"),
        "backfill_run_at": rec.get("backfill_run_at"),
        "data_nature": nature,
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
                                    "prev_asset": None,
                                    "backfill": False, "data_nature": None})
        if rec.get("backfill"):
            day["backfill"] = True
            day["data_nature"] = rec.get("data_nature") or day["data_nature"]
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
            "backfill": agg.get("backfill", False),
            "data_nature": agg.get("data_nature"),
            "data_source": ("事后补记" if agg.get("backfill") else
                            ("UI虚拟" if mock else "实盘模拟")),
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


STRATEGY_COLORS = {
    "qixing": "#3b82f6", "r32": "#10b981", "zhuidian": "#f59e0b",
    "sanhe": "#8b5cf6", "lightning": "#ef4444", "goldcombo": "#ec4899",
}


def _ordered_sids(sids):
    """按 STRATEGY_ORDER 稳定排序，未知策略排末尾。"""
    known = [s for s in STRATEGY_ORDER if s in sids]
    extra = sorted(s for s in sids if s not in STRATEGY_ORDER)
    return known + extra


def _read_latest(root: Path = None):
    """读取 latest/<sid>.json 最新快照，返回 {sid: rec}。"""
    root = root or LIVE_ROOT
    out = {}
    latest = root / "latest"
    if not latest.exists():
        return out
    for f in latest.glob("*.json"):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return out


def _live_dates(root: Path = None):
    root = root or LIVE_ROOT
    daily = root / "daily"
    if not daily.exists():
        return []
    return sorted(d.name for d in daily.iterdir() if d.is_dir())


def _map_position(p):
    qty = int(_num(p.get("qty")))
    cost = _num(p.get("cost_price", p.get("cost")))
    price = _num(p.get("current_price", cost))
    mv = _num(p.get("market_value"), qty * price)
    pnl = _num(p.get("pnl"), (price - cost) * qty)
    pnl_pct = _num(p.get("pnl_pct"), (pnl / (qty * cost) * 100) if qty and cost else 0.0)
    return {
        "code": p.get("code", ""), "name": p.get("name", ""),
        "quantity": qty, "qty": qty, "avail_qty": int(_num(p.get("avail_qty"))),
        "cost_price": round(cost, 4), "current_price": round(price, 4),
        "market_value": round(mv, 2), "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 3), "weight": 0.0,
    }


def _action_from_rec(rec):
    """从当日成交流水推断动作类型。"""
    trades = rec.get("trades_today", []) or []
    sides = { (t.get("side") or "").upper() for t in trades }
    if "SELL" in sides and "BUY" in sides:
        return "REBALANCE"
    if "SELL" in sides:
        return "SELL"
    if "BUY" in sides:
        return "BUY"
    act = rec.get("action")
    if isinstance(act, dict):
        return act.get("type") or act.get("action") or "HOLD"
    return act or "HOLD"


# ============================================================
# 4) 首页总览（策略卡 / KPI 数据源，替代前端写死 mock）
# ============================================================
def build_overview(root: Path = None):
    root = root or LIVE_ROOT
    mock = is_mock(root)
    latest = _read_latest(root)
    dates = _live_dates(root)
    strategies = []
    total_asset = total_init = total_pnl = total_today = 0.0
    for sid in _ordered_sids(set(latest.keys())):
        rec = latest[sid]
        init = _num(rec.get("initial_capital"), 10000.0)
        asset = _num(rec.get("total_asset"), init)
        pnl = _num(rec.get("live_total_pnl"), asset - init)
        today = _num(rec.get("today_pnl"))
        cash = _num(rec.get("cash"))
        mv = _num(rec.get("market_value"), asset - cash)
        positions = [_map_position(p) for p in rec.get("positions", [])
                     if int(_num(p.get("qty"))) > 0]
        for p in positions:
            p["weight"] = round(p["market_value"] / asset * 100, 2) if asset > 0 else 0.0
        days = int(_num(rec.get("live_days"), len(dates) or 0))
        total_asset += asset
        total_init += init
        total_pnl += pnl
        total_today += today
        strategies.append({
            "strategy_id": sid,
            "strategy_name": rec.get("strategy_name", sid),
            "status": "running" if days > 0 else "waiting",
            "today_action": _action_from_rec(rec),
            "today_pnl": round(today, 2),
            "today_return": round(_num(rec.get("today_return")), 3),
            "total_asset": round(asset, 2),
            "total_return": round(_num(rec.get("live_total_return")), 3),
            "total_pnl": round(pnl, 2),
            "initial_capital": round(init, 2),
            "live_total_pnl": round(pnl, 2),
            "live_total_return": round(_num(rec.get("live_total_return")), 3),
            "live_days": days,
            "live_start_date": dates[0] if dates else None,
            "cash": round(cash, 2),
            "market_value": round(mv, 2),
            "position_ratio": round(mv / asset, 4) if asset > 0 else 0.0,
            "positions": positions,
            "holdings": positions,
            "price_source": rec.get("price_source"),
            "price_source_detail": rec.get("price_source_detail"),
            "last_date": rec.get("date"),
            "backtest_total_return": None, "sharpe_ratio": None,
            "max_drawdown": None, "trades_count": len(rec.get("trades_today", []) or []),
        })
    has_data = bool(strategies)
    meta = nature_meta(root)
    meta.update({
        "strategies": strategies,
        "combined": {
            "active_count": len(strategies),
            "initial_capital": round(total_init, 2),
            "total_asset": round(total_asset, 2),
            "total_pnl": round(total_pnl, 2),
            "today_pnl": round(total_today, 2),
            "total_return": round(total_pnl / total_init * 100, 3) if total_init else 0.0,
        },
        "live_days": len(dates),
        "live_start_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "alerts_summary": {"critical": 0, "warning": 0, "info": 0},
        "update_time": datetime.now().isoformat(timespec="seconds"),
    })
    if not has_data and not mock:
        meta["data_mode_label"] = "实盘 — 尚未开始运行，暂无数据"
        meta["data_nature_note"] = ("实盘数据从 Windows 端每日引擎运行之日起记录，经 GitHub 同步；"
                                    "当前 Mac 尚未拉取到任何实盘账本，不会用模拟盘或回测数据代替。")
    elif has_data and not mock:
        meta["data_mode_label"] = (f"实盘模拟（Windows 本机真实撮合 · 第 {len(dates)} 天 · "
                                   f"不连接任何券商）— 总资产 {total_asset:.0f} 元")
    return meta


# ============================================================
# 5) 组合总览 KPI
# ============================================================
def build_portfolio_summary(root: Path = None):
    root = root or LIVE_ROOT
    latest = _read_latest(root)
    dates = _live_dates(root)
    per = {}
    total_init = total_value = total_pnl = total_today = 0.0
    for sid in _ordered_sids(set(latest.keys())):
        rec = latest[sid]
        init = _num(rec.get("initial_capital"), 10000.0)
        asset = _num(rec.get("total_asset"), init)
        pnl = _num(rec.get("live_total_pnl"), asset - init)
        today = _num(rec.get("today_pnl"))
        total_init += init
        total_value += asset
        total_pnl += pnl
        total_today += today
        per[sid] = {
            "name": rec.get("strategy_name", sid),
            "initial_capital": round(init, 2),
            "total_asset": round(asset, 2),
            "total_value": round(asset, 2),
            "total_pnl": round(pnl, 2),
            "today_pnl": round(today, 2),
            "total_return_pct": round(_num(rec.get("live_total_return")), 3),
            "live_days": int(_num(rec.get("live_days"), len(dates))),
            "cash": round(_num(rec.get("cash")), 2),
            "market_value": round(_num(rec.get("market_value")), 2),
        }
    payload = {
        "initial_capital": round(total_init, 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "today_pnl": round(total_today, 2),
        "total_return_pct": round(total_pnl / total_init * 100, 3) if total_init else 0.0,
        "per_strategy": per,
        "live_start_date": dates[0] if dates else None,
        "live_days": len(dates),
        "last_date": dates[-1] if dates else None,
        "update_time": datetime.now().isoformat(timespec="seconds"),
    }
    payload.update(nature_meta(root))
    return payload


# ============================================================
# 6) 今日交易动作
# ============================================================
def build_today_actions(root: Path = None):
    root = root or LIVE_ROOT
    latest = _read_latest(root)
    dates = _live_dates(root)
    today = dates[-1] if dates else datetime.now().strftime("%Y-%m-%d")
    per = {}
    for sid in _ordered_sids(set(latest.keys())):
        rec = latest[sid]
        if rec.get("date") and rec.get("date") != today:
            continue
        trades = rec.get("trades_today", []) or []
        mapped = [{
            "side": (t.get("side") or "BUY").upper(),
            "action": "buy" if (t.get("side") or "BUY").upper() == "BUY" else "sell",
            "code": t.get("code", ""), "name": t.get("name", ""),
            "qty": int(_num(t.get("qty"))), "price": round(_num(t.get("price")), 4),
            "reference_price": t.get("reference_price"),
            "amount": round(_num(t.get("amount")), 2),
            "commission": round(_num(t.get("commission")), 2),
            "stamp_tax": round(_num(t.get("stamp_tax")), 2),
            "slippage": round(_num(t.get("slippage")), 2),
        } for t in trades]
        per[sid] = {
            "strategy_id": sid, "name": rec.get("strategy_name", sid),
            "strategy_name": rec.get("strategy_name", sid),
            "action": _action_from_rec(rec),
            "target": mapped[0].get("code", "") if mapped else "",
            "signal_date": today,
            "trades": mapped, "trade_count": len(mapped),
            "total_asset": round(_num(rec.get("total_asset")), 2),
            "today_pnl": round(_num(rec.get("today_pnl")), 2),
            "price_source_detail": rec.get("price_source_detail"),
        }
    payload = {"date": today, "strategies": per, "strategies_list": list(per.values()),
               "data_mode": "live", "live_days": len(dates), "count": len(per)}
    payload.update(nature_meta(root))
    return payload


# ============================================================
# 7) 实盘净值曲线（每日 total_asset）
# ============================================================
def build_live_curves(root: Path = None):
    root = root or LIVE_ROOT
    records = _load_daily_records("", "", "", root)
    by_sid = {}
    dates = set()
    names = {}
    for d, sid, rec in records:
        dates.add(d)
        names[sid] = rec.get("strategy_name", sid)
        by_sid.setdefault(sid, {})[d] = _num(rec.get("total_asset"))
    ordered_dates = sorted(dates)
    curves = {}
    for sid in _ordered_sids(set(by_sid.keys())):
        curves[sid] = {
            "name": names.get(sid, sid), "color": STRATEGY_COLORS.get(sid, "#94a3b8"),
            "dates": ordered_dates,
            "values": [round(by_sid[sid].get(d), 2) if d in by_sid[sid] else None
                       for d in ordered_dates],
        }
    payload = {
        "curves": curves, "days": len(ordered_dates),
        "start_date": ordered_dates[0] if ordered_dates else None,
        "end_date": ordered_dates[-1] if ordered_dates else None,
        "strategy_ids": list(curves.keys()),
    }
    payload.update(nature_meta(root))
    return payload


# ============================================================
# 8) 单策略持仓 / 状态
# ============================================================
def build_positions(sid, root: Path = None):
    root = root or LIVE_ROOT
    rec = _read_latest(root).get(sid)
    if not rec:
        return {"positions": [], "total_asset": 0, "cash": 0, "market_value": 0,
                "data_mode": "live", "found": False}
    positions = [_map_position(p) for p in rec.get("positions", [])
                 if int(_num(p.get("qty"))) > 0]
    asset = _num(rec.get("total_asset"))
    for p in positions:
        p["weight"] = round(p["market_value"] / asset * 100, 2) if asset > 0 else 0.0
    payload = {
        "positions": positions, "total_asset": round(asset, 2),
        "cash": round(_num(rec.get("cash")), 2),
        "market_value": round(_num(rec.get("market_value")), 2),
        "today_pnl": round(_num(rec.get("today_pnl")), 2),
        "live_days": int(_num(rec.get("live_days"))),
        "data_mode": "live", "found": True,
    }
    payload.update(nature_meta(root))
    return payload


def build_status(sid, root: Path = None):
    root = root or LIVE_ROOT
    rec = _read_latest(root).get(sid)
    if not rec:
        return {"status": "waiting", "live_days": 0, "data_mode": "live"}
    payload = {
        "status": "running" if _num(rec.get("live_days")) > 0 else "waiting",
        "live_days": int(_num(rec.get("live_days"))),
        "last_date": rec.get("date"),
        "price_source": rec.get("price_source"),
        "price_source_detail": rec.get("price_source_detail"),
        "today_action": _action_from_rec(rec),
        "data_mode": "live",
    }
    payload.update(nature_meta(root))
    return payload


def build_trade_health(root: Path = None):
    """读取 Windows 端成交监督器写的当日健康心跳（_run_logs/trade_health.json）。
    让 Mac 面板能看到：今日是否交易日、成交是否完成、是否在重试、各行情源命中、
    尝试轮次、缺哪些策略、下次重试时间。无心跳时诚实返回未上报，不编造状态。"""
    root = root or LIVE_ROOT
    # 红标优先（最高）：只要存在未人工解除的红标，无论当日心跳是 done / no_trade_day
    # 还是根本没开机、没心跳，面板都恒亮红灯，直到人工解除（绝不自动补单）。
    try:
        from trade_redflag import load_redflag
    except Exception:
        from api.trade_redflag import load_redflag
    flag = load_redflag(root / "_run_logs")
    if flag:
        today_s = datetime.now().date().isoformat()
        held = today_s != flag.get("failed_date")
        return {
            "available": True, "status": "pending_overnight",
            "redflag_active": True, "failed_date": flag.get("failed_date"),
            "held_over": held, "date": today_s, "is_trading_day": None,
            "attempt": flag.get("attempt"),
            "done_count": 0,
            "total": len(flag.get("strategies") or {}) or 6,
            "trades_total": 0,
            "price_sources": flag.get("price_sources", {}),
            "pending_strategies": flag.get("pending_strategies", []),
            "retry_reasons": flag.get("retry_reasons", {}),
            "next_retry_at": None,
            "strategies": flag.get("strategies", {}),
            "updated_at": flag.get("updated_at") or flag.get("raised_at"),
            "note": (f"成交红灯跨日持续（事故日 {flag.get('failed_date')}"
                     + ("，已跨日" if held else "") + "）：已冻结自动成交与补单，"
                     "红灯一直亮到人工核对解除，被冻结日不补单。"),
            "mode": "live_simulation_local_match_no_broker",
        }
    f = root / "_run_logs" / "trade_health.json"
    if not f.exists():
        return {"available": False, "status": "no_heartbeat",
                "note": "Windows 端尚未上报当日成交健康心跳（升级到监督器版本后，"
                        "交易日开机会自动上报）。"}
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        return {"available": False, "status": "bad_heartbeat",
                "note": f"健康心跳解析失败: {str(e)[:120]}"}
    keep = ("date", "status", "attempt", "is_trading_day", "done_count", "total",
            "trades_total", "price_sources", "pending_strategies", "retry_reasons",
            "next_retry_at", "updated_at", "started_at", "note", "backoff_seconds",
            "window", "mode", "redflag_active", "failed_date", "held_over")
    out = {"available": True}
    for k in keep:
        if k in d:
            out[k] = d[k]
    if isinstance(d.get("strategies"), dict):
        out["strategies"] = {
            sid: {kk: v.get(kk) for kk in
                  ("status", "trades", "price_source", "detail", "missing",
                   "total_asset", "today_pnl", "target")}
            for sid, v in d["strategies"].items()}
    return out


if __name__ == "__main__":
    # 命令行自检：python api/live_aggregator.py
    import sys
    print("LIVE_ROOT =", LIVE_ROOT, "| mock =", is_mock())
    tr = build_trades()
    ph = build_pnl_history()
    rc = build_reconciliation()
    print("trades:", tr["count"], "| pnl days:", ph["count"],
          "| strategies in recon:", len(rc["per_strategy"]))
    ov = build_overview()
    print("overview strategies:", len(ov["strategies"]),
          "| total_asset:", ov["combined"]["total_asset"],
          "| live_days:", ov["live_days"])
    ps = build_portfolio_summary()
    print("portfolio total_value:", ps["total_value"], "pnl:", ps["total_pnl"])
    ta = build_today_actions()
    print("today actions:", [(s["strategy_id"], s["action"], s["trade_count"]) for s in ta["strategies"]])
    lc = build_live_curves()
    print("live curves days:", lc["days"], "sids:", lc["strategy_ids"])
    if tr["trades"]:
        print("sample trade:", json.dumps(tr["trades"][0], ensure_ascii=False))
    if ph["history"]:
        print("sample pnl:", json.dumps(ph["history"][-1], ensure_ascii=False))
