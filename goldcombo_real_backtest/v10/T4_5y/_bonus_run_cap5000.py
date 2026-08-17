#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T4 补充诚实验证: V10 + capital_per_stock=5000 (子账户够买 1 手)
不改 V10 类任何一行, 只调 子账户 capital, 验证 V10 真实触发率
"""
import json
import os
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

import backtrader as bt

PROJECT_ROOT = '/Users/junze/quant-monitor-local'
KLINE_DIR = '/Users/junze/quant-monitor-local/data/ashare_kline'
POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v10/T4_5y'

INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.003
START_DATE = '2021-08-14'
END_DATE = '2026-08-14'

# ============== 子账户预算调高 ==============
# 派单原口径 500 元/股 → size=0 (V10 sizing 数学)
# 诚实验证用 5000 元/股: 0.20*5000=1000, 可买 1 手 100 股价 10 元股
CAPITAL_PER_STOCK = 5000.0
CHECKPOINT_EVERY = 50

sys.path.insert(0, PROJECT_ROOT)
from strategies.goldcombo.goldcombo_strategy_ashare_v10 import GoldComboV10_HighYield  # noqa


def run_single(code, start, end, capital):
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
    df = df[(df['date'] >= pd.Timestamp(start)) & (df['date'] <= pd.Timestamp(end))].reset_index(drop=True)
    if len(df) < 60:
        return None
    df = df[['date','open','high','low','close','volume']].set_index('date')

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(GoldComboV10_HighYield)  # 一字不差 import, 不传额外参数
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
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
        return {'code': code, 'error': str(e)[:100]}

    final = cerebro.broker.getvalue()
    ret = (final / capital - 1) * 100
    dd = strat.analyzers.dd.get_analysis()
    max_dd = dd.drawdown if hasattr(dd,'drawdown') else dd.get('drawdown', 0.0)
    sh = strat.analyzers.sharpe.get_analysis()
    sharpe = sh.get('sharperatio', None) or 0.0
    ta = strat.analyzers.ta.get_analysis()
    try:
        trades = ta.total.closed
    except Exception:
        trades = 0
    return {
        'code': code,
        'final_value': round(final, 2),
        'return_pct': round(ret, 4),
        'max_drawdown_pct': round(-max(max_dd, 0.0), 4),
        'sharpe_ratio': round(sharpe, 4),
        'trade_count': int(trades),
    }


def main():
    with open(POOL_FILE) as f:
        pool = json.load(f)['pool_5y']['codes']
    effective = len(pool) * CAPITAL_PER_STOCK
    print(f'[T4-bonus] period {START_DATE} ~ {END_DATE}')
    print(f'[T4-bonus] pool={len(pool)} capital_per_stock={CAPITAL_PER_STOCK} effective={effective}')

    results, failed, errors = [], [], []
    t0 = time.time()
    for i, code in enumerate(pool):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i+1)) * (len(pool) - i - 1) if i > 0 else 0
            print(f'[T4-bonus] {i+1}/{len(pool)} ({100*(i+1)/len(pool):.1f}%) '
                  f'elapsed={elapsed:.0f}s ETA={eta:.0f}s')
        try:
            r = run_single(code, START_DATE, END_DATE, CAPITAL_PER_STOCK)
            if r is None:
                failed.append(code); continue
            if 'error' in r:
                errors.append((code, r['error'])); continue
            results.append(r)
        except Exception as e:
            errors.append((code, str(e)[:100]))
    elapsed = time.time() - t0
    print(f'[T4-bonus] done in {elapsed:.0f}s ({elapsed/60:.1f} min)')
    print(f'[T4-bonus] success={len(results)} failed_load={len(failed)} errors={len(errors)}')

    if not results:
        return

    total_final = sum(r['final_value'] for r in results)
    total_ret = (total_final / effective - 1) * 100
    avg_ret = np.mean([r['return_pct'] for r in results])
    avg_dd = np.mean([r['max_drawdown_pct'] for r in results])
    worst_dd = np.min([r['max_drawdown_pct'] for r in results])
    valid_sh = [r['sharpe_ratio'] for r in results if r['sharpe_ratio'] is not None]
    avg_sh = np.mean(valid_sh) if valid_sh else 0.0
    trades = sum(r['trade_count'] for r in results)
    traded = [r for r in results if r.get('trade_count', 0) > 0]
    n_years = 5.0
    annualized = ((1 + total_ret/100) ** (1/n_years) - 1) * 100

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'V10_HighYield (GoldComboV10_HighYield 用户原版, 2026-08-16)',
        'strategy_name': '黄金组合A · V10 激进左翼高收益版 (补充诚实验证 · 子账户 5000 元)',
        'note': '用户派单硬约束: 子账户 500 元 → V10 per_pos_pct=0.20 导致 size=0 (本金不够买 1 手)。'
                '本补充跑批把 capital_per_stock 从 500 → 5000, 让 V10 能真实成交, 验证策略实际触发率与收益特征。'
                'V10 策略类一字不差 import, 未做修改。',
        'data_period': '5Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': effective,
            'capital_per_stock': CAPITAL_PER_STOCK,
            'cci_thresh': -70.0, 'di_neg_thresh': 20.0, 'di_pos_thresh': 15.0,
            'vote_min': 1, 'price_min': 3.0, 'per_pos_pct': 0.20,
            'hard_sl': 0.30, 'trail_sl': 0.25, 'cci_bubble': 200.0,
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
        },
        'real_metrics': {
            'total_return_pct': round(total_ret, 4),
            'annualized_return_pct': round(annualized, 4),
            'avg_per_stock_return_pct': round(avg_ret, 4),
            'max_drawdown_pct_avg': round(avg_dd, 4),
            'max_drawdown_pct_worst': round(worst_dd, 4),
            'sharpe_ratio_avg': round(avg_sh, 4),
            'trade_count': int(trades),
            'success_count': len(results),
            'traded_stocks_count': len(traded),
        },
        'individual_stock_results_sample': results[:20],
        'traded_stocks_full': traded,
    }

    out = os.path.join(OUT_DIR, 'baseline_ashare_real_5y_v10_cap5000.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f'[T4-bonus] === RESULT ===')
    print(f'[T4-bonus] ⭐ 总收益: {total_ret:.4f}%')
    print(f'[T4-bonus] ⭐ 最大回撤 worst: {worst_dd:.4f}%')
    print(f'[T4-bonus] annualized: {annualized:.4f}%')
    print(f'[T4-bonus] avg_max_dd: {avg_dd:.4f}%')
    print(f'[T4-bonus] sharpe_avg: {avg_sh:.4f}')
    print(f'[T4-bonus] trades: {trades}')
    print(f'[T4-bonus] traded_stocks: {len(traded)}')
    print(f'[T4-bonus] written: {out}')


if __name__ == '__main__':
    main()
