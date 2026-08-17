#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4 · V20_NoMA 零均线数值化版策略类跑 1950 只沪深 A 股 5Y 真回测 (2026-08-16)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 1950 只 (排除 688/300/8/4, ashare_pool.json 预生成)
- 时间窗: 2021-08-14 ~ 2026-08-14 (5Y)
- 策略类: GoldComboV20_NoMA (用户原版零均线数值化版, 一字不差 import, 不允许任何修改)
- 入场: 收盘价 > 60日 最高价(-1) + cooldown=0 (纯通道突破, 无均线)
- 出场: 15% 硬止损 OR 35% 峰值回撤止盈 OR 价格 < 峰值 - 3*ATR(14) OR CCI泡沫破灭
- 仓位: 95% 集中持仓 (cash_pct=0.95, 单只满仓)
- 资金: setcash(50000.0) 锁死 (用户原话硬约束)
- 输出: T4_5y/baseline_ashare_real_5y_v20.json

用户原话硬约束 (2026-08-16):
1. "使用 GoldComboV20_NoMA, 5万本金锁死, 1950沪深池, 5Y窗口, 类名不得改, 一字不差" → 一字不差 import, 不允许任何修改
2. "严禁添加任何外部 hold/lock/lockday 逻辑" → V20 内部仅 self.cooldown 字段, 无外部 lock
3. "硬性规则全内嵌" → 所有规则 (60日通道突破 + cooldown 60日禁买 + 15%止损 + 35%峰值 + 3*ATR断裂 + CCI泡沫破灭 + 95%集中持仓) 都在类内, 不外置
4. "卖点剔除所有MA, 用具体数值/ATR/CCI" → 策略类 0 个 bt.ind.SMA / bt.indicators.SMA
5. "setcash(50000.0) 锁死" → 每只子账户强制 5万本金
6. "5Y 沪深池回测" → 5Y 数据期 2021-08-14 ~ 2026-08-14, 1950 只沪深池

V20 用户原版来源: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V20_NoMA.rtf
V20 用户上传 sha256: 9021d4fb1537abb33d519fc85d1b9b5bc8249ef554c4e47d6d15ab256087fde2
V20 已一字不差写入: /Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v20.py
git commit SHA: 7120228
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
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v20/T4_5y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_5y_v20.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

INITIAL_CAPITAL = 50000.0  # ⚠️ 用户原话硬约束: setcash(50000.0) 锁死
COMMISSION_RATE = 0.001
SLIPPAGE = 0.003
START_DATE = '2021-08-14'
END_DATE = '2026-08-14'

# 单股独立子账户: 用户原话锁死 5万/股 (复刻 V11-V17 配置)
CAPITAL_PER_STOCK = 50000.0

# Checkpoint 间隔
CHECKPOINT_EVERY = 50


# ==================== V20 用户原版策略类 ====================
# 一字不差 import, 不允许任何修改 (用户原话硬约束)
sys.path.insert(0, PROJECT_ROOT)
from strategies.goldcombo.goldcombo_strategy_ashare_v20 import GoldComboV20_NoMA  # noqa: E402


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
    # ===== V20 用户原版, 不传任何额外参数 (硬约束: 不准擅自修改 10 参数) =====
    cerebro.addstrategy(GoldComboV20_NoMA)

    data_feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data_feed)

    # ⚠️ 用户原话硬约束: setcash(50000.0) 锁死
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
    n_pool = len(pool_5y)
    # 等权聚合: 总额 = 50000 × N, 每只 50000/只独立 (符合用户原话"setcash 50000 锁死")
    effective_capital = CAPITAL_PER_STOCK * n_pool

    log_lines = []
    def log(msg, also_print=True):
        log_lines.append(msg)
        if also_print:
            print(msg)

    log(f'[T4] start {datetime.now().isoformat()}')
    log(f'[T4] V20 用户原版 · GoldComboV20_NoMA (零均线数值化版: 卖点剔除所有MA, 用具体数值/ATR/CCI, 一字不差 import)')
    log(f'[T4] period: {START_DATE} ~ {END_DATE} (5Y)')
    log(f'[T4] pool size: {n_pool} 沪深 A 股 (排除 688/300/8/4)')
    log(f'[T4] INITIAL_CAPITAL (用户原话锁死): {INITIAL_CAPITAL}')
    log(f'[T4] CAPITAL_PER_STOCK: {CAPITAL_PER_STOCK}')
    log(f'[T4] effective_capital (合计): {effective_capital}')
    log(f'[T4] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}')
    log(f'[T4] V20 10 参数: break_n=60/atr_period=14/atr_multi=3.0/cci_peak=100/cci_fall=80/trail_sl=0.35/hard_sl=0.15/price_min=1.0/cash_pct=0.95/cool_days=60')
    log(f'[T4] V20 3 指标: Highest(60日高)/ATR(14)/CCI(14) — 零 SMA/MA')
    log(f'[T4] 入场 (纯通道突破, 非均线): 收盘价 > 60日 最高价(-1) + cooldown=0')
    log(f'[T4] 出场 4 机制 (全数值化, 无 MA):')
    log(f'[T4]   卖A: 15% 硬止损 (数值)')
    log(f'[T4]   卖B: 35% 峰值回撤止盈 (数值, 宽容, 比 V17 20% 更宽容)')
    log(f'[T4]   卖C: 价格 < 峰值 - 3*ATR(14) (波动率断裂, 替代破线)')
    log(f'[T4]   卖D: CCI 5 日前 > 100 现 < 80 (动量泡沫破灭, 无均线)')
    log(f'[T4] 冷却机制 (V20 内部 cooldown): 卖后 60 日禁买, 不是 subagent 加的外部 hold/lock')
    log(f'[T4] 仓位 (95% 集中持仓): cash × 0.95 → 单只满仓, 集中火力')
    log(f'[T4] 过滤: price < 1.0 OR ATR=NaN OR CCI=NaN → return (math.isnan 防护)')

    results = []
    failed = []
    errors = []
    t0 = time.time()

    for i, code in enumerate(pool_5y):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (n_pool - i - 1) if i > 0 else 0
            log(f'[T4] progress {i+1}/{n_pool} ({100*(i+1)/n_pool:.1f}%) '
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

    # V20 策略类 sha256 (用户原版对照)
    import hashlib
    v20_path = '/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v20.py'
    with open(v20_path, 'rb') as f:
        v20_sha256 = hashlib.sha256(f.read()).hexdigest()

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'V20_NoMA (GoldComboV20_NoMA 用户原版零均线数值化版, 2026-08-16)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · V20 零均线数值化版',
        'data_period': '5Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': n_pool,
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业 (沪深 600/601/603/605/000/002 only)',
        'engine': 'backtrader 1.9.78.123 真实回测',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'strategy_file_sha256': v20_sha256,
        'entry_logic_v20': '零均线数值化: 收盘价 > 60日 最高价(-1) + cooldown=0',
        'exit_logic_v20': '15% 硬止损 + 35% 峰值回撤止盈 + 3*ATR(14) 波动率断裂 + CCI泡沫破灭 (5日前>100 现<80)',
        'position_sizing_v20': '95% 集中持仓: cash × 0.95 → 单只满仓 (cash_pct=0.95)',
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': effective_capital,
            'capital_per_stock': CAPITAL_PER_STOCK,
            'break_n': 60, 'atr_period': 14, 'atr_multi': 3.0,
            'cci_peak': 100.0, 'cci_fall': 80.0,
            'trail_sl': 0.35, 'hard_sl': 0.15,
            'price_min': 1.0, 'cash_pct': 0.95, 'cool_days': 60,
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
            'v9_5y_worst_dd': -19.65,
            'v7fixobv_5y_return_pct': -1.0586,
            'v7fixobv_5y_trade_count': 7586,
            'v7fixobv_5y_pool': 1950,
            'v7fixobv_5y_worst_dd': -69.13,
            'v10_path_b_5y_return_pct': 1.5991,
            'v10_path_b_5y_trade_count': 5598,
            'v10_path_b_5y_pool': 1950,
            'v10_path_b_5y_worst_dd': -15.79,
            'v11_5y_return_pct': 0.4444,
            'v11_5y_trade_count': 12063,
            'v11_5y_pool': 1950,
            'v11_5y_worst_dd': -20.9535,
            'v12_5y_return_pct': 1.0246,
            'v12_5y_trade_count': 9321,
            'v12_5y_pool': 1950,
            'v12_5y_worst_dd': -18.5878,
            'v13_5y_return_pct': -0.9685,
            'v13_5y_trade_count': 9842,
            'v13_5y_pool': 1950,
            'v13_5y_worst_dd': -11.3087,
            'v14_5y_return_pct': -0.3366,
            'v14_5y_trade_count': 14871,
            'v14_5y_pool': 1950,
            'v14_5y_worst_dd': -16.82,
            'v16_5y_return_pct': -4.9108,
            'v16_5y_trade_count': 29078,
            'v16_5y_pool': 1950,
            'v16_5y_worst_dd': -73.4941,
            'v17_5y_return_pct': -9.4598,
            'v17_5y_trade_count': 8716,
            'v17_5y_pool': 1950,
            'v17_5y_worst_dd': -71.8066,
            'v20_5y_return_pct': round(total_return_pct, 4),
            'v20_5y_trade_count': int(total_trades),
            'v20_5y_pool': n_pool,
            'v20_5y_worst_dd': round(worst_max_dd, 4),
        },
        'user_predicted': '用户原话 (2026-08-16 派单): "新的策略 开始回测"。重点观察 (沿用 V17 惯例): 总收益 / 笔数 / worst DD。用户底线硬约束: "卖点剔除所有MA, 用具体数值/ATR/CCI"',
        'honest_declaration': (
            'V20_NoMA 是用户上传的零均线数值化版 (类名 GoldComboV20_NoMA, 卖点剔除所有MA, 用具体数值/ATR/CCI)。'
            'V20 一字不差, 未加任何外部 hold/lock (cooldown 是 V20 内部 self.cooldown 字段)。'
            'V20 替换 V17_LowFreqBreakout 旧类, 强制 setcash(50000.0) 锁死。'
            'V20 数据可比因都跑 1950 只沪深 A 股 5Y (排除 688/300 科创+创业)。'
            'V20 是 v1-v17 之外的新范式 (零均线数值化), 用具体数值/ATR/CCI 替代所有 SMA/MA。'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T4] === RESULT ===')
    log(f'[T4] pool: {len(results)}/{n_pool} 成功')
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
