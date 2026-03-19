"""Agent 工厂函数

创建和初始化 Agent 实例。
"""

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from loguru import logger

from deepcobot.config import Config
from deepcobot.agent.utils import HEARTBEAT_FILE, DEFAULT_HEARTBEAT_CONTENT
from deepcobot.agent.prompts import build_system_prompt
from deepcobot.agent.templates import DEFAULT_AGENTS_MD, DEFAULT_PROFILE_MD
from deepcobot.agent.builder import (
    build_middlewares,
    build_memory_sources,
    build_skills_sources,
    build_async_subagents,
    setup_api_key,
    get_interrupt_config,
    build_compact_tool_middleware,
    build_mcp_tools,
)

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


def _ensure_workspace(workspace: Path) -> None:
    """确保工作空间目录结构存在"""
    workspace.mkdir(parents=True, exist_ok=True)
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    (memory_dir / "daily").mkdir(exist_ok=True)  # 每日日志目录
    (workspace / "skills").mkdir(exist_ok=True)

    # 创建默认的记忆文件（如果不存在）
    agents_md = memory_dir / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(DEFAULT_AGENTS_MD, encoding="utf-8")
        logger.info(f"Created default AGENTS.md at {agents_md}")

    profile_md = memory_dir / "PROFILE.md"
    if not profile_md.exists():
        profile_md.write_text(DEFAULT_PROFILE_MD, encoding="utf-8")
        logger.info(f"Created default PROFILE.md at {profile_md}")

    # 创建默认的 HEARTBEAT.md 文件（如果不存在）
    heartbeat_path = workspace / HEARTBEAT_FILE
    if not heartbeat_path.exists():
        heartbeat_path.write_text(DEFAULT_HEARTBEAT_CONTENT, encoding="utf-8")
        logger.info(f"Created default {HEARTBEAT_FILE} at {heartbeat_path}")


def create_agent(config: Config) -> dict[str, Any]:
    """
    创建 Agent 实例（同步版本，使用 MemorySaver）。

    注意：推荐使用 create_agent_async 进行异步操作以支持 SQLite 持久化。

    Args:
        config: 配置对象

    Returns:
        包含 graph 和相关资源的字典
    """
    create_deep_agent, MemoryMiddleware, LocalShellBackend, _ = _ensure_deepagents()
    from langgraph.checkpoint.memory import MemorySaver

    workspace = config.agent.workspace
    _ensure_workspace(workspace)

    logger.info(f"Initializing agent with workspace: {workspace}")

    system_prompt = build_system_prompt(config)
    backend = LocalShellBackend(root_dir=str(workspace), virtual_mode=False)
    checkpointer = MemorySaver()  # 同步版本使用内存存储

    logger.info("Checkpointer: MemorySaver (non-persistent)")

    middlewares = build_middlewares(config)
    memory_sources = build_memory_sources(config)
    skills_sources = build_skills_sources(config)
    provider, model_name = setup_api_key(config)
    interrupt_on = get_interrupt_config(config)
    async_subagents = build_async_subagents(config)

    model = config.agent.model

    # 构建压缩工具中间件
    compact_middleware, composite_backend = build_compact_tool_middleware(
        config, model, backend
    )
    if compact_middleware is not None:
        middlewares.append(compact_middleware)
        effective_backend = composite_backend
    else:
        effective_backend = backend

    agent_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "backend": effective_backend,
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


async def create_agent_async(config: Config) -> dict[str, Any]:
    """
    异步创建 Agent 实例（支持 SQLite 持久化）。

    Args:
        config: 配置对象

    Returns:
        包含 graph 和相关资源的字典
    """
    create_deep_agent, MemoryMiddleware, LocalShellBackend, _ = _ensure_deepagents()

    workspace = config.agent.workspace

    # 使用 asyncio.to_thread 将同步的文件操作移到线程池
    await asyncio.to_thread(_ensure_workspace, workspace)

    logger.info(f"Initializing agent with workspace: {workspace}")

    # 创建 AsyncExitStack 用于管理 MCP 连接生命周期
    exit_stack = AsyncExitStack()

    system_prompt = build_system_prompt(config)
    backend = LocalShellBackend(root_dir=str(workspace), virtual_mode=False)

    # 使用异步 SQLite Checkpointer
    checkpoints_path = workspace / "checkpoints.db"
    checkpointer = await _create_async_sqlite_checkpointer(str(checkpoints_path))
    logger.info(f"Checkpointer: SQLite at {checkpoints_path}")

    middlewares = build_middlewares(config)
    memory_sources = build_memory_sources(config)
    skills_sources = build_skills_sources(config)
    provider, model_name = setup_api_key(config)
    interrupt_on = get_interrupt_config(config)
    async_subagents = build_async_subagents(config)

    model = config.agent.model

    # 构建压缩工具中间件
    compact_middleware, composite_backend = build_compact_tool_middleware(
        config, model, backend
    )
    if compact_middleware is not None:
        middlewares.append(compact_middleware)
        effective_backend = composite_backend
    else:
        effective_backend = backend

    # 加载 MCP 工具
    mcp_tools = await build_mcp_tools(config, exit_stack)

    agent_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "backend": effective_backend,
        "checkpointer": checkpointer,
        "middleware": middlewares,
        "interrupt_on": interrupt_on,
        "memory": memory_sources,
        "skills": skills_sources,
    }

    if async_subagents:
        agent_kwargs["subagents"] = async_subagents

    if mcp_tools:
        agent_kwargs["tools"] = mcp_tools

    graph = create_deep_agent(**agent_kwargs)
    logger.info(f"Agent created: model={model}, auto_approve={config.agent.auto_approve}")

    return {
        "graph": graph,
        "checkpointer": checkpointer,
        "backend": backend,
        "workspace": workspace,
        "exit_stack": exit_stack,
    }