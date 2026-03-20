# DeepCoBot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README_CN.md) | English

**Production-Ready AI Assistant Framework powered by [DeepAgents](https://github.com/langchain-ai/deepagents) & [LangGraph](https://github.com/langchain-ai/langgraph).**

DeepCoBot bridges the LangChain/LangGraph ecosystem with real-world deployment scenarios, providing enterprise-grade AI agents with multi-channel support, visual debugging, and comprehensive observability.

## Why DeepCoBot?

Built on the powerful [DeepAgents SDK](https://github.com/langchain-ai/deepagents), DeepCoBot extends its capabilities for production use:

| Feature | What You Get |
|---------|-------------|
| 🧠 **Intelligent Memory** | Persistent conversation memory with semantic recall |
| 🛠️ **Extensible Skills** | Custom skill system for domain-specific capabilities |
| 🔄 **State Management** | LangGraph checkpointer for pause/resume workflows |
| 📊 **Full Observability** | LangSmith tracing, Prometheus metrics, structured logs |
| 🌐 **Multi-Channel** | Telegram, Discord, Feishu, DingTalk, Web API, CLI |
| 🎨 **Visual Debugging** | LangGraph Studio & DeepAgents UI integration |
| 🔌 **MCP Support** | Model Context Protocol for external tool integration |

## Ecosystem Advantage

DeepCoBot leverages the full power of the LangChain ecosystem:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DeepCoBot Architecture                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Claude     │  │  GPT-4o     │  │  DeepSeek   │  Multi-Model    │
│  │  Anthropic  │  │  OpenAI     │  │  Qwen/Local │  Support        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    DeepAgents SDK                              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │ │
│  │  │   Memory     │ │   Skills     │ │  Filesystem  │   Core    │ │
│  │  │  Middleware  │ │  Middleware  │ │  Middleware  │   Engine   │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │ │
│  │  │ Local Shell  │ │  SQLite Save │ │ MCP Adapters │           │ │
│  │  │   Backend    │ │  Checkpoint  │ │  (External)  │           │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘           │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                          │                                          │
│                          ▼                                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    LangGraph Runtime                           │ │
│  │   Graph Orchestration │ State Persistence │ Streaming        │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                          │                                          │
│         ┌────────────────┼────────────────┐                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ LangSmith   │  │ LangGraph   │  │ DeepAgents  │   Observability │
│  │ Tracing     │  │ Studio      │  │ UI          │   & Debug       │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Channel Layer                              │   │
│  │  Telegram │ Discord │ Feishu │ DingTalk │ Web API │ CLI    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### What You Get from the Ecosystem

| From | Benefits |
|------|----------|
| **LangGraph** | Graph-based agent orchestration, state persistence, human-in-the-loop, streaming support |
| **LangChain** | 100+ tool integrations, document loaders, vector stores, output parsers |
| **LangSmith** | Production tracing, prompt versioning, evaluation datasets, cost tracking |
| **DeepAgents SDK** | Reference agent implementation, middleware patterns, shell sandbox |
| **MCP** | Universal tool protocol for external services (files, APIs, databases) |

## Requirements

- Python >= 3.11
- DeepAgents SDK >= 0.4

## Quick Start

### Installation

**From Source (Recommended)**

```bash
# Clone the repository
git clone https://github.com/cobothub/deepcobot.git
cd deepcobot

# Create virtual environment (requires Python 3.11+)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in development mode
pip install -e .

# Install with specific channel support
pip install -e ".[telegram]"    # Telegram
pip install -e ".[discord]"     # Discord
pip install -e ".[feishu]"      # Feishu
pip install -e ".[dingtalk]"    # DingTalk
pip install -e ".[web]"         # Web API

# Install all features
pip install -e ".[all]"

# Install development dependencies
pip install -e ".[dev]"
```

**From PyPI (Coming Soon)**

```bash
# Will be available after first release
pip install deepcobot
```

### Configuration

1. Create configuration directory:

```bash
mkdir -p ~/.deepcobot
```

2. Create configuration file `~/.deepcobot/config.toml`:

**Using Anthropic Claude:**

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[channels.cli]
enabled = true
```

**Using OpenAI:**

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "openai:gpt-4o"

[providers.openai]
api_key = "${OPENAI_API_KEY}"

[channels.cli]
enabled = true
```

**Using OpenAI-Compatible APIs** (e.g., DeepSeek, Qwen, Moonshot, Zhipu, local LLMs):

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

See [config.example.toml](config.example.toml) for complete configuration options.

3. Set environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"  # For Anthropic Claude
# or
export OPENAI_API_KEY="your-api-key"      # For OpenAI
# or
export DEEPSEEK_API_KEY="your-api-key"    # For DeepSeek
```

### Running

```bash
# Start CLI interactive session
deepcobot run

# Specify configuration file
deepcobot run --config /path/to/config.toml

# Start bot channels (Telegram, Discord, Feishu, DingTalk, etc.)
deepcobot bot

# Start LangGraph server
deepcobot serve --port 8123
```

### Using DeepAgents UI

DeepCoBot supports integration with [deepagents-ui](https://github.com/langchain-ai/deep-agents-ui), a web-based interface for interacting with your AI assistant.

**Install DeepAgents UI**

```bash
# Clone the repository
git clone https://github.com/langchain-ai/deep-agents-ui.git
cd deep-agents-ui

# Install dependencies
yarn install
```

**Running with UI**

1. Start the LangGraph server:

```bash
deepcobot serve --port 8123
```

You will see output like:
```
╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: http://127.0.0.1:8123
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
- 📚 API Docs: http://127.0.0.1:8123/docs
```

The Studio UI link allows you to connect to [LangGraph Studio](https://studio.langchain.com/) (LangSmith cloud service) for tracing and debugging. This is optional - you can use DeepAgents UI locally without LangSmith.

2. Start the DeepAgents UI:

```bash
cd deep-agents-ui
yarn dev
```

3. Open your browser at [http://localhost:3000](http://localhost:3000)

4. Configure the connection in the UI:
   - **Deployment URL**: `http://127.0.0.1:8123` (or your server address)
   - **Assistant ID**: `agent` (defined in `langgraph.json`)

**Features**

- Real-time chat interface with streaming responses
- Thread management for conversation history
- File visualization from agent state
- Tool call inspection and approval
- Debug mode for step-by-step execution
- Dark/Light theme support

## Usage Examples

### CLI Interaction

```bash
$ deepcobot run

Welcome to DeepCoBot!
Type your message and press Enter. Type 'exit' or 'quit' to end.

You: Hello, please introduce yourself
Assistant: Hello! I am an AI assistant that can help you with various tasks...
```

### Telegram Bot

Configure `~/.deepcobot/config.toml`:

```toml
[channels.telegram]
enabled = true
token = "${TELEGRAM_BOT_TOKEN}"
allowed_users = ["your_telegram_id"]
```

Run:

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
deepcobot bot
```

### DingTalk Bot

Configure `~/.deepcobot/config.toml`:

```toml
[channels.dingtalk]
enabled = true
client_id = "${DINGTALK_CLIENT_ID}"
client_secret = "${DINGTALK_CLIENT_SECRET}"
allowed_users = []
```

Run:

```bash
export DINGTALK_CLIENT_ID="your-client-id"
export DINGTALK_CLIENT_SECRET="your-client-secret"
deepcobot bot
```

### Web API

Configuration:

```toml
[channels.web]
enabled = true
host = "0.0.0.0"
port = 8080
api_key = "${WEB_API_KEY}"
```

API Call:

```bash
curl -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello"}'
```

## Configuration Reference

### Core Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `agent.workspace` | Workspace directory | `~/.deepcobot/workspace` |
| `agent.model` | LLM model (format: `provider:model`) | `anthropic:claude-sonnet-4-6` |
| `agent.max_tokens` | Maximum output tokens | `8192` |
| `agent.enable_memory` | Enable memory system | `true` |
| `agent.enable_skills` | Enable skills system | `true` |
| `agent.auto_approve` | Auto-approve tools | `false` |

### LLM Provider Configuration

DeepCoBot supports multiple LLM providers with OpenAI-compatible API format:

| Provider | Model Format | API Base |
|----------|-------------|----------|
| Anthropic | `anthropic:claude-sonnet-4-6` | Default: `https://api.anthropic.com` |
| OpenAI | `openai:gpt-4o` | Default: `https://api.openai.com/v1` |
| DeepSeek | `deepseek:deepseek-chat` | `https://api.deepseek.com/v1` |
| Moonshot | `moonshot:moonshot-v1-8k` | `https://api.moonshot.cn/v1` |
| Zhipu (智谱) | `zhipu:glm-4` | `https://open.bigmodel.cn/api/paas/v4` |
| Qwen (通义千问) | `qwen:qwen-turbo` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Local LLM (Ollama) | `ollama:llama3` | `http://localhost:11434/v1` |

To use a custom provider, define it in the `[providers]` section with `api_key` and `api_base`:

```toml
[providers.custom_provider]
api_key = "${CUSTOM_API_KEY}"
api_base = "https://your-api-endpoint.com/v1"
```

### LangSmith Configuration

Configure LangSmith for tracing and debugging:

```toml
[langsmith]
enabled = true
api_key = "${LANGSMITH_API_KEY}"  # Your LangSmith API key (lsv2_pt_...)
project = "my-project"             # Optional: project name
```

Or via environment variables:

```bash
export LANGSMITH_API_KEY="lsv2_pt_xxxx"
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_PROJECT="my-project"
```

## Observability

DeepCoBot provides observability through LangSmith integration.

### LangSmith Tracing

[LangSmith](https://www.langchain.com/langsmith) is a platform for tracing, testing, and debugging LLM applications. DeepCoBot integrates seamlessly with LangSmith for detailed observability.

**Enable LangSmith Tracing:**

```toml
[langsmith]
enabled = true
api_key = "${LANGSMITH_API_KEY}"
project = "deepcobot-traces"
```

**What LangSmith Captures:**

- **Conversation Traces**: Complete message flows with timing information
- **Tool Calls**: All tool invocations with inputs/outputs and approval status
- **Memory Operations**: Memory reads and writes during conversations
- **Skills Execution**: Skill loading and execution details
- **Token Usage**: Input/output token counts for cost tracking
- **Latency Metrics**: Response time breakdown by component

**Benefits:**

1. **Debug Complex Issues**: Step through conversations to understand agent behavior
2. **Cost Analysis**: Track token usage across sessions
3. **Performance Optimization**: Identify bottlenecks in tool calls or LLM responses
4. **Regression Testing**: Create test cases from traced conversations

**Access LangSmith Dashboard:**

Once enabled, traces appear in [LangSmith Dashboard](https://smith.langchain.com/). You can also use [LangGraph Studio](https://studio.langchain.com/) when running `deepcobot serve`:

```bash
deepcobot serve --port 8123
# Open the Studio UI link shown in the output
```

### Structured Logging

Configure logging for production environments:

```toml
[logging]
level = "INFO"
json_format = true
file = "~/.deepcobot/deepcobot.log"
```

Or via environment variable:

```bash
export DEEPCOBOT_LOG_LEVEL="DEBUG"
export DEEPCOBOT_LOG_JSON="true"
```

### Environment Variables

- `ANTHROPIC_API_KEY`: Anthropic API key
- `OPENAI_API_KEY`: OpenAI API key
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `DISCORD_BOT_TOKEN`: Discord Bot Token
- `DINGTALK_CLIENT_ID`: DingTalk Client ID
- `DINGTALK_CLIENT_SECRET`: DingTalk Client Secret
- `FEISHU_APP_ID`: Feishu App ID
- `FEISHU_APP_SECRET`: Feishu App Secret
- `LANGSMITH_API_KEY`: LangSmith API key for tracing (optional)
- `DEEPCOBOT_LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR)
- `DEEPCOBOT_LOG_JSON`: Use JSON format logs (true/false)

## Docker Deployment

```bash
# Build image
docker build -f docker/Dockerfile -t deepcobot .

# Use Docker Compose
cd docker
docker-compose up -d
```

## Development

```bash
# Clone repository
git clone https://github.com/cobothub/deepcobot.git
cd deepcobot

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code linting
ruff check deepcobot
mypy deepcobot
```

## Message Flow

```
Inbound:  Channel → MessageBus → DeepAgents SDK → LLM
Outbound: LLM → DeepAgents SDK → MessageBus → Channel
```

**Core Components:**
- **MessageBus**: Async queue for bidirectional message routing
- **DeepAgents SDK**: Core agent engine with memory, skills, filesystem middleware
- **LangGraph Runtime**: State persistence, checkpoint recovery, streaming support
- **Channel Adapters**: Unified interface for multi-platform deployment

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

This project draws design inspiration from the following excellent projects:

### [OpenClaw](https://github.com/openclaw/openclaw)

### [CoPaw](https://github.com/agentscope-ai/CoPaw)

### [Nanobot](https://github.com/HKUDS/nanobot)

### Design Philosophy

DeepCoBot's core philosophy is **production-ready by default**, bridging the gap between DeepAgents SDK capabilities and real-world deployment needs. By learning from the design excellence of the above projects, we provide:

- **Ecosystem Integration**: Seamless integration with LangChain tools, LangGraph workflows, and LangSmith observability
- **Multi-Channel Deployment**: Unified message processing across Telegram, Discord, Feishu, DingTalk, Web API, and CLI
- **Enterprise-Grade Features**: Persistent memory, skill extensibility, tool approval, and health monitoring
- **Developer Experience**: Configuration-driven setup with visual debugging support via LangGraph Studio