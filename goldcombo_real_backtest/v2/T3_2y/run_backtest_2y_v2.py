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
OUT_DIR = '/Users/junze/goldcombo_real_backtest/v2/T3_2y'
OUT_JSON = os.path.join(OUT_DIR, 'baseline_ashare_real_2y_v2.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

INITIAL_CAPITAL = 100000.0  # v2 用户原代码初始资金 (与 v1 stub 10000 不同)
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


# ==================== v2 改良共振策略 (Gated Voting) ====================
# 来源: 用户上传 ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第二版.py
# 剥离 RTF 后 sha256: a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1
# 类名沿用 GoldComboStrategy 保持 run_backtest 接口不变; 入场逻辑改为 Gated Voting:
#   C3 必选 (MACD 低位金叉) + [C4/C7/C8] 辅助投票 ≥ 2
# v1 阈值: C3 (macd<0 AND signal<0) + C4 BOLL扩口 + C7 CCI<-100 + C8 +DI<10 AND -DI>30 (AND 全开)
# v2 阈值: C3 仅 macd<0 放宽 + 辅助投票≥2 (C7 CCI<-80 + C8 +DI<15 AND -DI>25)
class GoldComboStrategy(bt.Strategy):
    """v2 改良共振版 (Gated Voting) — C3 必选 + [C4/C7/C8] 辅助 ≥2 投票"""
    params = dict(
        sl_pct=STOP_LOSS_PCT,        # 硬止损 8%
        cci_thresh=-80,              # CCI 超卖阈值 (v2 放宽自 -100)
        di_neg_thresh=25,            # -DI 阈值 (v2 放宽自 30)
        di_pos_thresh=15,            # +DI 阈值 (v2 放宽自 10)
        vote_min=2,                  # 辅助条件至少满足个数
        print_log=False,
    )

    def __init__(self):
        # 指标初始化 (与用户 v2 源码 1:1)
        self.macd = bt.ind.MACD(self.data.close, period_me1=12, period_me2=26, period_signal=9)
        self.cci = bt.ind.CCI(self.data, period=14)
        self.dmi = bt.ind.DMI(self.data, period=14)
        self.plus_di = self.dmi.plusDI
        self.minus_di = self.dmi.minusDI
        self.adx = self.dmi.adx if hasattr(self.dmi, 'adx') else bt.ind.ADX(self.data, period=14)
        self.bb = bt.ind.BollingerBands(self.data.close, period=20, devfactor=2.0)
        self.trix = bt.ind.TRIX(self.data.close, period=12)
        self.trma = bt.ind.SMA(self.trix, period=9)

        # 持仓与统计跟踪 (沿用 v1 类字段,保持 run_backtest 接口不变)
        self.entry_price = None
        self.order = None
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0.0
        self.trade_pnls = []

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price

    def next(self):
        # 跳过暖机期 (BOLL 20 需至少 20 根)
        if len(self) < 60:
            return

        # ===== 持仓管理 =====
        if self.position:
            # 1. 硬止损
            if self.entry_price is not None:
                if self.data.close[0] < self.entry_price * (1.0 - self.p.sl_pct):
                    price = self.data.close[0]
                    pnl = (price - self.entry_price) * self.position.size
                    self.close()
                    self.trade_count += 1
                    self.loss_count += 1
                    self.total_pnl += pnl
                    self.trade_pnls.append(pnl)
                    self.entry_price = None
                    return

            # 2. 卖点（任一满足即离场，与用户 v2 源码一致）
            s2 = self.cci[0] > 120
            s3 = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
            s4 = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
            s6 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)

            if s2 or s3 or s4 or s6:
                price = self.data.close[0]
                pnl = (price - self.entry_price) * self.position.size if self.entry_price else 0
                self.close()
                self.trade_count += 1
                if pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                self.total_pnl += pnl
                self.trade_pnls.append(pnl)
                self.entry_price = None
            return

        # ===== 空仓买入 (Gated Voting) =====
        if not self.position:
            bw = self.bb.top[0] - self.bb.bot[0]
            bw_prev = self.bb.top[-1] - self.bb.bot[-1]

            # 核心条件 C3：MACD 低位金叉（必选，v2 放宽：去掉 signal<0 限制）
            c3 = (self.macd.macd[0] > self.macd.signal[0]) and \
                 (self.macd.macd[-1] <= self.macd.signal[-1]) and \
                 (self.macd.macd[0] < 0)

            # 辅助条件组
            c4 = bw > bw_prev                          # BOLL 开口
            c7 = self.cci[0] < self.p.cci_thresh      # CCI 超卖 (放宽至 -80)
            c8 = (self.plus_di[0] < self.p.di_pos_thresh) and \
                 (self.minus_di[0] > self.p.di_neg_thresh)  # DMI 空方 (放宽至 15/25)

            # 投票计数：辅助条件满足几个？
            aux_votes = sum([c4, c7, c8])

            # 核心门控 + 投票买入
            if c3 and (aux_votes >= self.p.vote_min):
                size = self.broker.getcash() * 0.95 / self.data.close[0]
                size = max(int(size / 100) * 100, 100)
                if size > 0:
                    self.buy(size=size)
                    if self.p.print_log:
                        print(f'[改良买入] {self.data.datetime.date(0)} 辅助触发数:{aux_votes}')

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
        'strategy_version': 'v2 (Gated Voting, 用户上传 2026-08-14)',
        'strategy_name': '黄金组合A · 沪深 A 股 (排除科创+创业) · v2 改良共振版',
        'data_period': '2Y',
        'data_window': {'start': START_DATE, 'end': END_DATE},
        'pool_size': len(pool_2y),
        'pool_filter': 'exclude 688xxx 科创 + 300xxx 创业, 600/601/603/605/000/002 only',
        'engine': 'backtrader 1.9.78.123 真实回测 (非闭式估算代理)',
        'entry_logic_v2': 'C3 必选 (MACD 低位金叉) + [C4/C7/C8] 辅助 ≥ 2 投票',
        'generated_at': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_total, 1),
        'config': {
            'initial_capital': INITIAL_CAPITAL,
            'effective_capital': EFFECTIVE_CAPITAL,
            'capital_per_stock': round(capital_per_stock, 2),
            'commission': COMMISSION_RATE,
            'slippage': SLIPPAGE,
            'stop_loss_pct': STOP_LOSS_PCT,
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
            'closed_trades': int(closed_trades),
            'win_count': int(total_wins),
            'loss_count': int(total_losses),
            'win_rate_pct': round(win_rate_pct, 2),
            'success_count': len(results),
            'failed_count': len(failed),
            'error_count': len(errors),
        },
        'individual_stock_results_sample': results[:20],  # 前 20 只样本
        'traded_stocks_full': sorted([r['code'] for r in results if r.get('trade_count', 0) > 0]),
        'failed_codes_sample': failed[:20],
        'error_codes_sample': errors[:10],
        'comparison_to_v1': {
            'v1_2y_return_pct': 0.0,
            'v1_2y_trade_count': 0,
            'v1_2y_initial_capital': 10000.0,
            'v1_2y_traded_stocks_count': 0,
            'v2_2y_return_pct': round(total_return_pct, 4),
            'v2_2y_trade_count': int(total_trades),
            'v2_2y_initial_capital': INITIAL_CAPITAL,
            'v2_2y_traded_stocks_count': len([r for r in results if r.get('trade_count', 0) > 0]),
            'note': 'v1 baseline (T3_2y/baseline_ashare_real_2y.json) 0 触发 0 笔; v2 是用户上传放宽阈值后的改良版, 非 subagent 擅自改阈值。',
        },
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