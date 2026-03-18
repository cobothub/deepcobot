# DeepCoBot

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

中文文档 | [English](README.md)

极简封装的个人 AI 助理框架，基于 [DeepAgents](https://github.com/langchain-ai/deepagents) 构建。

## 特性

- **配置驱动**: 一切皆可配置，通过 TOML 文件零代码启动
- **多渠道支持**: CLI、Telegram、Discord、飞书、钉钉、Web API
- **DeepAgents 集成**: 内置记忆系统、技能系统、工具审批
- **LangGraph 兼容**: 支持 LangGraph 服务器部署
- **可观测性**: 内置健康检查、Prometheus 指标、结构化日志

## 快速开始

### 安装

```bash
# 基础安装
pip install deepcobot

# 安装特定渠道支持
pip install deepcobot[telegram]    # Telegram
pip install deepcobot[discord]     # Discord
pip install deepcobot[feishu]      # 飞书
pip install deepcobot[dingtalk]    # 钉钉
pip install deepcobot[web]         # Web API

# 安装所有功能
pip install deepcobot[all]
```

### 配置

1. 创建配置目录：

```bash
mkdir -p ~/.deepcobot
```

2. 创建配置文件 `~/.deepcobot/config.toml`：

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[channels.cli]
enabled = true
```

3. 设置环境变量：

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 运行

```bash
# 启动 CLI 交互会话
deepcobot run

# 指定配置文件
deepcobot run --config /path/to/config.toml

# 启动 LangGraph 服务器
deepcobot serve --port 8123
```

## 使用示例

### CLI 交互

```bash
$ deepcobot run

Welcome to DeepCoBot!
Type your message and press Enter. Type 'exit' or 'quit' to end.

You: 你好，请介绍一下你自己
Assistant: 你好！我是一个 AI 助手，可以帮助你完成各种任务...
```

### Telegram Bot

配置 `~/.deepcobot/config.toml`：

```toml
[channels.telegram]
enabled = true
token = "${TELEGRAM_BOT_TOKEN}"
allowed_users = ["your_telegram_id"]
```

运行：

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
deepcobot run
```

### Web API

配置：

```toml
[channels.web]
enabled = true
host = "0.0.0.0"
port = 8080
api_key = "${WEB_API_KEY}"
```

调用：

```bash
curl -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "你好"}'
```

## 配置说明

### 核心配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `agent.workspace` | 工作空间目录 | `~/.deepcobot/workspace` |
| `agent.model` | LLM 模型 | `anthropic:claude-sonnet-4-6` |
| `agent.max_tokens` | 最大输出 token | `8192` |
| `agent.enable_memory` | 启用记忆系统 | `true` |
| `agent.enable_skills` | 启用技能系统 | `true` |
| `agent.auto_approve` | 自动审批工具 | `false` |

### 环境变量

- `ANTHROPIC_API_KEY`: Anthropic API 密钥
- `OPENAI_API_KEY`: OpenAI API 密钥
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `DISCORD_BOT_TOKEN`: Discord Bot Token
- `DEEPCOBOT_LOG_LEVEL`: 日志级别 (DEBUG, INFO, WARNING, ERROR)
- `DEEPCOBOT_LOG_JSON`: 使用 JSON 格式日志 (true/false)

## Docker 部署

```bash
# 构建镜像
docker build -f docker/Dockerfile -t deepcobot .

# 使用 Docker Compose
cd docker
docker-compose up -d
```

## 开发

```bash
# 克隆仓库
git clone https://github.com/deepcobot/deepcobot.git
cd deepcobot

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check deepcobot
mypy deepcobot
```

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         DeepCoBot                               │
├─────────────────────────────────────────────────────────────────┤
│  消息渠道层  │  Telegram  │  Discord  │  Feishu  │  DingTalk  │  Web API  │  CLI  │
│              └───────────────────────┬─────────────────────────┘
│                                        │
│                                        ▼
│  消息总线层                      MessageBus (异步队列)
│                                        │
│                                        ▼
│  Agent 核心层                    DeepCoBotAgent (SDK 封装)
│                                        │
├────────────────────────────────────────┼────────────────────────┤
│  DeepAgents SDK                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │Filesystem   │ │  Memory     │ │  Skills     │               │
│  │Middleware   │ │ Middleware  │ │ Middleware  │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │LocalShell   │ │ SqliteSaver │ │ AsyncSub    │               │
│  │Backend      │ │(Checkpointer)│ │AgentMiddle  │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
├─────────────────────────────────────────────────────────────────┤
│  服务层       │ CronService │ Heartbeat │ LangGraph Server     │
└─────────────────────────────────────────────────────────────────┘
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 致谢

本项目参考了以下优秀项目的设计思想：

### [OpenClaw](https://github.com/openclaw/openclaw)

### [CoPaw](https://github.com/agentscope-ai/CoPaw)

### [Nanobot](https://github.com/HKUDS/nanobot)

### 设计理念

DeepCoBot 的核心理念是**极简封装**，专注于 DeepAgents 未提供的配置层和渠道接入层，最大化复用已有能力。通过参考上述项目的设计精华，我们实现了：

- 清晰的分层架构（配置层 → 渠道层 → Agent 层 → 服务层）
- 可扩展的渠道接入机制
- 统一的消息处理流程
- 完善的服务治理能力