#!/usr/bin/env python3
"""
goldcombo(黄金组合A策略) A股K线数据下载脚本
从新浪财经API下载日线K线数据到 data/ashare_kline/ 目录
带重试机制和进度显示
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime

# 配置
KLINE_DIR = '/Users/junze/quant-monitor-local/data/ashare_kline'
BASELINE_FILE = '/Users/junze/quant-monitor-local/strategies/goldcombo/ratchet_baseline_ashare.json'
START_DATE = '20240101'
END_DATE = '20260917'
MAX_RETRIES = 3
RETRY_DELAY = 2

# 禁用代理（东方财富/新浪国内API不需要代理）
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

def get_stock_pool():
    """从baseline文件获取股票池"""
    with open(BASELINE_FILE, 'r') as f:
        d = json.load(f)
    pool_2y = d.get('data_periods', {}).get('2y', {}).get('ashare_pool_used', [])
    pool_5y = d.get('data_periods', {}).get('5y', {}).get('ashare_pool_used', [])
    # 合并去重
    all_codes = list(set(pool_2y + pool_5y))
    all_codes.sort()
    return all_codes

def get_sina_symbol(code):
    """转换股票代码为新浪格式: 沪市sh, 深市sz"""
    if code.startswith('6') or code.startswith('9'):
        return f'sh{code}'
    else:
        return f'sz{code}'

def download_kline_sina(code):
    """从新浪财经下载日线K线数据"""
    symbol = get_sina_symbol(code)
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=1000'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn'
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200 and r.text.strip():
                data = json.loads(r.text)
                if data and len(data) > 0:
                    df = pd.DataFrame(data)
                    # 重命名列以匹配 goldcombo 期望的格式
                    df = df.rename(columns={
                        'day': 'date',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'close': 'close',
                        'volume': 'volume'
                    })
                    # 确保日期格式
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    # 过滤日期范围
                    df = df[(df['date'] >= START_DATE[:4]+'-'+START_DATE[4:6]+'-'+START_DATE[6:]) & 
                            (df['date'] <= END_DATE[:4]+'-'+END_DATE[4:6]+'-'+END_DATE[6:])]
                    return df
            return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None
    return None

def main():
    print(f"=== goldcombo(黄金组合A策略) A股K线数据下载 ===")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"K线目录: {KLINE_DIR}")
    
    # 创建目录
    os.makedirs(KLINE_DIR, exist_ok=True)
    
    # 获取股票池
    codes = get_stock_pool()
    print(f"股票池数量: {len(codes)} 只")
    
    # 检查已下载的
    existing = set(f.replace('.csv', '') for f in os.listdir(KLINE_DIR) if f.endswith('.csv'))
    to_download = [c for c in codes if c not in existing]
    print(f"已下载: {len(existing)} 只, 待下载: {len(to_download)} 只")
    
    if not to_download:
        print("全部已下载，无需更新")
        return
    
    # 下载
    success = 0
    failed = 0
    for i, code in enumerate(to_download):
        df = download_kline_sina(code)
        if df is not None and len(df) >= 200:
            csv_path = os.path.join(KLINE_DIR, f'{code}.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            success += 1
        else:
            failed += 1
        
        # 进度显示
        if (i + 1) % 50 == 0 or i == len(to_download) - 1:
            print(f"  进度: {i+1}/{len(to_download)} | 成功: {success} | 失败: {failed} | 最新: {code}")
        
        # 限速，避免被封
        time.sleep(0.1)
    
    print(f"\n=== 下载完成 ===")
    print(f"成功: {success} 只")
    print(f"失败: {failed} 只")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 验证
    total_csv = len([f for f in os.listdir(KLINE_DIR) if f.endswith('.csv')])
    print(f"K线目录CSV总数: {total_csv} 只")

if __name__ == '__main__':
    main()
