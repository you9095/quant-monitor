#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金组合A（goldcombo / V24 DMAStrategy）每日模拟专用数据更新脚本
=================================================================
作用：把 V24 策略池 13 个标的（5 ETF + 3 股票 + 5 可转债）的真实日线 K 线
      下载/增量更新到 run_backtest_5y_v24.py 期望的三个专用目录：
        data/v24_etf_kline/   510300 510500 512880 512690 512480
        data/v24_stk_kline/   000001 600519 000333
        data/v24_bonds/       113050 110079 113011 113013 113016
数据源：新浪财经日线接口（真实行情，前复权由数据源给出）。

铁律（PROJECT_RULES 规则7）：
  - 只写真实下载到的行情；标的退市/到期则数据自然停在最后交易日，
    绝不前向填充、不造数据、不用快照冒充当日。
  - 可转债已退市（113011/113013/113016 2023 年退市，113050/110079 2025-07 退市），
    更新时如实保留其最后交易日，不补点。

Usage:
    python3 scripts/fetch_v24_pool_kline.py            # 增量更新全部 13 标的
    python3 scripts/fetch_v24_pool_kline.py --full     # 全量重拉(datalen=1300)
"""
import os
# 国内行情接口，禁用一切代理
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    os.environ[k] = ''
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import argparse
import time
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT = Path('/Users/junze/quant-monitor-local')
DATA = ROOT / 'data'

# V24 固定池（与 /Users/junze/goldcombo_real_backtest/v24/T4_5y/run_backtest_5y_v24.py 一致）
POOL = {
    'etf':  ['510300', '510500', '512880', '512690', '512480'],
    'stk':  ['000001', '600519', '000333'],
    'bonds': ['113050', '110079', '113011', '113013', '113016'],
}
DIRS = {
    'etf':  DATA / 'v24_etf_kline',
    'stk':  DATA / 'v24_stk_kline',
    'bonds': DATA / 'v24_bonds',
}
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}


def sina_symbol(code: str) -> str:
    """代码转新浪前缀。沪市:5xx ETF / 6xx,9xx 股票 / 11x,13x 债券 → sh；其余深市 → sz。"""
    if code[0] in ('5', '6', '9') or code.startswith(('11', '13')):
        return 'sh' + code
    return 'sz' + code  # 0xx/3xx 股票、159 深市ETF、12x 深市转债


def fetch(code: str, datalen: int):
    url = (f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           f'CN_MarketData.getKLineData?symbol={sina_symbol(code)}'
           f'&scale=240&ma=no&datalen={datalen}')
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and r.text.strip():
                d = json.loads(r.text)
                if d:
                    df = pd.DataFrame(d).rename(columns={'day': 'date'})
                    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
                    for c in ('open', 'high', 'low', 'close', 'volume'):
                        df[c] = pd.to_numeric(df[c], errors='coerce')
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    return df.dropna(subset=['close'])
            return None
        except Exception:
            if attempt < 2:
                time.sleep(2)
    return None


def update_one(kind: str, code: str, full: bool):
    d = DIRS[kind]
    d.mkdir(parents=True, exist_ok=True)
    csv = d / f'{code}.csv'
    datalen = 1300 if full else 120  # 增量：最近约 120 个交易日足够覆盖缺口
    new = fetch(code, datalen)
    if new is None or new.empty:
        return f'{code}: 下载失败/无数据'
    if csv.exists() and not full:
        old = pd.read_csv(csv, encoding='utf-8-sig')
        old['date'] = pd.to_datetime(old['date']).dt.strftime('%Y-%m-%d')
        merged = pd.concat([old, new]).drop_duplicates(subset='date', keep='last') \
            .sort_values('date').reset_index(drop=True)
    else:
        merged = new.sort_values('date').reset_index(drop=True)
    merged.to_csv(csv, index=False, encoding='utf-8-sig')
    return f'{code}: {merged["date"].iloc[0]} ~ {merged["date"].iloc[-1]} ({len(merged)} 行)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--full', action='store_true', help='全量重拉 datalen=1300')
    args = ap.parse_args()
    print(f'=== 黄金组合A V24 池数据{"全量" if args.full else "增量"}更新 {datetime.now():%Y-%m-%d %H:%M:%S} ===')
    for kind, codes in POOL.items():
        print(f'--- {kind} ({DIRS[kind]}) ---')
        for code in codes:
            msg = update_one(kind, code, args.full)
            print('  ' + msg)
            time.sleep(0.15)
    print('=== 完成 ===')


if __name__ == '__main__':
    main()
