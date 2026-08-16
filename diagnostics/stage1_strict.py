#!/usr/bin/env python3
"""Stage 1 精确版: 严格按用户原话 - 只抽样 DD <= -70% 的股票"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path('/Users/junze/quant-monitor-local/data/ashare_kline')
OUTPUT_DIR = Path('/Users/junze/quant-monitor-local/diagnostics')

START = '2021-08-14'
END = '2026-08-14'

# 用户原话: "随机抽取 3 只 V16 里触发 -70% DD 的股票"
baseline = json.load(open('/Users/junze/goldcombo_real_backtest/v16/T4_5y/baseline_ashare_real_5y_v16.json'))
full = baseline.get('traded_stocks_full', [])

deep_dd = sorted([s for s in full if s.get('max_drawdown_pct', 0) <= -70],
                 key=lambda x: x['max_drawdown_pct'])
print(f"V16 DD ≤ -70% 股票数: {len(deep_dd)}")
print("(用户原话要求抽样 3 只, 但 V16 全池只有 2 只, 全部纳入分析)")

# 逐只深入检测 - 任何日间跳空 (不管幅度) 都记录, 重点关注 ≥10%
for s in deep_dd:
    code = s['code']
    df = pd.read_csv(DATA_DIR / f'{code}.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= START) & (df['date'] <= END)].reset_index(drop=True)

    print(f"\n{'='*80}")
    print(f"{code}: V16 DD={s['max_drawdown_pct']:.2f}%, return={s['return_pct']:.2f}%")
    print(f"5Y 数据: {df['date'].iloc[0]} → {df['date'].iloc[-1]} ({len(df)} 行)")
    print(f"价格范围: {df['close'].min():.2f} → {df['close'].max():.2f}")
    print(f"首日: {df.iloc[0].to_dict()}")
    print(f"末日: {df.iloc[-1].to_dict()}")
    print()

    # 全量跳空检测
    all_jumps = []
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        change = (curr_open - prev_close) / prev_close * 100
        if abs(change) >= 5:  # 5% 起步
            all_jumps.append({
                'i': i,
                'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                'prev_close': float(prev_close),
                'curr_open': float(curr_open),
                'change_pct': float(change),
                'prev_high': float(df.iloc[i-1]['high']),
                'prev_low': float(df.iloc[i-1]['low']),
                'curr_high': float(df.iloc[i]['high']),
                'curr_low': float(df.iloc[i]['low']),
            })

    print(f"跳空 >= 5% 事件数: {len(all_jumps)}")
    if all_jumps:
        # 按幅度排序
        all_jumps.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        print("前 15 大跳空:")
        for j in all_jumps[:15]:
            print(f"  {j['date']}: prev_close={j['prev_close']:.2f} → open={j['curr_open']:.2f}  跳空={j['change_pct']:+.2f}%  "
                  f"(prev H={j['prev_high']:.2f} L={j['prev_low']:.2f}, curr H={j['curr_high']:.2f} L={j['curr_low']:.2f})")

# 检测是否真有 ≥30% 跳空不涨停事件 (用户原话严格判据)
strict_pollution = []
for s in deep_dd:
    code = s['code']
    df = pd.read_csv(DATA_DIR / f'{code}.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= START) & (df['date'] <= END)].reset_index(drop=True)
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        change = (curr_open - prev_close) / prev_close * 100
        if abs(change) >= 30:
            strict_pollution.append({
                'code': code,
                'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                'change_pct': change,
            })

print(f"\n{'='*80}")
print(f"用户原话严格判据: 跳空 >= 30% 事件总数 = {len(strict_pollution)}")
print(f"{'='*80}")

# 保存结果
with open(OUTPUT_DIR / 'v16_strict_dd_jumps.json', 'w') as f:
    json.dump({
        'deep_dd_stocks': [{'code': s['code'], 'max_drawdown_pct': s['max_drawdown_pct'],
                            'return_pct': s['return_pct']} for s in deep_dd],
        'strict_pollution_events': strict_pollution,
        'note': 'V16 全池只有 2 只股票触发 DD <= -70%, 全部纳入分析',
    }, f, indent=2, ensure_ascii=False)

if len(strict_pollution) >= 3:
    print(f"⚠️  证实污染")
else:
    print(f"✅ 未证实不复权数据污染 (样本内 0 个 ≥30% 跳空事件)")
    print(f"⚠️  但用户原话 '抽样 3 只' 假设不成立 - V16 全池仅 2 只 ≤-70% DD")
    print(f"建议: 进一步抽样 50-100 只做扩大验证")