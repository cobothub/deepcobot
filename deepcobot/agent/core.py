"""Agent 核心封装

封装 DeepAgents SDK 的 create_deep_agent 方法，通过配置驱动 Agent 初始化。
"""

from pathlib import Path
from typing import Any

from loguru import logger

from deepcobot.config import Config

# 延迟导入，避免在未安装时立即报错
_create_deep_agent = None
_MemoryMiddleware = None
_LocalShellBackend = None
_AsyncSqliteSaver = None


def _ensure_deepagents():
    """确保 DeepAgents SDK 已安装并导入必要组件"""
    global _create_deep_agent, _MemoryMiddleware, _LocalShellBackend, _AsyncSqliteSaver
    if _create_deep_agent is None:
        try:
            from deepagents import create_deep_agent, MemoryMiddleware
            from deepagents.backends import LocalShellBackend
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            _create_deep_agent = create_deep_agent
            _MemoryMiddleware = MemoryMiddleware
            _LocalShellBackend = LocalShellBackend
            _AsyncSqliteSaver = AsyncSqliteSaver
        except ImportError as e:
            raise ImportError(
                "DeepAgents SDK not installed. "
                "Install it with: pip install deepagents>=0.4 langgraph-checkpoint-sqlite"
            ) from e
    return _create_deep_agent, _MemoryMiddleware, _LocalShellBackend, _AsyncSqliteSaver


async def _create_async_sqlite_checkpointer(db_path: str):
    """
    异步创建 SQLite Checkpointer。

    Args:
        db_path: SQLite 数据库文件路径

    Returns:
        AsyncSqliteSaver 实例
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    # from_conn_string 是异步上下文管理器，返回 AsyncIterator
    # 我们需要手动管理生命周期，这里先直接创建
    import aiosqlite
    conn = await aiosqlite.connect(db_path)
    return AsyncSqliteSaver(conn)


def create_agent(config: Config) -> dict[str, Any]:
    """
    创建 Agent 实例（同步版本，使用 MemorySaver）。

    注意：推荐使用 _create_agent_async 进行异步操作以支持 SQLite 持久化。

    Args:
        config: 配置对象

    Returns:
        包含 graph 和相关资源的字典
    """
    create_deep_agent, MemoryMiddleware, LocalShellBackend, _ = _ensure_deepagents()
    from langgraph.checkpoint.memory import MemorySaver

    workspace = config.agent.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(exist_ok=True)
    (workspace / "skills").mkdir(exist_ok=True)

    logger.info(f"Initializing agent with workspace: {workspace}")

    system_prompt = _build_system_prompt(config)
    backend = LocalShellBackend(root_dir=str(workspace))
    checkpointer = MemorySaver()  # 同步版本使用内存存储

    logger.info("Checkpointer: MemorySaver (non-persistent)")

    middlewares = _build_middlewares(config)
    memory_sources = _build_memory_sources(config)
    skills_sources = _build_skills_sources(config)

    model = config.agent.model
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider = "anthropic"
        model_name = model

    provider_config = config.get_provider(provider)
    api_key = provider_config.api_key if provider_config else None
    api_base = provider_config.api_base if provider_config else None

    if api_key:
        import os
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            if api_base:
                os.environ["OPENAI_BASE_URL"] = api_base
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            if api_base:
                os.environ["ANTHROPIC_BASE_URL"] = api_base

    interrupt_on = None
    if not config.agent.auto_approve:
        interrupt_on = {
            "execute": True,
            "write_file": True,
            "edit_file": True,
            "web_search": True,
            "task": True,
        }

    async_subagents = _build_async_subagents(config)

    agent_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "backend": backend,
        "checkpointer": checkpointer,
        "middleware": middlewares,
        "interrupt_on": interrupt_on,
        "memory": memory_sources,
        "skills": skills_sources,
    }

    if async_subagents:
        agent_kwargs["subagents"] = async_subagents

    graph = create_deep_agent(**agent_kwargs)
    logger.info(f"Agent created: model={model}, auto_approve={config.agent.auto_approve}")

    return {
        "graph": graph,
        "checkpointer": checkpointer,
        "backend": backend,
        "workspace": workspace,
    }


async def _create_agent_async(config: Config) -> dict[str, Any]:
    """
    异步创建 Agent 实例（支持 SQLite 持久化）。

    Args:
        config: 配置对象

    Returns:
        包含 graph 和相关资源的字典
    """
    create_deep_agent, MemoryMiddleware, LocalShellBackend, _ = _ensure_deepagents()

    workspace = config.agent.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(exist_ok=True)
    (workspace / "skills").mkdir(exist_ok=True)

    logger.info(f"Initializing agent with workspace: {workspace}")

    system_prompt = _build_system_prompt(config)
    backend = LocalShellBackend(root_dir=str(workspace))

    # 使用异步 SQLite Checkpointer
    checkpoints_path = workspace / "checkpoints.db"
    checkpointer = await _create_async_sqlite_checkpointer(str(checkpoints_path))
    logger.info(f"Checkpointer: SQLite at {checkpoints_path}")

    middlewares = _build_middlewares(config)
    memory_sources = _build_memory_sources(config)
    skills_sources = _build_skills_sources(config)

    model = config.agent.model
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider = "anthropic"
        model_name = model

    provider_config = config.get_provider(provider)
    api_key = provider_config.api_key if provider_config else None
    api_base = provider_config.api_base if provider_config else None

    if api_key:
        import os
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            if api_base:
                os.environ["OPENAI_BASE_URL"] = api_base
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            if api_base:
                os.environ["ANTHROPIC_BASE_URL"] = api_base

    interrupt_on = None
    if not config.agent.auto_approve:
        interrupt_on = {
            "execute": True,
            "write_file": True,
            "edit_file": True,
            "web_search": True,
            "task": True,
        }

    async_subagents = _build_async_subagents(config)

    agent_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "backend": backend,
        "checkpointer": checkpointer,
        "middleware": middlewares,
        "interrupt_on": interrupt_on,
        "memory": memory_sources,
        "skills": skills_sources,
    }

    if async_subagents:
        agent_kwargs["subagents"] = async_subagents

    graph = create_deep_agent(**agent_kwargs)
    logger.info(f"Agent created: model={model}, auto_approve={config.agent.auto_approve}")

    return {
        "graph": graph,
        "checkpointer": checkpointer,
        "backend": backend,
        "workspace": workspace,
    }


def _build_system_prompt(config: Config) -> str:
    """
    构建系统提示词。

    Args:
        config: 配置对象

    Returns:
        系统提示词字符串
    """
    if config.agent.system_prompt:
        return config.agent.system_prompt

    workspace = config.agent.workspace

    parts = [
        "You are a helpful AI assistant.",
        "",
        f"## Working Directory",
        f"All file operations are relative to: {workspace}",
        "",
        "## Available Capabilities",
        "- File system operations (read, write, search, edit)",
        "- Shell command execution",
        "- Web search",
    ]

    # 添加记忆信息
    if config.agent.enable_memory:
        parts.append("- Persistent memory across sessions")

    # 添加技能信息
    if config.agent.enable_memory:
        skills_dir = workspace / "skills"
        if skills_dir.exists():
            skill_names = [
                d.name for d in skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            ]
            if skill_names:
                parts.append("")
                parts.append("## Loaded Skills")
                for name in skill_names:
                    parts.append(f"- {name}")

    # 添加异步子 Agent 信息
    if config.async_subagents:
        parts.append("")
        parts.append("## Available Async Sub-Agents")
        for subagent in config.async_subagents:
            parts.append(f"- {subagent.name}: {subagent.description}")

    return "\n".join(parts)


def _build_middlewares(config: Config) -> list[Any]:
    """
    构建中间件栈。

    注意: deepagents 的 memory 和 skills 通过 create_deep_agent 的参数传递，
    不是通过中间件。此函数保留用于未来可能的扩展。

    Args:
        config: 配置对象

    Returns:
        中间件列表
    """
    middlewares = []
    # 目前不需要额外中间件
    # memory 和 skills 通过 create_deep_agent 的参数直接传递
    return middlewares


def _build_memory_sources(config: Config) -> list[str] | None:
    """
    构建记忆源路径列表。

    Args:
        config: 配置对象

    Returns:
        记忆文件路径列表，如果未启用则返回 None
    """
    if not config.agent.enable_memory:
        return None

    workspace = config.agent.workspace
    memory_file = workspace / "memory" / "AGENTS.md"
    logger.info(f"Memory enabled: {memory_file}")
    return [str(memory_file)]


def _build_skills_sources(config: Config) -> list[str] | None:
    """
    构建技能源路径列表。

    Args:
        config: 配置对象

    Returns:
        技能目录路径列表，如果未启用则返回 None
    """
    if not config.agent.enable_skills:
        return None

    workspace = config.agent.workspace
    skills_dir = workspace / "skills"
    logger.info(f"Skills enabled: {skills_dir}")
    return [str(skills_dir)]


def _build_async_subagents(config: Config) -> list[dict[str, str]]:
    """
    构建异步子 Agent 列表。

    Args:
        config: 配置对象

    Returns:
        异步子 Agent 配置列表
    """
    if not config.async_subagents:
        return []

    subagents = []
    for subagent in config.async_subagents:
        subagents.append({
            "name": subagent.name,
            "description": subagent.description,
            "graph_id": subagent.graph_id,
            "url": subagent.url,
        })
        logger.info(f"Async sub-agent configured: {subagent.name}")

    return subagents


class AgentSession:
    """Agent 会话管理"""

    def __init__(self, config: Config):
        self.config = config
        self._graph = None
        self._checkpointer = None
        self._backend = None
        self._workspace: Path | None = None
        self._thread_id: str = "default"

    async def _ensure_initialized(self):
        """确保 Agent 已初始化（异步）"""
        if self._graph is None:
            resources = await _create_agent_async(self.config)
            self._graph = resources["graph"]
            self._checkpointer = resources["checkpointer"]
            self._backend = resources["backend"]
            self._workspace = resources["workspace"]

    @property
    def graph(self):
        """获取 Agent graph"""
        if self._graph is None:
            # 同步访问时，抛出错误提示
            raise RuntimeError(
                "Agent not initialized. Call 'await session.initialize()' first, "
                "or use an async context."
            )
        return self._graph

    @property
    def checkpointer(self):
        """获取 checkpointer"""
        if self._checkpointer is None:
            raise RuntimeError("Agent not initialized.")
        return self._checkpointer

    @property
    def workspace(self) -> Path:
        """获取工作空间路径"""
        if self._workspace is None:
            # workspace 可以同步初始化
            self._workspace = self.config.agent.workspace
            self._workspace.mkdir(parents=True, exist_ok=True)
        return self._workspace

    def set_thread_id(self, thread_id: str) -> None:
        """设置当前线程 ID"""
        self._thread_id = thread_id

    def get_thread_config(self) -> dict[str, Any]:
        """获取线程配置"""
        return {
            "configurable": {
                "thread_id": self._thread_id,
            }
        }

    async def invoke(self, message: str) -> str:
        """
        调用 Agent 处理消息。

        Args:
            message: 用户消息

        Returns:
            Agent 响应
        """
        await self._ensure_initialized()
        graph = self._graph
        thread_config = self.get_thread_config()

        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=thread_config,
        )

        # 提取最后一条助手消息
        if "messages" in result:
            for msg in reversed(result["messages"]):
                # 处理 langchain 消息对象（AIMessage, HumanMessage 等）
                msg_type = type(msg).__name__
                if msg_type == "AIMessage":
                    content = msg.content
                    # 处理 content 为 None 的情况（API 错误）
                    if content is None:
                        logger.error("API returned None content, possibly an authentication error")
                        return "Error: API returned empty response. Please check your API key and endpoint."
                    # OpenAI Responses API 返回的是列表格式
                    if isinstance(content, list):
                        # 提取所有 text 类型的内容
                        texts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                texts.append(item.get("text", ""))
                        return "\n".join(texts) if texts else ""
                    return str(content) if content else ""
                # 兼容字典格式的消息
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    return msg.get("content", "") or ""

        return ""

    async def stream(self, message: str):
        """
        流式调用 Agent。

        Args:
            message: 用户消息

        Yields:
            流式响应事件
        """
        graph = self.graph
        thread_config = self.get_thread_config()

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            config=thread_config,
            version="v1",
        ):
            yield event

    def reset(self) -> None:
        """重置会话"""
        self._thread_id = "default"