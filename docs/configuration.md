# 配置指南

本文档详细介绍 DeepCoBot 的配置选项。

## 配置文件位置

DeepCoBot 按以下顺序查找配置文件：

1. 命令行参数指定的路径 (`--config`)
2. `~/.deepcobot/config.toml`
3. 如果都找不到，使用默认配置

## 配置文件格式

DeepCoBot 使用 TOML 格式配置文件。

```toml
# 这是一个配置示例

[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"
max_tokens = 8192
```

## 核心配置

### `[agent]` - Agent 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `workspace` | string | `~/.deepcobot/workspace` | 工作空间目录 |
| `model` | string | `anthropic:claude-sonnet-4-6` | LLM 模型，格式: `provider:model` |
| `max_tokens` | int | `8192` | 最大输出 token 数 |
| `system_prompt` | string | - | 自定义系统提示词 |
| `enable_memory` | bool | `true` | 启用记忆系统 |
| `enable_skills` | bool | `true` | 启用技能系统 |
| `auto_approve` | bool | `false` | 自动审批工具调用 |

#### workspace

Agent 的所有文件操作都在此目录下进行。支持 `~` 表示用户主目录。

```toml
[agent]
workspace = "~/.deepcobot/workspace"
# 或绝对路径
workspace = "/var/lib/deepcobot/workspace"
```

#### model

LLM 模型配置，格式为 `provider:model_name`。

支持的提供商：
- `anthropic`: Claude 模型
- `openai`: GPT 模型
- 自定义提供商名称

```toml
[agent]
model = "anthropic:claude-sonnet-4-6"
# model = "openai:gpt-4"
# model = "custom:llama-3"
```

#### auto_approve

控制是否自动审批敏感工具调用。

| 值 | 行为 |
|----|------|
| `false` | 审批模式（默认）：`execute`、`write_file`、`edit_file`、`web_search`、`task` 需要手动审批 |
| `true` | 自动模式：所有工具调用自动执行 |

```toml
[agent]
auto_approve = false  # 推荐，更安全
```

### `[providers]` - LLM 提供商配置

配置 API 密钥和端点。

#### Anthropic

```toml
[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"
# api_base = "https://api.anthropic.com"  # 可选
```

#### OpenAI

```toml
[providers.openai]
api_key = "${OPENAI_API_KEY}"
# api_base = "https://api.openai.com/v1"  # 可选
```

#### 自定义提供商

```toml
[providers.custom]
api_key = "${CUSTOM_API_KEY}"
api_base = "https://api.custom.com/v1"
```

### 环境变量替换

配置文件支持环境变量替换，格式为 `${ENV_VAR}` 或 `${ENV_VAR:-default}`。

```toml
[providers.anthropic]
# 必须定义环境变量
api_key = "${ANTHROPIC_API_KEY}"

[providers.openai]
# 如果 OPENAI_API_KEY 未定义，使用默认值
api_key = "${OPENAI_API_KEY:-sk-default}"
```

## 渠道配置

### `[channels.cli]` - CLI 渠道

```toml
[channels.cli]
enabled = true  # 默认启用
```

### `[channels.telegram]` - Telegram 渠道

```toml
[channels.telegram]
enabled = true
token = "${TELEGRAM_BOT_TOKEN}"
proxy = "http://127.0.0.1:7890"  # 可选，代理设置
allowed_users = []  # 空列表允许所有用户
# allowed_users = ["user_id_1", "username_2"]  # 限制特定用户
```

获取 Bot Token：
1. 在 Telegram 中找到 @BotFather
2. 发送 `/newbot` 命令
3. 按提示创建 Bot
4. 获取 Token

### `[channels.discord]` - Discord 渠道

```toml
[channels.discord]
enabled = true
token = "${DISCORD_BOT_TOKEN}"
allowed_users = []
```

获取 Bot Token：
1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建新应用
3. 进入 Bot 页面，创建 Bot
4. 复制 Token
5. 启用 Message Content Intent

### `[channels.feishu]` - 飞书渠道

```toml
[channels.feishu]
enabled = true
app_id = "${FEISHU_APP_ID}"
app_secret = "${FEISHU_APP_SECRET}"
# encrypt_key = "${FEISHU_ENCRYPT_KEY}"  # 可选
# verification_token = "${FEISHU_VERIFICATION_TOKEN}"  # 可选
allowed_users = []
```

### `[channels.dingtalk]` - 钉钉渠道

```toml
[channels.dingtalk]
enabled = true
client_id = "${DINGTALK_CLIENT_ID}"
client_secret = "${DINGTALK_CLIENT_SECRET}"
allowed_users = []
```

### `[channels.web]` - Web API 渠道

```toml
[channels.web]
enabled = true
host = "0.0.0.0"
port = 8080
api_key = "${WEB_API_KEY}"  # 可选，启用认证
```

## 异步子 Agent

配置连接远程 LangGraph 服务器的异步子 Agent。

```toml
[[async_subagents]]
name = "research-agent"
description = "用于深度研究任务的异步 Agent"
graph_id = "research_graph"
url = "http://localhost:8123"

[[async_subagents]]
name = "code-review-agent"
description = "用于代码审查的异步 Agent"
graph_id = "code_review_graph"
url = "http://localhost:8124"
```

## Cron 任务

### `[cron]` - Cron 服务配置

```toml
[cron]
enabled = true
store_path = "~/.deepcobot/cron_jobs.json"
```

### 预定义任务

```toml
[[cron.jobs]]
name = "daily-report"
enabled = true
schedule = "0 9 * * *"  # 每天 9:00 (cron 表达式)
message = "请生成今天的日报"
channel = "telegram"
chat_id = "123456789"

[[cron.jobs]]
name = "hourly-check"
enabled = true
every = "1h"  # 每小时执行
message = "检查系统状态"

[[cron.jobs]]
name = "one-time-task"
enabled = true
at = "2024-12-31T23:59:59"  # 一次性执行
message = "新年快乐！"
```

### 调度类型

| 类型 | 字段 | 示例 |
|------|------|------|
| Cron | `schedule` | `0 9 * * *` (每天 9:00) |
| 间隔 | `every` | `1h`, `30m`, `1d` |
| 一次性 | `at` | `2024-12-31T23:59:59` |

## 服务配置

### `[services]` - 服务配置

```toml
[services]
health_enabled = true
health_port = 8081
heartbeat_interval = 60
metrics_enabled = true
metrics_port = 9090
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `health_enabled` | bool | `false` | 启用健康检查端点 |
| `health_port` | int | `8081` | 健康检查端口 |
| `heartbeat_interval` | int | `60` | 心跳检查间隔（秒）|
| `metrics_enabled` | bool | `false` | 启用 Prometheus 指标 |
| `metrics_port` | int | `9090` | 指标端口 |

## 日志配置

### `[logging]` - 日志配置

```toml
[logging]
level = "INFO"
json_format = false
file = "~/.deepcobot/deepcobot.log"
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `level` | string | `INFO` | 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `json_format` | bool | `false` | 使用 JSON 格式（适合日志收集） |
| `file` | string | - | 日志文件路径（可选） |

## Gateway 配置

```toml
[gateway]
enabled = false
url = "https://your-gateway.example.com"
api_key = "${GATEWAY_API_KEY}"
```

## 完整配置示例

```toml
# DeepCoBot 完整配置示例

[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"
max_tokens = 8192
enable_memory = true
enable_skills = true
auto_approve = false

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[channels.cli]
enabled = true

[channels.telegram]
enabled = true
token = "${TELEGRAM_BOT_TOKEN}"

[channels.web]
enabled = true
host = "0.0.0.0"
port = 8080

[cron]
enabled = true
store_path = "~/.deepcobot/cron_jobs.json"

[[cron.jobs]]
name = "daily-report"
enabled = true
schedule = "0 9 * * *"
message = "生成日报"

[services]
health_enabled = true
health_port = 8081
metrics_enabled = true
metrics_port = 9090

[logging]
level = "INFO"
json_format = false
```