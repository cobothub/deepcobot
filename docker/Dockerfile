# DeepCoBot Dockerfile
# 多阶段构建，优化镜像大小

# 构建阶段
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[all]"

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY deepcobot/ ./deepcobot/
COPY pyproject.toml ./

# 创建非 root 用户
RUN useradd -m -u 1000 deepcobot

# 创建工作目录
RUN mkdir -p /home/deepcobot/.deepcobot && \
    chown -R deepcobot:deepcobot /home/deepcobot

USER deepcobot
WORKDIR /home/deepcobot

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    DEEPCOBOT_LOG_LEVEL=INFO

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# 默认端口
EXPOSE 8080 8081 8123

# 默认入口
ENTRYPOINT ["deepcobot"]
CMD ["run"]