#!/bin/bash
# 三策略监控面板 · 一键安装启动脚本
# 用法：curl -fsSL .../install.sh | bash   或   bash install.sh [安装目录]
#
# 默认安装到 ~/quant-monitor，端口 8000
# 可选：bash install.sh /opt/quant-monitor 8080

set -e

# ============ 参数解析 ============
DEFAULT_DIR="$HOME/quant-monitor"
DEFAULT_PORT=8000
REPO_URL="https://github.com/you9095/quant-monitor.git"

INSTALL_DIR="${1:-$DEFAULT_DIR}"
PORT="${2:-$DEFAULT_PORT}"
CONTAINER_NAME="quant-monitor"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

# ============ 1. 依赖检查 ============
info "检查依赖..."

if ! command -v docker &>/dev/null; then
    err "未检测到 docker，请先安装 Docker Desktop 或 Docker Engine"
    err "macOS: https://docs.docker.com/desktop/install/mac-install/"
    err "Linux: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    err "未检测到 docker compose v2，请升级 Docker"
    exit 1
fi

ok "Docker 已就绪"

# ============ 2. 获取代码 ============
info "安装目录：$INSTALL_DIR"
info "服务端口：$PORT"

if [ -d "$INSTALL_DIR" ]; then
    warn "目录已存在：$INSTALL_DIR"
    info "切换到该目录并尝试重启..."
    cd "$INSTALL_DIR"

    if [ -f docker-compose.yml ]; then
        info "检测到现有 docker-compose.yml，尝试重启..."
        PORT="$PORT" docker compose up -d --build 2>&1 | tail -20 || {
            err "重启失败，请进入 $INSTALL_DIR 手动排查"
            exit 1
        }
        ok "重启成功"
        show_access_info
        exit 0
    else
        err "目录存在但不是有效的监控面板项目"
        exit 1
    fi
fi

info "克隆代码仓库..."
git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | tail -3 || {
    err "克隆失败，请检查网络或仓库地址"
    err "如果是私有仓库，请先用 ssh 配置 GitHub 访问"
    exit 1
}

cd "$INSTALL_DIR"
ok "代码已下载到 $INSTALL_DIR"

# ============ 3. 配置端口 ============
if [ "$PORT" != "$DEFAULT_PORT" ]; then
    info "设置自定义端口 $PORT..."
    # docker-compose.yml 已支持 ${PORT:-8000}，这里只需确保 .env 有值
    echo "PORT=$PORT" > .env
fi

# ============ 4. 启动服务 ============
info "构建并启动 Docker 容器..."
docker compose up -d --build 2>&1 | tail -15

# ============ 5. 健康检查 ============
info "等待服务启动..."
for i in {1..20}; do
    sleep 2
    if curl -fsS "http://localhost:$PORT/api/v1/health" &>/dev/null; then
        ok "服务健康检查通过"
        break
    fi
    if [ $i -eq 20 ]; then
        err "服务启动超时，请查看日志："
        err "  cd $INSTALL_DIR && docker compose logs -f"
        exit 1
    fi
    echo -n "."
done
echo

# ============ 6. 展示访问信息 ============
show_access_info() {
    cat <<EOF

${GREEN}============================================================${NC}
${GREEN}  ✓ 三策略监控面板已启动${NC}
${GREEN}============================================================${NC}

访问地址：
  ${BLUE}http://localhost:$PORT${NC}

策略列表（从 config/strategies.json 读取）：
EOF

    if [ -f "$INSTALL_DIR/config/strategies.json" ]; then
        # 用 python 解析 JSON 列出策略名
        python3 -c "
import json
with open('$INSTALL_DIR/config/strategies.json') as f:
    d = json.load(f)
for sid, cfg in d.items():
    print(f'  • {cfg.get(\"name\", sid)} ({sid}, v={cfg.get(\"version\", \"latest\")})')
" 2>/dev/null || echo "  （无法解析策略配置）"
    fi

    cat <<EOF

常用命令：
  查看日志：  cd $INSTALL_DIR && docker compose logs -f
  停止服务：  cd $INSTALL_DIR && docker compose down
  重启服务：  cd $INSTALL_DIR && docker compose restart
  更新镜像：  cd $INSTALL_DIR && docker compose pull && docker compose up -d

EOF
}

show_access_info

ok "安装完成"