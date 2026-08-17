#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4 · V7FIXOBV 用户原版策略类跑 1950 只沪深 A 股 5Y 真回测 (2026-08-15)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 1950 只 (排除 688/300, ashare_pool.json 预生成)
- 时间窗: 2021-08-14 ~ 2026-08-14 (5Y, 与 V9 5Y 完全一致)
- 策略类: GoldComboV7_Locked (V7FIXOBV 用户原版, OBV 修复, 一字不差 import)
- 入场: 5 强势信号 ≥ 3 投票 (DMI+MACD+TRIX+OBV(MyOBV 自定义)+CCI)
- 出场: 8% 硬止损 + 15% 峰值回撤止盈 + MACD 高位死叉
- 资金分配: 等权 1/N (子账户 500 元, 共 975000)
- 输出: T4_5y/baseline_ashare_real_5y_v7fixobv.json

用户原话五硬约束 (2026-08-15):
1. 不准修改 V7FIXOBV 任何一行 (含 MyOBV 类, 用户原话"不得更改")
2. 不准加任何外部 hold/lock/sl 逻辑
3. 不准擅自修改 V7LOCK 5 个参数 (vote_min/price_min/cash_pct/hard_sl/trail_sl)
4. 不准用 2033 只全 A 股池 (1950 只沪深 A 股, 与 V9 5Y 完全一致)
5. 不准用 ETF 池数据 (沪深 A 股)

V7FIXOBV 用户原版来源: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V7FIXOBV.rtf
V7FIXOBV 用户原版 sha256: ac13fcae9baa08f3c75a0d77e45c6c01ddf0bba557f790c80bcd99615e741102
V7FIXOBV 已一字不差写入: /Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py
git commit SHA: 40b73a4e439e01e6c051c84970feeab1e310b7d5
"""
import json
import os
import sys
import time
import warnings
from datetime import datetime
from typing import Dict, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# backtrader 1.x API
import backtrader as bt

# ==================== 配置 ====================
PROJECT_ROOT = '/Users/junze/quant-monitor-local'
KLINE_DIR = '/Users/junze/quant-monitor-local/data/ashare_kline'
POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v7fixobv/T4_5y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_5y_v7fixobv.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.003
START_DATE = '2021-08-14'
END_DATE = '2026-08-14'

# 子账户预算 (1950 × 500 = 975000)
MIN_CAPITAL_PER_STOCK = 500.0

# Checkpoint 间隔
CHECKPOINT_EVERY = 50


# ==================== V7FIXOBV 用户原版策略类 ====================
# 一字不差 import, 不允许任何修改 (用户原话硬约束)
sys.path.insert(0, PROJECT_ROOT)
from strategies.goldcombo.goldcombo_strategy_ashare_v7lock import GoldComboV7_Locked  # noqa: E402


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

    cerebro = bt.Cerebro(stdstats=False)
    # ===== V7FIXOBV 用户原版, 无 debug 参数 =====
    cerebro.addstrategy(GoldComboV7_Locked)

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
        return {'code': code, 'error': str(e)[:100], 'tb': tb[:500]}

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
    }


# ==================== 主程序 ====================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 加载池
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool_data = json.load(f)

    pool_5y = pool_data['pool_5y']['codes']
    effective_capital = max(INITIAL_CAPITAL, MIN_CAPITAL_PER_STOCK * len(pool_5y))
    capital_per_stock = effective_capital / len(pool_5y)

    log_lines = []
    def log(msg, also_print=True):
        log_lines.append(msg)
        if also_print:
            print(msg)

    log(f'[T4] start {datetime.now().isoformat()}')
    log(f'[T4] V7FIXOBV 用户原版 · GoldComboV7_Locked + MyOBV (OBV bug 修复版)')
    log(f'[T4] period: {START_DATE} ~ {END_DATE} (5Y)')
    log(f'[T4] pool size: {len(pool_5y)} 沪深 A 股')
    log(f'[T4] initial_capital: {INITIAL_CAPITAL}')
    log(f'[T4] effective_capital: {effective_capital}')
    log(f'[T4] capital_per_stock: {capital_per_stock:.2f}')
    log(f'[T4] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}')
    log(f'[T4] V7FIXOBV 5 参数: vote_min=3, price_min=3.0, cash_pct=0.95, hard_sl=0.08, trail_sl=0.15')
    log(f'[T4] V7FIXOBV 入口: 5 强势信号 ≥ 3 (DMI+MACD+TRIX+OBV+CCI)')
    log(f'[T4] V7FIXOBV 出口: 8% 硬止损 + 15% 峰值回撤 + MACD 高位死叉')

    results = []
    failed = []
    errors = []
    t0 = time.time()

    for i, code in enumerate(pool_5y):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (len(pool_5y) - i - 1) if i > 0 else 0
            log(f'[T4] progress {i+1}/{len(pool_5y)} ({100*(i+1)/len(pool_5y):.1f}%) '
                f'elapsed={elapsed:.0f}s ETA={eta:.0f}s', also_print=True)

        try:
            r = run_single_stock(code, START_DATE, END_DATE, capital_per_stock)
            if r is None:
                failed.append(code)
                continue
            if 'error' in r:
                errors.append((code, r['error']))
                continue
            results.append(r)
        except Exception as e:
            errors.append((code, str(e)[:100]))

    elapsed_total = time.time() - t0
    log(f'[T4] backtest loop done in {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)')
    log(f'[T4] success: {len(results)}, failed_load: {len(failed)}, errors: {len(errors)}')

    # ===== 汇总 =====
    if not results:
        log('[T4] FAIL: no successful backtest')
        with open(OUT_LOG, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
        return

    # 组合等权聚合 (子账户独立,期末聚合)
    total_final = sum(r['final_value'] for r in results)
    total_return_pct = (total_final / effective_capital - 1) * 100
    avg_return_pct = np.mean([r['return_pct'] for r in results])
    avg_max_dd = np.mean([r['max_drawdown_pct'] for r in results])
    worst_max_dd = np.min([r['max_drawdown_pct'] for r in results])

    valid_sharpe = [r['sharpe_ratio'] for r in results if r['sharpe_ratio'] is not None]
    avg_sharpe = np.mean(valid_sharpe) if valid_sharpe else 0.0

    total_trades = sum(r['trade_count'] for r in results)
    traded_stocks = [r for r in results if r.get('trade_count', 0) > 0]

    n_years = 5.0
    annualized = ((1 + total_return_pct / 100) ** (1 / n_years) - 1) * 100

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'V7FIXOBV (GoldComboV7_Locked + MyOBV 用户原版 OBV 修复版, 2026-08-15)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · V7FIXOBV 锁死修复版',
        'data_period': '5Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool_5y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业 (沪深 600/601/603/605/000/002 only)',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'entry_logic': '5 强势信号 ≥ 3 投票 (DMI 多方 + MACD 水上 + TRIX 零上 + OBV 强势 (MyOBV 自定义) + CCI 强势)',
        'exit_logic': '8% 硬止损 + 15% 峰值回撤止盈 + MACD 高位死叉',
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': effective_capital,
            'capital_per_stock': round(capital_per_stock, 2),
            'vote_min': 3, 'price_min': 3.0, 'cash_pct': 0.95,
            'hard_sl': 0.08, 'trail_sl': 0.15,
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
            'obv_implementation': '用户自定义 MyOBV 类 (同文件内嵌, bt.ind.SumN(bt.Cmp(...)*volume, period=1))',
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
        'individual_stock_results_sample': results[:20],
        'traded_stocks_full': traded_stocks,
        'failed_codes_sample': failed[:20],
        'error_codes_sample': errors[:10],
        'comparison_to_v9': {
            'v9_5y_return_pct': 0.111,
            'v9_5y_trade_count': 209,
            'v9_5y_pool': 1950,
            'v7fixobv_5y_return_pct': round(total_return_pct, 4),
            'v7fixobv_5y_trade_count': int(total_trades),
            'v7fixobv_5y_pool': len(pool_5y),
        },
        'honest_declaration': (
            'V7FIXOBV 是用户重传的 OBV bug 修复版 (类名 GoldComboV7_Locked, 含同名 MyOBV 自定义类)。'
            'V7FIXOBV 一字不差, 未加任何外部 hold/lock。'
            'V7FIXOBV 跟 V9 设计哲学完全不同 (V9 左侧抄底, V7FIXOBV 右侧主升), 数据可比因都跑 1950 只沪深 A 股 5Y。'
            'v1 截断版 + v2 OBV bug 版都已覆盖, V7FIXOBV 是 source of truth。'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T4] === RESULT ===')
    log(f'[T4] pool: {len(results)}/{len(pool_5y)} 成功')
    log(f'[T4] total_return_pct: {total_return_pct:.4f}%')
    log(f'[T4] annualized: {annualized:.4f}%')
    log(f'[T4] avg_max_dd: {avg_max_dd:.4f}%')
    log(f'[T4] worst_max_dd: {worst_max_dd:.4f}%')
    log(f'[T4] sharpe_avg: {avg_sharpe:.4f}')
    log(f'[T4] trades: {total_trades}')
    log(f'[T4] traded_stocks: {len(traded_stocks)}')
    log(f'[T4] written: {OUT_JSON}')
    log(f'[T4] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()