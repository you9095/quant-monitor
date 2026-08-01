#!/usr/bin/env bash
# sync_portfolio_to_assets.sh
# 路径 3 实施: 从本机真后端 get_portfolio_summary() 拉真 portfolio,
# 用 Python 精确 patch 写回 assets/data.js 中 mockData.portfolio 段。
# 调用方式: ./sync_portfolio_to_assets.sh
# 退出码: 0 成功 / 非 0 失败
# 写入位置: /Users/junze/quant-monitor-local/scripts/sync_portfolio_to_assets.sh
# 创建日期: 2026-08-01

set -euo pipefail

REPO_ROOT="/Users/junze/quant-monitor-local"
DATA_JS="${REPO_ROOT}/assets/data.js"
LOG_DIR="${REPO_ROOT}/logs/portfolio_zero_real_sync_20260801"
TMP_JSON="$(mktemp -t portfolio_sync_XXXXXX.json)"

mkdir -p "${LOG_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] start sync_portfolio_to_assets.sh" | tee -a "${LOG_DIR}/sync_run.log"

# ---- 1. 拿真 portfolio_summary ----
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

if [ ! -s "${TMP_JSON}" ]; then
  echo "[FATAL] ${TMP_JSON} 为空,后端无数据" | tee -a "${LOG_DIR}/sync_run.log"
  exit 2
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 真 portfolio 已拉到 ${TMP_JSON}" | tee -a "${LOG_DIR}/sync_run.log"

# ---- 2. 备份 data.js ----
BAK="${DATA_JS}.bak.$(date '+%Y%m%d_%H%M%S')"
cp -p "${DATA_JS}" "${BAK}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份到 ${BAK}" | tee -a "${LOG_DIR}/sync_run.log"

# ---- 3. Python 精确 patch: 只改 mockData.portfolio 段 ----
if ! python3 <<PYEOF
import re, json, sys, os
data_js = "${DATA_JS}"
with open("${TMP_JSON}", 'r', encoding='utf-8') as f:
    portfolio = json.load(f)

with open(data_js, 'r', encoding='utf-8') as f:
    src = f.read()

# 保留 schema 注释中的 total_value / total_return / last_update; 真后端多出 total_pnl / total_return_pct / initial_capital / per_strategy / live_start_date / update_time
# 字段映射: 真后端字段 -> mockData.portfolio 字段
new_block_lines = []
new_block_lines.append("    portfolio: {")
# 必填 schema 字段
new_block_lines.append(f"      total_value: {json.dumps(portfolio.get('total_value', 0), ensure_ascii=False)},")
new_block_lines.append(f"      total_return: {json.dumps(portfolio.get('total_return_pct', 0), ensure_ascii=False)},")
new_block_lines.append(f"      last_update: {json.dumps(portfolio.get('update_time') or portfolio.get('live_start_date') or '', ensure_ascii=False)},")
# 扩展字段: 供前端真后端 fallback 用 (index.html L1645/L1646 优先读 portfolio.total_pnl / total_return_pct)
if 'total_pnl' in portfolio:
    new_block_lines.append(f"      total_pnl: {json.dumps(portfolio['total_pnl'], ensure_ascii=False)},")
if 'total_return_pct' in portfolio:
    new_block_lines.append(f"      total_return_pct: {json.dumps(portfolio['total_return_pct'], ensure_ascii=False)},")
if 'initial_capital' in portfolio:
    new_block_lines.append(f"      initial_capital: {json.dumps(portfolio['initial_capital'], ensure_ascii=False)},")
if 'per_strategy' in portfolio:
    # per_strategy 必须是 JS 对象字面量,直接拼
    ps = portfolio['per_strategy']
    ps_lines = []
    for sid, sinfo in ps.items():
        ps_lines.append(f"        '{sid}': {{")
        for k, v in sinfo.items():
            ps_lines.append(f"          {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},")
        ps_lines.append(f"        }},")
    new_block_lines.append(f"      per_strategy: {{")
    new_block_lines.extend(ps_lines)
    new_block_lines.append(f"      }},")
new_block_lines.append("    },")
new_block = "\n".join(new_block_lines) + "\n"

# 用非贪婪匹配替换 "    portfolio: {" 开头到 "    }," 结束的整个 mockData.portfolio 块
# 注意: 这个块在 mockData 内,schema 段也有 portfolio (L41-45) -- 我们要锚定在 mockData.portfolio
# mockData.portfolio 紧跟在 strategies: [...] 数组后面,加 patterns[0] 锚点
pattern = re.compile(
    r"(mockData:\s*\{[\s\S]*?strategies:\s*\[[\s\S]*?\]\s*,\s*)(\s*portfolio:\s*\{[\s\S]*?\n\s*\}\s*,\s*\n)",
    re.MULTILINE
)
m = pattern.search(src)
if not m:
    print("[FATAL] mockData.portfolio 段未找到", file=sys.stderr)
    sys.exit(3)

new_src = src[:m.start(2)] + "\n" + new_block + src[m.end(2):]

with open(data_js, 'w', encoding='utf-8') as f:
    f.write(new_src)

print("[OK] mockData.portfolio 已 patch")
PYEOF
then
  echo "[FATAL] Python patch 失败" | tee -a "${LOG_DIR}/sync_run.log"
  cp -p "${BAK}" "${DATA_JS}"
  exit 4
fi

# ---- 4. 验证: 抓改后 portfolio 段,确认字段齐全 ----
echo "[$(date '+%Y-%m-%d %H:%M:%S')] patch 完成,验证字段..." | tee -a "${LOG_DIR}/sync_run.log"
VERIFY_OUT=$(grep -A 30 "mockData:" "${DATA_JS}" | awk '/portfolio: {/,/^    },/' | head -40 || true)
echo "${VERIFY_OUT}" | tee -a "${LOG_DIR}/sync_run.log"

# 必须包含 total_value, total_pnl, total_return_pct, initial_capital, per_strategy, last_update
for FIELD in total_value total_pnl total_return_pct initial_capital per_strategy last_update; do
  if ! grep -q "${FIELD}:" "${DATA_JS}"; then
    echo "[FATAL] patch 后缺字段: ${FIELD},回滚" | tee -a "${LOG_DIR}/sync_run.log"
    cp -p "${BAK}" "${DATA_JS}"
    exit 5
  fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 所有字段齐全, 同步成功" | tee -a "${LOG_DIR}/sync_run.log"

rm -f "${TMP_JSON}"
exit 0