"""Agent 核心封装

封装 DeepAgents SDK 的 create_deep_agent 方法，通过配置驱动 Agent 初始化。
"""

from pathlib import Path
from typing import Any

from loguru import logger

from deepcobot.config import Config


def create_agent(config: Config) -> dict[str, Any]:
    """
    创建 Agent 实例。

    封装 DeepAgents SDK 的 create_deep_agent，根据配置构建中间件栈。

    Args:
        config: 配置对象

    Returns:
        包含 graph 和相关资源的字典

    Raises:
        ImportError: DeepAgents SDK 未安装
        ValueError: 配置验证失败
    """
    try:
        from deepagents import create_deep_agent
        from deepagents.backends import LocalShellBackend
        from deepagents.checkpointer import SqliteSaver
    except ImportError as e:
        raise ImportError(
            "DeepAgents SDK not installed. "
            "Install it with: pip install deepagents>=0.4"
        ) from e

    workspace = config.agent.workspace
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建必要的子目录
    (workspace / "memory").mkdir(exist_ok=True)
    (workspace / "skills").mkdir(exist_ok=True)

    logger.info(f"Initializing agent with workspace: {workspace}")

    # 构建系统提示词
    system_prompt = _build_system_prompt(config)

    # 创建 Shell 后端
    backend = LocalShellBackend(root_dir=str(workspace))

    # 创建 Checkpointer
    checkpointer_path = workspace / "checkpoints.db"
    checkpointer = SqliteSaver(str(checkpointer_path))

    # 构建中间件栈
    middlewares = _build_middlewares(config)

    # 解析模型配置
    model = config.agent.model
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider = "anthropic"
        model_name = model

    # 获取提供商配置
    provider_config = config.get_provider(provider)
    api_key = provider_config.api_key if provider_config else None
    api_base = provider_config.api_base if provider_config else None

    # 配置审批
    interrupt_on = None if config.agent.auto_approve else [
        "execute",
        "write_file",
        "edit_file",
        "web_search",
        "task",
    ]

    # 构建异步子 Agent 列表
    async_subagents = _build_async_subagents(config)

    # 创建 Agent
    agent_kwargs: dict[str, Any] = {
        "model": model_name,
        "system_prompt": system_prompt,
        "backend": backend,
        "checkpointer": checkpointer,
        "api_key": api_key,
        "api_base": api_base,
        "middlewares": middlewares,
        "interrupt_on": interrupt_on,
    }

    if async_subagents:
        agent_kwargs["async_subagents"] = async_subagents

    graph = create_deep_agent(**agent_kwargs)

    logger.info(f"Agent created: model={model}, auto_approve={config.agent.auto_approve}")

    return {
        "graph": graph,
        "checkpointer": checkpointer,
        "backend": backend,
        "workspace": workspace,
    }


def _build_system_prompt(config: Config) -> str:
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
    if config.agent.enable_memory:
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

    Args:
        config: 配置对象

    Returns:
        中间件列表
    """
    middlewares = []
    workspace = config.agent.workspace

    # 记忆系统
    if config.agent.enable_memory:
        try:
            from deepagents.middlewares import MemoryMiddleware

            memory_file = workspace / "memory" / "AGENTS.md"
            middlewares.append(MemoryMiddleware(str(memory_file)))
            logger.info("Memory middleware enabled")
        except ImportError:
            logger.warning("MemoryMiddleware not available")

    # 技能系统
    if config.agent.enable_skills:
        try:
            from deepagents.middlewares import SkillsMiddleware

            skills_dir = workspace / "skills"
            middlewares.append(SkillsMiddleware(str(skills_dir)))
            logger.info("Skills middleware enabled")
        except ImportError:
            logger.warning("SkillsMiddleware not available")

    return middlewares


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
        self._agent_resources: dict[str, Any] | None = None
        self._thread_id: str = "default"

    @property
    def graph(self):
        """获取 Agent graph"""
        if self._agent_resources is None:
            self._agent_resources = create_agent(self.config)
        return self._agent_resources["graph"]

    @property
    def checkpointer(self):
        """获取 checkpointer"""
        if self._agent_resources is None:
            self._agent_resources = create_agent(self.config)
        return self._agent_resources["checkpointer"]

    @property
    def workspace(self) -> Path:
        """获取工作空间路径"""
        if self._agent_resources is None:
            self._agent_resources = create_agent(self.config)
        return self._agent_resources["workspace"]

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

    async def invoke(self, message: str) -> str:
        """
        调用 Agent 处理消息。

        Args:
            message: 用户消息

        Returns:
            Agent 响应
        """
        graph = self.graph
        thread_config = self.get_thread_config()

        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=thread_config,
        )

        # 提取最后一条助手消息
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if msg.get("role") == "assistant":
                    return msg.get("content", "")

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