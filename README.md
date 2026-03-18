# DeepCoBot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README_CN.md) | English

A minimalist personal AI assistant framework built on [DeepAgents](https://github.com/langchain-ai/deepagents).

## Requirements

- Python >= 3.11
- DeepAgents SDK (requires Python >= 3.11)

## Features

- **Configuration-Driven**: Everything is configurable, zero-code startup via TOML files
- **Multi-Channel Support**: CLI, Telegram, Discord, Feishu, DingTalk, Web API
- **DeepAgents Integration**: Built-in memory system, skills system, tool approval
- **LangGraph Compatible**: Support for LangGraph server deployment
- **Observability**: Built-in health checks, Prometheus metrics, structured logging

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

```toml
[agent]
workspace = "~/.deepcobot/workspace"
model = "anthropic:claude-sonnet-4-6"

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[channels.cli]
enabled = true
```

3. Set environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Running

```bash
# Start CLI interactive session
deepcobot run

# Specify configuration file
deepcobot run --config /path/to/config.toml

# Start LangGraph server
deepcobot serve --port 8123
```

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
deepcobot run
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
| `agent.model` | LLM model | `anthropic:claude-sonnet-4-6` |
| `agent.max_tokens` | Maximum output tokens | `8192` |
| `agent.enable_memory` | Enable memory system | `true` |
| `agent.enable_skills` | Enable skills system | `true` |
| `agent.auto_approve` | Auto-approve tools | `false` |

### Environment Variables

- `ANTHROPIC_API_KEY`: Anthropic API key
- `OPENAI_API_KEY`: OpenAI API key
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `DISCORD_BOT_TOKEN`: Discord Bot Token
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

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DeepCoBot                               │
├─────────────────────────────────────────────────────────────────┤
│  Channel Layer  │  Telegram  │  Discord  │  Feishu  │  DingTalk  │  Web API  │  CLI  │
│                 └───────────────────────┬───────────────────────┘
│                                           │
│                                           ▼
│  Message Bus Layer                   MessageBus (Async Queue)
│                                           │
│                                           ▼
│  Agent Core Layer                    DeepCoBotAgent (SDK Wrapper)
│                                           │
├───────────────────────────────────────────┼──────────────────────┤
│  DeepAgents SDK                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │Filesystem   │ │  Memory     │ │  Skills     │                │
│  │Middleware   │ │ Middleware  │ │ Middleware  │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │LocalShell   │ │ SqliteSaver │ │ AsyncSub    │                │
│  │Backend      │ │(Checkpointer)│ │AgentMiddle  │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│  Service Layer        │ CronService │ Heartbeat │ LangGraph     │
└─────────────────────────────────────────────────────────────────┘
```

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

This project draws design inspiration from the following excellent projects:

### [OpenClaw](https://github.com/openclaw/openclaw)

### [CoPaw](https://github.com/agentscope-ai/CoPaw)

### [Nanobot](https://github.com/HKUDS/nanobot)

### Design Philosophy

DeepCoBot's core philosophy is **minimalist encapsulation**, focusing on the configuration layer and channel integration layer that DeepAgents doesn't provide, maximizing reuse of existing capabilities. By learning from the design excellence of the above projects, we achieved:

- Clear layered architecture (Config Layer → Channel Layer → Agent Layer → Service Layer)
- Extensible channel integration mechanism
- Unified message processing flow
- Comprehensive service governance capabilities