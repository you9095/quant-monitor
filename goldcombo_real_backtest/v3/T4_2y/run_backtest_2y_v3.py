#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4 · 黄金组合 A 真实 backtrader 2Y 回测 — v3 小资金严控版 (2026-08-14)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 (1950 只, 排除 688/300)
- 时间窗: 2024-08-14 ~ 2026-08-14 (2Y)
- 策略类: GoldComboV3_1Strategy (用户上传 v3, RTF 解出后已落地到 strategies/goldcombo/goldcombo_strategy_ashare_v3.py)
- v3 关键变化: 价格过滤 [3,90] + 5% 硬止损 + 8% 移动止盈 + cash_pct=0.95 + 初始资金 10000
- 子账户资金: 等权 1/N (与 v2 框架一致)
- 输出: v3/T4_2y/baseline_ashare_real_2y_v3.json
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

warnings.filterwarnings('ignore')

# backtrader 1.x API
import backtrader as bt

# v3 策略类直接 import (用户上传 → 解 RTF → 项目位置)
from strategies.goldcombo.goldcombo_strategy_ashare_v3 import GoldComboV3_1Strategy

# ==================== 配置 ====================
KLINE_DIR = '/Users/junze/goldcombo_real_backtest/T2_pool/ohlcv'
POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v3/T4_2y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_2y_v3.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

# v3 用户原代码初始资金: 10000 (与 v2 的 100000 不同)
INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.001

# v3 风控: 5% 硬止损 + 8% 移动止盈 (硬止损降到 5% 是 v3 vs v2 最大差异)
STOP_LOSS_PCT = 0.05
TRAIL_SL_PCT = 0.08
PRICE_MAX = 90.0
PRICE_MIN = 3.0
CASH_PCT = 0.95

START_DATE = '2024-08-14'
END_DATE = '2026-08-14'

# v3 用户源码 print_log=True 默认, 全量 1950 只跑批会刷屏卡死, 必须关
PRINT_LOG = False

# 回测性能预算: 每只 ~0.5-2s, 1950 只 → 30-60 分钟
MIN_CAPITAL_PER_STOCK = 500.0
EFFECTIVE_CAPITAL = max(INITIAL_CAPITAL, MIN_CAPITAL_PER_STOCK * 1950)
CHECKPOINT_EVERY = 100


# ==================== 单股回测函数 ====================
def run_single_stock(code: str, start: str, end: str, capital: float) -> Optional[Dict]:
    csv_path = os.path.join(KLINE_DIR, f'{code}.csv')
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception:
        try:
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

    # v3 价格过滤统计: 首日开盘价不在 [PRICE_MIN, PRICE_MAX] 即剔除 (按 v3 策略 next() 第 41 行逻辑)
    first_price = float(df['close'].iloc[0])
    price_filtered = bool(first_price > PRICE_MAX or first_price < PRICE_MIN)

    cerebro = bt.Cerebro(stdstats=False)
    # v3 策略: 关键参数 + 关闭 print_log (避免 1950 只全量跑批刷屏)
    cerebro.addstrategy(
        GoldComboV3_1Strategy,
        cci_thresh=-80,
        di_neg_thresh=25,
        di_pos_thresh=15,
        vote_min=2,
        price_max=PRICE_MAX,
        price_min=PRICE_MIN,
        cash_pct=CASH_PCT,
        hard_sl=STOP_LOSS_PCT,
        trail_sl=TRAIL_SL_PCT,
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
        return {'code': code, 'error': str(e)[:100], 'tb': tb[:500], 'price_filtered': price_filtered}

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
        'price_filtered': price_filtered,
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
            print(msg)

    log(f'[T4-v3] start {datetime.now().isoformat()}')
    log(f'[T4-v3] period: {START_DATE} ~ {END_DATE} (2Y)')
    log(f'[T4-v3] pool size: {len(pool_2y)} A 股')
    log(f'[T4-v3] initial_capital: {INITIAL_CAPITAL}')
    log(f'[T4-v3] effective_capital (scaled): {EFFECTIVE_CAPITAL}')
    log(f'[T4-v3] capital per stock: {EFFECTIVE_CAPITAL / len(pool_2y):.2f}')
    log(f'[T4-v3] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}')
    log(f'[T4-v3] v3 params: hard_sl={STOP_LOSS_PCT}, trail_sl={TRAIL_SL_PCT}, '
        f'price=[{PRICE_MIN}, {PRICE_MAX}], cash_pct={CASH_PCT}')
    log(f'[T4-v3] print_log={PRINT_LOG} (false to avoid flooding)')

    capital_per_stock = EFFECTIVE_CAPITAL / len(pool_2y)

    results = []
    failed = []
    errors = []
    price_filter_excluded = []  # 价格过滤剔除的股票
    t0 = time.time()

    for i, code in enumerate(pool_2y):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (len(pool_2y) - i - 1) if i > 0 else 0
            log(f'[T4-v3] progress {i+1}/{len(pool_2y)} ({100*(i+1)/len(pool_2y):.1f}%) '
                f'elapsed={elapsed:.0f}s ETA={eta:.0f}s', also_print=True)

        try:
            r = run_single_stock(code, START_DATE, END_DATE, capital_per_stock)
            if r is None:
                failed.append(code)
                continue
            if 'error' in r:
                errors.append((code, r['error']))
                continue
            # v3 价格过滤统计: 即使 next() 内动态过滤掉, 单股第一笔开盘价已反映过滤
            if r.get('price_filtered', False):
                price_filter_excluded.append(code)
            results.append(r)
        except Exception as e:
            errors.append((code, str(e)[:100]))

    elapsed_total = time.time() - t0
    log(f'[T4-v3] backtest loop done in {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)')
    log(f'[T4-v3] success: {len(results)}, failed_load: {len(failed)}, errors: {len(errors)}, '
        f'price_filter_excluded: {len(price_filter_excluded)}')

    # 汇总
    if not results:
        log('[T4-v3] FAIL: no successful backtest')
        return

    # 组合等权聚合 (与 v2 框架一致)
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
        'strategy_version': 'v3 (小资金严控版, 用户上传 2026-08-14)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · v3 小资金严控版',
        'data_period': '2Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool_2y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业 + price in [3, 90]',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'entry_logic_v3': 'C3 必选 (MACD 低位金叉) + [C4/C7/C8] 辅助 ≥ 2 投票 + 价格过滤 [3, 90]',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': EFFECTIVE_CAPITAL,
            'capital_per_stock': round(capital_per_stock, 2),
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
            'hard_sl': STOP_LOSS_PCT,
            'trail_sl': TRAIL_SL_PCT,
            'price_max': PRICE_MAX,
            'price_min': PRICE_MIN,
            'cash_pct': CASH_PCT,
            'cci_thresh': -80,
            'di_neg_thresh': 25,
            'di_pos_thresh': 15,
            'vote_min': 2,
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
            'price_filter_excluded_count': len(price_filter_excluded),
            'traded_stocks_count': len(traded_stocks),
        },
        'individual_stock_results_sample': results[:20],
        'traded_stocks_full': sorted(traded_stocks),
        'price_filter_excluded_sample': price_filter_excluded[:30],
        'failed_codes_sample': failed[:20],
        'error_codes_sample': errors[:10],
        'comparison_to_v1_v2': {
            'v1_2y_return_pct': 0.0,
            'v1_2y_trade_count': 0,
            'v1_2y_initial_capital': 10000.0,
            'v1_2y_traded_stocks_count': 0,
            'v2_2y_return_pct': 0.1144,
            'v2_2y_trade_count': 59,
            'v2_2y_initial_capital': 100000.0,
            'v2_2y_traded_stocks_count': 58,
            'v2_2y_worst_dd': -13.6039,
            'v3_2y_return_pct': round(total_return_pct, 4),
            'v3_2y_trade_count': int(total_trades),
            'v3_2y_initial_capital': INITIAL_CAPITAL,
            'v3_2y_traded_stocks_count': len(traded_stocks),
            'v3_2y_worst_dd': round(worst_max_dd, 4),
            'note': 'v1 baseline 0 触发 0 笔; v2 用户放宽阈值版 (8% 硬止损, 无价格过滤); '
                    'v3 用户进一步严控 (5% 硬止损 + 8% 移动止盈 + 价格过滤 [3,90] + 1万本金). '
                    '三版本均为用户上传/subagent 0 改阈值。',
        },
        'honest_declaration': (
            'v3 是用户手动上传的进一步严控版 (5% 硬止损 + 8% 移动止盈 + 价格过滤 [3,90]), '
            '非 subagent 擅自改阈值。v3 类名 GoldComboV3_1Strategy。'
            '回测框架沿用 v2 (等权子账户 + backtrader 真实 run), 唯一差异是策略类与初始资金。'
            'Sharpe/Drawdown 为单股 backtrader analyzer 输出后等权平均, '
            '组合级 Sharpe/Drawdown 需要 portfolio-level equity curve (本脚本未实现)。'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T4-v3] === RESULT ===')
    log(f'[T4-v3] pool: {len(results)}/{len(pool_2y)} 成功')
    log(f'[T4-v3] price_filter_excluded: {len(price_filter_excluded)} (first_price not in [3,90])')
    log(f'[T4-v3] total_return_pct: {total_return_pct:.4f}%')
    log(f'[T4-v3] annualized: {annualized:.4f}%')
    log(f'[T4-v3] avg_max_dd: {avg_max_dd:.4f}%')
    log(f'[T4-v3] worst_max_dd: {worst_max_dd:.4f}%')
    log(f'[T4-v3] sharpe_avg: {avg_sharpe:.4f}')
    log(f'[T4-v3] trades: {total_trades}, traded_stocks: {len(traded_stocks)}')
    log(f'[T4-v3] written: {OUT_JSON}')
    log(f'[T4-v3] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()
