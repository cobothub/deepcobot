"""LangGraph Graph 导出模块

导出 Agent graph 供 LangGraph 服务器使用。
"""

from typing import Any

from loguru import logger

from deepcobot.config import Config, load_config


def create_graph(config: Config | None = None) -> Any:
    """
    创建并导出 LangGraph graph。

    Args:
        config: 配置对象，如果未提供则加载默认配置

    Returns:
        LangGraph graph 对象
    """
    if config is None:
        config = load_config()

    from deepcobot.agent import create_agent

    agent_resources = create_agent(config)
    return agent_resources["graph"]


# 默认 graph 实例（用于 langgraph.json 配置）
_default_graph = None


def get_graph() -> Any:
    """
    获取默认 graph 实例。

    Returns:
        LangGraph graph 对象
    """
    global _default_graph

    if _default_graph is None:
        _default_graph = create_graph()

    return _default_graph


# 导出 graph 变量（LangGraph 服务器期望的接口）
graph = None  # 延迟初始化


def __getattr__(name):
    """延迟初始化 graph"""
    global graph

    if name == "graph":
        if graph is None:
            graph = get_graph()
        return graph

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")