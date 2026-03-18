"""Internationalization (i18n) support for CLI.

Supports English and Chinese languages.
"""

from typing import Literal

# Supported languages
Language = Literal["en", "zh"]

# Default language
DEFAULT_LANGUAGE: Language = "en"

# Current language (can be changed at runtime)
_current_language: Language = DEFAULT_LANGUAGE


def set_language(lang: Language) -> None:
    """Set the current language."""
    global _current_language
    _current_language = lang


def get_language() -> Language:
    """Get the current language."""
    return _current_language


# Translation dictionaries
TRANSLATIONS: dict[str, dict[Language, str]] = {
    # App description
    "app.name": {
        "en": "DeepCoBot - A minimalist personal AI assistant framework",
        "zh": "DeepCoBot - 极简封装的个人 AI 助理框架",
    },
    "app.version_help": {
        "en": "Show version information",
        "zh": "显示版本信息",
    },

    # Run command
    "run.description": {
        "en": "Start an interactive CLI session.",
        "zh": "启动 CLI 交互会话。",
    },
    "run.example1": {
        "en": "deepcobot run",
        "zh": "deepcobot run",
    },
    "run.example2": {
        "en": "deepcobot run --config /path/to/config.toml",
        "zh": "deepcobot run --config /path/to/config.toml",
    },
    "run.example3": {
        "en": "deepcobot run --thread my-session",
        "zh": "deepcobot run --thread my-session",
    },
    "run.config_help": {
        "en": "Path to configuration file",
        "zh": "配置文件路径",
    },
    "run.thread_help": {
        "en": "Session thread ID for conversation persistence",
        "zh": "会话线程 ID（用于对话持久化）",
    },
    "run.auto_approve_help": {
        "en": "Auto-approve all tool calls",
        "zh": "自动审批所有工具调用",
    },
    "run.prompt_input": {
        "en": "Type your message and press Enter. Type 'exit' or 'quit' to end.",
        "zh": "输入消息后按回车发送。输入 'exit' 或 'quit' 退出。",
    },
    "run.prompt_reset": {
        "en": "Type 'reset' to clear conversation history.",
        "zh": "输入 'reset' 清空对话历史。",
    },
    "run.thinking": {
        "en": "Thinking...",
        "zh": "思考中...",
    },
    "run.goodbye": {
        "en": "Goodbye!",
        "zh": "再见！",
    },
    "run.history_cleared": {
        "en": "Conversation history cleared.",
        "zh": "对话历史已清空。",
    },
    "run.use_exit": {
        "en": "Use 'exit' or 'quit' to end the session.",
        "zh": "请输入 'exit' 或 'quit' 退出会话。",
    },
    "run.error": {
        "en": "Error:",
        "zh": "错误：",
    },

    # Config command
    "config.description": {
        "en": "Manage configuration file.",
        "zh": "管理配置文件。",
    },
    "config.example_init": {
        "en": "deepcobot config --init    # Create default config file",
        "zh": "deepcobot config --init    # 创建默认配置文件",
    },
    "config.example_show": {
        "en": "deepcobot config --show    # Show config file path",
        "zh": "deepcobot config --show    # 显示配置文件路径",
    },
    "config.init_help": {
        "en": "Create default configuration file",
        "zh": "创建默认配置文件",
    },
    "config.show_help": {
        "en": "Show current configuration path",
        "zh": "显示当前配置路径",
    },
    "config.created": {
        "en": "Created config file:",
        "zh": "已创建配置文件：",
    },
    "config.edit_hint": {
        "en": "Edit the file and configure your API keys:",
        "zh": "编辑该文件并配置你的 API 密钥：",
    },
    "config.not_exists": {
        "en": "(not exists)",
        "zh": "(不存在)",
    },
    "config.use_hint": {
        "en": "Use --init to create a config file or --show to display config path.",
        "zh": "使用 --init 创建配置文件或 --show 显示配置路径。",
    },

    # Serve command
    "serve.description": {
        "en": "Start LangGraph server.",
        "zh": "启动 LangGraph 服务器。",
    },
    "serve.example1": {
        "en": "deepcobot serve",
        "zh": "deepcobot serve",
    },
    "serve.example2": {
        "en": "deepcobot serve --port 8124",
        "zh": "deepcobot serve --port 8124",
    },
    "serve.config_help": {
        "en": "Path to configuration file",
        "zh": "配置文件路径",
    },
    "serve.host_help": {
        "en": "Server listen address",
        "zh": "服务器监听地址",
    },
    "serve.port_help": {
        "en": "Server listen port",
        "zh": "服务器监听端口",
    },
    "serve.server_title": {
        "en": "Starting Server",
        "zh": "启动服务器",
    },
    "serve.generated": {
        "en": "Generated langgraph.json",
        "zh": "已生成 langgraph.json",
    },
    "serve.starting": {
        "en": "Starting LangGraph server...",
        "zh": "正在启动 LangGraph 服务器...",
    },
    "serve.ctrlc": {
        "en": "Use Ctrl+C to stop",
        "zh": "按 Ctrl+C 停止",
    },
    "serve.not_found": {
        "en": "Error: langgraph CLI not found",
        "zh": "错误：未找到 langgraph CLI",
    },
    "serve.install_hint": {
        "en": "Install it with: pip install langgraph-cli",
        "zh": "安装命令：pip install langgraph-cli",
    },
    "serve.stopped": {
        "en": "Server stopped",
        "zh": "服务器已停止",
    },

    # Cron commands
    "cron.description": {
        "en": "Manage scheduled tasks",
        "zh": "管理定时任务",
    },
    "cron.list_description": {
        "en": "List all scheduled tasks.",
        "zh": "列出所有定时任务。",
    },
    "cron.list_example1": {
        "en": "deepcobot cron list",
        "zh": "deepcobot cron list",
    },
    "cron.list_example2": {
        "en": "deepcobot cron list --all",
        "zh": "deepcobot cron list --all",
    },
    "cron.all_help": {
        "en": "Show all tasks (including disabled)",
        "zh": "显示所有任务（包括禁用的）",
    },
    "cron.no_jobs": {
        "en": "No cron jobs found",
        "zh": "未找到定时任务",
    },
    "cron.table_id": {
        "en": "ID",
        "zh": "ID",
    },
    "cron.table_name": {
        "en": "Name",
        "zh": "名称",
    },
    "cron.table_schedule": {
        "en": "Schedule",
        "zh": "调度",
    },
    "cron.table_status": {
        "en": "Status",
        "zh": "状态",
    },
    "cron.table_next_run": {
        "en": "Next Run",
        "zh": "下次运行",
    },
    "cron.enabled": {
        "en": "enabled",
        "zh": "已启用",
    },
    "cron.disabled": {
        "en": "disabled",
        "zh": "已禁用",
    },
    "cron.every": {
        "en": "every",
        "zh": "每",
    },
    "cron.once": {
        "en": "once",
        "zh": "一次性",
    },

    # Cron add
    "cron.add_description": {
        "en": "Add a scheduled task.",
        "zh": "添加定时任务。",
    },
    "cron.add_example1": {
        "en": "deepcobot cron add \"daily-report\" \"Generate daily report\" --every 24h",
        "zh": "deepcobot cron add \"daily-report\" \"生成日报\" --every 24h",
    },
    "cron.add_example2": {
        "en": "deepcobot cron add \"hourly-check\" \"Check status\" --cron \"0 * * * *\"",
        "zh": "deepcobot cron add \"hourly-check\" \"检查状态\" --cron \"0 * * * *\"",
    },
    "cron.name_help": {
        "en": "Task name",
        "zh": "任务名称",
    },
    "cron.message_help": {
        "en": "Message to send to Agent",
        "zh": "发送给 Agent 的消息",
    },
    "cron.every_help": {
        "en": "Execution interval (e.g. 1h, 30m, 1d)",
        "zh": "执行间隔（如 1h, 30m, 1d）",
    },
    "cron.cron_help": {
        "en": "Cron expression (5 fields)",
        "zh": "Cron 表达式（5 字段）",
    },
    "cron.channel_help": {
        "en": "Channel to send results",
        "zh": "结果发送渠道",
    },
    "cron.chat_id_help": {
        "en": "Target chat ID for results",
        "zh": "结果发送目标",
    },
    "cron.created": {
        "en": "Created cron job:",
        "zh": "已创建定时任务：",
    },
    "cron.invalid_interval": {
        "en": "Invalid interval:",
        "zh": "无效的间隔：",
    },

    # Cron remove
    "cron.remove_description": {
        "en": "Remove a scheduled task.",
        "zh": "移除定时任务。",
    },
    "cron.remove_example": {
        "en": "deepcobot cron remove abc123",
        "zh": "deepcobot cron remove abc123",
    },
    "cron.job_id_help": {
        "en": "Task ID",
        "zh": "任务 ID",
    },
    "cron.removed": {
        "en": "Removed cron job:",
        "zh": "已移除定时任务：",
    },
    "cron.not_found": {
        "en": "Job not found:",
        "zh": "未找到任务：",
    },

    # Cron run
    "cron.run_description": {
        "en": "Execute a scheduled task immediately.",
        "zh": "立即执行定时任务。",
    },
    "cron.run_example": {
        "en": "deepcobot cron run abc123",
        "zh": "deepcobot cron run abc123",
    },
    "cron.running": {
        "en": "Running job:",
        "zh": "正在运行任务：",
    },
    "cron.executed": {
        "en": "Job executed:",
        "zh": "任务已执行：",
    },

    # Welcome panel
    "welcome.title": {
        "en": "Welcome",
        "zh": "欢迎",
    },
    "assistant.title": {
        "en": "Assistant",
        "zh": "助手",
    },

    # Errors
    "error.config": {
        "en": "Configuration Error:",
        "zh": "配置错误：",
    },
}


def t(key: str, lang: Language | None = None) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key
        lang: Optional language override

    Returns:
        Translated string
    """
    language = lang or _current_language
    if key in TRANSLATIONS:
        return TRANSLATIONS[key].get(language, TRANSLATIONS[key].get(DEFAULT_LANGUAGE, key))
    return key


def get_available_languages() -> list[Language]:
    """Get list of available languages."""
    return ["en", "zh"]