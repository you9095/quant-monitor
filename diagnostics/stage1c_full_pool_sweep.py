#!/usr/bin/env python3
"""Stage 1c: Full pool sweep - check ALL 1950 stocks for any 30%+ unlimitted jumps."""
import json
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

def check_stock(code, csv_dir='/Users/junze/quant-monitor-local/data/ashare_kline'):
    csv_path = Path(csv_dir) / f'{code}.csv'
    if not csv_path.exists():
        return code, {'error': 'not_found'}
    try:
        df = pd.read_csv(csv_path)
        if df.columns[0].startswith('\ufeff'):
            df.columns = [c.lstrip('\ufeff') for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df = df[(df['date'] >= '2021-08-14') & (df['date'] <= '2026-08-14')].reset_index(drop=True)

        jumps_found = []
        for i in range(1, len(df)):
            prev_close = df.iloc[i-1]['close']
            curr_open = df.iloc[i]['open']
            if prev_close <= 0:
                continue
            change = (curr_open - prev_close) / prev_close * 100
            if abs(change) >= 30:  # user threshold
                jumps_found.append({
                    'date': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                    'prev_close': float(prev_close),
                    'curr_open': float(curr_open),
                    'change_pct': round(change, 2),
                })

        return code, {
            'rows': len(df),
            'jumps_ge_30': len(jumps_found),
            'first_jumps': jumps_found[:5],
        }
    except Exception as e:
        return code, {'error': str(e)[:100]}


if __name__ == '__main__':
    # Load pool
    pool_files = [
        '/Users/junze/goldcombo_real_backtest/v9/T2_pool/ashare_pool.json',
    ]

    pool = set()
    for pf in pool_files:
        try:
            data = json.load(open(pf))
            if isinstance(data, list):
                for x in data:
                    code = x.get('code') if isinstance(x, dict) else x
                    if code:
                        pool.add(str(code).zfill(6))
        except Exception as e:
            print(f"Could not load {pf}: {e}")

    # Get all CSVs in dir as well
    csv_dir = Path('/Users/junze/quant-monitor-local/data/ashare_kline')
    for p in csv_dir.glob('*.csv'):
        pool.add(p.stem)

    pool_list = sorted(pool)
    print(f'Pool size: {len(pool_list)}')

    suspicious = []
    not_found = []
    errors = []
    clean_count = 0
    checked = 0

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(check_stock, code): code for code in pool_list}
        for fut in as_completed(futures):
            code, result = fut.result()
            checked += 1
            if 'error' in result:
                if result['error'] == 'not_found':
                    not_found.append(code)
                else:
                    errors.append((code, result['error']))
            elif result['jumps_ge_30'] > 0:
                suspicious.append((code, result))
            else:
                clean_count += 1

            if checked % 200 == 0:
                print(f'  checked={checked}/{len(pool_list)}, suspicious={len(suspicious)}, clean={clean_count}')

    print(f'\n=== Stage 1c full-pool sweep ===')
    print(f'Pool total: {len(pool_list)}')
    print(f'Clean (no jumps ≥30%): {clean_count}')
    print(f'Suspicious (≥1 jump ≥30%): {len(suspicious)}')
    print(f'Not found (no CSV): {len(not_found)}')
    print(f'Errors: {len(errors)}')
    if suspicious:
        print('\nFirst 20 suspicious:')
        for code, r in suspicious[:20]:
            print(f'  {code}: {r["jumps_ge_30"]} jumps')
            for j in r['first_jumps'][:3]:
                print(f'    {j["date"]}: {j["prev_close"]:.4f} → {j["curr_open"]:.4f} ({j["change_pct"]:+.2f}%)')

    out = {
        'stage': 'Stage 1c: full pool sweep',
        'pool_size': len(pool_list),
        'clean_count': clean_count,
        'suspicious_count': len(suspicious),
        'not_found_count': len(not_found),
        'error_count': len(errors),
        'suspicious_stocks': [{'code': c, **r} for c, r in suspicious],
        'verdict': 'no_pollution' if len(suspicious) == 0 else 'pollution_found',
    }
    out_path = Path('/Users/junze/quant-monitor-local/diagnostics/v16_full_pool_sweep.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f'\n[OK] Wrote {out_path}')
    sys.exit(0)
