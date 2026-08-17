#!/bin/bash
# T1: 数据源 + backtrader 环境核查 (2026-08-14)
set -e
echo "=== T1 环境核查 ==="
echo "--- 1. Python 环境 ---"
which python3.12
python3.12 --version

echo "--- 2. 依赖版本 ---"
python3.12 -c "import backtrader, pandas, numpy, akshare; print('bt', backtrader.__version__, 'pd', pandas.__version__, 'np', numpy.__version__, 'ak', akshare.__version__)"

echo "--- 3. 数据源扫描 ---"
ls /Users/junze/quant-monitor-local/data/ashare_kline/ | wc -l
echo "Total A-share CSV files"

echo "--- 4. 样本数据验证 (000010 + 600519) ---"
head -3 /Users/junze/quant-monitor-local/data/ashare_kline/000010.csv
echo "---"
head -3 /Users/junze/quant-monitor-local/data/ashare_kline/600519.csv

echo "--- 5. A 股池清单 ---"
python3.12 -c "
import json
with open('/Users/junze/quant-monitor-local/data/ashare_pool.json') as f:
    p = json.load(f)
print(f'pool: {len(p[\"pool\"])} stocks')
print(f'first 5: {[x[\"code\"] for x in p[\"pool\"][:5]]}')
"

echo "--- 6. 数据质量过滤后池子 ---"
python3.12 -c "
import json
with open('/Users/junze/quant-monitor-local/data/ashare_filter_summary.json') as f:
    s = json.load(f)
print(f'filter_logic: {s[\"filter_logic\"]}')
print(f'data_period: {s[\"data_period\"]}')
print(f'passed_count: {s[\"passed_count\"]}')
print(f'filter_timestamp: {s[\"filter_timestamp\"]}')
"

echo "=== T1 完成 ==="