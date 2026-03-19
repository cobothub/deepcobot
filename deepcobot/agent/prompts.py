"""系统 Prompt 构建模块

生成 Agent 系统提示词，包括角色定位和工作空间信息。
"""

from pathlib import Path

from deepcobot.config import Config


def build_system_prompt(config: Config) -> str:
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

    # 只构建基础部分
    sections = [_build_role_section(), _build_workspace_section(workspace)]

    return "\n\n".join(sections)


def _build_role_section() -> str:
    """构建角色定位部分"""
    return """## Role

You are a helpful AI assistant designed to help users with various tasks including:
- Answering questions and providing information
- Writing and editing code
- Executing shell commands
- Searching the web for information
- Managing files and directories

Always be helpful, accurate, and concise in your responses."""


def _build_workspace_section(workspace: Path) -> str:
    """构建工作空间部分"""
    return f"""## Working Directory

All file operations are relative to: `{workspace}`

When working with files:
- Always use relative paths when possible
- Create directories as needed
- Be careful with destructive operations (deletion, overwriting)"""