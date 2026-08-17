#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股池数据质量过滤 - 修复版
- 修复 bug: 旧脚本 apply_data_quality_filter() 找中文列名 '成交额',
  但下载时已 rename 为 'turnover' (与 ETF CSV 统一), 导致 0 通过.
- 用法: 跑在已下载的 2033 CSV 上, 输出真实 passed/rejected 列表.
"""
import os
import sys
import json
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('fix_filter')

DATA_DIR = Path('/Users/junze/quant-monitor-local/data')
KLINE_DIR = DATA_DIR / 'ashare_kline'
POOL_FILE = DATA_DIR / 'ashare_pool.json'

MIN_ROWS_5Y = 1000
MIN_AVG_TURNOVER = 1e7  # 1000 万/日

# 候选代码池: 从已下载的 2033 CSV 中识别 (因为原 pool 文件已被清空)
def collect_existing_codes() -> list:
    return sorted([f.stem for f in KLINE_DIR.glob('*.csv')])

def apply_fixed_filter(codes: list, pd) -> dict:
    """修复版: 使用英文列名 'turnover' (pd 模块显式传入避免未导入错误)"""
    import pandas as _pd  # local alias
    passed = []
    rejected_min_rows = []
    rejected_turnover = []
    err_codes = []
    for code in codes:
        p = KLINE_DIR / f'{code}.csv'
        try:
            df = _pd.read_csv(p)
            # 行数检查
            if len(df) < MIN_ROWS_5Y:
                rejected_min_rows.append({'code': code, 'rows': len(df)})
                continue
            # 找英文 turnover 列 (修复点)
            if 'turnover' not in df.columns:
                err_codes.append({'code': code, 'reason': 'no_turnover_col'})
                continue
            avg_turnover = df['turnover'].mean()
            if _pd.isna(avg_turnover):
                err_codes.append({'code': code, 'reason': 'turnover_nan'})
                continue
            if avg_turnover < MIN_AVG_TURNOVER:
                rejected_turnover.append({'code': code, 'avg_turnover': round(float(avg_turnover), 2)})
                continue
            passed.append(code)
        except Exception as e:
            err_codes.append({'code': code, 'reason': str(e)[:80]})
    return {
        'passed_codes': passed,
        'passed_count': len(passed),
        'rejected_min_rows': rejected_min_rows,
        'rejected_min_rows_count': len(rejected_min_rows),
        'rejected_turnover': rejected_turnover,
        'rejected_turnover_count': len(rejected_turnover),
        'err_codes': err_codes,
        'err_count': len(err_codes),
    }


def main():
    import pandas as pd  # 延后 import, 让 logger 先打印
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info('=' * 60)
    logger.info('修复版数据质量过滤 (英文 turnover 列)')
    logger.info('=' * 60)
    codes = collect_existing_codes()
    logger.info(f'已下载 CSV: {len(codes)} 个')

    t0 = time.time()
    result = apply_fixed_filter(codes, pd)
    elapsed = time.time() - t0
    logger.info(f'过滤完成: passed={result["passed_count"]} '
                f'min_rows_reject={result["rejected_min_rows_count"]} '
                f'turnover_reject={result["rejected_turnover_count"]} '
                f'err={result["err_count"]} 耗时={elapsed:.1f}s')

    # 落 filter summary
    out = {
        'filter_logic': 'rows >= 1000 AND avg(turnover) >= 1e7 (5Y 完整 + 流动性)',
        'min_rows': MIN_ROWS_5Y,
        'min_avg_turnover': MIN_AVG_TURNOVER,
        'data_period': '2021-08-13 ~ 2026-08-13',
        'source_csv_count': len(codes),
        'filter_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'fix_note': '2026-08-13 修复: apply_data_quality_filter 旧版用 成交额 (中文) 找列, 但 CSV 已经是 turnover (英文) - 0 通过根因',
        **result,
    }
    out_path = DATA_DIR / 'ashare_filter_summary.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logger.info(f'filter summary 写入: {out_path}')

    # 重建 pool: 仅保留 passed, 并附 name (从 akshare 取; 失败时用 code 代替)
    logger.info('重建 ashare_pool.json (passed codes only)')
    try:
        import akshare as ak
        all_codes_df = ak.stock_info_a_code_name()
        name_map = dict(zip(all_codes_df['code'], all_codes_df['name']))
    except Exception as e:
        logger.warning(f'无法从 akshare 取 name ({e}), 用 code 代替')
        name_map = {}
    passed_pool = [{'code': c, 'name': name_map.get(c, c)} for c in result['passed_codes']]
    pool = {
        'total_all_a': len(codes) + 1160,  # 3193 = 2033 ok + 1160 skipped
        'filtered_ashare_count': len(passed_pool),
        'excluded_breakdown': {
            'kechuang_688': 0,  # 不在主池
            'chuangye_30x': 0,
            'beizheng_8_4': 0,
        },
        'pool': passed_pool,
        'filter_logic': '主池 (60xxxx+00xxxx非30x) + rows≥1000 + avg_turnover≥1e7 (修复版)',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data_period': {'start': '2021-08-13', 'end': '2026-08-13'},
        'source': 'akshare.stock_info_a_code_name() (name lookup) + data/ashare_kline/ (K线验证)',
        'data_quality_filter': {
            'min_rows': MIN_ROWS_5Y,
            'min_avg_turnover': MIN_AVG_TURNOVER,
            'passed_count': result['passed_count'],
            'rejected_min_rows': result['rejected_min_rows_count'],
            'rejected_turnover': result['rejected_turnover_count'],
            'err_count': result['err_count'],
            'filter_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'fix_note': '2026-08-13: 旧 filter 用 成交额 中文列名, 修复为 turnover 英文列名',
        },
        'unresolved_codes_count': 1160,  # 待 eastmoney 恢复后补下
        'unresolved_note': 'eastmoney 当前 SSL EOF 错误, 1160 skipped 暂未补; passed 已基于 2033 已下 CSV',
    }
    with open(POOL_FILE, 'w', encoding='utf-8') as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    logger.info(f'pool 写入: {POOL_FILE} (passed={pool["filtered_ashare_count"]})')

    return 0


if __name__ == '__main__':
    sys.exit(main())
