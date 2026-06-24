#!/bin/bash
# 三策略监控面板 · 本地快速启动（无需 Docker）
# 用途：开发调试 / 当前无 Docker 环境的临时使用
# 推荐生产部署用 install.sh（Docker 单端口）

set -e

# 默认配置
DEFAULT_PORT=8000
PORT="${1:-$DEFAULT_PORT}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/api/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; }

# ============ 1. 检查端口 ============
if lsof -i:"$PORT" &>/dev/null; then
    err "端口 $PORT 已被占用："
    lsof -i:"$PORT" | tail -n +2
    err "请先释放端口或指定其他端口：bash start.sh 8080"
    exit 1
fi

# ============ 2. 检查 / 创建 venv ============
if [ ! -d "$VENV_DIR" ]; then
    info "创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
    ok "venv 已创建：$VENV_DIR"
fi

# ============ 3. 安装依赖 ============
info "检查 Python 依赖..."
# 在 macOS 开发环境跳过 gunicorn（避免代理问题），只装 flask
if [[ "$(uname)" == "Darwin" ]]; then
    "$VENV_DIR/bin/pip" install -q flask
else
    "$VENV_DIR/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
fi
ok "依赖已就绪"

# ============ 4. 启动服务 ============
info "启动服务（端口 $PORT）..."
cd "$PROJECT_DIR"
mkdir -p logs
PORT="$PORT" nohup "$VENV_DIR/bin/python" "$PROJECT_DIR/api/real_data_server_v2.py" \
    > "$PROJECT_DIR/logs/server.log" 2>&1 &
PID=$!

# ============ 5. 健康检查 ============
info "等待服务启动..."
for i in {1..15}; do
    sleep 1
    if curl -fsS "http://localhost:$PORT/api/v1/health" &>/dev/null; then
        ok "服务健康检查通过（PID=$PID）"
        break
    fi
    if [ $i -eq 15 ]; then
        err "服务启动超时，日志："
        tail -20 "$PROJECT_DIR/logs/server.log"
        kill "$PID" 2>/dev/null
        exit 1
    fi
    echo -n "."
done
echo

# ============ 6. 展示信息 ============
cat <<EOF

${GREEN}============================================================${NC}
${GREEN}  ✓ 三策略监控面板已启动${NC}
${GREEN}============================================================${NC}

访问地址：
  ${BLUE}http://localhost:$PORT${NC}

常用命令：
  停止服务：  kill $PID  或  lsof -ti:$PORT | xargs kill
  查看日志：  tail -f $PROJECT_DIR/logs/server.log
  重启服务：  bash $PROJECT_DIR/start.sh $PORT

EOF

ok "启动完成"