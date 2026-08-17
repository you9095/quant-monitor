#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4 · V11_EnergyPeak 能量衰竭离场策略类跑 1950 只沪深 A 股 5Y 真回测 (2026-08-16)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 1950 只 (排除 688/300/8/4, ashare_pool.json 预生成)
- 时间窗: 2021-08-14 ~ 2026-08-14 (5Y)
- 策略类: GoldComboV11_EnergyPeak (用户原版能量衰竭离场, 一字不差 import, 不允许任何修改)
- 入场: C3 MACD低位金叉 + [C4/C7/C8] 至少 1 投票 (vote_min=1, 极敏感)
- 出场: 15% 硬止损 (vs V10 30% 改严) + 20% 峰值回撤止盈 (vs V10 25% 改严) + 能量衰竭离场 (CCI 5日前>100 现<80 破MA10)
- 资金: 5万本金锁死 (用户原话硬约束: 不准改回 1万, 否则重演 V10 sizing bug)
- 输出: T4_5y/baseline_ashare_real_5y_v11.json

用户原话五硬约束 (2026-08-16):
1. "丢弃 V10 的 1万本金配置, 使用上方 GoldComboV11_EnergyPeak, setcash(50000.0) 锁死" → 强制 setcash(50000.0), 不准改 1万
2. "T2 单股验证: 仍用 600438 通威股份, 确认能打出 ≥3 笔且现金占用正常 (不应再 0 触发)" → T2 已 PASS (9 笔)
3. "T4 全池: 1950 只沪深 A, 5Y 窗口 2021-08-14~2026-08-14, 重点报 总收益, 笔数, worst DD" → 本任务
4. "若 T4 收益仍接近 0%, 执行用户指令方向 1: 证明左侧卖点需进一步右移, 届时再议 V12" → fallback
5. "一字不差, 不准加任何外部 hold/lock" → 不允许任何外部包装/拦截/hold/lock/sl

V11 用户原版来源: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合v11-energypeak.rtf
V11 用户原版 sha256: 6ceb76b0f1c633b8dfa673ed5b6ff16c62da3ba5c87666781335d49702b5ac8a
V11 已一字不差写入: /Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v11.py
git commit SHA: 097062c
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
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v11/T4_5y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_5y_v11.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

# ⚠️ 用户原话硬约束: 5万本金锁死, 不准改回 1万 (否则重演 V10 sizing bug)
INITIAL_CAPITAL = 50000.0
COMMISSION_RATE = 0.001
SLIPPAGE = 0.003
START_DATE = '2021-08-14'
END_DATE = '2026-08-14'

# 单股本金 = 5万 (用户原话硬约束: 强制 5万锁死, 不分子账户, 与 V10 路径 B 5000/只的派单方式不同)
CAPITAL_PER_STOCK = 50000.0

# Checkpoint 间隔
CHECKPOINT_EVERY = 100


# ==================== V11 用户原版策略类 ====================
# 一字不差 import, 不允许任何修改 (用户原话硬约束)
sys.path.insert(0, PROJECT_ROOT)
from strategies.goldcombo.goldcombo_strategy_ashare_v11 import GoldComboV11_EnergyPeak  # noqa: E402


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
    # ===== V11 用户原版, 不传任何额外参数 (硬约束: 不准擅自修改 10 个参数) =====
    cerebro.addstrategy(GoldComboV11_EnergyPeak)

    data_feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data_feed)

    # ⚠️ 用户原话硬约束: 5万本金锁死, 不准改回 1万 (否则重演 V10 sizing bug)
    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=COMMISSION_RATE)
    cerebro.broker.set_slippage_perc(perc=SLIPPAGE)

    # Analyzers
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='tr')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')

    start_value = cerebro.broker.getvalue()
    result = cerebro.run()
    final_value = cerebro.broker.getvalue()
    return_pct = (final_value / start_value - 1) * 100

    strat = result[0]

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

    log_lines = []
    def log(msg, also_print=True):
        log_lines.append(msg)
        if also_print:
            print(msg)

    log(f'[T4] start {datetime.now().isoformat()}')
    log(f'[T4] V11 用户原版 · GoldComboV11_EnergyPeak (能量衰竭离场, 一字不差 import)')
    log(f'[T4] period: {START_DATE} ~ {END_DATE} (5Y)')
    log(f'[T4] pool size: {len(pool_5y)} 沪深 A 股 (排除 688/300/8/4)')
    log(f'[T4] initial_capital: {INITIAL_CAPITAL} (⚠️ 用户原话硬约束: 5万锁死, 不准改 1万)')
    log(f'[T4] capital_per_stock: {CAPITAL_PER_STOCK} (单股本金 = 5万)')
    log(f'[T4] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}')
    log(f'[T4] V11 10 参数: cci_thresh=-70.0/di_neg=20.0/di_pos=15.0/vote_min=1/price_min=3.0/per_pos_pct=0.20/hard_sl=0.15/trail_sl=0.20/cci_peak=100.0/cci_fall=80.0')
    log(f'[T4] 入场: C3 MACD 零下金叉 + [C4/C7/C8] ≥ 1 (极敏感) | 出场: 15% 硬止损 (vs V10 30% 改严) + 20% 峰值回撤 (vs V10 25% 改严) + 能量衰竭离场 (CCI 5日前>100 现<80 破MA10)')

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
            r = run_single_stock(code, START_DATE, END_DATE, CAPITAL_PER_STOCK)
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

    # 组合等权聚合 (子账户独立, 期末聚合)
    # ⚠️ 用户原话硬约束: setcash(50000.0) 锁死, 不分子账户, 每只独立跑 5万
    total_final = sum(r['final_value'] for r in results)
    # 总初始资金 = 1950 × 50000 = 97,500,000 (用户原话锁死 5万/只, 不分子账户)
    total_initial = CAPITAL_PER_STOCK * len(results)
    total_return_pct = (total_final / total_initial - 1) * 100
    avg_return_pct = np.mean([r['return_pct'] for r in results])
    avg_max_dd = np.mean([r['max_drawdown_pct'] for r in results])
    worst_max_dd = np.min([r['max_drawdown_pct'] for r in results])

    valid_sharpe = [r['sharpe_ratio'] for r in results if r['sharpe_ratio'] is not None]
    avg_sharpe = np.mean(valid_sharpe) if valid_sharpe else 0.0

    total_trades = sum(r['trade_count'] for r in results)
    traded_stocks = [r for r in results if r.get('trade_count', 0) > 0]

    n_years = 5.0
    annualized = ((1 + total_return_pct / 100) ** (1 / n_years) - 1) * 100

    # V11 策略类 sha256 (用户原版对照)
    import hashlib
    v11_path = '/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v11.py'
    with open(v11_path, 'rb') as f:
        v11_sha256 = hashlib.sha256(f.read()).hexdigest()

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'V11_EnergyPeak (GoldComboV11_EnergyPeak 用户原版, 2026-08-16)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · V11 能量衰竭离场版',
        'data_period': '5Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool_5y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业 (沪深 600/601/603/605/000/002 only)',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'strategy_file_sha256': v11_sha256,
        'entry_logic_v11': 'C3 必选 (MACD 低位金叉) + [C4 (BOLL 开口) / C7 (CCI<-70) / C8 (DMI 空方)] ≥ 1 投票 (同 V10)',
        'exit_logic_v11': '15% 硬止损 (vs V10 30% 改严) + 20% 峰值回撤止盈 (vs V10 25% 改严) + 能量衰竭离场 (CCI 5日前>100 现<80 破MA10)',
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'capital_per_stock': CAPITAL_PER_STOCK,
            'total_initial_pool_capital': round(total_initial, 2),
            'cci_thresh': -70.0, 'di_neg_thresh': 20.0, 'di_pos_thresh': 15.0,
            'vote_min': 1, 'price_min': 3.0, 'per_pos_pct': 0.20,
            'hard_sl': 0.15, 'trail_sl': 0.20, 'cci_peak': 100.0, 'cci_fall': 80.0,
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
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
        'comparison': {
            'v9_5y_return_pct': 0.111,
            'v9_5y_trade_count': 209,
            'v9_5y_pool': 1950,
            'v7fixobv_5y_return_pct': -1.0586,
            'v7fixobv_5y_trade_count': 7586,
            'v7fixobv_5y_pool': 1950,
            'v10_path_b_5y_return_pct': 1.5991,
            'v10_path_b_5y_trade_count': 5598,
            'v10_path_b_5y_pool': 1950,
            'v11_5y_return_pct': round(total_return_pct, 4),
            'v11_5y_trade_count': int(total_trades),
            'v11_5y_pool': len(pool_5y),
            'v11_5y_worst_dd': round(worst_max_dd, 4),
        },
        'user_predicted': '用户原话: 重点报 总收益, 笔数, worst DD. 若 T4 收益仍接近 0%, 执行用户指令方向 1: 证明左侧卖点需进一步右移, 届时再议 V12',
        'honest_declaration': (
            'V11_EnergyPeak 是用户上传的能量衰竭离场版 (类名 GoldComboV11_EnergyPeak)。'
            'V11 一字不差, 未加任何外部 hold/lock。'
            'V11 替换 V10_HighYield 旧类, 强制 setcash(50000.0) 锁死 (用户原话硬约束, 不准改回 1万)。'
            'V11 数据可比因都跑 1950 只沪深 A 股 5Y。'
            'V11 vs V10 离场差异: 15% 硬止损 (改严) + 20% 峰值回撤 (改严) + 能量衰竭离场 (CCI 5日前>100 现<80 破MA10)。'
            'V11 vs V10 入场相同: C3 MACD 低位金叉必选 + [C4/C7/C8] ≥ 1 投票 (极敏感)。'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T4] === RESULT ===')
    log(f'[T4] pool: {len(results)}/{len(pool_5y)} 成功')
    log(f'[T4] ⭐ 总收益 (用户重点观察 1): {total_return_pct:.4f}%')
    log(f'[T4] ⭐ 笔数 (用户重点观察 2): {total_trades}')
    log(f'[T4] ⭐ 最大回撤 worst (用户重点观察 3): {worst_max_dd:.4f}%')
    log(f'[T4] annualized: {annualized:.4f}%')
    log(f'[T4] avg_max_dd: {avg_max_dd:.4f}%')
    log(f'[T4] sharpe_avg: {avg_sharpe:.4f}')
    log(f'[T4] traded_stocks: {len(traded_stocks)}')
    log(f'[T4] written: {OUT_JSON}')
    log(f'[T4] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()
