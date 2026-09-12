#!/bin/bash
# AI量化策略监控项目 - 依赖检查脚本
# 用法: ./scripts/check_dependencies.sh
# 最后更新: 2026-09-11

set -e

echo "=========================================="
echo "AI量化策略监控项目 - 依赖检查"
echo "=========================================="
echo ""

# 定义Python路径
PYTHON_HOMEBREW="/usr/local/bin/python3"
PYTHON_VENV="/Users/junze/quant-monitor-local/api/venv/bin/python"
PYTHON_SYSTEM="/usr/bin/python3"

# 检查函数
check_python() {
    local name=$1
    local python_path=$2
    
    echo "[$name]"
    echo "  路径: $python_path"
    
    if [ ! -f "$python_path" ]; then
        echo "  ❌ Python不存在"
        return 1
    fi
    
    # 检查版本
    local version=$("$python_path" --version 2>&1)
    echo "  版本: $version"
    
    # 检查pandas
    if "$python_path" -c "import pandas" 2>/dev/null; then
        local pandas_version=$("$python_path" -c "import pandas; print(pandas.__version__)" 2>/dev/null)
        echo "  ✅ pandas: $pandas_version"
    else
        echo "  ❌ pandas缺失"
        echo "    修复命令: $python_path -m pip install pandas numpy"
    fi
    
    # 检查numpy
    if "$python_path" -c "import numpy" 2>/dev/null; then
        local numpy_version=$("$python_path" -c "import numpy; print(numpy.__version__)" 2>/dev/null)
        echo "  ✅ numpy: $numpy_version"
    else
        echo "  ❌ numpy缺失"
    fi
    
    # 检查flask（后端服务需要）
    if "$python_path" -c "import flask" 2>/dev/null; then
        local flask_version=$("$python_path" -c "import flask; print(flask.__version__)" 2>/dev/null)
        echo "  ✅ flask: $flask_version"
    else
        echo "  ⚠️  flask缺失（后端服务需要）"
    fi
    
    echo ""
}

# 检查所有Python环境
check_python "Homebrew Python (daily_run用)" "$PYTHON_HOMEBREW"
check_python "项目venv Python (后端服务用)" "$PYTHON_VENV"
check_python "系统Python" "$PYTHON_SYSTEM"

# 检查策略脚本
echo "[策略脚本检查]"
STRATEGY_DIR="/Users/junze/.hermes/profiles/quant/skills/qixing"
if [ -f "$STRATEGY_DIR/qixing_strategy.py" ]; then
    echo "  ✅ qixing_strategy.py存在"
    # 尝试导入检查
    if "$PYTHON_HOMEBREW" -c "import sys; sys.path.insert(0, '$STRATEGY_DIR'); import qixing_strategy" 2>/dev/null; then
        echo "  ✅ qixing_strategy.py可正常导入"
    else
        echo "  ⚠️  qixing_strategy.py导入失败（可能有其他依赖缺失）"
    fi
else
    echo "  ❌ qixing_strategy.py不存在"
fi

if [ -f "/Users/junze/qixing_strategy/qixing_2y_engine.py" ]; then
    echo "  ✅ qixing_2y_engine.py存在"
else
    echo "  ❌ qixing_2y_engine.py不存在"
fi

echo ""

# 检查关键目录
echo "[关键目录检查]"
for dir in \
    "/Users/junze/quant-monitor-local/signals" \
    "/Users/junze/.hermes/work_logs" \
    "/Users/junze/qixing_strategy" \
    "/Users/junze/.hermes/profiles/quant/skills/qixing"; do
    if [ -d "$dir" ]; then
        echo "  ✅ $dir"
    else
        echo "  ❌ $dir 不存在"
    fi
done

echo ""
echo "=========================================="
echo "依赖检查完成"
echo "=========================================="
