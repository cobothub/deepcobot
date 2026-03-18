"""Agent 核心封装

封装 DeepAgents SDK 的 create_deep_agent 方法，通过配置驱动 Agent 初始化。
"""

from pathlib import Path
from typing import Any, Callable, Awaitable, AsyncIterator

from loguru import logger

# HEARTBEAT 文件名常量
HEARTBEAT_FILE = "HEARTBEAT.md"

# 默认 HEARTBEAT.md 内容
DEFAULT_HEARTBEAT_CONTENT = """# Heartbeat Tasks

This file is read periodically by the Heartbeat service.
Write your tasks here, and the agent will execute them on schedule.

## Example Tasks

<!-- Uncomment and modify the following lines to use: -->

<!-- - Check the status of my daily backup -->
<!-- - Generate a summary of today's calendar events -->
<!-- - Review and clean up temporary files in the workspace -->

## Notes

- Tasks are executed according to the heartbeat interval configured in config.toml
- Results can be dispatched to configured channels (Telegram, Discord, etc.)
- Use clear, specific instructions for best results
"""


def _sanitize_string(s: str) -> str:
    """
    清理字符串中的无效 UTF-8 代理字符。

    某些 API 返回的数据可能包含损坏的 Unicode 代理字符（如 \udce5），
    这些字符无法被正常编码为 UTF-8。此函数将其替换为 Unicode 替换字符。

    Args:
        s: 输入字符串

    Returns:
        清理后的字符串
    """
    if not isinstance(s, str):
        return str(s) if s is not None else ""

    # 使用 surrogatepass 错误处理来编码再解码，
    # 这样可以将无效的代理字符转换为 Unicode 替换字符
    try:
        return s.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
    except Exception:
        # 如果仍然失败，逐字符处理
        return ''.join(
            c if ord(c) < 0xD800 or ord(c) > 0xDFFF else '\ufffd'
            for c in s
        )

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

    # 创建默认的 HEARTBEAT.md 文件（如果不存在）
    heartbeat_path = workspace / HEARTBEAT_FILE
    if not heartbeat_path.exists():
        heartbeat_path.write_text(DEFAULT_HEARTBEAT_CONTENT, encoding="utf-8")
        logger.info(f"Created default {HEARTBEAT_FILE} at {heartbeat_path}")

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
    import asyncio

    create_deep_agent, MemoryMiddleware, LocalShellBackend, _ = _ensure_deepagents()

    workspace = config.agent.workspace

    # 使用 asyncio.to_thread 将同步的文件操作移到线程池
    def _ensure_workspace():
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        (workspace / "skills").mkdir(exist_ok=True)

        # 创建默认的 HEARTBEAT.md 文件（如果不存在）
        heartbeat_path = workspace / HEARTBEAT_FILE
        if not heartbeat_path.exists():
            heartbeat_path.write_text(DEFAULT_HEARTBEAT_CONTENT, encoding="utf-8")
            logger.info(f"Created default {HEARTBEAT_FILE} at {heartbeat_path}")

    await asyncio.to_thread(_ensure_workspace)

    logger.info(f"Initializing agent with workspace: {workspace}")

    system_prompt = await _build_system_prompt_async(config)
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


async def _build_system_prompt_async(config: Config) -> str:
    """
    异步构建系统提示词。

    Args:
        config: 配置对象

    Returns:
        系统提示词字符串
    """
    import asyncio

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

    # 添加技能信息（异步检查文件系统）
    if config.agent.enable_skills:
        skills_dir = workspace / "skills"

        def _get_skill_names():
            if skills_dir.exists():
                return [
                    d.name for d in skills_dir.iterdir()
                    if d.is_dir() and (d / "SKILL.md").exists()
                ]
            return []

        skill_names = await asyncio.to_thread(_get_skill_names)
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


def _build_system_prompt(config: Config) -> str:
    """
    构建系统提示词（同步版本）。

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
    if config.agent.enable_skills:
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
        # 审批回调函数
        self._approval_callback: Callable[[list[dict]], Awaitable[list[dict]]] | None = None
        # 事件回调函数
        self._event_callback: Callable[[dict], Awaitable[None]] | None = None

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

    def set_approval_callback(
        self, callback: Callable[[list[dict]], Awaitable[list[dict]]]
    ) -> None:
        """设置审批回调函数

        Args:
            callback: 异步回调函数，接收待审批的工具调用列表，
                     返回用户的决策列表
        """
        self._approval_callback = callback

    def set_event_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """设置事件回调函数，用于处理流式事件

        Args:
            callback: 异步回调函数，接收事件字典
        """
        self._event_callback = callback

    @property
    def auto_approve(self) -> bool:
        """是否自动审批"""
        return self.config.agent.auto_approve

    async def _get_state(self) -> Any:
        """获取当前状态"""
        return await self._graph.aget_state(self.get_thread_config())

    async def _check_and_handle_interrupt(self) -> tuple[bool, dict | None]:
        """检查并处理中断，循环处理所有可能的中断直到完成

        Returns:
            (是否有中断需要处理, 最终状态)
        """
        from langgraph.types import Command

        state = await self._get_state()
        if not state.interrupts:
            return False, None

        # 有中断，需要处理
        logger.info(f"Found {len(state.interrupts)} interrupt(s)")

        if self._approval_callback is None:
            logger.warning("Interrupt found but no approval callback set")
            return False, None

        final_state = None

        # 循环处理所有中断，直到没有新的中断
        while True:
            # 收集所有中断的值
            action_requests = []
            for interrupt in state.interrupts:
                interrupt_value = interrupt.value
                if isinstance(interrupt_value, dict) and "action_requests" in interrupt_value:
                    action_requests.extend(interrupt_value["action_requests"])

            if not action_requests:
                break

            # 调用回调获取用户决策
            decisions = await self._approval_callback(action_requests)

            # 使用 Command 恢复执行，使用流式 API 以触发事件回调
            resume_value = {"decisions": decisions}
            final_state = None
            async for event in self._graph.astream_events(
                Command(resume=resume_value),
                config=self.get_thread_config(),
                version="v1",
            ):
                # 调用事件回调以显示 spinner
                if self._event_callback:
                    await self._event_callback(event)

                # 保存最终状态
                event_type = event.get("event")
                if event_type == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict) and "messages" in output:
                        final_state = output

            # 检查是否有新的中断
            state = await self._get_state()
            if not state.interrupts:
                break

        # 如果没有从事件中获取到最终状态，从 state.values 获取
        if final_state is None or "messages" not in final_state:
            state = await self._get_state()
            final_state = state.values

        return True, final_state

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

        # 使用流式事件处理
        final_state = None
        event_count = 0

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": message}]} if message else None,
            config=thread_config,
            version="v1",
        ):
            event_count += 1
            event_type = event.get("event")
            event_name = event.get("name", "")

            # 记录工具相关事件
            if "tool" in event_type.lower() or "tool" in event_name.lower():
                logger.debug(f"Tool event #{event_count}: {event_type}, name: {event_name}")

            # 调用事件回调
            if self._event_callback:
                await self._event_callback(event)

        logger.debug(f"astream_events completed, received {event_count} events")

        # 流结束后检查是否有中断
        has_interrupt, resume_final_state = await self._check_and_handle_interrupt()
        if has_interrupt and resume_final_state is not None:
            final_state = resume_final_state

        # 总是从 state.values 获取最终状态（因为 on_chain_end 的 output 可能不包含 messages）
        if final_state is None or "messages" not in final_state:
            state = await self._get_state()
            final_state = state.values

        # 提取最后一条助手消息
        if final_state and "messages" in final_state:
            for msg in reversed(final_state["messages"]):
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
                        return _sanitize_string("\n".join(texts)) if texts else ""
                    return _sanitize_string(str(content)) if content else ""
                # 兼容字典格式的消息
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    return _sanitize_string(msg.get("content", "") or "")

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