# DeepCoBot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

中文文档 | [English](README.md)

**基于 [DeepAgents](https://github.com/langchain-ai/deepagents) 与 [LangGraph](https://github.com/langchain-ai/langgraph) 生态的生产级 AI 助理框架。**

DeepCoBot 将 LangChain/LangGraph 生态能力与实际部署场景无缝衔接，提供企业级 AI Agent 解决方案，支持多渠道部署、可视化调试与全链路可观测性。

## 为什么选择 DeepCoBot？

基于强大的 [DeepAgents SDK](https://github.com/langchain-ai/deepagents)，DeepCoBot 面向生产环境进行了扩展：

| 特性 | 说明 |
|-----|------|
| 🧠 **智能记忆** | 持久化对话记忆，支持语义召回 |
| 🛠️ **技能扩展** | 自定义技能系统，支持领域特定能力 |
| 🔄 **状态管理** | LangGraph Checkpointer 支持工作流暂停/恢复 |
| 📊 **全链路可观测** | LangSmith 追踪、Prometheus 指标、结构化日志 |
| 🌐 **多渠道部署** | Telegram、Discord、飞书、钉钉、Web API、CLI |
| 🎨 **可视化调试** | LangGraph Studio 与 DeepAgents UI 集成 |
| 🔌 **MCP 支持** | Model Context Protocol 外部工具集成 |

## 生态优势

DeepCoBot 充分发挥 LangChain 生态的全部能力：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DeepCoBot 架构图                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Claude     │  │  GPT-4o     │  │  DeepSeek   │  多模型         │
│  │  Anthropic  │  │  OpenAI     │  │  通义/本地   │  支持           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    DeepAgents SDK                              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │ │
│  │  │   Memory     │ │   Skills     │ │  Filesystem  │   核心    │ │
│  │  │  Middleware  │ │  Middleware  │ │  Middleware  │   引擎    │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │ │
│  │  │ Local Shell  │ │  SQLite Save │ │ MCP Adapters │           │ │
│  │  │   Backend    │ │  Checkpoint  │ │  (外部工具)   │           │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘           │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                          │                                          │
│                          ▼                                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    LangGraph Runtime                           │ │
│  │   图编排引擎  │  状态持久化  │  流式输出                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                          │                                          │
│         ┌────────────────┼────────────────┐                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ LangSmith   │  │ LangGraph   │  │ DeepAgents  │   可观测与      │
│  │ 追踪平台    │  │ Studio      │  │ UI          │   调试界面      │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      渠道接入层                              │   │
│  │  Telegram │ Discord │ 飞书 │ 钉钉 │ Web API │ CLI           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 生态能力一览

| 来源 | 能力收益 |
|------|----------|
| **LangGraph** | 图编排引擎、状态持久化、人机协作、流式输出 |
| **LangChain** | 100+ 工具集成、文档加载器、向量数据库、输出解析器 |
| **LangSmith** | 生产级追踪、Prompt 版本管理、评估数据集、成本监控 |
| **DeepAgents SDK** | 参考 Agent 实现、中间件模式、Shell 沙箱 |
| **MCP** | 通用工具协议，接入外部服务（文件、API、数据库等） |

## 系统要求

- Python >= 3.11
- DeepAgents SDK >= 0.4

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

## 可观测性

DeepCoBot 通过 LangSmith 集成提供可观测性支持。

### LangSmith 追踪

[LangSmith](https://www.langchain.com/langsmith) 是一个用于追踪、测试和调试 LLM 应用的平台。DeepCoBot 与 LangSmith 无缝集成，提供详细的可观测性。

**启用 LangSmith 追踪：**

```toml
[langsmith]
enabled = true
api_key = "${LANGSMITH_API_KEY}"
project = "deepcobot-traces"
```

**LangSmith 捕获的内容：**

- **对话追踪**：完整的消息流及时间信息
- **工具调用**：所有工具调用的输入/输出及审批状态
- **记忆操作**：对话过程中的记忆读写
- **技能执行**：技能加载和执行详情
- **Token 用量**：输入/输出 Token 数量，用于成本追踪
- **延迟指标**：各组件响应时间分解

**优势：**

1. **调试复杂问题**：逐步查看对话，理解 Agent 行为
2. **成本分析**：追踪跨会话的 Token 用量
3. **性能优化**：识别工具调用或 LLM 响应的瓶颈
4. **回归测试**：从追踪的对话创建测试用例

**访问 LangSmith 控制台：**

启用后，追踪数据会出现在 [LangSmith 控制台](https://smith.langchain.com/)。运行 `deepcobot serve` 时也可使用 [LangGraph Studio](https://studio.langchain.com/)：

```bash
deepcobot serve --port 8123
# 打开输出中显示的 Studio UI 链接
```

### 结构化日志

配置生产环境的日志输出：

```toml
[logging]
level = "INFO"
json_format = true
file = "~/.deepcobot/deepcobot.log"
```

或通过环境变量：

```bash
export DEEPCOBOT_LOG_LEVEL="DEBUG"
export DEEPCOBOT_LOG_JSON="true"
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

## 消息流

```
入站:  渠道 → MessageBus → DeepAgents SDK → LLM
出站:  LLM → DeepAgents SDK → MessageBus → 渠道
```

**核心组件：**
- **MessageBus**：异步队列，负责双向消息路由
- **DeepAgents SDK**：核心 Agent 引擎，集成记忆、技能、文件系统中件
- **LangGraph Runtime**：状态持久化、断点恢复、流式输出
- **Channel Adapters**：统一接口，支持多平台部署

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 致谢

本项目参考了以下优秀项目的设计思想：

### [OpenClaw](https://github.com/openclaw/openclaw)

### [CoPaw](https://github.com/agentscope-ai/CoPaw)

### [Nanobot](https://github.com/HKUDS/nanobot)

### 设计理念

DeepCoBot 的核心理念是**开箱即用的生产级方案**，弥合 DeepAgents SDK 能力与实际部署需求之间的鸿沟。通过参考上述项目的设计精华，我们提供：

- **生态集成**：无缝对接 LangChain 工具链、LangGraph 工作流、LangSmith 可观测平台
- **多渠道部署**：统一的接入层，支持 Telegram、Discord、飞书、钉钉、Web API、CLI 等多渠道
- **企业级特性**：持久化记忆、技能扩展、工具审批、健康监控等生产必备能力
- **开发者体验**：配置驱动启动，支持 LangGraph Studio 可视化调试