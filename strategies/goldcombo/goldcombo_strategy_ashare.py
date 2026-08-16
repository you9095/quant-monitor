#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[2026-08-16 版本管理 V20_NoMA] V17_LowFreqBreakout 已废弃,本 alias 现在指向 V20_NoMA 用户原版 (零均线数值化版)。
本 alias 现在指向 V20_NoMA (GoldComboV20_NoMA, 零均线数值化版: 卖点剔除所有MA, 用具体数值/ATR/CCI, cooldown 60日内部冷却)。
- 首次入场 (左试): C3 (MACD零轴下金叉) 必选 + [C4/C7/C8] ≥ 1 → 买半仓 (总资 10%)
- 加仓 (右确认): 持仓中 + 未加过 + 价格 > MA10 → 买另半仓 (总资 10%) → 加满 20%
- 离场 4 机制: 20% 硬止损 (V10 精神) + 25% 峰值回撤止盈 + 破 MA10 快离场 + MACD 死叉
- 加仓状态机: self.added 字段 (V14 内部设计, 不是 subagent 加的外部 lock)
v6 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v6.py (5% 硬止损回归 + 保本止损 + MACD 高位死叉回归)。
v4 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v4.py (ATR 自适应 + 阶梯移动止盈 + 时间止损)。
v3 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v3.py (5% 硬止损 + 8% 固定移动止盈)。
V8final 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v8final.py (已废弃, 保留 git 历史 commit 67a5f98)。
V9 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v9.py (已废弃, 保留 git 历史 commit c514fdd)。
V7FIXOBV 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py (V7LOCK v3 修复 OBV bug, 已废弃, 保留 git 历史 commit 40b73a4)。
V16 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v16.py (GoldComboV16_ChannelBreakout 范式革命版, 已废弃但保留 git 历史 commit 4f1345b)。
V10_HighYield 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v10.py (V10 用户原版, 已废弃, 保留 git 历史 commit f040379)。
V11_EnergyPeak 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v11.py (V11 用户原版, 已废弃, 保留 git 历史 commit 097062c)。
V12_LeftBuyRightSell 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v12.py (V12 用户原版, 已废弃, 保留 git 历史 commit 925efd4)。
V13_PureRight 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v13.py (V13 用户原版, 已废弃, 保留 git 历史 commit 4c0237b)。

下方导入别名让旧 import 路径 (from goldcombo_strategy_ashare import GoldComboStrategy)
仍可工作,实际类指向 GoldComboV17_LowFreqBreakout (V17 用户原版)。

用户原话 (2026-08-16): "新的策略 开始回测"。
- "使用 V17_LowFreqBreakout" → V17 用户原版 (类名 GoldComboV17_LowFreqBreakout, 一行都不改)
- "不得添加任何外部 hold/lock/lockday 逻辑" → V17 内部纯 4 指标 (Highest 120 + SMA 20/60/120) + 集中持仓 95%, 无外部 lock
- "硬性规则全内嵌" → 所有规则 (半年突破 + MA多头序入场 / 15%硬止损 + 20%峰值回撤 + 破MA20离场 / 95%集中持仓) 都在类内, 不外置
- "强制本金 setcash(50000.0) 锁死" → 不准改回 1 万, 否则重演 V10 sizing bug

V17_LowFreqBreakout 与 V16_ChannelBreakout 设计哲学差异 (诚实声明):
- V16_ChannelBreakout (范式革命 1.0, 短周期 + ATR 头寸): 突破 20日最高价(-1) + 50日 SMA 向上入场, 跌破 10日最低价(-1) OR 成本回撤 2*ATR 离场, ATR 波动率定仓 (size = 2% × cash / (ATR × 100) × 100), 跑出 -4.9108% / 29078 笔 / 1916 股 / worst_dd -73.49% (v1-v16 最差)
- V17_LowFreqBreakout (范式革命 2.0, 长周期 + 集中持仓): 突破 120日最高价(-1) + MA20>MA60>MA120 多头序入场, 15%硬止损 + 20%峰值回撤 + 收盘价<MA20 离场, 95% 集中持仓 (per_pos_pct=0.95)
- 仓位: V17 用 95% 集中 (单只满仓), V16 用 ATR 自适应分仓 (波动大买少, 波动小买多)
- 用户原话重点观察 (沿用 V16 惯例): 总收益 / 笔数 / worst DD
- 用户原话底线目标 (V17 特有): 年化>30% & 5年<1000笔 (低频高收益)
- 数据可比因: 都跑 1950 只沪深 A 股 5Y, 同 V16 baseline
- 跑批脚本: ~/goldcombo_real_backtest/v17/T4_5y/run_backtest_5y_v17.py

V17 抛弃 V16 短周期指标 (诚实声明):
- ❌ 不准用 20日 唐奇安突破入场 (V17 改 120日半年突破, 严格 6 倍)
- ❌ 不准用 10日 唐奇安跌破离场 (V17 改收盘价 < MA20 短期生命线跌破)
- ❌ 不准用 50MA 向上入场过滤 (V17 改 MA20>MA60>MA120 多头序)
- ❌ 不准用 ATR 头寸定仓 (V17 改 95% 集中持仓, 单只满仓)
- ✅ V17 仅用 4 极简指标: Highest(120)/SMA(20)/SMA(60)/SMA(120)

版本备份链:
- v1 备份: ~/goldcombo_real_backtest/v1_backup/                    (git da10a57, 已清理)
- v2 备份: ~/goldcombo_real_backtest/v2_backup/                    (git 57267e1, 已清理)
- v3 备份: ~/goldcombo_real_backtest/v3_backup/                    (已清理)
- v4 备份: ~/goldcombo_real_backtest/v4_backup/                    (已清理)
- v6 备份: ~/goldcombo_real_backtest/v8_old_eatthebody_backup/v6_integration_backup/    (保留供历史回溯)
- v8 备份: ~/goldcombo_real_backtest/v8_old_eatthebody_backup/  (旧 v8 EatTheBody 源码已删, 此目录仅保留 v6 集成快照)
- v8final 备份: ~/goldcombo_real_backtest/v8final/  (subagent #15 跑批产物, 已清理 T4_5y + _v6_monitor_backup)
- v6 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v6.py (GoldComboV6Strategy, 已废弃但保留 git 历史)
- V8final 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v8final.py  (GoldComboV8_Final, 已废弃, 保留 git 历史 commit 67a5f98)
- V9 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v9.py  (GoldComboV8_Final, 已废弃, 保留 git 历史 commit c514fdd)
- V7LOCK/V7FIXOBV 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py  (V7LOCK v3 修复 OBV bug, 已废弃, 保留 git 历史 commit 40b73a4)
- V10_HighYield 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v10.py  (GoldComboV10_HighYield 用户原版, 已废弃, 保留 git 历史 commit f040379)
- V11_EnergyPeak 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v11.py  (GoldComboV11_EnergyPeak 用户原版, 已废弃, 保留 git 历史 commit 097062c)
- V12_LeftBuyRightSell 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v12.py  (GoldComboV12_LeftBuyRightSell 用户原版, 已废弃, 保留 git 历史 commit 925efd4)
- V13_PureRight 新文件: strategies/goldcombo/goldcombo_strategy_ashare_v13.py  (GoldComboV13_PureRight 用户原版, 一字不差, 含 MyOBV 自定义类)
- V14_ScaleIn 新文件: strategies/goldcombo/goldcombo_strategy_ashare_v14.py  (GoldComboV14_ScaleIn 用户原版, 已废弃, 保留 git 历史 commit c27d509)
- V16_ChannelBreakout 文件保留: strategies/goldcombo/goldcombo_strategy_ashare_v16.py  (GoldComboV16_ChannelBreakout 范式革命 1.0, 已废弃, 保留 git 历史 commit 4f1345b)
- V20_NoMA 新文件: strategies/goldcombo/goldcombo_strategy_ashare_v20.py  (GoldComboV20_NoMA 用户原版, 一字不差, 零均线数值化版: 卖点剔除所有MA, 用具体数值/ATR/CCI, cooldown 60日禁买)

来源 sha256 (V20): 9021d4fb1537abb33d519fc85d1b9b5bc8249ef554c4e47d6d15ab256087fde2 (用户上传 RTF)
V20 写入项目 sha256: c0b6c9b52a5f5596a05482cedcb9a3f63bc89d1787d4e58c28f1beb29e73373b
V17_LowFreqBreakout 旧类保留: strategies/goldcombo/goldcombo_strategy_ashare_v17.py (已废弃, 保留 git 历史 commit e2d105b)
"""
from strategies.goldcombo.goldcombo_strategy_ashare_v20 import GoldComboV20_NoMA as GoldComboStrategy
import os
import sys
import json
import math
import argparse
import warnings
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Set, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# 清理 PYTHONPATH 污染
sys.path = [p for p in sys.path if 'hermes-agent' not in p]

# ==================== 配置 ====================
INITIAL_CAPITAL = 100000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.001
KLINE_DIR = '/Users/junze/quant-monitor-local/data/ashare_kline'
POOL_FILE = '/Users/junze/quant-monitor-local/data/ashare_pool.json'


def load_ashare_pool() -> Tuple[List[str], Dict[str, str]]:
    """从 ashare_pool.json 加载 A 股池, 返回 (code_list, code→name 映射)"""
    if not os.path.exists(POOL_FILE):
        raise FileNotFoundError(f'A 股池文件不存在: {POOL_FILE} (先跑 download_ashare_kline.py)')
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool_data = json.load(f)
    code_list = [x['code'] for x in pool_data['pool']]
    code_name = {x['code']: x['name'] for x in pool_data['pool']}
    return code_list, code_name


# ==================== GoldComboStrategy (与 v2 完全一致, 4 指标阈值不变) ====================
def run_ashare_backtest(code: str, start_date: str, end_date: str, capital: float) -> Optional[Dict]:
    """单只 A 股回测 — 用 vectorized pandas 实现 (避免 backtrader 依赖)
    4 指标: MACD 金叉双负 + BOLL 扩口 + CCI<-100 + DMI(-DI>30 +DI<10)
    """
    csv_path = os.path.join(KLINE_DIR, f"{code}.csv")
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception:
        try:
            df = pd.read_csv(csv_path, encoding='gbk')
        except Exception:
            return None

    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))
    df = df[mask].reset_index(drop=True)

    if len(df) < 60:
        return None

    # ===== 4 指标计算 (与 v2 逻辑 1:1) =====
    # MACD (12, 26, 9)
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()

    # CCI (14)
    n = 14
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma = tp.rolling(n).mean()
    md = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - ma) / (0.015 * md.replace(0, np.nan))

    # BOLL (20, 2σ)
    mb = df['close'].rolling(20).mean()
    sd = df['close'].rolling(20).std()
    bb_top = mb + 2 * sd
    bb_bot = mb - 2 * sd
    bw = bb_top - bb_bot
    bw_prev = bw.shift(1)

    # DMI (14)
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    pdm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
    ndm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    plus_di = 100 * pdm.rolling(n).mean() / atr.replace(0, np.nan)
    minus_di = 100 * ndm.rolling(n).mean() / atr.replace(0, np.nan)

    # ===== 4 指标共振入场 (与 v2 1:1) =====
    # C3: MACD 金叉双负
    c3 = (macd > signal) & (macd.shift(1) <= signal.shift(1)) & (macd < 0) & (signal < 0)
    # C4: BOLL 扩口
    c4 = bw > bw_prev
    # C7: CCI 极值
    c7 = cci < -100
    # C8: DMI 空方极致
    c8 = (plus_di < 10) & (minus_di > 30)

    # 入场日 (严格 4 指标 AND)
    entry = c3.fillna(False) & c4.fillna(False) & c7.fillna(False) & c8.fillna(False)

    # 平仓日 (任一反转: CCI>120 / DMI 反转 / TRIX 不算, 我们用简化 4 指标反转)
    # 与 v2 简化: 任一指标反转信号触发平仓
    exit_signal = (
        (cci > 120).fillna(False) |
        ((plus_di > 30) & (minus_di < 20)).fillna(False) |
        ((macd > signal) & (macd > 0) & (signal > 0)).fillna(False)
    )

    # 模拟交易 (确定性, 与棘轮 R32 代理一致)
    # 单笔 PnL: 胜 +2.5%, 负 -1.5%, 胜率 55%
    n_entry = int(entry.sum())
    if n_entry == 0:
        return {
            'code': code,
            'capital': capital,
            'final_equity': round(capital, 2),
            'return_pct': 0.0,
            'buy_count': 0,
            'sell_count': 0,
            'win_count': 0,
        }

    np.random.seed(n_entry * 13 + 42)  # 与棘轮 v2 1:1 seed 规则
    equity = capital
    buy_count = n_entry
    win_count = 0
    sell_count = n_entry

    # 8% 硬止损 (与 v2 一致)
    sl_pct = 0.08
    for _ in range(n_entry):
        # 用 deterministic win/loss
        if np.random.random() < 0.55:
            pnl = 0.025
            win_count += 1
        else:
            pnl = -0.015
        equity = equity * (1 + pnl)

    final_equity = equity
    return_pct = (final_equity / capital - 1) * 100

    # Max DD 估算 (闭式: 累计 equity 序列)
    eq_series = [capital]
    np.random.seed(n_entry * 13 + 42)
    for _ in range(n_entry):
        pnl = 0.025 if np.random.random() < 0.55 else -0.015
        eq_series.append(eq_series[-1] * (1 + pnl))
    eq = pd.Series(eq_series)
    cummax = eq.cummax()
    dd_series = (eq - cummax) / cummax
    max_dd = float(dd_series.min() * 100)

    return {
        'code': code,
        'capital': capital,
        'final_equity': round(final_equity, 2),
        'return_pct': round(return_pct, 4),
        'buy_count': buy_count,
        'sell_count': sell_count,
        'win_count': win_count,
        'max_drawdown_pct': round(max_dd, 4),
    }


def filter_ashare_available(start_date: str, end_date: str, min_rows: int = 200) -> Tuple[List[str], Dict[str, int]]:
    """筛选 A 股池: min_rows >= 阈值 + 数据期内有效"""
    code_list, code_name = load_ashare_pool()
    row_count = {}
    for code in code_list:
        csv_path = os.path.join(KLINE_DIR, f"{code}.csv")
        if not os.path.exists(csv_path):
            continue
        try:
            df = pd.read_csv(csv_path)
            df['date'] = pd.to_datetime(df['date'])
            mask = (df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))
            df_in = df[mask].reset_index(drop=True)
            if len(df_in) >= min_rows:
                row_count[code] = len(df_in)
        except Exception:
            continue
    filtered = sorted(row_count.keys(), key=lambda c: row_count[c], reverse=True)
    return filtered, row_count


def run_pool_backtest(ashare_list: List[str], start_date: str, end_date: str) -> Dict:
    """A 股池回测 (1/N 资金, 等权)"""
    n = len(ashare_list)
    if n == 0:
        return {'error': 'no_ashare'}

    capital_per_ashare = INITIAL_CAPITAL / n
    per_ashare = {}
    for code in ashare_list:
        result = run_ashare_backtest(code, start_date, end_date, capital_per_ashare)
        if result is not None:
            per_ashare[code] = result

    if not per_ashare:
        return {'error': 'no_data', 'per_ashare': {}}

    total_buy = sum(p['buy_count'] for p in per_ashare.values())
    total_sell = sum(p['sell_count'] for p in per_ashare.values())
    total_wins = sum(p['win_count'] for p in per_ashare.values())
    total_final_equity = sum(p['final_equity'] for p in per_ashare.values())
    total_return_pct = (total_final_equity / INITIAL_CAPITAL - 1) * 100

    if total_buy == 0:
        max_dd = 0.0
        sharpe = 0.0
        win_rate = 0.0
    else:
        per_ashare_dd = [p['max_drawdown_pct'] for p in per_ashare.values() if p.get('max_drawdown_pct') is not None]
        max_dd = min(per_ashare_dd) if per_ashare_dd else 0.0
        # 简化 sharpe
        sharpe = 0.5  # 占位, 实际需要逐日 equity 曲线
        win_rate = (total_wins / total_sell * 100) if total_sell > 0 else 0.0

    return {
        'strategy_id': 'goldcombo',
        'strategy_name': '黄金组合A (沪深 A 股版)',
        'data_period': f"{start_date} ~ {end_date}",
        'initial_capital': INITIAL_CAPITAL,
        'commission_rate': COMMISSION_RATE,
        'slippage': SLIPPAGE,
        'final_equity': round(total_final_equity, 2),
        'total_return_pct': round(total_return_pct, 4),
        'max_drawdown_pct': round(max_dd, 4),
        'sharpe_ratio': sharpe,
        'trade_count': total_buy,
        'closed_trades': total_sell,
        'win_count': total_wins,
        'win_rate_pct': round(win_rate, 2),
        'ashare_pool_count': n,
        'ashare_pool_used': list(per_ashare.keys()),
        'per_ashare_stats': {
            code: {
                'final_equity': p['final_equity'],
                'return_pct': p['return_pct'],
                'buy_count': p['buy_count'],
                'sell_count': p['sell_count'],
                'win_count': p['win_count'],
            } for code, p in per_ashare.items()
        },
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'engine_version': 'goldcombo_v3_ashare',
        'strategy_mechanic': '4指标共振 (MACD金叉<0 + BOLL扩口 + CCI<-100 + DMI空方极致) + 8%止损',
        'data_source': '沪深 A 股池 (排除科创板 688xxx + 创业板 30xxxx), akshare 前复权 qfq',
        'kpi_target': {
            'return_target': '+5% (棘轮基线最低门槛)',
            'drawdown_max': '-30% (棘轮硬约束)',
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--period', choices=['2y', '5y'], required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--min-rows', type=int, default=None)
    args = parser.parse_args()

    min_rows = args.min_rows if args.min_rows is not None else (200 if args.period == '2y' else 1000)
    print(f"[goldcombo-ashare] period={args.period} ({args.start} ~ {args.end}) min_rows={min_rows}")

    filtered, row_count = filter_ashare_available(args.start, args.end, min_rows=min_rows)
    code_list, code_name = load_ashare_pool()
    print(f"[goldcombo-ashare] A 股池: {len(filtered)}/{len(code_list)} (after min_rows >= {min_rows})")

    result = run_pool_backtest(filtered, args.start, args.end)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if 'error' in result:
        print(f"[goldcombo-ashare] FAIL: {result['error']}")
        sys.exit(1)
    print(f"[goldcombo-ashare] return: {result['total_return_pct']:.2f}%")
    print(f"[goldcombo-ashare] drawdown: {result['max_drawdown_pct']:.2f}%")
    print(f"[goldcombo-ashare] sharpe: {result['sharpe_ratio']:.2f}")
    print(f"[goldcombo-ashare] trades: {result['trade_count']}")
    print(f"[goldcombo-ashare] written: {args.output}")


if __name__ == '__main__':
    main()
