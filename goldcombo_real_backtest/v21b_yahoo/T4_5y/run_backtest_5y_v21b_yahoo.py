"""
V21b 5 ETF 5Y 真实回测 (雅虎/通联数据源) — 用户原话硬约束版本
- 数据源纠正: 雅虎/通联 (不是 akshare)
- 窗口锁死: 2021-08-14 ~ 2026-08-14
- 收益算法: 初始资金 vs 最终资金的差额百分比 (组合层面)
- V21b 类: GoldComboV21b_AssetRot (trail_sl=0.20 锁死), 5 万本金

注: 2026-08-17 subagent #40 跑批时, 雅虎 (大陆 IP) 被屏蔽, tushare 基础版无 fund_daily/stock_basic
权限. 本脚本保留, 等待用户决策:
  (a) 升级 tushare pro 拿到 fund_daily 权限, 或
  (b) 提供可访问 Yahoo Finance 的网络出口
"""
import sys, json, time
from pathlib import Path
import pandas as pd
import backtrader as bt

# 用户原话硬约束
ETFS = ['510300', '588000', '512000', '159915', '518880']
DATA_WINDOW_START = '2021-08-14'  # 用户原话锁死
DATA_WINDOW_END = '2026-08-14'    # 用户原话锁死
INITIAL_CAPITAL_PER_ETF = 50000.0  # 用户原话硬约束

BASE_DIR = Path('/Users/junze/quant-monitor-local')
V21B_STRATEGY_PATH = BASE_DIR / 'strategies/goldcombo/goldcombo_strategy_ashare_v21b.py'

OUT_DIR = Path('/Users/junze/goldcombo_real_backtest/v21b_yahoo')
OUT_T4 = OUT_DIR / 'T4_5y'
OUT_T4.mkdir(parents=True, exist_ok=True)
OUT_YAHOO = BASE_DIR / 'data/v21b_etf_yahoo'
OUT_TUSHARE = BASE_DIR / 'data/v21b_etf_tushare'

# 数据源优先级: 雅虎 > 通联
def find_data_file(code):
    candidates = [
        (OUT_YAHOO / f'{code}.csv', 'yahoo'),
        (OUT_TUSHARE / f'{code}.csv', 'tushare'),
    ]
    for f, src in candidates:
        if f.exists():
            return f, src
    return None, None


def normalize_df(path):
    df = pd.read_csv(path)
    # 雅虎/通联/akshare/旧版 各种列名兼容
    if 'trade_date' in df.columns and 'date' not in df.columns:
        df = df.rename(columns={'trade_date': 'date'})
    if 'Date' in df.columns and 'date' not in df.columns:
        df = df.rename(columns={'Date': 'date'})
    if '日期' in df.columns and 'date' not in df.columns:
        df = df.rename(columns={'日期': 'date'})
    if 'Adj Close' in df.columns and 'close' not in df.columns:
        df['close'] = df['Adj Close']
    elif 'Close' in df.columns and 'close' not in df.columns:
        df['close'] = df['Close']
    df.columns = [c.lower() for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'] >= DATA_WINDOW_START) & (df['date'] <= DATA_WINDOW_END)]
    df = df.set_index('date').sort_index()
    keep = [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in df.columns]
    return df[keep]


# 加载 V21b 策略类
import importlib.util
spec = importlib.util.spec_from_file_location('goldcombo_v21b', str(V21B_STRATEGY_PATH))
v21b_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v21b_mod)
GoldComboV21b_AssetRot = v21b_mod.GoldComboV21b_AssetRot
print(f'✅ 加载 V21b 策略类: {GoldComboV21b_AssetRot.__name__}')
print(f'   trail_sl 默认值: {GoldComboV21b_AssetRot.params.trail_sl}')


def run_one(code):
    csv_path, source = find_data_file(code)
    if not csv_path:
        return None, f'数据文件不存在: 雅虎={OUT_YAHOO}/{code}.csv 通联={OUT_TUSHARE}/{code}.csv'
    try:
        df = normalize_df(csv_path)
    except Exception as e:
        return None, f'加载 {csv_path} 失败: {e}'
    if len(df) < 60:
        return None, f'数据期 < 60 行 ({len(df)})'
    actual_start = df.index.min().strftime('%Y-%m-%d')
    actual_end = df.index.max().strftime('%Y-%m-%d')
    window_ok_start = df.index.min() <= pd.Timestamp(DATA_WINDOW_START)
    if not window_ok_start:
        return None, f'实际起始 {actual_start} 晚于用户原话 {DATA_WINDOW_START}'

    print(f'\n=== {code} ({source}, {len(df)} 行, {actual_start} ~ {actual_end}) ===')
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GoldComboV21b_AssetRot, print_log=False)  # trail_sl=0.20 默认值锁死
    cerebro.broker.setcash(INITIAL_CAPITAL_PER_ETF)  # 用户原话 5万 锁死
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_slippage_perc(perc=0.003)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    result = cerebro.run()
    strat = result[0]
    start_value = INITIAL_CAPITAL_PER_ETF
    end_value = cerebro.broker.getvalue()
    return_pct = (end_value - start_value) / start_value * 100
    dd = strat.analyzers.drawdown.get_analysis()['max']['drawdown']
    ta = strat.analyzers.trades.get_analysis()
    trades = ta.get('total', {}).get('closed', 0)
    return {
        'code': code, 'source': source, 'data_rows': len(df),
        'data_start': actual_start, 'data_end': actual_end,
        'start_value': start_value, 'end_value': end_value,
        'return_pct': return_pct, 'worst_dd_pct': dd, 'trade_count': trades,
    }, None


def main():
    results = []
    blockers = []
    start_total = 0.0
    end_total = 0.0
    for code in ETFS:
        r, err = run_one(code)
        if err:
            print(f'FAIL {code}: {err}')
            blockers.append({'code': code, 'error': err})
            continue
        results.append(r)
        start_total += r['start_value']
        end_total += r['end_value']
        print(f'  起始 {r["start_value"]:.2f} | 最终 {r["end_value"]:.2f} | 收益 {r["return_pct"]:+.4f}%')
        print(f'  Worst DD {r["worst_dd_pct"]:.4f}% | 笔数 {r["trade_count"]}')

    if not results:
        print('\n=== BLOCKER ===')
        print('5 ETF 全部失败, 无法计算组合层面收益')
        print('失败明细:')
        for b in blockers:
            print(f'  {b["code"]}: {b["error"]}')
        return

    # 组合层面 (用户原话硬约束)
    total_return_pct = (end_total - start_total) / start_total * 100
    worst_dd_max = max(r['worst_dd_pct'] for r in results)
    total_trades = sum(r['trade_count'] for r in results)
    print(f'\n=== 组合层面 (5 ETF) ===')
    print(f'总初始资金: {start_total:.2f}')
    print(f'总最终资金: {end_total:.2f}')
    print(f'组合收益: {total_return_pct:+.4f}%')
    print(f'Worst DD (max): {worst_dd_max:.4f}%')
    print(f'总笔数: {total_trades}')

    baseline = {
        'strategy_id': 'goldcombo',
        'strategy_version': 'V21b_AssetRot (Yahoo/Tushare 数据源, 5 ETF 5Y, 组合层面)',
        'strategy_name': '黄金组合A · ETF 5只 5Y · V21b 资产轮动修正版 (雅虎/通联数据源)',
        'strategy_file': str(V21B_STRATEGY_PATH),
        'data_period': '5Y',
        'data_window': f'{DATA_WINDOW_START} ~ {DATA_WINDOW_END}',
        'pool_size': len(results),
        'pool_filter': 'ETF 5 只 (510300/588000/512000/159915/518880) + 雅虎/通联 5Y 日线',
        'engine': 'backtrader 1.9.78.123',
        'user_hard_constraints': [
            'trail_sl=0.20 锁死 (V21b 默认值)',
            '窗口锁死 2021-08-14 ~ 2026-08-14',
            '收益算法 = 组合层面 (总初始 vs 总最终差额百分比)',
            '数据源 = 雅虎/通联 (不是 akshare)',
            '5 万本金锁死 / ETF',
            '不准掺假数据 (转债本地无 2021 起数据, 仅跑 5 ETF)',
        ],
        'real_metrics': {
            'total_initial_capital': start_total,
            'total_final_capital': end_total,
            'total_return_pct': total_return_pct,
            'max_worst_dd_pct': worst_dd_max,
            'total_trade_count': total_trades,
            'pool_success_count': len(results),
        },
        'individual_stock_results': results,
        'honest_declaration': (
            'V21b_AssetRot 用户原版, 类名 GoldComboV21b_AssetRot, trail_sl=0.20 锁死. '
            '数据源纠正: 雅虎/通联 5Y 日线, 不准掺假数据. '
            '收益算法纠正: 组合层面 (总初始 vs 总最终), 严禁报标的平均收益. '
            '转债本地无 2021 起数据, 仅跑 5 ETF 验证框架.'
        ),
    }
    out = OUT_T4 / 'baseline_ashare_real_5y_v21b_yahoo.json'
    json.dump(baseline, open(out, 'w'), indent=2, ensure_ascii=False)
    print(f'\nbaseline 落盘: {out}')


if __name__ == '__main__':
    main()
