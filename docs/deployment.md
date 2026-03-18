# 部署指南

本文档介绍 DeepCoBot 的各种部署方式。

## 目录

- [本地部署](#本地部署)
- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [环境变量](#环境变量)
- [监控配置](#监控配置)
- [故障排查](#故障排查)

## 本地部署

### 系统要求

- Python 3.10 或更高版本
- 至少 512MB 内存
- 100MB 磁盘空间

### 安装步骤

1. **创建虚拟环境**

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
```

2. **安装 DeepCoBot**

```bash
pip install deepcobot
```

3. **创建配置文件**

```bash
mkdir -p ~/.deepcobot
cp config.example.toml ~/.deepcobot/config.toml
```

4. **配置环境变量**

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

5. **启动服务**

```bash
deepcobot run
```

## Docker 部署

### 使用预构建镜像

```bash
docker pull deepcobot/deepcobot:latest
docker run -d \
  --name deepcobot \
  -v ~/.deepcobot:/home/deepcobot/.deepcobot \
  -e ANTHROPIC_API_KEY=your-api-key \
  deepcobot/deepcobot:latest
```

### 使用 Docker Compose

1. **准备配置文件**

```bash
mkdir -p config
cp config.example.toml config/config.toml
```

2. **创建环境变量文件**

```bash
# .env
ANTHROPIC_API_KEY=your-api-key
TELEGRAM_BOT_TOKEN=your-bot-token  # 可选
```

3. **启动服务**

```bash
cd docker
docker-compose up -d
```

4. **查看日志**

```bash
docker-compose logs -f deepcobot
```

5. **停止服务**

```bash
docker-compose down
```

### Docker Compose 配置说明

```yaml
# docker-compose.yml
version: '3.8'

services:
  deepcobot:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    restart: unless-stopped
    ports:
      - "8080:8080"   # Web API
      - "8081:8081"   # 健康检查
      - "8123:8123"   # LangGraph Server
    volumes:
      - ./config:/home/deepcobot/.deepcobot:ro
      - deepcobot-workspace:/home/deepcobot/.deepcobot/workspace
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    env_file:
      - .env
```

## Kubernetes 部署

### Deployment 配置

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deepcobot
  labels:
    app: deepcobot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: deepcobot
  template:
    metadata:
      labels:
        app: deepcobot
    spec:
      containers:
      - name: deepcobot
        image: deepcobot/deepcobot:latest
        ports:
        - containerPort: 8080
          name: web
        - containerPort: 8081
          name: health
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: deepcobot-secrets
              key: anthropic-api-key
        volumeMounts:
        - name: config
          mountPath: /home/deepcobot/.deepcobot
          readOnly: true
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /live
            port: 8081
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8081
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: deepcobot-config
```

### Service 配置

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: deepcobot
spec:
  selector:
    app: deepcobot
  ports:
  - port: 8080
    targetPort: 8080
    name: web
  - port: 8081
    targetPort: 8081
    name: health
```

## 环境变量

### 必需变量

| 变量名 | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥（使用 Claude 模型时必需）|
| `OPENAI_API_KEY` | OpenAI API 密钥（使用 GPT 模型时必需）|

### 可选变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - |
| `DISCORD_BOT_TOKEN` | Discord Bot Token | - |
| `FEISHU_APP_ID` | 飞书应用 ID | - |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | - |
| `DINGTALK_CLIENT_ID` | 钉钉客户端 ID | - |
| `DINGTALK_CLIENT_SECRET` | 钉钉客户端密钥 | - |
| `DEEPCOBOT_LOG_LEVEL` | 日志级别 | `INFO` |
| `DEEPCOBOT_LOG_JSON` | JSON 格式日志 | `false` |
| `DEEPCOBOT_LOG_FILE` | 日志文件路径 | - |

## 监控配置

### 启用健康检查

```toml
[services]
health_enabled = true
health_port = 8081
```

### 启用 Prometheus 指标

```toml
[services]
metrics_enabled = true
metrics_port = 9090
```

### Prometheus 抓取配置

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'deepcobot'
    static_configs:
      - targets: ['deepcobot:9090']
```

### Grafana Dashboard

导入示例 Dashboard 或创建自定义面板，监控以下指标：

- `deepcobot_requests_total`: 请求总数
- `deepcobot_request_duration_seconds`: 请求延迟
- `deepcobot_active_sessions`: 活跃会话数
- `deepcobot_channel_up`: 渠道状态

## 故障排查

### 常见问题

#### 1. API Key 无效

**症状**: 启动时报错 `Authentication error`

**解决方案**:
- 检查环境变量是否正确设置
- 确认 API Key 没有过期

```bash
# 验证环境变量
echo $ANTHROPIC_API_KEY
```

#### 2. 端口被占用

**症状**: 启动时报错 `Address already in use`

**解决方案**:
- 更改端口号
- 或停止占用端口的进程

```bash
# 查找占用端口的进程
lsof -i :8080

# 更改端口
deepcobot run --port 8081
```

#### 3. 权限问题

**症状**: 无法创建工作空间目录

**解决方案**:
- 检查用户对目录的权限
- 或更改工作空间路径

```bash
# 创建目录并设置权限
mkdir -p ~/.deepcobot/workspace
chmod 755 ~/.deepcobot
```

#### 4. 依赖缺失

**症状**: `ImportError: No module named 'xxx'`

**解决方案**:
- 安装对应的可选依赖

```bash
# 安装 Telegram 支持
pip install deepcobot[telegram]

# 安装所有功能
pip install deepcobot[all]
```

### 日志调试

启用 DEBUG 级别日志：

```bash
export DEEPCOBOT_LOG_LEVEL=DEBUG
deepcobot run
```

或使用 JSON 格式日志（用于日志收集系统）：

```bash
export DEEPCOBOT_LOG_JSON=true
deepcobot run
```

### 获取帮助

如果以上方法无法解决问题，请：

1. 查阅 [GitHub Issues](https://github.com/deepcobot/deepcobot/issues)
2. 提交新的 Issue，包含：
   - 错误信息
   - 配置文件（脱敏）
   - 运行环境信息