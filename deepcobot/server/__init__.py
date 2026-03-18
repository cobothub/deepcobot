"""LangGraph 服务器模块"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from deepcobot.config import Config
from deepcobot.server.graph import create_graph, get_graph


def generate_langgraph_json(
    config: Config,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    生成 langgraph.json 配置文件。

    Args:
        config: 配置对象
        output_path: 输出路径（可选）

    Returns:
        langgraph.json 配置字典
    """
    langgraph_config = {
        "python_version": "3.11",
        "dependencies": [
            "deepagents>=0.4",
            "langgraph>=0.2",
        ],
        "graphs": {
            "agent": "./deepcobot/server/graph.py:graph",
        },
        "env": ".env",
    }

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(json.dumps(langgraph_config, indent=2))
        logger.info(f"Generated langgraph.json at {output_path}")

    return langgraph_config


__all__ = ["create_graph", "get_graph", "generate_langgraph_json"]