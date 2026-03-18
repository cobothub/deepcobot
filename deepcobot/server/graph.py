"""LangGraph Graph 导出模块

导出 Agent graph 供 LangGraph 服务器使用。

LangGraph CLI 支持两种导出方式：
1. graph 变量直接是 StateGraph 实例
2. graph 变量是返回 StateGraph 的工厂函数（支持 async）
"""

from typing import Any

from loguru import logger

from deepcobot.config import Config, load_config


async def create_graph_async(config: Config | None = None) -> Any:
    """
    异步创建并导出 LangGraph graph。

    Args:
        config: 配置对象，如果未提供则加载默认配置

    Returns:
        LangGraph graph 对象
    """
    if config is None:
        config = load_config()

    from deepcobot.agent.factory import create_agent_async

    agent_resources = await create_agent_async(config)
    return agent_resources["graph"]


# 默认 graph 实例（用于 langgraph.json 配置）
_default_graph = None


async def get_graph_async() -> Any:
    """
    异步获取默认 graph 实例。

    Returns:
        LangGraph graph 对象
    """
    global _default_graph

    if _default_graph is None:
        _default_graph = await create_graph_async()

    return _default_graph


# LangGraph 异步工厂函数
# LangGraph CLI 会调用这个函数来获取 graph
async def graph(config: dict | None = None) -> Any:
    """
    LangGraph 异步工厂函数，返回编译后的 graph。

    LangGraph CLI 期望 graph 是一个 StateGraph 实例或返回 StateGraph 的函数。
    支持异步函数以避免阻塞调用。

    Args:
        config: 可选配置字典（LangGraph 运行时可能传入）

    Returns:
        编译后的 LangGraph StateGraph
    """
    return await get_graph_async()