"""Agent 配置构建函数"""

from typing import Any

from loguru import logger

from deepcobot.config import Config


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
    return middlewares


def build_memory_sources(config: Config) -> list[str] | None:
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


def build_skills_sources(config: Config) -> list[str] | None:
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
        "web_search": True,
        "task": True,
    }