# DeepCoBot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

中文文档 | [English](README.md)

极简封装的个人 AI 助理框架，基于 [DeepAgents](https://github.com/langchain-ai/deepagents) 构建。

## 系统要求

- Python >= 3.11
- DeepAgents SDK（需要 Python >= 3.11）

## 特性

- **配置驱动**: 一切皆可配置，通过 TOML 文件零代码启动
- **多渠道支持**: CLI、Telegram、Discord、飞书、钉钉、Web API
- **DeepAgents 集成**: 内置记忆系统、技能系统、工具审批
- **LangGraph 兼容**: 支持 LangGraph 服务器部署
- **DeepAgents UI**: 支持与 deepagents-ui 网页界面集成，提供实时对话、会话管理、文件可视化等功能
- **可观测性**: 内置健康检查、Prometheus 指标、结构化日志

## 快速开始

### 安装

**从源码安装（推荐）**

```bash
# 克隆仓库
git clone https://github.com/cobothub/deepcobot.git
cd deepcobot

# 创建虚拟环境（需要 Python 3.11+）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 开发模式安装
pip install -e .

# 安装特定渠道支持
pip install -e ".[telegram]"    # Telegram
pip install -e ".[discord]"     # Discord
pip install -e ".[feishu]"      # 飞书
pip install -e ".[dingtalk]"    # 钉钉
pip install -e ".[web]"         # Web API

# 安装所有功能
pip install -e ".[all]"

# 安装开发依赖
pip install -e ".[dev]"
```

**从 PyPI 安装（即将发布）**

```bash
# 首次发布后可用
pip install deepcobot
```

### 配置

1. 创建配置目录：

```bash
mkdir -p ~/.deepcobot
```

2. 创建配置文件 `~/.deepcobot/config.toml`：

**使用 Anthropic Claude:**

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[channels.cli]
enabled = true
```

**使用 OpenAI:**

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "openai:gpt-4o"

[providers.openai]
api_key = "${OPENAI_API_KEY}"

[channels.cli]
enabled = true
```

**使用 OpenAI 兼容 API**（如 DeepSeek、通义千问、月之暗面、智谱、本地大模型等）:

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "deepseek:deepseek-chat"

[providers.deepseek]
api_key = "${DEEPSEEK_API_KEY}"
api_base = "https://api.deepseek.com/v1"

[channels.cli]
enabled = true
```

完整配置选项请参考 [config.example.cn.toml](config.example.cn.toml)。

3. 设置环境变量：

```bash
export ANTHROPIC_API_KEY="your-api-key"  # Anthropic Claude
# 或
export OPENAI_API_KEY="your-api-key"      # OpenAI
# 或
export DEEPSEEK_API_KEY="your-api-key"    # DeepSeek
```

### 运行

```bash
# 启动 CLI 交互会话
deepcobot run

# 指定配置文件
deepcobot run --config /path/to/config.toml

# 启动机器人渠道（Telegram、Discord、飞书、钉钉等）
deepcobot bot

# 启动 LangGraph 服务器
deepcobot serve --port 8123
```

### 使用 DeepAgents UI

DeepCoBot 支持与 [deepagents-ui](https://github.com/langchain-ai/deep-agents-ui) 集成，提供网页界面与 AI 助手交互。

**安装 DeepAgents UI**

```bash
# 克隆仓库
git clone https://github.com/langchain-ai/deep-agents-ui.git
cd deep-agents-ui

# 安装依赖
yarn install
```

**启动 UI**

1. 启动 LangGraph 服务器：

```bash
deepcobot serve --port 8123
```

你会看到类似输出：
```
╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: http://127.0.0.1:8123
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
- 📚 API Docs: http://127.0.0.1:8123/docs
```

Studio UI 链接可以连接到 [LangGraph Studio](https://studio.langchain.com/)（LangSmith 云服务）进行 tracing 和调试。这是可选的 - 你可以直接使用本地的 DeepAgents UI，无需 LangSmith。

2. 启动 DeepAgents UI：

```bash
cd deep-agents-ui
yarn dev
```

3. 打开浏览器访问 [http://localhost:3000](http://localhost:3000)

4. 在 UI 中配置连接：
   - **Deployment URL**: `http://127.0.0.1:8123`（或你的服务器地址）
   - **Assistant ID**: `agent`（定义在 `langgraph.json` 中）

**功能特性**

- 实时聊天界面，支持流式响应
- 会话管理，查看对话历史
- 查看 agent 状态中的文件
- 工具调用检查与审批
- 调试模式，支持逐步执行
- 深色/浅色主题支持

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
deepcobot bot
```

### 钉钉机器人

配置 `~/.deepcobot/config.toml`：

```toml
[channels.dingtalk]
enabled = true
client_id = "${DINGTALK_CLIENT_ID}"
client_secret = "${DINGTALK_CLIENT_SECRET}"
allowed_users = []
```

运行：

```bash
export DINGTALK_CLIENT_ID="your-client-id"
export DINGTALK_CLIENT_SECRET="your-client-secret"
deepcobot bot
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
| `agent.model` | LLM 模型（格式：`提供商:模型名`） | `anthropic:claude-sonnet-4-6` |
| `agent.max_tokens` | 最大输出 token | `8192` |
| `agent.enable_memory` | 启用记忆系统 | `true` |
| `agent.enable_skills` | 启用技能系统 | `true` |
| `agent.auto_approve` | 自动审批工具 | `false` |

### LLM 提供商配置

DeepCoBot 支持多种 OpenAI 兼容格式的 LLM 提供商：

| 提供商 | 模型格式 | API Base |
|--------|----------|----------|
| Anthropic | `anthropic:claude-sonnet-4-6` | 默认：`https://api.anthropic.com` |
| OpenAI | `openai:gpt-4o` | 默认：`https://api.openai.com/v1` |
| DeepSeek | `deepseek:deepseek-chat` | `https://api.deepseek.com/v1` |
| 月之暗面 | `moonshot:moonshot-v1-8k` | `https://api.moonshot.cn/v1` |
| 智谱 | `zhipu:glm-4` | `https://open.bigmodel.cn/api/paas/v4` |
| 通义千问 | `qwen:qwen-turbo` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 本地大模型 (Ollama) | `ollama:llama3` | `http://localhost:11434/v1` |

使用自定义提供商时，在 `[providers]` 部分定义 `api_key` 和 `api_base`：

```toml
[providers.custom_provider]
api_key = "${CUSTOM_API_KEY}"
api_base = "https://your-api-endpoint.com/v1"
```

### LangSmith 配置

配置 LangSmith 用于追踪和调试：

```toml
[langsmith]
enabled = true
api_key = "${LANGSMITH_API_KEY}"  # LangSmith API 密钥 (lsv2_pt_...)
project = "my-project"             # 可选：项目名称
```

或通过环境变量配置：

```bash
export LANGSMITH_API_KEY="lsv2_pt_xxxx"
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_PROJECT="my-project"
```

### 环境变量

- `ANTHROPIC_API_KEY`: Anthropic API 密钥
- `OPENAI_API_KEY`: OpenAI API 密钥
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `DISCORD_BOT_TOKEN`: Discord Bot Token
- `DINGTALK_CLIENT_ID`: 钉钉 Client ID
- `DINGTALK_CLIENT_SECRET`: 钉钉 Client Secret
- `FEISHU_APP_ID`: 飞书 App ID
- `FEISHU_APP_SECRET`: 飞书 App Secret
- `LANGSMITH_API_KEY`: LangSmith API 密钥用于追踪（可选）
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
git clone https://github.com/cobothub/deepcobot.git
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