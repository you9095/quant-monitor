#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股池 K 线批量下载脚本
- 数据源: akshare.stock_zh_a_hist (前复权 qfq)
- 数据期: 2021-08-13 ~ 2026-08-13 (5Y)
- 输出: ~/quant-monitor-local/data/ashare_kline/{code}.csv
- 跳过: 已存在的 (缓存复用)
- 重试: 单只最多 2 次, 失败入 skipped 名单
- 并发: 2 (避免 eastmoney 限流)
"""
import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 关键: 清理代理 env 避免 akshare 走 ClashX fake-IP 失败
for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']:
    os.environ.pop(k, None)

import akshare as ak
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('download')

# akshare 列名 → 英文列名映射 (与 ETF CSV 格式对齐)
COLUMN_MAP = {
    '日期': 'date', '股票代码': 'code', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low', '成交量': 'volume', '成交额': 'turnover',
    '振幅': 'amplitude', '涨跌幅': 'change_pct', '涨跌额': 'change_amt',
    '换手率': 'turnover_rate',
}

# ==================== 配置 ====================
DATA_DIR = Path('/Users/junze/quant-monitor-local/data')
KLINE_DIR = DATA_DIR / 'ashare_kline'
POOL_FILE = DATA_DIR / 'ashare_pool.json'

START_DATE = '20210813'
END_DATE = '20260813'
START_DATE_HUMAN = '2021-08-13'
END_DATE_HUMAN = '2026-08-13'

MIN_ROWS_5Y = 1000  # 5Y 数据期至少 1000 行
MIN_AVG_TURNOVER = 1e7  # 平均成交额 ≥ 1000 万/日 (1e7 元)


# ==================== 过滤 A 股池 ====================
def filter_ashare_pool() -> dict:
    """过滤 A 股池: 排除 688/30x/8xx/4xx, 保留 60xxxx + 00xxxx (非 300/301)"""
    logger.info('加载全 A 股代码清单...')
    df = ak.stock_info_a_code_name()
    logger.info(f'全 A 股总数: {len(df)}')

    # 过滤逻辑
    def is_ashare_main(code: str) -> bool:
        # 沪 A 主板: 60xxxx (6 位, 以 60 开头, 但不是 688)
        if code.startswith('60') and not code.startswith('688'):
            return True
        # 深 A 主板: 00xxxx (6 位, 以 00 开头, 但不是 300/301)
        if code.startswith('00') and not code.startswith('300') and not code.startswith('301'):
            return True
        return False

    filtered_df = df[df['code'].apply(is_ashare_main)].reset_index(drop=True)
    excluded_kechuang = len(df[df['code'].str.startswith('688')])
    excluded_chuangye = len(df[df['code'].str.startswith(('300', '301'))])
    excluded_beizheng = len(df[df['code'].str.startswith(('8', '4'))])
    logger.info(f'过滤后 A 股池: {len(filtered_df)} 只')
    logger.info(f'  排除科创板 688: {excluded_kechuang}')
    logger.info(f'  排除创业板 30x: {excluded_chuangye}')
    logger.info(f'  排除北证 8/4: {excluded_beizheng}')

    return {
        'total_all_a': len(df),
        'filtered_ashare_count': len(filtered_df),
        'excluded_breakdown': {
            'kechuang_688': excluded_kechuang,
            'chuangye_30x': excluded_chuangye,
            'beizheng_8_4': excluded_beizheng,
        },
        'pool': [{'code': row['code'], 'name': row['name']} for _, row in filtered_df.iterrows()],
        'filter_logic': '保留 60xxxx (沪A主板) + 00xxxx (深A主板, 非300/301), 排除 688/30x/8xx/4xx',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }


# ==================== 单只下载 ====================
def fetch_one(code: str, max_retry: int = 3) -> dict:
    """单只 A 股下载, 返回 {'code', 'rows', 'elapsed', 'error'}"""
    csv_path = KLINE_DIR / f'{code}.csv'
    if csv_path.exists():
        # 缓存命中, 仅验证行数
        try:
            df = pd.read_csv(csv_path)
            return {'code': code, 'rows': len(df), 'cached': True, 'elapsed': 0.0, 'error': None}
        except Exception:
            csv_path.unlink(missing_ok=True)

    last_error = None
    for attempt in range(1, max_retry + 1):
        start = time.time()
        try:
            df = ak.stock_zh_a_hist(
                symbol=code, period='daily',
                start_date=START_DATE, end_date=END_DATE, adjust='qfq'
            )
            elapsed = time.time() - start
            if df is None or len(df) == 0:
                last_error = 'empty_response'
                time.sleep(1.0)
                continue
            # 转换列名为英文 (统一 ETF 格式)
            df = df.rename(columns=COLUMN_MAP)
            # 仅保留核心 6 列 + 成交额 (供流动性过滤)
            keep_cols = [c for c in ['date', 'code', 'open', 'close', 'high', 'low', 'volume', 'turnover'] if c in df.columns]
            df = df[keep_cols]
            # 保存 CSV
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            return {'code': code, 'rows': len(df), 'cached': False, 'elapsed': elapsed, 'error': None}
        except Exception as e:
            last_error = f'{type(e).__name__}: {str(e)[:80]}'
            logger.debug(f'  {code} attempt {attempt} FAIL: {last_error}')
            time.sleep(1.0 + attempt * 0.5)  # 递增退避
    return {'code': code, 'rows': 0, 'cached': False, 'elapsed': 0.0, 'error': last_error}


# ==================== 批量下载 ====================
def download_all(codes: list, max_workers: int = 2) -> dict:
    """并发下载所有 A 股 K 线"""
    KLINE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f'开始下载 {len(codes)} 只 A 股, 并发 {max_workers}')
    results = []
    skipped = []
    t_start = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_one, code): code for code in codes}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            completed += 1
            if r['error']:
                skipped.append(r['code'])
            if completed % 50 == 0 or completed == len(codes):
                elapsed = time.time() - t_start
                rate = completed / elapsed
                eta = (len(codes) - completed) / rate if rate > 0 else 0
                ok_count = sum(1 for x in results if not x['error'])
                logger.info(f'进度 {completed}/{len(codes)} OK={ok_count} 跳过={len(skipped)} '
                            f'耗时={elapsed:.0f}s 速率={rate:.1f}/s ETA={eta:.0f}s')

    elapsed_total = time.time() - t_start
    ok_count = sum(1 for x in results if not x['error'])
    logger.info(f'下载完成: OK={ok_count}/{len(codes)} 跳过={len(skipped)} 总耗时={elapsed_total:.1f}s')

    return {
        'total_candidates': len(codes),
        'ok_count': ok_count,
        'skipped_count': len(skipped),
        'skipped_codes': skipped,
        'elapsed_sec': round(elapsed_total, 1),
        'rate_per_sec': round(ok_count / elapsed_total, 2) if elapsed_total > 0 else 0,
    }


# ==================== min_rows + 流动性过滤 ====================
def apply_data_quality_filter(codes: list) -> dict:
    """min_rows ≥ 1000 + 平均成交额 ≥ 1000 万/日"""
    logger.info(f'数据质量过滤: min_rows ≥ {MIN_ROWS_5Y}, 平均成交额 ≥ {MIN_AVG_TURNOVER / 1e4:.0f} 万元/日')
    passed = []
    rejected = {'min_rows': [], 'turnover': []}
    for code in codes:
        csv_path = KLINE_DIR / f'{code}.csv'
        if not csv_path.exists():
            rejected['min_rows'].append(code)
            continue
        try:
            df = pd.read_csv(csv_path)
            if len(df) < MIN_ROWS_5Y:
                rejected['min_rows'].append(code)
                continue
            # 成交额列: 中文 '成交额' (akshare 列名)
            turnover_col = '成交额' if '成交额' in df.columns else None
            if turnover_col is None:
                rejected['turnover'].append(code)
                continue
            avg_turnover = df[turnover_col].mean()
            if avg_turnover < MIN_AVG_TURNOVER:
                rejected['turnover'].append(code)
                continue
            passed.append(code)
        except Exception as e:
            logger.warning(f'{code} 读取失败: {e}')
            rejected['min_rows'].append(code)
    logger.info(f'过滤后保留: {len(passed)} 只, 拒绝: min_rows={len(rejected["min_rows"])} turnover={len(rejected["turnover"])}')
    return {
        'passed_codes': passed,
        'passed_count': len(passed),
        'rejected_min_rows_count': len(rejected['min_rows']),
        'rejected_turnover_count': len(rejected['turnover']),
        'rejected_min_rows_sample': rejected['min_rows'][:10],
        'rejected_turnover_sample': rejected['turnover'][:10],
    }


# ==================== Main ====================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-workers', type=int, default=2)
    parser.add_argument('--pool-only', action='store_true', help='只生成 pool 不下载')
    parser.add_argument('--download-only', action='store_true', help='跳过 pool 生成直接下载')
    parser.add_argument('--filter-only', action='store_true', help='只做数据质量过滤')
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KLINE_DIR.mkdir(parents=True, exist_ok=True)

    pool_data = None
    codes = None

    # Step 1: 生成 A 股池
    if not args.download_only and not args.filter_only:
        logger.info('=' * 60)
        logger.info('STEP 1: 生成 A 股池 (排除科创/创业/北证)')
        logger.info('=' * 60)
        pool_data = filter_ashare_pool()
        pool_data['data_period'] = {
            'start': START_DATE_HUMAN,
            'end': END_DATE_HUMAN,
        }
        pool_data['source'] = 'akshare.stock_info_a_code_name()'
        with open(POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(pool_data, f, ensure_ascii=False, indent=2)
        logger.info(f'A 股池已写入: {POOL_FILE} ({pool_data["filtered_ashare_count"]} 只)')
        codes = [x['code'] for x in pool_data['pool']]
        if args.pool_only:
            return

    # Step 2: 下载 K 线
    if not args.filter_only:
        if codes is None and POOL_FILE.exists():
            with open(POOL_FILE, 'r', encoding='utf-8') as f:
                pool_data = json.load(f)
            codes = [x['code'] for x in pool_data['pool']]
            logger.info(f'从 {POOL_FILE} 加载 A 股池: {len(codes)} 只')
        if codes is None:
            logger.error('无 codes 可下载')
            sys.exit(1)
        logger.info('=' * 60)
        logger.info('STEP 2: 批量下载 K 线 (5Y, 并发 {})'.format(args.max_workers))
        logger.info('=' * 60)
        download_summary = download_all(codes, max_workers=args.max_workers)
        summary_path = DATA_DIR / 'ashare_download_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(download_summary, f, ensure_ascii=False, indent=2)
        logger.info(f'下载摘要写入: {summary_path}')

    # Step 3: 数据质量过滤
    if not args.pool_only:
        logger.info('=' * 60)
        logger.info('STEP 3: 数据质量过滤 (min_rows + 流动性)')
        logger.info('=' * 60)
        if codes is None and POOL_FILE.exists():
            with open(POOL_FILE, 'r', encoding='utf-8') as f:
                pool_data = json.load(f)
            codes = [x['code'] for x in pool_data['pool']]
        filter_result = apply_data_quality_filter(codes)
        filter_path = DATA_DIR / 'ashare_filter_summary.json'
        with open(filter_path, 'w', encoding='utf-8') as f:
            json.dump(filter_result, f, ensure_ascii=False, indent=2)
        logger.info(f'过滤摘要写入: {filter_path}')

        # 更新 pool 文件, 只保留通过过滤的代码
        if pool_data:
            passed_set = set(filter_result['passed_codes'])
            pool_data['pool'] = [x for x in pool_data['pool'] if x['code'] in passed_set]
            pool_data['filtered_ashare_count'] = len(pool_data['pool'])
            pool_data['data_quality_filter'] = {
                'min_rows': MIN_ROWS_5Y,
                'min_avg_turnover_wan': MIN_AVG_TURNOVER / 1e4,
                'passed_count': filter_result['passed_count'],
                'rejected_min_rows': filter_result['rejected_min_rows_count'],
                'rejected_turnover': filter_result['rejected_turnover_count'],
                'filter_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            with open(POOL_FILE, 'w', encoding='utf-8') as f:
                json.dump(pool_data, f, ensure_ascii=False, indent=2)
            logger.info(f'更新 pool 文件: 最终保留 {pool_data["filtered_ashare_count"]} 只')


if __name__ == '__main__':
    main()
