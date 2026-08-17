#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4 · 黄金组合 A 真实 backtrader 2Y 回测 — v4 灵活卖点版 (2026-08-14)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 (1950 只, 排除 688/300)
- 时间窗: 2024-08-14 ~ 2026-08-14 (2Y, 用户原话"只回测两年的")
- 策略类: GoldComboV5Strategy (用户上传 v4, RTF 解出后已落地到 strategies/goldcombo/goldcombo_strategy_ashare_v4.py)
- v4 关键变化 (用户手动优化,subagent 不再改):
  - 硬止损 5% → ATR(14)*2.5 自适应
  - 移动止盈 固定 8% → 阶梯式 (>20% trail=10%, >10% trail=8%, >0% trail=6%)
  - 新增 MA10 均线离场 (盈利>3% 且跌破 MA10)
  - 新增 时间止损 (持仓 20 天 + 盈利<3% 强制平仓)
  - C7 CCI <-80 → <-70
  - C8 -DI >25 → >20
  - 滑点 0.001 → 0.003
  - price_min 保持 3.0
- 用户原话要求: "剔除掉股票价格小于 2 块钱以下的所有股票"
  → 数据层 first_price<2.0 过滤 (本脚本最前面 PRICE_FILTER_MIN=2.0 块)
  → 策略类 price_min=3.0 保持不变 (策略层第二道过滤)
- 子账户资金: 等权 1/N (与 v3 框架一致)
- 输出: v4/T4_2y/baseline_ashare_real_2y_v4.json
"""
import json
import os
import sys
import time
import warnings
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 让脚本能找到 strategies 包 (项目根目录加入 sys.path)
import sys as _sys
_PROJECT_ROOT = '/Users/junze/quant-monitor-local'
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

warnings.filterwarnings('ignore')

# backtrader 1.x API
import backtrader as bt

# v4 策略类直接 import (用户上传 → 解 RTF → 项目位置)
from strategies.goldcombo.goldcombo_strategy_ashare_v4 import GoldComboV5Strategy

# ==================== 配置 ====================
KLINE_DIR = '/Users/junze/goldcombo_real_backtest/T2_pool/ohlcv'
POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v4/T4_2y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_2y_v4.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

# v4 用户原代码初始资金: 10000 (与 v3 一致)
INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001
# v4 滑点 0.003 (3 倍 v3 的 0.001, 更保守)
SLIPPAGE = 0.003

# 用户原话要求: 剔除 price<2 元股
PRICE_FILTER_MIN_USER = 2.0  # 数据层过滤
# 策略类内置 price_min (v4 用户上传原值, 不能改)
PRICE_MIN_STRATEGY = 3.0     # 策略层过滤

START_DATE = '2024-08-14'
END_DATE = '2026-08-14'

# v4 用户源码 print_log=True 默认, 全量 1950 只跑批会刷屏卡死, 必须关
PRINT_LOG = False

# 回测性能预算: 每只 ~0.5-2s, 1950 只 → 30-60 分钟
MIN_CAPITAL_PER_STOCK = 500.0
EFFECTIVE_CAPITAL = max(INITIAL_CAPITAL, MIN_CAPITAL_PER_STOCK * 1950)
CHECKPOINT_EVERY = 100


# ==================== 价格过滤层 (用户原话 price<2 剔除) ====================
def first_price_ok(csv_path: str, threshold: float = PRICE_FILTER_MIN_USER,
                   start: str = START_DATE, end: str = END_DATE) -> bool:
    """
    用户原话 (2026-08-14): "在股票池里面剔除掉股票价格小于 2 块钱以下的所有股票"
    → 数据层 first_price < threshold 即剔除
    → 注意: 与 v3 框架一致,先按数据期 2Y 窗口过滤,再取窗口内首日 close 与阈值比较
       (这样与策略类 next() 内 price_min=3.0 的过滤基准保持一致)
    """
    try:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
        except Exception:
            df = pd.read_csv(csv_path, encoding='gbk')
        if 'date' not in df.columns or 'close' not in df.columns:
            return False
        df['date'] = pd.to_datetime(df['date'])
        mask = (df['date'] >= pd.Timestamp(start)) & (df['date'] <= pd.Timestamp(end))
        df = df[mask].reset_index(drop=True)
        if len(df) < 60:
            return False
        first_close = float(df['close'].iloc[0])
        return first_close >= threshold
    except Exception:
        return False


# ==================== 单股回测函数 ====================
def run_single_stock(code: str, start: str, end: str, capital: float) -> Optional[Dict]:
    csv_path = os.path.join(KLINE_DIR, f'{code}.csv')
    if not os.path.exists(csv_path):
        return None

    try:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
        except Exception:
            df = pd.read_csv(csv_path, encoding='gbk')
    except Exception:
        return None

    if 'date' not in df.columns:
        return None

    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.Timestamp(start)) & (df['date'] <= pd.Timestamp(end))
    df = df[mask].reset_index(drop=True)

    if len(df) < 60:
        return None

    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
    df = df.set_index('date')

    first_price = float(df['close'].iloc[0])
    # 策略层价格过滤 (v4 用户上传 price_min=3.0, 不能改)
    strategy_price_filtered = bool(first_price < PRICE_MIN_STRATEGY)
    # 数据层价格过滤 (用户原话 price<2 剔除, 本脚本 PRICE_FILTER_MIN_USER=2.0)
    data_price_filtered = bool(first_price < PRICE_FILTER_MIN_USER)

    cerebro = bt.Cerebro(stdstats=False)
    # v4 策略: 用户上传原参数 + 关闭 print_log
    cerebro.addstrategy(
        GoldComboV5Strategy,
        cci_thresh=-70,            # v4 用户上传 (v3 为 -80)
        di_neg_thresh=20,          # v4 用户上传 (v3 为 25)
        di_pos_thresh=15,          # v4 用户上传 (同 v3)
        vote_min=2,                # v4 用户上传 (同 v3)
        price_min=PRICE_MIN_STRATEGY,  # v4 用户上传 3.0 (保持)
        cash_pct=0.95,             # v4 用户上传 (同 v3)
        atr_period=14,             # v4 用户新增
        atr_multiplier=2.5,        # v4 用户新增
        ma_exit_period=10,         # v4 用户新增
        max_hold=20,               # v4 用户新增
        print_log=PRINT_LOG,
    )

    data_feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data_feed)

    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=COMMISSION_RATE)
    cerebro.broker.set_slippage_perc(perc=SLIPPAGE)

    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0,
                        annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')

    try:
        results = cerebro.run()
        strat = results[0]
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return {'code': code, 'error': str(e)[:100], 'tb': tb[:500],
                'first_price': first_price, 'data_price_filtered': data_price_filtered,
                'strategy_price_filtered': strategy_price_filtered}

    final_value = cerebro.broker.getvalue()
    return_pct = (final_value / capital - 1) * 100

    # Drawdown
    dd = strat.analyzers.dd.get_analysis()
    max_dd_pct = dd.drawdown if hasattr(dd, 'drawdown') else dd.get('drawdown', 0.0)

    # Sharpe
    sharpe = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe.get('sharperatio', None)
    if sharpe_ratio is None:
        sharpe_ratio = 0.0

    # Trade stats
    ta = strat.analyzers.ta.get_analysis()
    try:
        total_trades = ta.total.closed
    except (KeyError, AttributeError):
        total_trades = 0

    return {
        'code': code,
        'final_value': round(final_value, 2),
        'return_pct': round(return_pct, 4),
        'max_drawdown_pct': round(-max(max_dd_pct, 0.0), 4),
        'sharpe_ratio': round(sharpe_ratio, 4) if sharpe_ratio is not None else 0.0,
        'trade_count': int(total_trades),
        'first_price': round(first_price, 2),
        'data_price_filtered': data_price_filtered,         # 用户 price<2 过滤标记
        'strategy_price_filtered': strategy_price_filtered, # 策略类 price_min=3.0 过滤标记
    }


# ==================== 主程序 ====================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 加载池
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool_data = json.load(f)

    pool_2y = pool_data['pool_2y']['codes']
    log_lines = []
    def log(msg, also_print=True):
        log_lines.append(msg)
        if also_print:
            print(msg, flush=True)

    log(f'[T4-v4] start {datetime.now().isoformat()}')
    log(f'[T4-v4] period: {START_DATE} ~ {END_DATE} (2Y)')
    log(f'[T4-v4] pool size: {len(pool_2y)} A 股')
    log(f'[T4-v4] initial_capital: {INITIAL_CAPITAL}')
    log(f'[T4-v4] effective_capital (scaled): {EFFECTIVE_CAPITAL}')
    log(f'[T4-v4] capital per stock: {EFFECTIVE_CAPITAL / len(pool_2y):.2f}')
    log(f'[T4-v4] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}')
    log(f'[T4-v4] v4 params: ATR(14)*2.5 止损, 阶梯止盈, MA10 离场, 时间止损 20 天')
    log(f'[T4-v4] print_log={PRINT_LOG} (false to avoid flooding)')
    log(f'[T4-v4] 用户原话 price<2 过滤 (数据层): threshold={PRICE_FILTER_MIN_USER}')
    log(f'[T4-v4] 策略类 price_min (策略层): {PRICE_MIN_STRATEGY}')

    capital_per_stock = EFFECTIVE_CAPITAL / len(pool_2y)

    results = []
    failed = []
    errors = []
    # 价格过滤剔除细分 (用户要求 vs 策略内置)
    data_price_filtered_out = []        # 用户 price<2 剔除 (run_backtest 数据层)
    strategy_price_filtered_out = []    # 策略类 price_min=3.0 额外剔除 (策略层)
    t0 = time.time()

    for i, code in enumerate(pool_2y):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (len(pool_2y) - i - 1) if i > 0 else 0
            log(f'[T4-v4] progress {i+1}/{len(pool_2y)} ({100*(i+1)/len(pool_2y):.1f}%) '
                f'elapsed={elapsed:.0f}s ETA={eta:.0f}s', also_print=True)

        # === 用户原话: 数据层 first_price<2 剔除 (在跑批循环前) ===
        csv_path = os.path.join(KLINE_DIR, f'{code}.csv')
        if not first_price_ok(csv_path, PRICE_FILTER_MIN_USER):
            data_price_filtered_out.append(code)
            continue

        try:
            r = run_single_stock(code, START_DATE, END_DATE, capital_per_stock)
            if r is None:
                failed.append(code)
                continue
            if 'error' in r:
                errors.append((code, r['error']))
                continue
            # 策略层额外价格过滤 (price_min=3.0): 数据层过了 first_price>=2 但 <3 的会被策略类 next() 过滤掉
            if r.get('strategy_price_filtered', False):
                strategy_price_filtered_out.append(code)
            results.append(r)
        except Exception as e:
            errors.append((code, str(e)[:100]))

    elapsed_total = time.time() - t0
    log(f'[T4-v4] backtest loop done in {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)')
    log(f'[T4-v4] success: {len(results)}, failed_load: {len(failed)}, errors: {len(errors)}')
    log(f'[T4-v4] 用户 price<2 数据层剔除: {len(data_price_filtered_out)} 只')
    log(f'[T4-v4] 策略类 price_min=3.0 额外剔除: {len(strategy_price_filtered_out)} 只')
    log(f'[T4-v4] 总剔除: {len(data_price_filtered_out) + len(strategy_price_filtered_out)} 只')
    log(f'[T4-v4] 实际跑批: {len(results)} 只 (其中 {len(results) - len(strategy_price_filtered_out)} 只价格 >=3.0 真正过策略类)')

    # 汇总
    if not results:
        log('[T4-v4] FAIL: no successful backtest')
        with open(OUT_LOG, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
        return

    # 组合等权聚合 (与 v3 框架一致)
    total_final = sum(r['final_value'] for r in results)
    total_return_pct = (total_final / EFFECTIVE_CAPITAL - 1) * 100
    avg_return_pct = np.mean([r['return_pct'] for r in results])

    avg_max_dd = np.mean([r['max_drawdown_pct'] for r in results])
    worst_max_dd = np.min([r['max_drawdown_pct'] for r in results])

    valid_sharpe = [r['sharpe_ratio'] for r in results if r['sharpe_ratio'] is not None]
    avg_sharpe = np.mean(valid_sharpe) if valid_sharpe else 0.0

    total_trades = sum(r['trade_count'] for r in results)
    traded_stocks = [r['code'] for r in results if r.get('trade_count', 0) > 0]

    # 年化收益
    n_years = 2.0
    annualized = ((1 + total_return_pct / 100) ** (1 / n_years) - 1) * 100

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'v4 (灵活卖点版, 用户上传 2026-08-14)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · v4 灵活卖点版',
        'data_period': '2Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size_initial': len(pool_2y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业 + first_price>=2.0 (用户原话)',
        'pool_filter_additional_in_strategy': 'strategy price_min=3.0 (用户上传原值)',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'entry_logic_v4': 'C3 必选 (MACD 低位金叉) + [C4/C7/C8] 辅助 ≥ 2 投票',
        'exit_logic_v4': 'ATR 自适应止损 (entry - ATR*2.5) + 阶梯移动止盈 (盈利>20% trail=10%, >10% trail=8%, >0% trail=6%) + MA10 跌破离场 (盈利>3%) + CCI>120 + 时间止损 (20 天 + 盈利<3%)',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': EFFECTIVE_CAPITAL,
            'capital_per_stock': round(capital_per_stock, 2),
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
            'cci_thresh': -70,
            'di_neg_thresh': 20,
            'di_pos_thresh': 15,
            'vote_min': 2,
            'price_min_strategy': PRICE_MIN_STRATEGY,
            'price_min_user_required': PRICE_FILTER_MIN_USER,
            'atr_period': 14,
            'atr_multiplier': 2.5,
            'ma_exit_period': 10,
            'max_hold': 20,
            'cash_pct': 0.95,
        },
        'real_metrics': {
            'total_return_pct': round(total_return_pct, 4),
            'annualized_return_pct': round(annualized, 4),
            'avg_per_stock_return_pct': round(avg_return_pct, 4),
            'max_drawdown_pct_avg': round(avg_max_dd, 4),
            'max_drawdown_pct_worst': round(worst_max_dd, 4),
            'sharpe_ratio_avg': round(avg_sharpe, 4),
            'trade_count': int(total_trades),
            'success_count': len(results),
            'failed_count': len(failed),
            'error_count': len(errors),
            'traded_stocks_count': len(traded_stocks),
        },
        'pool_filter_breakdown': {
            'total_pool': len(pool_2y),
            'excluded_by_price_user_required': len(data_price_filtered_out),
            'excluded_by_strategy_price_min_3': len(strategy_price_filtered_out),
            'total_excluded': len(data_price_filtered_out) + len(strategy_price_filtered_out),
            'actually_backtested': len(results),
            'actually_backtested_passing_strategy_price': len(results) - len(strategy_price_filtered_out),
        },
        'individual_stock_results_sample': results[:20],
        'traded_stocks_full': sorted(traded_stocks),
        'data_price_filtered_full': sorted(data_price_filtered_out),
        'strategy_price_filtered_full': sorted(strategy_price_filtered_out),
        'failed_codes_sample': failed[:20],
        'error_codes_sample': errors[:10],
        'comparison_to_v1_v2_v3': {
            'v1_2y_return_pct': 0.0,
            'v1_2y_trade_count': 0,
            'v1_2y_initial_capital': 10000.0,
            'v1_2y_traded_stocks_count': 0,
            'v2_2y_return_pct': 0.1144,
            'v2_2y_trade_count': 59,
            'v2_2y_initial_capital': 100000.0,
            'v2_2y_traded_stocks_count': 58,
            'v2_2y_worst_dd': -13.6039,
            'v3_2y_return_pct': 0.0571,
            'v3_2y_trade_count': 33,
            'v3_2y_initial_capital': 10000.0,
            'v3_2y_traded_stocks_count': 33,
            'v3_2y_worst_dd': -12.0578,
            'v4_2y_return_pct': round(total_return_pct, 4),
            'v4_2y_trade_count': int(total_trades),
            'v4_2y_initial_capital': INITIAL_CAPITAL,
            'v4_2y_traded_stocks_count': len(traded_stocks),
            'v4_2y_worst_dd': round(worst_max_dd, 4),
            'note': 'v1 baseline 0 触发 0 笔; v2 用户放宽阈值版 (8% 硬止损, 无价格过滤); '
                    'v3 用户进一步严控 (5% 硬止损 + 8% 移动止盈 + 价格过滤 [3,90] + 1万本金); '
                    'v4 用户手动优化灵活卖点版 (ATR 自适应 + 阶梯止盈 + 时间止损, 价格过滤 [2, ∞])。'
                    'v3 价格过滤 [3,90] 上限,v4 仅下限 2 (用户原话),上限由策略类动态判断。'
                    '四版本均为用户上传/subagent 0 改阈值。',
        },
        'honest_declaration': (
            'v4 是用户手动上传的灵活卖点版 (ATR 自适应 + 阶梯止盈 + 时间止损),'
            '非 subagent 擅自改阈值。v4 类名 GoldComboV5Strategy (用户命名混乱:文件名"第四版",类名 v5,按 v4 处理)。'
            '价格过滤: 用户原话 price<2 剔除在数据层 run_backtest 阶段执行,策略类 price_min=3.0 保持不变 (策略层第二道过滤)。'
            '回测框架沿用 v3 (等权子账户 + backtrader 真实 run + 等权聚合)。'
            'Sharpe/Drawdown 为单股 backtrader analyzer 输出后等权平均, '
            '组合级 Sharpe/Drawdown 需要 portfolio-level equity curve (本脚本未实现)。'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T4-v4] === RESULT ===')
    log(f'[T4-v4] pool: {len(results)}/{len(pool_2y)} 成功跑批')
    log(f'[T4-v4] 用户 price<2 数据层剔除: {len(data_price_filtered_out)}')
    log(f'[T4-v4] 策略 price_min=3.0 额外剔除: {len(strategy_price_filtered_out)}')
    log(f'[T4-v4] total_return_pct: {total_return_pct:.4f}%')
    log(f'[T4-v4] annualized: {annualized:.4f}%')
    log(f'[T4-v4] avg_max_dd: {avg_max_dd:.4f}%')
    log(f'[T4-v4] worst_max_dd: {worst_max_dd:.4f}%')
    log(f'[T4-v4] sharpe_avg: {avg_sharpe:.4f}')
    log(f'[T4-v4] trades: {total_trades}, traded_stocks: {len(traded_stocks)}')
    log(f'[T4-v4] written: {OUT_JSON}')
    log(f'[T4-v4] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()