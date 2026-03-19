"""Agent 配置构建函数"""

from contextlib import AsyncExitStack
from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger

from deepcobot.config import Config

# 延迟导入
_create_summarization_tool_middleware = None
_CompositeBackend = None
_FilesystemBackend = None


def _ensure_summarization_deps():
    """确保压缩工具依赖已导入"""
    global _create_summarization_tool_middleware, _CompositeBackend, _FilesystemBackend
    if _create_summarization_tool_middleware is None:
        try:
            from deepagents.middleware.summarization import create_summarization_tool_middleware
            from deepagents.backends import CompositeBackend
            from deepagents.backends.filesystem import FilesystemBackend

            _create_summarization_tool_middleware = create_summarization_tool_middleware
            _CompositeBackend = CompositeBackend
            _FilesystemBackend = FilesystemBackend
        except ImportError as e:
            raise ImportError(
                "Summarization dependencies not installed. "
                "Install with: pip install deepagents>=0.4"
            ) from e
    return _create_summarization_tool_middleware, _CompositeBackend, _FilesystemBackend


def build_middlewares(config: Config) -> list[Any]:
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
    # compact_tool middleware 在 factory.py 中处理，因为它需要 model 和 backend
    return middlewares


def build_memory_sources(config: Config) -> list[str] | None:
    """
    构建记忆源路径列表。

    加载 memory/ 目录下的 AGENTS.md 和 PROFILE.md，
    复用 DeepAgents MemoryMiddleware 的提示词和注入机制。

    Args:
        config: 配置对象

    Returns:
        记忆文件路径列表，如果未启用则返回 None
    """
    if not config.agent.enable_memory:
        return None

    workspace = config.agent.workspace
    memory_dir = workspace / "memory"
    sources = []

    # 1. AGENTS.md - Agent 指令和约定
    agents_md = memory_dir / "AGENTS.md"
    if agents_md.exists():
        sources.append(str(agents_md))

    # 2. PROFILE.md - 用户画像和偏好
    profile_md = memory_dir / "PROFILE.md"
    if profile_md.exists():
        sources.append(str(profile_md))

    if sources:
        logger.info(f"Memory enabled: {len(sources)} file(s) in {memory_dir}")
    else:
        logger.info(f"Memory enabled but no files found in {memory_dir}")

    return sources if sources else None


def build_skills_sources(config: Config) -> list[str] | None:
    """
    构建技能源路径列表。

    Args:
        config: 配置对象

    Returns:
        技能目录路径列表，如果未启用则返回 None
    """
    if not config.agent.enable_skills:
        logger.info("Skills disabled by config")
        return None

    workspace = config.agent.workspace
    skills_dir = workspace / "skills"
    skills_dir_str = str(skills_dir)

    # 检查 skills 目录是否存在
    if skills_dir.exists():
        # 列出子目录（skills）
        subdirs = [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        logger.info(f"Skills enabled: {skills_dir_str}, found {len(subdirs)} skill(s): {subdirs}")
    else:
        logger.warning(f"Skills directory not found: {skills_dir_str}")

    return [skills_dir_str]


def build_async_subagents(config: Config) -> list[dict[str, str]]:
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


def setup_api_key(config: Config) -> tuple[str, str]:
    """
    设置 API 密钥环境变量。

    Args:
        config: 配置对象

    Returns:
        (provider, model_name) 元组
    """
    import os

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
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            if api_base:
                os.environ["OPENAI_BASE_URL"] = api_base
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            if api_base:
                os.environ["ANTHROPIC_BASE_URL"] = api_base

    return provider, model_name


def get_interrupt_config(config: Config) -> dict[str, bool] | None:
    """
    获取中断配置。

    Args:
        config: 配置对象

    Returns:
        中断配置字典，如果自动审批则返回 None
    """
    if config.agent.auto_approve:
        return None

    return {
        "execute": True,
        "write_file": True,
        "edit_file": True,
        "web_search": False,
        "task": False,
    }


def build_compact_tool_middleware(
    config: Config,
    model: str,
    backend: Any,
) -> tuple[Any, Any] | tuple[None, None]:
    """
    构建手动压缩对话工具中间件。

    该中间件提供 compact_conversation 工具，允许 AI 主动压缩对话历史，
    释放上下文窗口空间。

    Args:
        config: 配置对象
        model: 模型标识符 (如 "anthropic:claude-sonnet-4-6")
        backend: 后端实例 (LocalShellBackend 等)

    Returns:
        (middleware, composite_backend) 元组，如果未启用则返回 (None, None)
    """
    if not config.agent.enable_compact_tool:
        return None, None

    (
        create_summarization_tool_middleware,
        CompositeBackend,
        FilesystemBackend,
    ) = _ensure_summarization_deps()

    # 创建 CompositeBackend，将大型工具结果和对话历史路由到工作目录
    workspace = config.agent.workspace

    # 确保目录存在
    large_results_dir = workspace / ".cache" / "large_results"
    large_results_dir.mkdir(parents=True, exist_ok=True)
    conversation_history_dir = workspace / ".cache" / "conversation_history"
    conversation_history_dir.mkdir(parents=True, exist_ok=True)

    large_results_backend = FilesystemBackend(
        root_dir=str(large_results_dir),
        virtual_mode=True,
    )
    conversation_history_backend = FilesystemBackend(
        root_dir=str(conversation_history_dir),
        virtual_mode=True,
    )
    composite_backend = CompositeBackend(
        default=backend,
        routes={
            "/large_tool_results/": large_results_backend,
            "/conversation_history/": conversation_history_backend,
        },
    )

    middleware = create_summarization_tool_middleware(model, composite_backend)
    logger.info(f"Compact conversation tool enabled, cache at {workspace / '.cache'}")

    return middleware, composite_backend


async def build_mcp_tools(config: Config, exit_stack: AsyncExitStack) -> list[BaseTool]:
    """构建 MCP 工具列表

    连接 MCP 服务器并加载其工具，优雅降级处理连接失败。

    Args:
        config: 配置对象
        exit_stack: AsyncExitStack 用于管理 MCP 连接生命周期

    Returns:
        LangChain BaseTool 列表
    """
    try:
        from deepcobot.agent.mcp.tools import load_mcp_tools

        tools = await load_mcp_tools(config, exit_stack)
        if tools:
            logger.info(f"Loaded {len(tools)} MCP tool(s)")
        return tools
    except ImportError:
        logger.warning(
            "MCP support not available. Install with: pip install langchain-mcp-adapters"
        )
        return []
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}")
        return []
