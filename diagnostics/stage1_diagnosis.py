#!/usr/bin/env python3
"""Stage 1: V16 -70% DD 股票抽样诊断 + 不复权数据污染检测"""
import json
import random
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path('/Users/junze/quant-monitor-local/data/ashare_kline')
OUTPUT_DIR = Path('/Users/junze/quant-monitor-local/diagnostics')
OUTPUT_DIR.mkdir(exist_ok=True)

START = '2021-08-14'
END = '2026-08-14'

# Step 1: 从 V16 baseline 提取所有 DD <= -70% 股票
baseline = json.load(open('/Users/junze/goldcombo_real_backtest/v16/T4_5y/baseline_ashare_real_5y_v16.json'))
full_results = baseline.get('traded_stocks_full', [])
print(f"V16 traded_stocks_full 总数: {len(full_results)}")

deep_dd = [s for s in full_results if s.get('max_drawdown_pct', 0) <= -70]
deep_dd_sorted = sorted(deep_dd, key=lambda x: x['max_drawdown_pct'])
print(f"DD ≤ -70% 股票数: {len(deep_dd)}")
for s in deep_dd_sorted:
    print(f"  {s['code']}: DD={s['max_drawdown_pct']:.2f}%, return={s['return_pct']:.2f}%")

# 用户原话要求 3 只抽样, 但只 2 只满足 ≤-70%, 补 1 只 ≤-60%
if len(deep_dd_sorted) < 3:
    print(f"\n⚠️ 只有 {len(deep_dd_sorted)} 只 ≤-70% DD, 扩大候选到 ≤-60% DD")
    deep_dd_sorted = sorted([s for s in full_results if s.get('max_drawdown_pct', 0) <= -60],
                            key=lambda x: x['max_drawdown_pct'])

# 抽样: 用 random.seed(42) 可复现
random.seed(42)
random.shuffle(deep_dd_sorted)
sample = deep_dd_sorted[:3]
sample_codes = [s['code'] for s in sample]
print(f"\n抽样 3 只 (random.seed(42) 可复现): {sample_codes}")

# Step 2: 跳空检测
print("\n" + "="*80)
print("跳空检测 (检测不复权污染信号)")
print("="*80)

jumps_report = []
for s in sample:
    code = s['code']
    df = pd.read_csv(DATA_DIR / f'{code}.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= START) & (df['date'] <= END)].reset_index(drop=True)

    jumps = []
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        change_pct = (curr_open - prev_close) / prev_close * 100

        if abs(change_pct) >= 20:  # 跳空 >= 20% 才可疑
            # 检查是否涨停 (主板 ±10%, 创业板/科创板 ±20%, 这里保守用 10%)
            prev_20_mean = df.iloc[max(0, i-20):i]['close'].mean()
            is_limit_up = curr_open >= prev_20_mean * 1.099

            # 前日变化 (除权除息通常前日 close 突然降)
            prev_change_pct = 0
            if i >= 2:
                prev_change_pct = (df.iloc[i-1]['close'] - df.iloc[i-2]['close']) / df.iloc[i-2]['close'] * 100

            jumps.append({
                'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                'prev_close': float(prev_close),
                'curr_open': float(curr_open),
                'change_pct': float(change_pct),
                'is_limit_up': bool(is_limit_up),
                'prev_change_pct': float(prev_change_pct),
            })

    jumps_report.append({
        'code': code,
        'worst_dd': s['max_drawdown_pct'],
        'final_return_pct': s['return_pct'],
        'jump_count': len(jumps),
        'jumps': jumps[:15],
    })
    print(f"\n{code}: V16 DD={s['max_drawdown_pct']:.2f}%, return={s['return_pct']:.2f}%")
    print(f"  5Y 跳空 >= 20% 次数: {len(jumps)}")
    for j in jumps[:10]:
        flag = "⚠️不涨停" if (not j['is_limit_up'] and abs(j['change_pct']) >= 20) else "✅涨停"
        print(f"  {j['date']}: prev_close={j['prev_close']:.2f}, open={j['curr_open']:.2f}, "
              f"跳空={j['change_pct']:+.2f}% {flag}")

# 保存
with open(OUTPUT_DIR / 'v16_deep_dd.json', 'w') as f:
    json.dump([{'code': s['code'], 'max_drawdown_pct': s['max_drawdown_pct'],
                'return_pct': s['return_pct']} for s in deep_dd_sorted], f, indent=2)

with open(OUTPUT_DIR / 'v16_jump_analysis.json', 'w') as f:
    json.dump(jumps_report, f, indent=2, ensure_ascii=False)

# Step 3: 判定污染
print("\n" + "="*80)
print("污染判定")
print("="*80)

pollution_signals = []
for r in jumps_report:
    for j in r['jumps']:
        # 严格: 跳空 >= 30% 且未涨停 → 不复权污染信号
        if abs(j['change_pct']) >= 30 and not j['is_limit_up']:
            pollution_signals.append({
                'code': r['code'],
                'date': j['date'],
                'jump_pct': j['change_pct'],
                'prev_close': j['prev_close'],
                'curr_open': j['curr_open'],
                'reason': f'跳空 {j["change_pct"]:+.2f}% 但未涨停 (主板股票)'
            })

print(f"\n严格判据 (跳空 >= 30% 且不涨停): {len(pollution_signals)} 个疑似事件")
for p in pollution_signals:
    print(f"  {p['code']} {p['date']}: {p['reason']}")

# 弱判据: 跳空 >= 20% 且不涨停 (任何主板股票跳空 20%+ 都不正常)
weak_signals = []
for r in jumps_report:
    for j in r['jumps']:
        if abs(j['change_pct']) >= 20 and not j['is_limit_up']:
            weak_signals.append({**p, 'code': r['code'], 'date': j['date']})

print(f"\n弱判据 (跳空 >= 20% 且不涨停): {len(weak_signals)} 个疑似事件")
for p in weak_signals:
    print(f"  {p['code']} {p['date']}: 跳空={p['jump_pct']:+.2f}%, prev_close={p['prev_close']:.2f}→open={p['curr_open']:.2f}")

# 保存结论
conclusion = {
    'sample_codes': sample_codes,
    'sample_jumps_count': [r['jump_count'] for r in jumps_report],
    'strict_pollution_events': len(pollution_signals),
    'weak_pollution_events': len(weak_signals),
    'pollution_signals': pollution_signals,
    'weak_signals': weak_signals,
    'verified': len(pollution_signals) >= 3,  # 用户原话 >=3 即证实污染
    'note': 'V16 整体 worst_dd=-73.49% 实际来自单股 000755 三特索道 (DD=-73.49%) 和 601007 金陵饭店 (DD=-72.35%)'
}
with open(OUTPUT_DIR / 'stage1_conclusion.json', 'w') as f:
    json.dump(conclusion, f, indent=2, ensure_ascii=False)

print(f"\n" + "="*80)
if len(pollution_signals) >= 3:
    print(f"⚠️  证实污染: {len(pollution_signals)} 个'跳空>=30% 不涨停'事件")
    print("结论: 1950 只 CSV 是不复权数据, 全部回测作废")
else:
    print(f"✅ 未证实严格污染 (仅 {len(pollution_signals)} 个 ≥30% 跳空不涨停事件)")
    if len(weak_signals) >= 3:
        print(f"⚠️ 但弱判据有 {len(weak_signals)} 个 ≥20% 跳空不涨停事件")
        print("结论: 数据有可疑信号但未达严格污染判据, 建议进一步核实")
    else:
        print("结论: 数据可信, 跳过 Stage 3-4")