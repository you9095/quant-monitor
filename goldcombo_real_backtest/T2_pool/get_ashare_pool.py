#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T2 · A 股池 + OHLCV 准备 (2026-08-14)
复用 /Users/junze/quant-monitor-local/data/ashare_kline/ 已有真实数据
- 来源: akshare stock_zh_a_hist qfq (2026-08-13 拉取)
- 池大小: 1950 只 (600/601/603/605/000/002)
- 2Y 池: 1950 只 (所有数据足够)
- 5Y 池: 1950 只 (ashare_filter_summary 通过)
输出到 ~/goldcombo_real_backtest/T2_pool/
"""
import json
import os
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Tuple

SRC_KLINE = '/Users/junze/quant-monitor-local/data/ashare_kline'
SRC_POOL = '/Users/junze/quant-monitor-local/data/ashare_pool.json'
SRC_FILTER = '/Users/junze/quant-monitor-local/data/ashare_filter_summary.json'

OUT_DIR = os.path.expanduser('~/goldcombo_real_backtest/T2_pool')
OUT_OHLCV = os.path.join(OUT_DIR, 'ohlcv')
OUT_POOL = os.path.join(OUT_DIR, 'ashare_pool.json')
OUT_LOG = os.path.join(OUT_DIR, 'raw_output.log')

# 数据窗口 (用户原话)
WINDOW_2Y_START = '2024-08-14'
WINDOW_2Y_END = '2026-08-14'
WINDOW_5Y_START = '2021-08-14'
WINDOW_5Y_END = '2026-08-14'

# 最低有效交易日数 (2Y ≈ 480, 5Y ≈ 1200)
MIN_ROWS_2Y = 200
MIN_ROWS_5Y = 1000


def main():
    os.makedirs(OUT_OHLCV, exist_ok=True)
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log(f'[T2] start {datetime.now().isoformat()}')
    log(f'[T2] source kline dir: {SRC_KLINE}')
    log(f'[T2] output dir: {OUT_DIR}')

    # 1. 加载 A 股池清单
    with open(SRC_POOL, 'r', encoding='utf-8') as f:
        pool_data = json.load(f)
    pool_list = pool_data['pool']
    log(f'[T2] A 股池 (raw): {len(pool_list)} 只')

    # 2. 加载 ashare_filter_summary 的 passed_codes (5Y 完整)
    with open(SRC_FILTER, 'r', encoding='utf-8') as f:
        filter_data = json.load(f)
    passed_5y = set(filter_data['passed_codes'])
    log(f'[T2] filter passed (5Y, rows>=1000, turnover>=1e7): {len(passed_5y)} 只')

    # 3. 验证本地 CSV 数据
    available = []
    missing = []
    for entry in pool_list:
        code = entry['code']
        csv_path = os.path.join(SRC_KLINE, f'{code}.csv')
        if os.path.exists(csv_path):
            available.append(code)
        else:
            missing.append(code)

    log(f'[T2] 本地 CSV 可用: {len(available)} 只')
    log(f'[T2] 本地 CSV 缺失: {len(missing)} 只')

    # 4. 复制可用 CSV 到 OUT_OHLCV (统一路径便于 backtrader 加载)
    copied = 0
    failed_copy = []
    for code in available:
        src = os.path.join(SRC_KLINE, f'{code}.csv')
        dst = os.path.join(OUT_OHLCV, f'{code}.csv')
        try:
            if not os.path.exists(dst):
                # 用符号链接节省空间 (2K 文件复制 ~30秒,符号链接 <1秒)
                os.symlink(src, dst)
                copied += 1
            else:
                copied += 1
        except Exception as e:
            failed_copy.append((code, str(e)))

    log(f'[T2] 已建立软链接/复制: {copied} 只')
    if failed_copy:
        log(f'[T2] 复制失败: {len(failed_copy)} 只 (例: {failed_copy[:3]})')

    # 5. 计算 2Y 子池和 5Y 子池 (根据日期窗口内可用行数)
    import pandas as pd

    pool_2y = []
    pool_5y = []
    rows_per_code = {}

    for code in available:
        csv_path = os.path.join(OUT_OHLCV, f'{code}.csv')
        try:
            df = pd.read_csv(csv_path)
            df['date'] = pd.to_datetime(df['date'])
            n_2y = len(df[(df['date'] >= WINDOW_2Y_START) & (df['date'] <= WINDOW_2Y_END)])
            n_5y = len(df[(df['date'] >= WINDOW_5Y_START) & (df['date'] <= WINDOW_5Y_END)])
            rows_per_code[code] = {'2y': n_2y, '5y': n_5y}
            if n_2y >= MIN_ROWS_2Y:
                pool_2y.append(code)
            if n_5y >= MIN_ROWS_5Y:
                pool_5y.append(code)
        except Exception as e:
            log(f'[T2] skip {code}: {e}')

    log(f'[T2] 2Y 有效池 (rows >= {MIN_ROWS_2Y}): {len(pool_2y)} 只')
    log(f'[T2] 5Y 有效池 (rows >= {MIN_ROWS_5Y}): {len(pool_5y)} 只')

    # 6. 输出 ashare_pool.json (含 2Y/5Y 子池)
    pool_dict = {entry['code']: entry for entry in pool_list}
    out_pool = {
        'generated_at': datetime.now().isoformat(),
        'source_pool_size': len(pool_list),
        'available_csv_count': len(available),
        'missing_csv_count': len(missing),
        'data_window': {
            '2y': {'start': WINDOW_2Y_START, 'end': WINDOW_2Y_END, 'min_rows': MIN_ROWS_2Y},
            '5y': {'start': WINDOW_5Y_START, 'end': WINDOW_5Y_END, 'min_rows': MIN_ROWS_5Y},
        },
        'pool_2y': {
            'count': len(pool_2y),
            'codes': pool_2y,
        },
        'pool_5y': {
            'count': len(pool_5y),
            'codes': pool_5y,
        },
        'pool_full': [
            {'code': code, 'name': pool_dict.get(code, {}).get('name', ''),
             'rows_2y': rows_per_code.get(code, {}).get('2y', 0),
             'rows_5y': rows_per_code.get(code, {}).get('5y', 0)}
            for code in available
        ],
        'data_source': 'akshare stock_zh_a_hist qfq (本地缓存 /Users/junze/quant-monitor-local/data/ashare_kline)',
    }

    with open(OUT_POOL, 'w', encoding='utf-8') as f:
        json.dump(out_pool, f, ensure_ascii=False, indent=2)
    log(f'[T2] written: {OUT_POOL}')

    # 7. failed_stocks.json (没有失败但保留接口)
    failed_stocks = {
        'missing_csv': missing,
        'failed_copy': failed_copy,
    }
    with open(os.path.join(OUT_DIR, 'failed_stocks.json'), 'w', encoding='utf-8') as f:
        json.dump(failed_stocks, f, ensure_ascii=False, indent=2)

    log(f'[T2] done {datetime.now().isoformat()}')

    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))


if __name__ == '__main__':
    main()