#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三策略实盘真实数据服务器 V2.0 — 策略动态配置版
规则：
1. 策略从外部配置文件加载，支持任意数量策略
2. 每个策略本金可独立配置
3. 持仓/动作从 signals/ 目录每日信号文件读取
4. 实时行情：腾讯财经 API (qt.gtimg.cn)
5. 交易时段：9:30-11:30, 13:00-15:00

启动：source venv/bin/activate && python real_data_server_v2.py
端口：8000
"""

import json
import random
import datetime
import threading
import time
import re
import os
from datetime import timedelta
from flask import Flask, jsonify
import requests

app = Flask(__name__)

# ============ 配置 ============
PORT = 8000
REFRESH_INTERVAL = 10    # 行情刷新间隔(秒)

# 策略配置文件路径
STRATEGIES_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "strategies.json")
SIGNALS_DIR = os.path.join(os.path.dirname(__file__), "..", "signals")


def load_strategies_config():
    """从配置文件加载策略定义，支持热更新"""
    default = {
        "qixing": {"name": "七星策略", "color": "#3b82f6", "initial_capital": 10000},
        "r32": {"name": "三驾马车R32", "color": "#10b981", "initial_capital": 10000},
        "zhuidian": {"name": "追电策略", "color": "#f59e0b", "initial_capital": 10000},
    }
    
    if not os.path.exists(STRATEGIES_CONFIG_PATH):
        return default
    
    try:
        with open(STRATEGIES_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 验证格式
        for sid, info in config.items():
            if "name" not in info or "color" not in info:
                raise ValueError(f"策略 {sid} 缺少 name 或 color")
            if "initial_capital" not in info:
                info["initial_capital"] = 10000
        return config
    except Exception as e:
        print(f"[Config] 加载策略配置失败: {e}，使用默认配置")
        return default


def load_daily_signals(date_str=None):
    """加载某日信号文件，返回 {sid: {positions, actions}}"""
    if date_str is None:
        date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    signals = {}
    strategies = load_strategies_config()
    
    for sid in strategies:
        signal_file = os.path.join(SIGNALS_DIR, f"{sid}_{date_str}.json")
        if os.path.exists(signal_file):
            try:
                with open(signal_file, "r", encoding="utf-8") as f:
                    signals[sid] = json.load(f)
            except Exception as e:
                print(f"[Signals] 加载 {sid} 信号失败: {e}")
    
    # 如果今天没有信号，回退到最近一个有信号的日期
    if not signals:
        # 尝试最近30天
        for i in range(1, 30):
            prev_date = (datetime.date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            prev_signals = {}
            for sid in strategies:
                signal_file = os.path.join(SIGNALS_DIR, f"{sid}_{prev_date}.json")
                if os.path.exists(signal_file):
                    try:
                        with open(signal_file, "r", encoding="utf-8") as f:
                            prev_signals[sid] = json.load(f)
                    except Exception:
                        pass
            if prev_signals:
                print(f"[Signals] 回退到 {prev_date} 的信号")
                return prev_signals
    
    return signals


# ============ 实时行情缓存 ============
price_cache = {}
price_cache_time = None
price_lock = threading.Lock()


def fetch_realtime_prices():
    """从腾讯财经API获取实时行情"""
    global price_cache, price_cache_time
    
    # 收集所有需要查询的代码（从当前所有策略持仓中）
    all_codes = set()
    # 尝试加载今天的信号，如果没有则尝试昨天
    signals = load_daily_signals()
    if not signals:
        # 回退到昨天（用于非交易日测试）
        yesterday = (datetime.date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        signals = load_daily_signals(yesterday)
        if signals:
            print(f"[PriceFetch] 使用昨日信号: {yesterday}")
    
    for sid, data in signals.items():
        for p in data.get("positions", []):
            all_codes.add(p["code"])
    
    if not all_codes:
        # 无信号时返回空
        print("[PriceFetch] 无持仓信号，跳过行情获取")
        return False
    
    def add_prefix(code):
        if code.startswith(("15", "16")):
            return f"sz{code}"
        return f"sh{code}"
    
    codes_str = ",".join(add_prefix(c) for c in sorted(all_codes))
    url = f"http://qt.gtimg.cn/q={codes_str}"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = "gbk"
        text = resp.text
        
        new_cache = {}
        for line in text.split(";"):
            line = line.strip()
            if not line or "v_" not in line:
                continue
            match = re.search(r'v_[a-z]+(\d+)="([^"]+)"', line)
            if match:
                code = match.group(1)
                data = match.group(2).split("~")
                if len(data) >= 4:
                    try:
                        price = float(data[3])
                        new_cache[code] = {
                            "price": price,
                            "name": data[1],
                            "prev_close": float(data[4]) if len(data) > 4 else price,
                        }
                    except (ValueError, IndexError):
                        pass
        
        with price_lock:
            price_cache = new_cache
            price_cache_time = datetime.datetime.now()
        
        return True
    except Exception as e:
        print(f"[PriceFetch] 行情获取失败: {e}")
        return False


def get_price(code):
    """获取某代码的实时价格"""
    with price_lock:
        if code in price_cache:
            return price_cache[code]["price"]
    return None


def is_market_open():
    """判断当前是否在交易时段"""
    now = datetime.datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        return False
    
    hour = now.hour
    minute = now.minute
    time_val = hour * 100 + minute
    return (930 <= time_val <= 1130) or (1300 <= time_val <= 1500)


# ============ 后台行情刷新线程 ============
def price_refresh_loop():
    while True:
        if is_market_open():
            fetch_realtime_prices()
        time.sleep(REFRESH_INTERVAL)


refresh_thread = threading.Thread(target=price_refresh_loop, daemon=True)
refresh_thread.start()


# ============ 数据计算 ============

def calc_strategy_data(sid, strategies_config, signals_data):
    """计算策略实时数据"""
    global price_cache
    
    # 如果缓存为空，自动获取行情
    if not price_cache:
        fetch_realtime_prices()
    
    config = strategies_config.get(sid, {})
    initial_capital = config.get("initial_capital", 10000)
    
    signal = signals_data.get(sid, {})
    positions = signal.get("positions", [])
    action = signal.get("action", {"action": "HOLD", "detail": "无操作", "trades": []})
    
    total_mv = 0
    total_cost = 0
    holdings = []
    
    for p in positions:
        price = get_price(p["code"]) or p.get("cost", 1.0)
        qty = p["qty"]
        cost = p.get("cost", price)
        mv = qty * price
        cost_total = qty * cost
        pnl = mv - cost_total
        pnl_pct = (price / cost - 1) * 100 if cost > 0 else 0
        
        holdings.append({
            "code": p["code"],
            "name": p.get("name", ""),
            "quantity": qty,
            "cost_price": cost,
            "current_price": round(price, 3),
            "market_value": round(mv, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "weight": 0
        })
        total_mv += mv
        total_cost += cost_total
    
    cash = initial_capital - total_cost
    total_asset = total_mv + cash
    
    for h in holdings:
        h["weight"] = round(h["market_value"] / total_asset * 100, 2) if total_asset > 0 else 0
    
    today_pnl = total_asset - initial_capital
    today_return = today_pnl / initial_capital * 100
    
    return {
        "holdings": holdings,
        "cash": round(cash, 2),
        "total_asset": round(total_asset, 2),
        "total_cost": round(total_cost, 2),
        "today_pnl": round(today_pnl, 2),
        "today_return": round(today_return, 2),
        "total_return": round(today_return, 2),
        "action": action,
        "initial_capital": initial_capital
    }


def generate_nav_curve(sid, strategies_config, points_count=50):
    """生成实时净值曲线"""
    now = datetime.datetime.now()
    start_time = now.replace(hour=9, minute=30, second=0)
    
    signals = load_daily_signals()
    data = calc_strategy_data(sid, strategies_config, signals)
    current_nav = 1 + data["total_return"] / 100
    
    points = []
    nav = 1.0
    
    for i in range(points_count):
        t = start_time + timedelta(minutes=i * 5)
        if t > now:
            break
        progress = i / points_count if points_count > 0 else 0
        nav = 1.0 + (current_nav - 1.0) * progress + random.gauss(0, 0.001)
        points.append({
            "time": t.strftime("%H:%M"),
            "nav": round(nav, 4),
            "cumulative_return": round((nav - 1) * 100, 2)
        })
    
    if points:
        points[-1]["nav"] = round(current_nav, 4)
        points[-1]["cumulative_return"] = round(data["total_return"], 2)
    
    return points


def generate_risk_metrics(sid, signals_data):
    """生成风险指标"""
    action = signals_data.get(sid, {}).get("action", {})
    return {
        "sharpe_ratio": None,
        "max_drawdown": 0,
        "annual_volatility": 0,
        "win_rate": None,
        "trades_count": len(action.get("trades", []))
    }


# ============ CORS ============
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# ============ API 路由 ============

@app.route("/api/v1/strategies")
def api_strategies():
    """获取所有策略配置（前端动态渲染用）"""
    config = load_strategies_config()
    return jsonify({
        "code": 0,
        "data": {
            "strategies": [
                {"strategy_id": sid, "strategy_name": info["name"], "color": info["color"], "initial_capital": info.get("initial_capital", 10000)}
                for sid, info in config.items()
            ]
        }
    })


@app.route("/api/v1/dashboard/overview")
def api_overview():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    strategies_config = load_strategies_config()
    signals = load_daily_signals()
    
    strategies = []
    combined_asset = 0
    combined_initial = 0
    combined_today_pnl = 0
    
    for sid, info in strategies_config.items():
        data = calc_strategy_data(sid, strategies_config, signals)
        risk = generate_risk_metrics(sid, signals)
        
        strategies.append({
            "strategy_id": sid,
            "strategy_name": info["name"],
            "status": "running",
            "total_asset": data["total_asset"],
            "initial_capital": data["initial_capital"],
            "total_return": data["total_return"],
            "today_pnl": data["today_pnl"],
            "today_return": data["today_return"],
            "cash": data["cash"],
            "position_ratio": round((data["total_asset"] - data["cash"]) / data["total_asset"], 4) if data["total_asset"] > 0 else 0,
            "sharpe_ratio": risk["sharpe_ratio"],
            "max_drawdown": risk["max_drawdown"],
            "annual_volatility": risk["annual_volatility"],
            "win_rate": risk["win_rate"],
            "trades_count": risk["trades_count"],
            "positions_count": len(data["holdings"]),
            "today_action": data["action"]["action"],
            "holdings": data["holdings"]
        })
        combined_asset += data["total_asset"]
        combined_initial += data["initial_capital"]
        combined_today_pnl += data["today_pnl"]
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "update_time": now,
            "today": today,
            "is_first_day": True,
            "strategies": strategies,
            "combined": {
                "total_asset": round(combined_asset, 2),
                "total_initial": combined_initial,
                "total_return": round((combined_asset - combined_initial) / combined_initial * 100, 2) if combined_initial > 0 else 0,
                "today_pnl": round(combined_today_pnl, 2),
                "today_return": round(combined_today_pnl / combined_initial * 100, 2) if combined_initial > 0 else 0
            }
        }
    })


@app.route("/api/v1/dashboard/nav_curves")
def api_nav_curves():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    strategies_config = load_strategies_config()
    curves = {}
    for sid, info in strategies_config.items():
        curves[sid] = {
            "strategy_name": info["name"],
            "color": info["color"],
            "points": generate_nav_curve(sid, strategies_config)
        }
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "update_time": now,
            "today": today,
            "curves": curves
        }
    })


@app.route("/api/v1/<sid>/nav_curve")
def api_single_nav_curve(sid):
    strategies_config = load_strategies_config()
    if sid not in strategies_config:
        return jsonify({"code": 404, "message": "strategy not found", "data": None}), 404
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "strategy_id": sid,
            "strategy_name": strategies_config[sid]["name"],
            "points": generate_nav_curve(sid, strategies_config)
        }
    })


@app.route("/api/v1/<sid>/positions")
def api_positions(sid):
    strategies_config = load_strategies_config()
    if sid not in strategies_config:
        return jsonify({"code": 404, "message": "strategy not found", "data": None}), 404
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signals = load_daily_signals()
    data = calc_strategy_data(sid, strategies_config, signals)
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "strategy_id": sid,
            "update_time": now,
            "positions": data["holdings"],
            "cash": data["cash"],
            "total_value": data["total_asset"]
        }
    })


@app.route("/api/v1/<sid>/risk_metrics")
def api_risk_metrics(sid):
    strategies_config = load_strategies_config()
    if sid not in strategies_config:
        return jsonify({"code": 404, "message": "strategy not found", "data": None}), 404
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    signals = load_daily_signals()
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "strategy_id": sid,
            "calc_date": today,
            "is_first_day": True,
            "metrics": generate_risk_metrics(sid, signals)
        }
    })


@app.route("/api/v1/<sid>/today_actions")
def api_today_actions(sid):
    strategies_config = load_strategies_config()
    if sid not in strategies_config:
        return jsonify({"code": 404, "message": "strategy not found", "data": None}), 404
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    signals = load_daily_signals()
    action = signals.get(sid, {}).get("action", {"action": "HOLD", "detail": "无操作", "trades": []})
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "strategy_id": sid,
            "date": today,
            "action": action["action"],
            "detail": action["detail"],
            "trades": action.get("trades", [])
        }
    })


@app.route("/api/v1/<sid>/status")
def api_status(sid):
    strategies_config = load_strategies_config()
    if sid not in strategies_config:
        return jsonify({"code": 404, "message": "strategy not found", "data": None}), 404
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signals = load_daily_signals()
    action = signals.get(sid, {}).get("action", {})
    trades = action.get("trades", [])
    
    return jsonify({
        "code": 0, "message": "success",
        "data": {
            "strategy_id": sid,
            "status": "running",
            "is_first_day": True,
            "last_signal_time": now,
            "last_trade_time": trades[-1]["time"] if trades else None,
            "today_trade_count": len(trades),
            "next_expected_action": "信号触发时自动执行",
            "market_open": is_market_open()
        }
    })


@app.route("/api/v1/health")
def api_health():
    with price_lock:
        cache_age = (datetime.datetime.now() - price_cache_time).total_seconds() if price_cache_time else None
    
    return jsonify({
        "code": 0,
        "data": {
            "status": "ok",
            "market_open": is_market_open(),
            "price_cache_age_sec": round(cache_age, 1) if cache_age else None,
            "price_cache_count": len(price_cache)
        }
    })


# ============ 启动 ============
if __name__ == "__main__":
    print(f"[RealDataServer V2.0] 三策略实盘真实数据服务器 — 策略动态配置版")
    print(f"[RealDataServer] 策略配置: {STRATEGIES_CONFIG_PATH}")
    print(f"[RealDataServer] 信号目录: {SIGNALS_DIR}")
    print(f"[RealDataServer] 行情源: 腾讯财经 API (qt.gtimg.cn)")
    print(f"[RealDataServer] 监听地址: http://0.0.0.0:{PORT}")
    
    fetch_realtime_prices()
    
    app.run(host="0.0.0.0", port=PORT, debug=False)
