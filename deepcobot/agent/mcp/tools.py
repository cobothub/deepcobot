"""MCP 工具加载器

使用 langchain-mcp-adapters 加载 MCP 服务器工具并转换为 LangChain 工具。
"""

from contextlib import AsyncExitStack
from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger

from deepcobot.config import Config


def _detect_transport_type(server_config: Any) -> str:
    """自动检测传输类型"""
    if server_config.type:
        return server_config.type

    if server_config.command:
        return "stdio"
    elif server_config.url:
        # 约定：URL 以 /sse 结尾使用 SSE 传输，否则使用 streamableHttp
        return "sse" if server_config.url.rstrip("/").endswith("/sse") else "streamableHttp"

    return "stdio"


def _create_connection(server_config: Any) -> Any:
    """根据配置创建连接对象"""
    from langchain_mcp_adapters.sessions import StdioConnection, SSEConnection, StreamableHttpConnection

    transport_type = _detect_transport_type(server_config)

    if transport_type == "stdio":
        return StdioConnection(
            transport="stdio",
            command=server_config.command,
            args=server_config.args,
            env=server_config.env or None,
        )
    elif transport_type == "sse":
        return SSEConnection(
            transport="sse",
            url=server_config.url,
            headers=server_config.headers or None,
        )
    elif transport_type == "streamableHttp":
        return StreamableHttpConnection(
            transport="http",  # langchain-mcp-adapters uses "http" for streamableHttp
            url=server_config.url,
            headers=server_config.headers or None,
        )
    else:
        raise ValueError(f"Unknown transport type: {transport_type}")


async def load_mcp_tools(
    config: Config,
    exit_stack: AsyncExitStack,
) -> list[BaseTool]:
    """加载 MCP 工具

    连接配置的 MCP 服务器并加载其工具，转换为 LangChain BaseTool。

    Args:
        config: 配置对象
        exit_stack: AsyncExitStack 用于管理 MCP 连接生命周期

    Returns:
        LangChain BaseTool 列表
    """
    from langchain_mcp_adapters.tools import load_mcp_tools as _load_mcp_tools

    if not config.mcp.servers:
        return []

    all_tools: list[BaseTool] = []

    for server_name, server_config in config.mcp.servers.items():
        try:
            # 检查必要配置
            if not server_config.command and not server_config.url:
                logger.warning(
                    f"MCP server '{server_name}': no command or url configured, skipping"
                )
                continue

            # 创建连接
            connection = _create_connection(server_config)

            # 加载工具
            tools = await _load_mcp_tools(
                session=None,
                connection=connection,
                server_name=server_name,
                tool_name_prefix=True,  # 使用 mcp_{server}_{tool} 格式
            )

            # 过滤启用的工具
            enabled_tools = set(server_config.enabled_tools)
            allow_all_tools = "*" in enabled_tools

            if allow_all_tools:
                filtered_tools = tools
            else:
                filtered_tools = []
                for tool in tools:
                    # 工具名格式为 mcp_{server}_{tool_name}
                    if tool.name in enabled_tools:
                        filtered_tools.append(tool)
                    else:
                        logger.debug(
                            f"MCP: skipping tool '{tool.name}' from server '{server_name}' "
                            f"(not in enabled_tools)"
                        )

            all_tools.extend(filtered_tools)
            logger.info(
                f"MCP server '{server_name}': connected, {len(filtered_tools)} tool(s) registered"
            )

        except Exception as e:
            logger.error(f"MCP server '{server_name}': failed to connect: {e}")
            # 优雅降级：继续处理其他服务器

    return all_tools