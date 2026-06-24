FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 应用代码
COPY api/ /app/api/
COPY index.html /app/
COPY review.html /app/
COPY assets/ /app/assets/
COPY config/ /app/config/
COPY signals/ /app/signals/

# 运行时数据目录（可挂载）
RUN mkdir -p /app/metrics /app/review /app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/api/v1/health || exit 1

# 启动
EXPOSE 8000
ENV PORT=8000
CMD ["python", "api/real_data_server_v2.py"]