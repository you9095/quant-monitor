#!/usr/bin/env python3
"""
goldcombo · 黄金组合A 回测脚本 (根目录版)

策略来源: ~/Downloads/股票筛选项目/自己写量化策略和脚本/GoldComboStrategy-2.py
  (RTF 包裹的 Python 源码, 由 makefile / cron 调用本脚本时, 已自动解出真 Python 代码)

策略核心:
  - 黄金组合A: 极致恐慌反转模型
  - 4 指标 (MACD + BOLL + CCI + DMI) + TRIX/TRMA 趋势确认
  - 入场 = C3 (MACD 低位金叉 + 双负) AND C4 (BOLL 开口放大) AND C7 (CCI<-100) AND C8 (+DI<10, -DI>30)
  - 出场 = S2 OR S3 OR S4 OR S6
  - 止损: sl_pct = 0.08 (8% 硬止损)

cron 调度:
  - 2026-08-13 01:30 启动 2Y/5Y 回测 (生成 outputs/goldcombo/*.json)
  - 2026-08-13 02:30 启动棘轮 50 轮迭代 (后续 subagent 接管)

核心目录产物:
  - signals/goldcombo_YYYY-MM-DD.json (真实回测后生成)
  - outputs/goldcombo/goldcombo_2y_*.json (2Y 数据回测结果)
  - outputs/goldcombo/goldcombo_5y_*.json (5Y 数据回测结果)
"""
from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 让脚本可独立运行 (从根目录或 cron 调用)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


# === backtrader 框架 (从 RTF 解出的真代码, 与 user 附件 1:1) ===
def _import_backtrader():
    """backtrader 可选依赖, 没有时给清晰错误 (用户 P0 硬约束: 失败必诚实声明)"""
    try:
        import backtrader as bt
        return bt
    except ImportError as e:
        raise SystemExit(
            f"[goldcombo] backtrader 未安装: {e}\n"
            "  安装: pip install backtrader  或  uv add backtrader\n"
            "  本策略骨架依赖 backtrader,无 backtrader 无法跑回测。"
        )


class GoldComboStrategy:
    """
    黄金组合 A: 极致恐慌反转模型
    
    买点: MACD 低位金叉 (C3) + BOLL 开口 (C4) + CCI<-100(C7) + DMI 空方极致 (C8)
    """
    pass


# 动态定义策略类 (从 RTF 提取的真代码, 1:1 还原)
def _build_strategy_class():
    """从 RTF 提取的真代码, 1:1 还原 GoldComboStrategy"""
    bt = _import_backtrader()

    class GoldComboStrategy(bt.Strategy):
        # 黄金组合 A：极致恐慌反转模型
        # 买点：MACD 低位金叉 (C3) + BOLL 开口 (C4) + CCI<-100(C7) + DMI 空方极致 (C8)
        params = dict(sl_pct=0.08, print_log=True)

        def __init__(self):
            self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
            self.cci = bt.ind.CCI(period=14)
            self.plus_di = bt.ind.PlusDI(period=14)
            self.minus_di = bt.ind.MinusDI(period=14)
            self.adx = bt.ind.ADX(period=14)
            self.bb = bt.ind.BollingerBands(period=20, devfactor=2)
            self.trix = bt.ind.TRIX(period=12)
            self.trma = bt.ind.SMA(self.trix, period=9)
            self.entry_price = None

        def notify_order(self, order):
            if order.status in [order.Completed]:
                if order.isbuy():
                    self.entry_price = order.executed.price

        def next(self):
            if self.position:
                if self.entry_price is not None:
                    if self.data.close[0] < self.entry_price * (1.0 - self.p.sl_pct):
                        self.close()
                        return
                s2 = self.cci[0] > 120
                s3 = (self.plus_di[0] > 30) and (self.minus_di[0] < 20) and (self.adx[0] > 32)
                s4 = (self.trix[0] > self.trma[0]) and (self.trix[0] > 0)
                s6 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[0] > 0) and (self.macd.signal[0] > 0)
                if s2 or s3 or s4 or s6:
                    self.close()
                return
            if not self.position:
                bw = self.bb.top[0] - self.bb.bot[0]
                bw_prev = self.bb.top[-1] - self.bb.bot[-1]
                c3 = (self.macd.macd[0] > self.macd.signal[0]) and (self.macd.macd[-1] <= self.macd.signal[-1]) and (self.macd.macd[0] < 0) and (self.macd.signal[0] < 0)
                c4 = bw > bw_prev
                c7 = self.cci[0] < -100
                c8 = (self.plus_di[0] < 10) and (self.minus_di[0] > 30)
                if c3 and c4 and c7 and c8:
                    self.buy()

    return GoldComboStrategy


# === 数据获取 stub (cron 8/13 01:30 启动后会被真实数据源替换) ===
def fetch_data_stub(period_years: int = 2):
    """
    数据获取 stub (M01 集成阶段占位)
    
    真实数据源 (cron 8/13 启动后接入):
      - 优选: akshare / tushare pro (A 股 ETF 数据)
      - 备选: yfinance (美股 / 港股 ETF)
      - 兜底: 本地 CSV~/quant-monitor-local/data/etf_*.csv
    
    占位实现: 用 backtrader feed 构造 synthetic 数据 (非真实行情)
    """
    bt = _import_backtrader()
    try:
        import pandas as pd
        import numpy as np
    except ImportError as e:
        raise SystemExit(
            f"[goldcombo] pandas/numpy 未安装: {e}\n"
            "  安装: pip install pandas numpy"
        )
    
    np.random.seed(42)
    end = datetime(2026, 8, 12)
    start = end - timedelta(days=period_years * 365)
    dates = pd.date_range(start, end, freq='D')
    n = len(dates)
    
    returns = np.random.normal(0.0005, 0.012, n)
    close = 100.0 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.008, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.008, n)))
    open_ = close * (1 + np.random.normal(0, 0.005, n))
    volume = np.random.randint(1000000, 5000000, n)
    
    df = pd.DataFrame({
        'datetime': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    df.set_index('datetime', inplace=True)
    
    return bt.feeds.PandasData(dataname=df)


def write_signal_placeholder(
    out_path: Path,
    today_str: str,
    initial_capital: float,
    period_years: int,
    final_value: float,
    trades_count: int,
) -> None:
    """M01 集成阶段写 signal 文件 (占位空数据, schema 与其他 5 策略一致)"""
    pnl = final_value - initial_capital
    return_pct = round((final_value - initial_capital) / initial_capital * 100, 2) if initial_capital > 0 else 0.0
    
    signal = {
        "date": today_str,
        "strategy_id": "goldcombo",
        "data_source": "M01_placeholder_until_real_backtest",
        "data_period": f"{period_years}Y (待 cron 8/13 01:30 真实回测)",
        "caliber": f"M01 集成阶段 R0_initial 占位 · sl_pct=0.08 · 入场 C3+C4+C7+C8",
        "initial_capital": initial_capital,
        "positions": [],  # 占位空持仓
        "action": {
            "action": "HOLD",
            "target": "",
            "detail": f"M01 集成阶段占位 · stub 跑出 final_value={final_value:.2f} trades={trades_count} (非真实回测)"
        },
        "today_pnl": 0.0,
        "today_return": 0.0,
        "live_total_pnl": pnl,
        "live_total_return": return_pct,
        "live_days": 0,
        "live_start_date": today_str,
        "backtest_total_return": None,  # 占位, cron 8/13 启动后填真值
        "backtest_sharpe": None,
        "backtest_max_drawdown": None,
        "backtest_annualized_return": None,
        "backtest_trades": trades_count,
        "backtest_version": "R0_initial",
        "backtest_data_period": f"{period_years}Y (待 cron 8/13 01:30)",
        "version": "R0_initial",
        "source_file": "/Users/junze/quant-monitor-local/strategies/goldcombo/",
        "source_file_latest": None,
        "source_file_count": 0,
        "source_file_first_date": None,
        "source_file_last_date": None,
        "validation": {
            "note": "M01 集成阶段 stub 跑通 backtrader 框架, 真实回测由 cron 8/13 01:30 启动后生成",
            "expected_run_date": "2026-08-13",
            "initial_capital_source": "config/strategies.json goldcombo.initial_capital",
            "synced_to_monitor": True,
            "stub_final_value": final_value,
        }
    }
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(signal, f, ensure_ascii=False, indent=2)
    print(f"[goldcombo] 信号 placeholder 写入: {out_path}")


def run_stub_backtest(period_years: int = 2, output_dir: str | None = None) -> int:
    """
    M01 集成阶段: 跑 1 次 stub backtest (验证 backtrader 框架 + 4 指标 + 入场/出场/止损逻辑)
    真实回测由 cron 8/13 01:30 启动后用真实数据源跑
    """
    bt = _import_backtrader()
    GoldComboStrategy = _build_strategy_class()
    
    initial_capital = 10000.0
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboStrategy)
    cerebro.broker.setcash(initial_capital)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.001)
    
    data = fetch_data_stub(period_years=period_years)
    cerebro.adddata(data)
    
    print(f"[goldcombo] {'='*60}")
    print(f"[goldcombo] 黄金组合A: 极致恐慌反转模型")
    print(f"[goldcombo] 数据期: {period_years}Y (synthetic stub, 非真实行情)")
    print(f"[goldcombo] 起始资金: {initial_capital:.2f}")
    print(f"[goldcombo] 策略: GoldComboStrategy (sl_pct=0.08)")
    print(f"[goldcombo] 入场: C3(低位金叉) + C4(BOLL 开口) + C7(CCI<-100) + C8(DMI 极致)")
    print(f"[goldcombo] 出场: S2(CCI>120) OR S3(DMI 反转) OR S4(TRIX 上穿) OR S6(MACD 双正)")
    print(f"[goldcombo] 止损: 8% 硬止损")
    print(f"[goldcombo] {'='*60}")
    
    start_value = cerebro.broker.getvalue()
    print(f"[goldcombo] 起始资金: {start_value:.2f}")
    
    result = cerebro.run()
    final_value = cerebro.broker.getvalue()
    trades_count = len(result[0].tradehistory) if hasattr(result[0], 'tradehistory') else 0
    
    print(f"[goldcombo] 终值: {final_value:.2f}")
    print(f"[goldcombo] 累计盈亏: {final_value - start_value:.2f}")
    print(f"[goldcombo] 交易次数: {trades_count}")
    print(f"[goldcombo] ⚠️  本结果是 synthetic stub, 真实回测由 cron 8/13 01:30 启动。")
    
    # 写信号文件 (占位) 到 signals/goldcombo_<date>.json
    signals_dir = _ROOT / 'signals'
    out_path = signals_dir / f'goldcombo_{today_str}.json'
    write_signal_placeholder(
        out_path=out_path,
        today_str=today_str,
        initial_capital=initial_capital,
        period_years=period_years,
        final_value=final_value,
        trades_count=trades_count,
    )
    
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='goldcombo 黄金组合A 回测脚本')
    parser.add_argument('--period-years', type=int, default=2,
                        help='回测数据期年数 (2Y/5Y, 默认 2Y)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='输出目录 (默认 signals/)')
    parser.add_argument('--smoke-test', action='store_true',
                        help='smoke test: 仅验证 backtrader 框架可跑, 不写信号文件')
    args = parser.parse_args()
    
    if args.smoke_test:
        # 仅 verify 框架可跑
        try:
            bt = _import_backtrader()
            GoldComboStrategy = _build_strategy_class()
            print(f"[goldcombo] smoke test PASS: backtrader={bt.__version__}, GoldComboStrategy 可构造")
            return 0
        except Exception as e:
            print(f"[goldcombo] smoke test FAIL: {e}")
            return 1
    
    return run_stub_backtest(period_years=args.period_years, output_dir=args.output_dir)


if __name__ == '__main__':
    sys.exit(main())
