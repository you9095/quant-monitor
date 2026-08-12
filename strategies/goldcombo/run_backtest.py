#!/usr/bin/env python3
"""
goldcombo · 黄金组合A 回测入口 (策略目录独立版)

M01 集成阶段 (2026-08-12): 占位 stub, 真实回测由 cron 8/13 01:30 启动后调用
scripts/run_goldcombo_backtest.py (根目录版) 跑出 2Y/5Y 数据。

本文件供 strategies/goldcombo/ 目录独立运行使用, 适合开发期 / 调试 / 单元测试。

真实数据: backtrader 默认从 yfinance / akshare / 本地 CSV 获取。本 stub 用
synthetic pandas DataFrame (10 天 EMA 自相似) 保证接口可跑, 跑出 0 持仓
+0 盈亏占位结果。**禁止用 mockData 蒙混占位** (用户 P0 硬约束)。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 允许从 strategies/goldcombo/ 目录独立运行
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))


# === backtrader 框架 (与 scripts/run_goldcombo_backtest.py 1:1 一致) ===
def _import_backtrader():
    """backtrader 可选依赖, 没有时给清晰错误"""
    try:
        import backtrader as bt
        return bt
    except ImportError as e:
        raise SystemExit(
            f"[goldcombo] backtrader 未安装: {e}\n"
            "  安装: pip install backtrader  或  uv add backtrader\n"
            "  本策略骨架依赖 backtrader,无 backtrader 无法跑回测。"
        )


def build_synthetic_data(bt, period_days: int = 250):
    """
    用 backtrader feed 构造一段可跑的回测数据 (占位, 非真实行情)。
    真实回测 cron 8/13 启动后必须替换为真实数据源 (yfinance / akshare / tushare)。
    """
    import pandas as pd
    import numpy as np

    np.random.seed(42)  # 可复现
    end = datetime(2026, 8, 12)
    start = end - timedelta(days=period_days)
    dates = pd.date_range(start, end, freq='D')
    n = len(dates)

    # 几何布朗运动 + 轻微均值回归 (占位)
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

    data = bt.feeds.PandasData(dataname=df)
    return data


def main(period_days: int = 250, output_dir: str | None = None) -> int:
    """独立回测入口 (供开发/调试用, 真实回测走 scripts/run_goldcombo_backtest.py)"""
    bt = _import_backtrader()

    # 从 strategies/goldcombo/../scripts/ 加载 GoldComboStrategy 类
    sys.path.insert(0, str(_ROOT / 'scripts'))
    try:
        from run_goldcombo_backtest import GoldComboStrategy
    except ImportError as e:
        raise SystemExit(
            f"[goldcombo] 无法从 scripts/run_goldcombo_backtest.py 导入 GoldComboStrategy: {e}\n"
            "  请确认 scripts/run_goldcombo_backtest.py 已存在且可 import。"
        )

    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboStrategy)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.001)

    data = build_synthetic_data(bt, period_days)
    cerebro.adddata(data)

    start_value = cerebro.broker.getvalue()
    print(f'[goldcombo stub] 起始资金: {start_value:.2f}')
    print(f'[goldcombo stub] 数据期: {period_days} 天 (synthetic, 非真实行情)')
    print(f'[goldcombo stub] 真实回测请用 scripts/run_goldcombo_backtest.py')
    result = cerebro.run()
    final_value = cerebro.broker.getvalue()
    print(f'[goldcombo stub] 终值: {final_value:.2f}')
    print(f'[goldcombo stub] 累计盈亏: {final_value - start_value:.2f}')
    print(f'[goldcombo stub] ⚠️  本结果是 synthetic placeholder,不是真实回测。')
    return 0


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='goldcombo 独立回测 stub')
    ap.add_argument('--period-days', type=int, default=250, help='回测数据期天数 (默认 250)')
    args = ap.parse_args()
    sys.exit(main(period_days=args.period_days))
