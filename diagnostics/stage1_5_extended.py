#!/usr/bin/env python3
"""Stage 1.5 扩大验证: 抽样 50 只股票做跳空检测, 验证是否真有不复权污染"""
import json
import random
from pathlib import Path

import pandas as pd

DATA_DIR = Path('/Users/junze/quant-monitor-local/data/ashare_kline')
OUTPUT_DIR = Path('/Users/junze/quant-monitor-local/diagnostics')

START = '2021-08-14'
END = '2026-08-14'

# 用 1950 只池的前 200 只做随机抽样 50 只
pool_file = '/Users/junze/goldcombo_real_backtest/v9/T2_pool/ashare_pool.json'
try:
    pool = json.load(open(pool_file))
except FileNotFoundError:
    # 备用: 从 csv 文件名抽
    all_csv = sorted([f.stem for f in DATA_DIR.glob('*.csv')])
    pool = all_csv

random.seed(42)
sample_pool = random.sample(pool, min(50, len(pool)))
print(f"抽样 {len(sample_pool)} 只股票: {sample_pool[:10]}...")

# 跳空统计
results = []
for code in sample_pool:
    f = DATA_DIR / f'{code}.csv'
    if not f.exists():
        continue
    df = pd.read_csv(f)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= START) & (df['date'] <= END)].reset_index(drop=True)

    if len(df) < 100:
        continue

    # 跳空检测
    max_jump = 0
    big_jumps = []  # >= 15% 的跳空
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        if prev_close == 0:
            continue
        change = (curr_open - prev_close) / prev_close * 100
        if abs(change) > abs(max_jump):
            max_jump = change
        if abs(change) >= 15:
            big_jumps.append({
                'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                'prev_close': float(prev_close),
                'curr_open': float(curr_open),
                'change_pct': float(change),
            })

    results.append({
        'code': code,
        'max_jump_pct': float(max_jump),
        'big_jump_count': len(big_jumps),
        'big_jumps': big_jumps[:5],
        'price_min': float(df['close'].min()),
        'price_max': float(df['close'].max()),
    })

# 排序: 最大跳空幅度
results_sorted = sorted(results, key=lambda x: abs(x['max_jump_pct']), reverse=True)
print(f"\n{'='*80}")
print("最大跳空 Top 20:")
for r in results_sorted[:20]:
    flag = "⚠️" if abs(r['max_jump_pct']) >= 25 else "  "
    print(f"  {flag} {r['code']}: max_jump={r['max_jump_pct']:+.2f}%, "
          f"big_jumps(>=15%)={r['big_jump_count']}, price_range=[{r['price_min']:.2f}, {r['price_max']:.2f}]")

# 统计
total_big_jumps = sum(r['big_jump_count'] for r in results)
print(f"\n{'='*80}")
print(f"50 只抽样统计:")
print(f"  总跳空 >= 15% 事件: {total_big_jumps}")
print(f"  最大跳空幅度: {results_sorted[0]['max_jump_pct']:+.2f}% ({results_sorted[0]['code']})")
print(f"  跳空 >= 25% 股票数: {sum(1 for r in results if abs(r['max_jump_pct']) >= 25)}")
print(f"  跳空 >= 30% 股票数: {sum(1 for r in results if abs(r['max_jump_pct']) >= 30)}")
print(f"{'='*80}")

with open(OUTPUT_DIR / 'v16_50sample_jumps.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# 关键判据: 主板股票日间跳空正常情况下不会 ≥10% (除涨停板)
# 涨跌停 ±10% 才有 ~10% 跳空
# 如果有股票出现 ≥25% 跳空且未涨停, 才是真正的不复权污染
print("\n⚠️ 如果抽样中发现 ≥25% 跳空且不涨停事件, 才是真污染信号")
print("用户原话判据: 跳空 ≥ 30% 且不涨停 ≥ 3 个事件 → 证实污染")

# 检查是否有 ≥30% 跳空
extreme_jumps = [r for r in results if abs(r['max_jump_pct']) >= 30]
print(f"\n≥ 30% 跳空股票数: {len(extreme_jumps)}")
for r in extreme_jumps:
    print(f"  {r['code']}: {r['max_jump_pct']:+.2f}%")