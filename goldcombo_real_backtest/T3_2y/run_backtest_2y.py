#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T3 · 黄金组合 A 真实 backtrader 2Y 回测 (2026-08-14)
- 引擎: backtrader 1.9.78.123 (非闭式估算代理)
- 池: 沪深 A 股 (1950 只, 排除 688/300)
- 时间窗: 2024-08-14 ~ 2026-08-14 (2Y)
- 策略: 4 指标 AND (MACD金叉<0 + BOLL扩口 + CCI<-100 + DMI空方极致)
- 出场: CCI>120 / DMI反转 / MACD双正
- 止损: 8% 硬止损
- 资金分配: 等权 1/N
- 输出: T3_2y/baseline_ashare_real_2y.json
"""
import json
import os
import sys
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# backtrader 1.x API
import backtrader as bt

# ==================== 配置 ====================
KLINE_DIR = '/Users/junze/goldcombo_real_backtest/T2_pool/ohlcv'
POOL_FILE = '/Users/junze/goldcombo_real_backtest/T2_pool/ashare_pool.json'
OUT_DIR = '/Users/junze/goldcombo_real_backtest/T3_2y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_2y.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

INITIAL_CAPITAL = 10000.0  # 与 stub 一致 (用户 P0)
COMMISSION_RATE = 0.001
SLIPPAGE = 0.001
STOP_LOSS_PCT = 0.08

START_DATE = '2024-08-14'
END_DATE = '2026-08-14'

# ===== 回测性能预算 =====
# 每只股票 backtrader run ≈ 0.5-2 秒 (单股 ~500 交易日)
# 1950 只 → 预计 30-60 分钟
# 子账户资金: 10000 / 1950 ≈ 5.13 元/股 (bt minimum)
MIN_CAPITAL_PER_STOCK = 500.0  # 强制最低子账户资金
EFFECTIVE_CAPITAL = max(INITIAL_CAPITAL, MIN_CAPITAL_PER_STOCK * 1950)

# Checkpoint 间隔
CHECKPOINT_EVERY = 100  # 每 100 只落一次进度


# ==================== 4 指标策略 ====================
class GoldComboStrategy(bt.Strategy):
    """4 指标 AND 入场 + 出场 + 8% 硬止损 — 与 goldcombo_strategy_ashare.py 1:1 逻辑"""
    params = dict(
        sl_pct=STOP_LOSS_PCT,
    )

    def __init__(self):
        # 1. MACD (12, 26, 9)
        self.macd = bt.ind.MACD(self.data.close, period_me1=12, period_me2=26, period_signal=9)
        self.macd_cross = bt.ind.CrossOver(self.macd.macd, self.macd.signal)

        # 2. BOLL (20, 2σ)
        self.boll = bt.ind.BollingerBands(self.data.close, period=20, devfactor=2.0)
        self.bw = self.boll.top - self.boll.bot
        self.bw_prev = self.bw(-1)  # shift(1)

        # 3. CCI (14)
        self.cci = bt.ind.CCI(self.data, period=14)

        # 4. DMI / ADX (14)
        self.dmi = bt.ind.DMI(self.data, period=14)
        self.plus_di = self.dmi.plusDI  # +DI
        self.minus_di = self.dmi.minusDI  # -DI

        # 持仓与止损跟踪
        self.entry_price = None
        self.order = None
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0.0
        self.trade_pnls = []

    def next(self):
        # 跳过暖机期
        if len(self) < 60:
            return

        # ===== 入场: 4 指标 AND (T 日触发, T+1 开盘买入) =====
        if not self.position:
            c3 = self.macd_cross[0] > 0 and self.macd.macd[0] < 0 and self.macd.signal[0] < 0
            c4 = self.bw[0] > self.bw_prev[0] if self.bw_prev[0] is not None else False
            c7 = self.cci[0] < -100
            c8 = self.plus_di[0] < 10 and self.minus_di[0] > 30

            if c3 and c4 and c7 and c8:
                size = self.broker.getcash() * 0.95 / self.data.close[0]
                size = max(int(size / 100) * 100, 100)  # 整百股
                if size > 0:
                    self.order = self.buy(size=size)
                    self.entry_price = self.data.close[0]
                    return

        # ===== 持仓中: 出场 OR 止损 =====
        if self.position:
            price = self.data.close[0]

            # 8% 硬止损
            if self.entry_price is not None and price <= self.entry_price * (1 - self.p.sl_pct):
                self.order = self.close()
                self.trade_count += 1
                self.loss_count += 1
                pnl = (price - self.entry_price) * self.position.size
                self.total_pnl += pnl
                self.trade_pnls.append(pnl)
                self.entry_price = None
                return

            # 出场: 任一反转信号
            exit_cci = self.cci[0] > 120
            exit_dmi = self.plus_di[0] > 30 and self.minus_di[0] < 20
            exit_macd = (self.macd.macd[0] > self.macd.signal[0]
                         and self.macd.macd[0] > 0
                         and self.macd.signal[0] > 0)

            if exit_cci or exit_dmi or exit_macd:
                self.order = self.close()
                self.trade_count += 1
                pnl = (price - self.entry_price) * self.position.size if self.entry_price else 0
                if pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                self.total_pnl += pnl
                self.trade_pnls.append(pnl)
                self.entry_price = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_pnls.append(trade.pnlcomm)


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
    cerebro.addstrategy(GoldComboStrategy)

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
    # backtrader TradeAnalyzer structure varies; use safe accessors
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
        'win_count': int(getattr(strat, 'win_count', 0)),
        'loss_count': int(getattr(strat, 'loss_count', 0)),
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

    log(f'[T3] start {datetime.now().isoformat()}')
    log(f'[T3] period: {START_DATE} ~ {END_DATE} (2Y)')
    log(f'[T3] pool size: {len(pool_2y)} A 股')
    log(f'[T3] initial_capital: {INITIAL_CAPITAL}')
    log(f'[T3] effective_capital (scaled): {EFFECTIVE_CAPITAL}')
    log(f'[T3] capital per stock: {EFFECTIVE_CAPITAL / len(pool_2y):.2f}')
    log(f'[T3] commission: {COMMISSION_RATE}, slippage: {SLIPPAGE}, sl_pct: {STOP_LOSS_PCT}')

    capital_per_stock = EFFECTIVE_CAPITAL / len(pool_2y)

    results = []
    failed = []
    errors = []
    t0 = time.time()

    for i, code in enumerate(pool_2y):
        if (i + 1) % CHECKPOINT_EVERY == 0 or i == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (len(pool_2y) - i - 1) if i > 0 else 0
            log(f'[T3] progress {i+1}/{len(pool_2y)} ({100*(i+1)/len(pool_2y):.1f}%) '
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
    log(f'[T3] backtest loop done in {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)')
    log(f'[T3] success: {len(results)}, failed_load: {len(failed)}, errors: {len(errors)}')

    # 汇总
    if not results:
        log('[T3] FAIL: no successful backtest')
        return

    # ===== 组合等权聚合 =====
    # 真实 backtrader: 每只股票独立子账户, 期末聚合
    total_final = sum(r['final_value'] for r in results)
    total_return_pct = (total_final / EFFECTIVE_CAPITAL - 1) * 100
    avg_return_pct = np.mean([r['return_pct'] for r in results])

    # 最大回撤: 用每只股票最大回撤的等权平均 (真实组合回撤需 portfolio 级 equity curve)
    avg_max_dd = np.mean([r['max_drawdown_pct'] for r in results])
    worst_max_dd = np.min([r['max_drawdown_pct'] for r in results])

    # Sharpe: 等权平均
    valid_sharpe = [r['sharpe_ratio'] for r in results if r['sharpe_ratio'] is not None]
    avg_sharpe = np.mean(valid_sharpe) if valid_sharpe else 0.0

    # Trade 总数
    total_trades = sum(r['trade_count'] for r in results)
    total_wins = sum(r['win_count'] for r in results)
    total_losses = sum(r['loss_count'] for r in results)
    closed_trades = total_wins + total_losses
    win_rate_pct = (total_wins / closed_trades * 100) if closed_trades > 0 else 0.0

    # 年化收益 (简单线性)
    n_years = 2.0
    annualized = ((1 + total_return_pct / 100) ** (1 / n_years) - 1) * 100

    summary = {
        'strategy_id': 'goldcombo',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业)',
        'data_period': '2Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool_2y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业, 600/601/603/605/000/002 only',
        'engine': 'backtrader 1.9.78.123 真实回测 (非闭式估算代理)',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': EFFECTIVE_CAPITAL,
            'capital_per_stock': round(capital_per_stock, 2),
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
            'stop_loss_pct': STOP_LOSS_PCT,
        },
        'real_metrics': {
            'total_return_pct': round(total_return_pct, 4),
            'annualized_return_pct': round(annualized, 4),
            'avg_per_stock_return_pct': round(avg_return_pct, 4),
            'max_drawdown_pct_avg': round(avg_max_dd, 4),
            'max_drawdown_pct_worst': round(worst_max_dd, 4),
            'sharpe_ratio_avg': round(avg_sharpe, 4),
            'trade_count': int(total_trades),
            'closed_trades': int(closed_trades),
            'win_count': int(total_wins),
            'loss_count': int(total_losses),
            'win_rate_pct': round(win_rate_pct, 2),
            'success_count': len(results),
            'failed_count': len(failed),
            'error_count': len(errors),
        },
        'individual_stock_results_sample': results[:20],  # 前 20 只样本
        'failed_codes_sample': failed[:20],
        'error_codes_sample': errors[:10],
        'honest_declaration': (
            '这是 backtrader 真实回测, 非闭式估算代理 (区别于 goldcombo_strategy_ashare.py '
            'vectorized numpy 模拟). 与 ratchet_final_baseline_ashare.json 数据期/口径不同, '
            '不可直接比较. Sharpe/Drawdown 为单股 backtrader analyzer 输出后等权平均, '
            '组合级 Sharpe/Drawdown 需要 portfolio-level equity curve (本脚本未实现).'
        ),
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f'[T3] === RESULT ===')
    log(f'[T3] pool: {len(results)}/{len(pool_2y)} 成功')
    log(f'[T3] total_return_pct: {total_return_pct:.2f}%')
    log(f'[T3] annualized: {annualized:.2f}%')
    log(f'[T3] avg_max_dd: {avg_max_dd:.2f}%')
    log(f'[T3] worst_max_dd: {worst_max_dd:.2f}%')
    log(f'[T3] sharpe_avg: {avg_sharpe:.4f}')
    log(f'[T3] trades: {total_trades} (wins: {total_wins}, losses: {total_losses})')
    log(f'[T3] win_rate: {win_rate_pct:.2f}%')
    log(f'[T3] written: {OUT_JSON}')
    log(f'[T3] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()