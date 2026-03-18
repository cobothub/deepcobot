"""系统 Prompt 构建模块

生成 Agent 系统提示词，包括角色定位和技能信息注入。
"""

from pathlib import Path
from typing import Any

from deepcobot.config import Config


def build_system_prompt(
    config: Config,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """
    构建系统提示词。

    Args:
        config: 配置对象
        extra_context: 额外的上下文信息

    Returns:
        系统提示词字符串
    """
    if config.agent.system_prompt:
        return config.agent.system_prompt

    workspace = config.agent.workspace

    # 构建基础部分
    sections = [_build_role_section(), _build_workspace_section(workspace)]

    # 添加能力部分
    capabilities = _build_capabilities_section(config)
    if capabilities:
        sections.append(capabilities)

    # 添加技能部分
    skills = _build_skills_section(workspace, config.agent.enable_skills)
    if skills:
        sections.append(skills)

    # 添加异步子 Agent 部分
    subagents = _build_subagents_section(config)
    if subagents:
        sections.append(subagents)

    # 添加额外上下文
    if extra_context:
        context = _build_context_section(extra_context)
        if context:
            sections.append(context)

    # 添加工具使用指南
    sections.append(_build_tool_guidelines())

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


def _build_capabilities_section(config: Config) -> str:
    """构建能力部分"""
    capabilities = [
        "- File system operations (read, write, search, edit)",
        "- Shell command execution",
        "- Web search",
    ]

    if config.agent.enable_memory:
        capabilities.append("- Persistent memory across sessions")

    if config.agent.enable_skills:
        capabilities.append("- Custom skills loaded from workspace")

    if config.async_subagents:
        capabilities.append("- Launch async sub-agents for parallel tasks")

    if len(capabilities) <= 3:
        return ""

    return "## Available Capabilities\n\n" + "\n".join(capabilities)


def _build_skills_section(
    workspace: Path,
    enable_skills: bool,
) -> str:
    """构建技能部分"""
    if not enable_skills:
        return ""

    skills_dir = workspace / "skills"
    if not skills_dir.exists():
        return ""

    skill_info = []
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        # 读取技能描述（第一行通常是标题）
        try:
            content = skill_file.read_text()
            first_line = content.split("\n")[0].strip()
            # 移除 markdown 标题符号
            title = first_line.lstrip("# ").strip()
            skill_info.append(f"- **{skill_dir.name}**: {title}")
        except Exception:
            skill_info.append(f"- **{skill_dir.name}**")

    if not skill_info:
        return ""

    return "## Loaded Skills\n\n" + "\n".join(skill_info)


def _build_subagents_section(config: Config) -> str:
    """构建异步子 Agent 部分"""
    if not config.async_subagents:
        return ""

    subagent_info = [
        f"- **{sa.name}**: {sa.description}"
        for sa in config.async_subagents
    ]

    return "## Available Async Sub-Agents\n\n" + "\n".join(subagent_info)


def _build_context_section(context: dict[str, Any]) -> str:
    """构建额外上下文部分"""
    if not context:
        return ""

    lines = ["## Context"]
    for key, value in context.items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def _build_tool_guidelines() -> str:
    """构建工具使用指南"""
    return """## Tool Usage Guidelines

When using tools:
1. Always verify the safety of operations before executing
2. Use appropriate tools for each task
3. Handle errors gracefully and provide helpful feedback
4. Ask for clarification when requirements are ambiguous

When executing shell commands:
1. Prefer non-destructive operations
2. Show the command before execution when it might have side effects
3. Explain the purpose and expected outcome

When editing files:
1. Back up important files before modification
2. Make minimal changes necessary
3. Verify the changes work as expected"""


def build_skill_prompt(skill_content: str, skill_name: str) -> str:
    """
    构建单个技能的提示词。

    Args:
        skill_content: SKILL.md 文件内容
        skill_name: 技能名称

    Returns:
        技能提示词
    """
    return f"""## Skill: {skill_name}

{skill_content}"""


def build_memory_prompt(memory_content: str) -> str:
    """
    构建记忆提示词。

    Args:
        memory_content: 记忆文件内容

    Returns:
        记忆提示词
    """
    if not memory_content.strip():
        return ""

    return f"""## Memory

The following information has been remembered from previous conversations:

{memory_content}"""