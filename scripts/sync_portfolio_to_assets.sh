#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/Users/junze/quant-monitor-local"
DATA_JS="${REPO_ROOT}/assets/data.js"
LOG_DIR="${REPO_ROOT}/logs/portfolio_zero_real_sync"
TMP_JSON="$(mktemp -t portfolio_sync_XXXXXX.json)"

mkdir -p "${LOG_DIR}"

echo "$(date '+%Y-%m-%d %H:%M:%S') start sync_portfolio_to_assets.sh" | tee -a "${LOG_DIR}/sync_run.log"

# 1. 拿真 portfolio_summary
if ! python3 -c "
import sys, json
sys.path.insert(0, '${REPO_ROOT}/api')
from live_data import get_portfolio_summary
with open('${TMP_JSON}', 'w', encoding='utf-8') as f:
    json.dump(get_portfolio_summary(), f, ensure_ascii=False, indent=2, default=str)
" 2>>"${LOG_DIR}/sync_run.log"; then
  echo "[FATAL] get_portfolio_summary 失败" | tee -a "${LOG_DIR}/sync_run.log"
  exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') fetched portfolio_summary successfully" | tee -a "${LOG_DIR}/sync_run.log"

# 2. 备份 data.js
BAK="${DATA_JS}.bak.$(date '+%Y%m%d_%H%M%S')"
cp -p "${DATA_JS}" "${BAK}"
echo "$(date '+%Y-%m-%d %H:%M:%S') backed up data.js to ${BAK}" | tee -a "${LOG_DIR}/sync_run.log"

# 3. Python 精确 patch
python3 << 'PYTHON_EOF'
import re, json

REPO_ROOT = "/Users/junze/quant-monitor-local"
DATA_JS = "/Users/junze/quant-monitor-local/assets/data.js"
TMP_JSON = "/tmp/portfolio_sync_XXXXXX.json"

with open(TMP_JSON, 'r', encoding='utf-8') as f:
    real_data = json.load(f)

with open(DATA_JS, 'r', encoding='utf-8') as f:
    content = f.read()

ms_start = content.find('mockData: {')
if ms_start < 0:
    print('[FATAL] 无法在 data.js 中找到 mockData 开头')
    exit(1)

portal_begin = content.find('"portfolio": {', ms_start)
if portal_begin < 0:
    print('[FATAL] 无法在 data.js 中找到 portfolio 开头')
    exit(1)

last_update_pos = content.find('last_update:', portal_begin)
if last_update_pos < 0:
    print('[FATAL] 无法在 portfolio 内部找到 last_update')
    exit(1)

line_end = content.find('\n', last_update_pos)
if line_end < 0:
    line_end = len(content)

original_block = content[portal_begin:line_end]

real_initial = real_data['initial_capital']
real_total_value = real_data['total_value']
real_total_pnl = real_data['total_pnl']
real_total_return_pct = real_data.get('total_return_pct', 0)
real_last_update_dynamic = 'new Date().toISOString()'

new_portfolio_block = '      initial_capital: ' + str(real_initial) + ',\n'
new_portfolio_block += '      total_value: ' + str(real_total_value) + ',\n'
new_portfolio_block += '      total_pnl: ' + str(real_total_pnl) + ',\n'
new_portfolio_block += '      total_return_pct: ' + str(real_total_return_pct) + ',\n'
new_portfolio_block += '      last_update: ' + real_last_update_dynamic + ',\n'

if original_block != new_portfolio_block:
    new_content = content.replace(original_block, new_portfolio_block, 1)
    with open(DATA_JS, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Patched data.js mockData.portfolio section')
    print('  initial_capital:', real_initial)
    print('  total_value:', real_total_value)
    print('  total_pnl:', real_total_pnl)
    print('  total_return_pct:', real_total_return_pct)
else:
    print('data.js portfolio 字段已是最新值，无需修改')

# 4. 验证
for FIELD in ['total_value', 'total_pnl', 'total_return_pct', 'initial_capital', 'last_update']:
    if not re.search(FIELD + ':', DATA_JS):
        print('[FATAL] 缺字段 ' + FIELD, ',回滚')
        exit(5)

print('all fields verified present')

# V6 fixture 检测
import subprocess
result = subprocess.run(['grep', 'total_value:', DATA_JS], capture_output=True, text=True)
total_value_line = result.stdout
if total_value_line:
    TOTAL_VALUE = total_value_line.split(':')[1].strip().split()[0]
    print('V6 total_value:', TOTAL_VALUE)

PYTHON_EOF

# 5. commit + push
cd "${REPO_ROOT}"
git add assets/data.js
git commit -m "data: sync 真 portfolio_summary $(date +%Y-%m-%d)"
git push origin master

echo "$(date '+%Y-%m-%d %H:%M:%S') sync completed and pushed" | tee -a "${LOG_DIR}/sync_run.log"
