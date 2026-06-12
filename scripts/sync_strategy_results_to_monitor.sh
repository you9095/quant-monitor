#!/bin/bash
# 量化策略迭代完成后自动更新监控面板
# 用法: ./sync_strategy_results_to_monitor.sh <strategy_id> <result_json_path>

set -e

SID="$1"
RESULT_JSON="$2"
MONITOR_DIR="/Users/junze/quant-monitor-local"
DATE=$(date +%Y-%m-%d)
API_URL="http://localhost:8000/api/v1"

if [ -z "$SID" ] || [ -z "$RESULT_JSON" ]; then
    echo "Usage: $0 <strategy_id> <result_json>"
    echo "Example: $0 qixing /path/to/qixing_round4_results.json"
    exit 1
fi

# 从结果JSON提取R120最终结果
python3 << 'PYSCRIPT'
import json
import subprocess
import sys
from datetime import datetime

sid = sys.argv[1] if len(sys.argv) > 1 else 'qixing'
result_file = sys.argv[2] if len(sys.argv) > 2 else '/Users/junze/qixing_strategy/qixing_round4_results.json'
date = datetime.now().strftime('%Y-%m-%d')

with open(result_file) as f:
    results = json.load(f)

# 找到最后一条ACCEPT结果（最新版本）
final = None
for r in reversed(results):
    if r.get('verdict') == 'ACCEPT':
        final = r
        break

if not final:
    # 取最后一个结果
    final = results[-1] if results else {}

tr = final.get('total_return_pct', 0)
ann = final.get('annualized_return_pct', 0)
max_dd = final.get('max_drawdown_pct', 0)
sharpe = final.get('sharpe_ratio', 0)
trades = final.get('trades', 0)

print(f'Total Return: {tr}%')
print(f'Annualized: {ann}%')
print(f'Max Drawdown: {max_dd}%')
print(f'Sharpe: {sharpe}')
print(f'Trades: {trades}')
PYSCRIPT

# 生成信号文件
python3 << PYEOF
import json
from datetime import datetime
from pathlib import Path

sid = '$SID'
result_file = '$RESULT_JSON'
monitor_dir = Path('$MONITOR_DIR')
date = datetime.now().strftime('%Y-%m-%d')

with open(result_file) as f:
    results = json.load(f)

# 找到最后一条ACCEPT结果
final = None
for r in reversed(results):
    if r.get('verdict') == 'ACCEPT':
        final = r
        break

if not final:
    final = results[-1] if results else {}

signal = {
    'date': date,
    'strategy_id': sid,
    'positions': [
        {'code': '159915', 'name': '创业板ETF', 'qty': 2450, 'cost': 4.02}
    ],
    'action': {
        'action': 'REBALANCE',
        'target': '最优参数组合',
        'detail': f'策略迭代更新 - 年化{final.get("annualized_return_pct", 0)}% 回撤{final.get("max_drawdown_pct", 0)}%',
        'trades': []
    },
    'total_return': final.get('total_return_pct', 0),
    'today_pnl': 0,
    'today_return': 0,
    'sharpe': final.get('sharpe_ratio', 0),
    'max_drawdown': final.get('max_drawdown_pct', 0),
    'trades': final.get('trades', 0),
    'version': f'R{final.get("round", "latest")}'
}

signal_file = monitor_dir / 'signals' / f'{sid}_{date}.json'
with open(signal_file, 'w') as f:
    json.dump(signal, f, indent=2, ensure_ascii=False)

print(f'✓ Created signal file: {signal_file}')

# 更新复盘文件
review_file = monitor_dir / 'review' / f'{date}.json'
if review_file.exists():
    with open(review_file) as f:
        review = json.load(f)
else:
    review = {
        'date': date,
        'summary': {},
        'strategies': {},
        'notes': ''
    }

review['strategies'][sid] = {
    'total_return': final.get('total_return_pct', 0),
    'annualized_return': final.get('annualized_return_pct', 0),
    'max_drawdown': final.get('max_drawdown_pct', 0),
    'sharpe': final.get('sharpe_ratio', 0),
    'trades_count': final.get('trades', 0)
}

with open(review_file, 'w') as f:
    json.dump(review, f, indent=2, ensure_ascii=False)

print(f'✓ Updated review file: {review_file}')
PYEOF

echo "✓ Strategy $SID synced to monitoring panel"