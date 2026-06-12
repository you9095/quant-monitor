#!/bin/bash
# 量化策略自动更新脚本 → 监控面板
# 用法: ./update_strategy_to_monitor.sh <strategy_id> <result_json_path>

set -e

SID="$1"
RESULT_JSON="$2"
MONITOR_DIR="/Users/junze/quant-monitor-local"
DATE=$(date +%Y-%m-%d)

if [ -z "$SID" ] || [ -z "$RESULT_JSON" ]; then
    echo "Usage: $0 <strategy_id> <result_json>"
    exit 1
fi

# 从结果JSON提取关键指标
TOTAL_RETURN=$(python3 -c "import json; d=json.load(open('$RESULT_JSON')); print(d.get('total_return_pct',0))")
ANNUALIZED=$(python3 -c "import json; d=json.load(open('$RESULT_JSON')); print(d.get('annualized_return_pct',0))")
MAX_DD=$(python3 -c "import json; d=json.load(open('$RESULT_JSON')); print(d.get('max_drawdown_pct',0))")
SHARPE=$(python3 -c "import json; d=json.load(open('$RESULT_JSON')); print(d.get('sharpe_ratio',0))")
TRADES=$(python3 -c "import json; d=json.load(open('$RESULT_JSON')); print(d.get('trades',0))")

# 生成信号文件
cat > "$MONITOR_DIR/signals/${SID}_${DATE}.json" << EOF
{
  "date": "$DATE",
  "strategy_id": "$SID",
  "positions": [{"code": "159915", "name": "创业板ETF", "qty": 2450, "cost": 4.02}],
  "action": {
    "action": "REBALANCE",
    "target": "最优参数组合",
    "detail": "策略迭代更新 - 年化${ANNUALIZED}% 回撤${MAX_DD}%",
    "trades": []
  },
  "total_return": $TOTAL_RETURN,
  "annualized_return": $ANNUALIZED,
  "today_pnl": 0,
  "today_return": 0,
  "sharpe": $SHARPE,
  "max_drawdown": $MAX_DD,
  "trades": $TRADES,
  "version": "R$(basename $RESULT_JSON | grep -o 'R[0-9]*' || echo latest)"
}
EOF

echo "✓ Updated $MONITOR_DIR/signals/${SID}_${DATE}.json"

# 更新复盘数据
python3 << PYEOF
import json
from pathlib import Path

date = "$DATE"
sid = "$SID"
monitor_dir = Path("$MONITOR_DIR")

review_file = monitor_dir / "review" / f"{date}.json"
if review_file.exists():
    with open(review_file) as f:
        review = json.load(f)
    if sid not in review.get("strategies", {}):
        review["strategies"][sid] = {
            "total_return": $TOTAL_RETURN,
            "annualized_return": $ANNUALIZED,
            "max_drawdown": $MAX_DD,
            "sharpe": $SHARPE,
            "trades_count": $TRADES
        }
        with open(review_file, 'w') as f:
            json.dump(review, f, indent=2, ensure_ascii=False)
        print("✓ Updated review file")
PYEOF

echo "✓ Strategy $SID updated to monitoring panel"