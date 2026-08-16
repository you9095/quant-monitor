#!/usr/bin/env python3
"""Stage 1b: Broader diagnosis - sample more stocks, check close-to-close & high/low jumps."""
import json
import random
import pandas as pd
from pathlib import Path

random.seed(42)

v16 = json.load(open('/Users/junze/goldcombo_real_backtest/v16/T4_5y/baseline_ashare_real_5y_v16.json'))
full = v16.get('traded_stocks_full', [])

# Sample 10 from severe DD pool to broaden evidence
deep_dd_stocks = sorted(full, key=lambda s: s.get('max_drawdown_pct') or 0)[:10]
print('Top-10 worst DD stocks in V16:')
for s in deep_dd_stocks:
    print(f"  {s['code']}: DD={s['max_drawdown_pct']:.2f}%")

results = []
for s in deep_dd_stocks:
    code = s['code']
    csv_path = Path(f'/Users/junze/quant-monitor-local/data/ashare_kline/{code}.csv')
    if not csv_path.exists():
        continue

    df = pd.read_csv(csv_path)
    if df.columns[0].startswith('\ufeff'):
        df.columns = [c.lstrip('\ufeff') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= '2021-08-14') & (df['date'] <= '2026-08-14')].reset_index(drop=True)

    # Multiple jump metrics
    open_prevclose_jumps = []  # open[t] vs close[t-1]
    close_close_changes = []   # close[t] vs close[t-1]
    intraday_extremes = []     # |high - low| / low
    dividend_suspects = []     # close[t-1] vs open[t]: close >> open (downward jump)

    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        curr_open = df.iloc[i]['open']
        curr_close = df.iloc[i]['close']
        curr_high = df.iloc[i]['high']
        curr_low = df.iloc[i]['low']

        if prev_close <= 0:
            continue

        # 1. open vs prev_close
        c1 = (curr_open - prev_close) / prev_close * 100
        if abs(c1) >= 15:
            open_prevclose_jumps.append((df.iloc[i]['date'].strftime('%Y-%m-%d'),
                                          float(prev_close), float(curr_open), round(c1, 2)))

        # 2. close vs prev_close
        c2 = (curr_close - prev_close) / prev_close * 100
        close_close_changes.append((df.iloc[i]['date'].strftime('%Y-%m-%d'),
                                     float(prev_close), float(curr_close), round(c2, 2)))

        # 3. intraday extreme
        if curr_low > 0:
            r = (curr_high - curr_low) / curr_low * 100
            intraday_extremes.append((df.iloc[i]['date'].strftime('%Y-%m-%d'),
                                       float(curr_high), float(curr_low), round(r, 2)))

        # 4. dividend suspect: prev_close stable, then open[t] << prev_close (downward jump)
        # A dividend payout is usually 1-5% so > 15% is suspicious
        if c1 < -15:
            dividend_suspects.append((df.iloc[i]['date'].strftime('%Y-%m-%d'),
                                      float(prev_close), float(curr_open), round(c1, 2)))

    # Sort by absolute size
    open_prevclose_jumps.sort(key=lambda x: -abs(x[3]))
    dividend_suspects.sort(key=lambda x: x[3])

    # Look for non-A-share-prefix codes (688, 300, 8, 4 prefixes often = STAR/ChiNext/BSE)
    prefix = code[:3]
    board = 'main_60/00' if prefix.startswith('60') or prefix.startswith('00') else \
            'STAR_688' if prefix.startswith('688') else \
            'ChiNext_30' if prefix.startswith('30') else \
            'BSE_8/4' if prefix.startswith('8') or prefix.startswith('4') else 'other'

    results.append({
        'code': code,
        'board_type': board,
        'dd_pct': s['max_drawdown_pct'],
        'rows': len(df),
        'price_start_2021': float(df.iloc[0]['close']),
        'price_end_2026': float(df.iloc[-1]['close']),
        'price_min_5y': float(df['close'].min()),
        'price_max_5y': float(df['close'].max()),
        'open_prevclose_jumps_ge15': len(open_prevclose_jumps),
        'open_prevclose_jumps_top5': open_prevclose_jumps[:5],
        'downward_jumps_gt15pct': len(dividend_suspects),
        'downward_jumps_top5': dividend_suspects[:5],
        'biggest_intraday_range_pct': max([x[3] for x in intraday_extremes]) if intraday_extremes else 0,
    })

    print(f"\n=== {code} ({board}) ===")
    print(f"  Price 2021-08: {results[-1]['price_start_2021']:.4f} → 2026-08: {results[-1]['price_end_2026']:.4f}")
    print(f"  Price min/max 5Y: {results[-1]['price_min_5y']:.4f} / {results[-1]['price_max_5y']:.4f}")
    print(f"  Open vs prev_close jumps ≥15%: {len(open_prevclose_jumps)}")
    for j in open_prevclose_jumps[:3]:
        print(f"    {j[0]}: prev={j[1]:.4f} → open={j[2]:.4f} ({j[3]:+.2f}%)")
    print(f"  Downward jumps (< -15%): {len(dividend_suspects)}")
    for j in dividend_suspects[:3]:
        print(f"    {j[0]}: prev={j[1]:.4f} → open={j[2]:.4f} ({j[3]:+.2f}%)")

# Save
out_path = Path('/Users/junze/quant-monitor-local/diagnostics/v16_extended_dd_diagnosis.json')
with open(out_path, 'w') as f:
    json.dump({
        'stage': 'Stage 1b: extended diagnosis - top-10 worst DD stocks',
        'random_seed': 42,
        'samples': results,
        'summary': {
            'total_stocks_with_jumps_ge_15_open_prevclose': sum(r['open_prevclose_jumps_ge15'] for r in results),
            'max_intraday_range_pct': max((r['biggest_intraday_range_pct'] for r in results), default=0),
        },
    }, f, indent=2, ensure_ascii=False)
print(f"\n[OK] Wrote {out_path}")
