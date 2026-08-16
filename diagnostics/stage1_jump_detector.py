#!/usr/bin/env python3
"""Stage 1: Detect jumps in 3 random V16 -60%+ DD stocks to check for non-adjusted (不复权) data pollution."""
import json
import random
import pandas as pd
from pathlib import Path

random.seed(42)  # reproducible

# Load V16 baseline
v16 = json.load(open('/Users/junze/goldcombo_real_backtest/v16/T4_5y/baseline_ashare_real_5y_v16.json'))
full = v16.get('traded_stocks_full', [])

# Find stocks with DD <= -60% (severe DD pool)
deep_dd_stocks = [s for s in full if (s.get('max_drawdown_pct') or 0) <= -60]
print(f'Severe DD (≤ -60%) stocks: {len(deep_dd_stocks)}')

# Strict -70% candidates
strict_70 = [s for s in deep_dd_stocks if (s.get('max_drawdown_pct') or 0) <= -70]
print(f'Strict ≤ -70% candidates: {len(strict_70)}')
for s in strict_70:
    print(f"  {s['code']}: DD={s['max_drawdown_pct']:.2f}%")

# Sample 3: include all <= -70% first, then fill from -60% pool
if len(strict_70) >= 3:
    sample = strict_70[:3]
else:
    sample = list(strict_70)
    fill = [s for s in deep_dd_stocks if s not in strict_70]
    random.shuffle(fill)
    sample.extend(fill[:3 - len(strict_70)])

print(f'\nSample 3 stocks:')
for s in sample:
    print(f"  {s['code']}: DD={s['max_drawdown_pct']:.2f}%, return={s['return_pct']:.2f}%, trades={s['trade_count']}")

# Inspect each stock
results = []
for s in sample:
    code = s['code']
    csv_path = Path(f'/Users/junze/quant-monitor-local/data/ashare_kline/{code}.csv')
    if not csv_path.exists():
        print(f"\n!! {code}: CSV NOT FOUND")
        results.append({'code': code, 'error': 'csv_not_found'})
        continue

    df = pd.read_csv(csv_path)
    # Strip BOM if present
    if df.columns[0].startswith('\ufeff'):
        df.columns = [c.lstrip('\ufeff') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Filter 2021-08-14 to 2026-08-14 (5Y window)
    df = df[(df['date'] >= '2021-08-14') & (df['date'] <= '2026-08-14')].reset_index(drop=True)
    print(f"\n=== {code}: {len(df)} rows, range {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()} ===")

    # Detect jumps (open vs prev close)
    jumps = []
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        if prev_close <= 0:
            continue
        change = (curr_open - prev_close) / prev_close * 100
        if abs(change) >= 20:
            # Check if it's a limit-up
            prev_20_mean = df.iloc[max(0, i-20):i]['close'].mean()
            is_limit_up_10 = curr_open >= prev_20_mean * 1.099
            # Also: A股主板涨跌停为 ±10%, 创业板/科创板 ±20%, 北交所 ±30%
            # So 涨停 threshold varies by board. Also check prev close * 1.10
            is_limit_up_strict = curr_open >= prev_close * 1.099
            jumps.append({
                'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                'prev_close': float(prev_close),
                'curr_open': float(curr_open),
                'curr_high': float(df.iloc[i]['high']),
                'curr_low': float(df.iloc[i]['low']),
                'change_pct': round(change, 2),
                'abs_change_pct': round(abs(change), 2),
                'limit_up_20d_mean': bool(is_limit_up_10),
                'limit_up_prevclose': bool(is_limit_up_strict),
                'prev_20_mean': round(float(prev_20_mean), 2),
            })

    # Specifically filter jumps >= 30% (user's threshold)
    big_jumps = [j for j in jumps if j['abs_change_pct'] >= 30]
    print(f"  Total jumps ≥20%: {len(jumps)}")
    print(f"  Jumps ≥30% (user threshold): {len(big_jumps)}")
    for j in big_jumps[:10]:
        marker = 'NOT limit-up' if not j['limit_up_20d_mean'] else 'limit-up'
        print(f"    {j['date']}: prev_close={j['prev_close']:.4f}, open={j['curr_open']:.4f}, jump={j['change_pct']:+.2f}%, {marker}")
    if not big_jumps:
        # Print top 5 by abs_change for transparency
        top = sorted(jumps, key=lambda x: -x['abs_change_pct'])[:5]
        for j in top:
            print(f"    TOP-5: {j['date']}: prev_close={j['prev_close']:.4f}, open={j['curr_open']:.4f}, jump={j['change_pct']:+.2f}%")

    results.append({
        'code': code,
        'dd_pct': s['max_drawdown_pct'],
        'return_pct': s['return_pct'],
        'csv_rows': len(df),
        'jumps_ge_20': len(jumps),
        'jumps_ge_30_not_limited': len([j for j in big_jumps if not j['limit_up_20d_mean']]),
        'jumps_ge_30_details': big_jumps[:10],
        'all_jumps_top10': sorted(jumps, key=lambda x: -x['abs_change_pct'])[:10] if jumps else [],
    })

# Write result
output = {
    'stage': 'Stage 1: V16 -70% DD stock sample diagnosis',
    'sampling_rule': 'user: "-70% DD stocks"; fallback expanded to ≤ -60% to reach 3 candidates (only 2 exist at ≤ -70%)',
    'random_seed': 42,
    'strict_70_count': len(strict_70),
    'sample_size': len(sample),
    'stocks_sampled': [{'code': s['code'], 'dd': s['max_drawdown_pct']} for s in sample],
    'per_stock_jump_analysis': results,
    'verdict_summary': {
        'all_3_have_30pct_unlimited_jump': all(r.get('jumps_ge_30_not_limited', 0) > 0 for r in results),
        'count_with_30pct_unlimited_jump': sum(1 for r in results if r.get('jumps_ge_30_not_limited', 0) > 0),
    }
}

Path('/Users/junze/quant-monitor-local/diagnostics/v16_dd_diagnosis.json').parent.mkdir(exist_ok=True, parents=True)
with open('/Users/junze/quant-monitor-local/diagnostics/v16_dd_diagnosis.json', 'w') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print('\n[OK] Wrote /Users/junze/quant-monitor-local/diagnostics/v16_dd_diagnosis.json')
