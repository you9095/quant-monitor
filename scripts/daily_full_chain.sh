#!/bin/bash
# ============================================================================
# AI量化策略监控项目 - 每日运行链 v3（修复版）
# ============================================================================
# 修复历史:
#   v1 (2026-06): 初始版本，5策略daily_run + 桥接
#   v2 (2026-08-31): 重建版本，因pandas缺失切换到模拟模式，导致数据灾难
#   v3 (2026-09-11): 修复版本
#     - 强制使用 /usr/local/bin/python3（Homebrew Python 3.14，有pandas）
#     - 添加依赖检查（pandas/numpy/akshare必须可用）
#     - 禁止模拟模式，策略运行失败时报错停止，不生成假数据
#     - 添加数据异常突变检测
#     - 添加备份机制
# ============================================================================

set -euo pipefail

# ==================== 代理禁用（2026-09-17 修复）====================
# 根因: macOS系统代理(127.0.0.1:7890)在代理工具未运行时导致Python requests ProxyError
# 行情API(东方财富/新浪等)均为国内可直接访问, 无需走代理
# 方案: 在本脚本运行期间统一禁用所有代理, 不影响电脑上其他工作的代理使用
export NO_PROXY="*"
export no_proxy="*"
export HTTP_PROXY=""
export HTTPS_PROXY=""
export http_proxy=""
export https_proxy=""
export ALL_PROXY=""
export all_proxy=""

# ==================== 配置 ====================
# 强制使用Homebrew Python 3.14（有pandas 3.0.3）
PYTHON="/usr/local/bin/python3"

MONITOR_DIR="/Users/junze/quant-monitor-local"
SIGNALS_DIR="$MONITOR_DIR/signals"
WORK_LOGS_DIR="/Users/junze/.hermes/work_logs"
BRIDGE="$MONITOR_DIR/scripts/bridge_worklog_to_signal.py"
STRATEGY_DIR="/Users/junze/.hermes/profiles/quant/skills/qixing"
QXING_STRATEGY_DIR="/Users/junze/qixing_strategy"

# 策略列表
STRATEGIES=("qixing" "r32" "zhuidian" "sanhe" "lightning" "goldcombo")

# 日期
TODAY=$(date +%Y-%m-%d)

# 日志
LOG_FILE="/Users/junze/.hermes/logs/daily_chain.log"

# ==================== 函数 ====================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" | tee -a "$LOG_FILE" >&2
}

# 依赖检查 - 这是v3的核心修复
check_dependencies() {
    log "--- [0/4] 依赖检查 ---"
    
    # 检查Python是否存在
    if [ ! -f "$PYTHON" ]; then
        error "Python不存在: $PYTHON"
        error "请安装Homebrew Python: brew install python@3.14"
        exit 1
    fi
    
    # 检查pandas
    if ! "$PYTHON" -c "import pandas" 2>/dev/null; then
        error "pandas缺失！"
        error "修复命令: $PYTHON -m pip install pandas numpy akshare"
        error "禁止切换到模拟模式，必须修复依赖后再运行"
        exit 1
    fi
    
    # 检查numpy
    if ! "$PYTHON" -c "import numpy" 2>/dev/null; then
        error "numpy缺失！"
        error "修复命令: $PYTHON -m pip install numpy"
        exit 1
    fi
    
    # 检查akshare（策略脚本需要）
    if ! "$PYTHON" -c "import akshare" 2>/dev/null; then
        error "akshare缺失！"
        error "修复命令: $PYTHON -m pip install akshare"
        error "禁止切换到模拟模式，必须修复依赖后再运行"
        exit 1
    fi
    
    # 检查策略脚本
    if [ ! -f "$STRATEGY_DIR/qixing_strategy.py" ]; then
        error "策略脚本不存在: $STRATEGY_DIR/qixing_strategy.py"
        error "策略脚本实际位置: $STRATEGY_DIR/ 和 $QXING_STRATEGY_DIR/"
        error "禁止切换到模拟模式，必须确认策略脚本路径后再运行"
        exit 1
    fi
    
    local pandas_version=$("$PYTHON" -c "import pandas; print(pandas.__version__)")
    local numpy_version=$("$PYTHON" -c "import numpy; print(numpy.__version__)")
    local akshare_version=$("$PYTHON" -c "import akshare; print(akshare.__version__)")
    
    log "  Python: $($PYTHON --version)"
    log "  pandas: $pandas_version ✅"
    log "  numpy: $numpy_version ✅"
    log "  akshare: $akshare_version ✅"
    log "  策略脚本: $STRATEGY_DIR/qixing_strategy.py ✅"
    log "  依赖检查通过"
}

# 备份当前信号文件（防止数据被覆盖）
backup_signals() {
    log "--- [0.5/4] 备份当前信号文件 ---"
    local backup_dir="$SIGNALS_DIR/.backup/$(date +%Y-%m-%d_%H%M%S)_pre_daily_run"
    mkdir -p "$backup_dir"
    
    for strategy in "${STRATEGIES[@]}"; do
        local signal_file="$SIGNALS_DIR/${strategy}_${TODAY}.json"
        if [ -f "$signal_file" ]; then
            cp "$signal_file" "$backup_dir/"
        fi
        # 同时备份最近一次的信号文件
        local latest_file=$(ls -t "$SIGNALS_DIR/${strategy}_"*.json 2>/dev/null | head -1)
        if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
            cp "$latest_file" "$backup_dir/"
        fi
    done
    
    log "  备份位置: $backup_dir"
}

# 拉取ETF行情
fetch_etf_data() {
    log "--- [1/4] 拉取ETF行情 ---"
    log "  31个ETF行情由 daily_stock_screener (0 0 * * *) + sync_portfolio_to_assets (16:30 1-5) 维护"
    # 这里可以添加实际的行情拉取逻辑
    # 目前依赖其他cron任务维护行情数据
}

# 策略日频运行 - 核心修复：禁止模拟模式
run_strategies() {
    log "--- [2/4] 策略日频运行（真实数据模式，禁止模拟）---"
    
    local failed_strategies=()
    
    # 2026-09-19 重大修复: 改用 daily_runner_v2.py 运行5个策略
    # 之前错误地调用棘轮回测脚本(参数优化), 现在改用真正的每日信号生成脚本
    local DAILY_RUNNER="/Users/junze/.hermes/scripts/p7/daily_runner_v2.py"
    
    if [ ! -f "$DAILY_RUNNER" ]; then
        error "  ❌ daily_runner_v2.py 不存在: $DAILY_RUNNER"
        error "  禁止切换到模拟模式！"
        failed_strategies+=("all")
    else
        log "  → 运行5策略 daily_runner_v2 (qixing/r32/zhuidian/sanhe/lightning)"
        # 禁用代理环境变量
        export NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""
        
        if "$PYTHON" "$DAILY_RUNNER" --date "$TODAY" --strategy all --skip-fetch 2>>"$LOG_FILE"; then
            log "  ✅ 5策略 daily_runner_v2 运行成功"
        else
            error "  ❌ daily_runner_v2 运行失败"
            error "  禁止切换到模拟模式！"
            failed_strategies+=("r32" "zhuidian" "sanhe" "lightning" "qixing")
        fi
    fi
    
    # goldcombo(黄金组合A策略) 单独运行 (不在 daily_runner_v2 中)
    log "  → goldcombo(黄金组合A策略)"
    local goldcombo_script="$MONITOR_DIR/strategies/goldcombo/goldcombo_ratchet_ashare.py"
    local output_dir="$WORK_LOGS_DIR/goldcombo"
    mkdir -p "$output_dir"
    
    if [ ! -f "$goldcombo_script" ]; then
        error "  ❌ goldcombo 策略脚本不存在: $goldcombo_script"
        failed_strategies+=("goldcombo")
    else
        # goldcombo 有argparse但不支持 --date, 只传 --output-path
        if "$PYTHON" "$goldcombo_script" --output-path "$output_dir/goldcombo_${TODAY}.json" 2>>"$LOG_FILE"; then
            log "  ✅ goldcombo 运行成功"
        else
            error "  ❌ goldcombo 运行失败"
            failed_strategies+=("goldcombo")
        fi
    fi
    
    # 报告失败的策略
    if [ ${#failed_strategies[@]} -gt 0 ]; then
        error "  以下策略运行失败: ${failed_strategies[*]}"
        error "  这些策略将保持上日数据，不生成假数据"
        error "  请排查失败原因后重新运行"
        # 不退出，继续桥接（使用已有的work_logs）
    else
        log "  全部策略运行成功"
    fi
}

# 桥接 work_logs → signals
bridge_worklogs() {
    log "--- [3/4] 桥接 work_logs → signals ---"
    
    if [ ! -f "$BRIDGE" ]; then
        error "桥接脚本不存在: $BRIDGE"
        exit 1
    fi
    
    # 运行桥接脚本（使用正确的Python环境）
    if "$PYTHON" "$BRIDGE" 2>>"$LOG_FILE"; then
        log "  桥接完成"
    else
        error "  桥接失败"
        exit 1
    fi

    # 2026-09-17 新增: 信号新鲜度验证 - 确保桥接后所有策略信号日期=当天
    log "  --- 信号新鲜度验证 ---"
    local stale_strategies=()
    for strategy in "${STRATEGIES[@]}"; do
        local signal_file="$SIGNALS_DIR/${strategy}_${TODAY}.json"
        if [ ! -f "$signal_file" ]; then
            error "  ❌ $strategy: 当天信号文件不存在: $signal_file"
            stale_strategies+=("$strategy")
            continue
        fi
        local sig_date=$("$PYTHON" -c "
import json
with open('$signal_file') as f:
    d = json.load(f)
print(d.get('date', d.get('signal_date', 'UNKNOWN')))
" 2>/dev/null)
        if [ "$sig_date" = "$TODAY" ]; then
            log "  ✅ $strategy: signal_date=$sig_date"
        else
            error "  ❌ $strategy: signal_date=$sig_date ≠ $TODAY (数据陈旧!)"
            stale_strategies+=("$strategy")
        fi
    done
    if [ ${#stale_strategies[@]} -gt 0 ]; then
        error "  ⚠️  以下策略信号陈旧: ${stale_strategies[*]}"
        error "  请检查桥接脚本和策略运行日志"
        # 不退出，因为数据可能仍然可用，但需要告警
    fi
}

# 数据异常突变检测 - v3新增
check_data_anomaly() {
    log "--- [4/4] 数据异常突变检测 ---"
    
    local has_anomaly=0
    
    for strategy in "${STRATEGIES[@]}"; do
        # 获取最近两天的信号文件
        local files=($(ls -t "$SIGNALS_DIR/${strategy}_"*.json 2>/dev/null | head -2))
        
        if [ ${#files[@]} -lt 2 ]; then
            log "  $strategy: 历史数据不足，跳过检测"
            continue
        fi
        
        local latest_file="${files[0]}"
        local previous_file="${files[1]}"
        
        # 读取累计盈亏
        local latest_pnl=$("$PYTHON" -c "
import json
with open('$latest_file') as f:
    data = json.load(f)
print(data.get('live_total_pnl', 0))
" 2>/dev/null || echo "0")
        
        local previous_pnl=$("$PYTHON" -c "
import json
with open('$previous_file') as f:
    data = json.load(f)
print(data.get('live_total_pnl', 0))
" 2>/dev/null || echo "0")
        
        # 计算变化率
        local change_rate=$("$PYTHON" -c "
latest = float('$latest_pnl')
previous = float('$previous_pnl')
if abs(previous) < 0.01:
    print('100' if abs(latest) > 0.01 else '0')
else:
    change = (latest - previous) / abs(previous) * 100
    print(f'{change:.2f}')
" 2>/dev/null || echo "0")
        
        # 检测异常：变化超过±50%，或方向反转
        local is_anomaly=$("$PYTHON" -c "
latest = float('$latest_pnl')
previous = float('$previous_pnl')
change = float('$change_rate')

# 方向反转
if (latest > 0 and previous < 0) or (latest < 0 and previous > 0):
    print('1')
# 变化超过50%
elif abs(change) > 50:
    print('1')
else:
    print('0')
" 2>/dev/null || echo "0")
        
        if [ "$is_anomaly" = "1" ]; then
            error "  ⚠️  $strategy 数据异常突变!"
            error "    上日累计盈亏: $previous_pnl"
            error "    今日累计盈亏: $latest_pnl"
            error "    变化率: ${change_rate}%"
            error "    请检查数据是否正确！"
            has_anomaly=1
        else
            log "  ✅ $strategy 数据正常 (累计盈亏: $latest_pnl, 变化: ${change_rate}%)"
        fi
    done
    
    if [ "$has_anomaly" = "1" ]; then
        error "  检测到数据异常突变！"
        error "  请人工确认数据正确性后再继续"
        # 不退出，因为数据可能是正确的（比如大幅盈利），但需要告警
    else
        log "  全部策略数据正常"
    fi
}

# ==================== 主流程 ====================

main() {
    log ""
    log "===== 五策略每日运行链 v3（修复版）====="
    log "日期: $TODAY"
    log "Python: $PYTHON"
    log ""
    
    # Step 0: 依赖检查（核心修复）
    check_dependencies
    
    # Step 0.5: 备份当前信号文件
    backup_signals
    
    # Step 1: 拉取ETF行情
    fetch_etf_data
    
    # Step 2: 策略日频运行（禁止模拟模式）
    run_strategies
    
    # Step 3: 桥接 work_logs → signals
    bridge_worklogs
    
    # Step 4: 数据异常突变检测
    check_data_anomaly
    
    log ""
    log "===== 每日运行链 v3 完成 ====="
    log ""
}

# 运行主流程
main "$@"
