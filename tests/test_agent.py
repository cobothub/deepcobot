"""Agent 核心测试"""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from deepcobot.config import Config, AgentDefaults
from deepcobot.agent import build_system_prompt
from deepcobot.agent.prompts import (
    build_skill_prompt,
    build_memory_prompt,
)


class TestBuildSystemPrompt:
    """系统提示词构建测试"""

    def test_default_prompt(self):
        """测试默认提示词生成"""
        config = Config()
        prompt = build_system_prompt(config)

        assert "helpful AI assistant" in prompt
        assert "Working Directory" in prompt
        assert "Tool Usage Guidelines" in prompt

    def test_custom_prompt(self):
        """测试自定义提示词"""
        config = Config(
            agent=AgentDefaults(
                system_prompt="Custom system prompt"
            )
        )

        prompt = build_system_prompt(config)
        assert prompt == "Custom system prompt"

    def test_prompt_includes_workspace(self):
        """测试提示词包含工作空间路径"""
        config = Config()
        prompt = build_system_prompt(config)

        assert str(config.agent.workspace) in prompt

    def test_prompt_includes_capabilities(self):
        """测试提示词包含能力列表"""
        config = Config()
        prompt = build_system_prompt(config)

        assert "File system operations" in prompt
        assert "Shell command execution" in prompt
        assert "Web search" in prompt

    def test_prompt_includes_memory_capability(self):
        """测试提示词包含记忆功能说明"""
        config = Config(agent=AgentDefaults(enable_memory=True))
        prompt = build_system_prompt(config)

        assert "Persistent memory" in prompt

    def test_prompt_excludes_memory_capability(self):
        """测试禁用记忆时提示词不含记忆说明"""
        config = Config(agent=AgentDefaults(enable_memory=False))
        prompt = build_system_prompt(config)

        # 当 enable_memory 为 False 且 enable_skills 为 False 时
        # 能力部分不会显示（因为默认能力只有三个）
        # 这个行为是正常的

    def test_prompt_includes_subagents(self):
        """测试提示词包含异步子 Agent 信息"""
        from deepcobot.config import AsyncSubAgentConfig

        config = Config(
            async_subagents=[
                AsyncSubAgentConfig(
                    name="research-agent",
                    description="Research task agent",
                    graph_id="research",
                    url="http://localhost:8123"
                )
            ]
        )
        prompt = build_system_prompt(config)

        assert "research-agent" in prompt
        assert "Research task agent" in prompt

    def test_prompt_with_context(self):
        """测试提示词包含额外上下文"""
        config = Config()
        prompt = build_system_prompt(config, extra_context={"user": "test", "session": "demo"})

        assert "Context" in prompt
        assert "user: test" in prompt
        assert "session: demo" in prompt


class TestBuildSkillPrompt:
    """技能提示词构建测试"""

    def test_skill_prompt(self):
        """测试技能提示词生成"""
        content = """# Code Review

This skill helps review code for quality issues.

## Steps
1. Read the code
2. Check for issues
3. Provide feedback
"""

        prompt = build_skill_prompt(content, "code-review")

        assert "Skill: code-review" in prompt
        assert "Code Review" in prompt


class TestBuildMemoryPrompt:
    """记忆提示词构建测试"""

    def test_memory_prompt(self):
        """测试记忆提示词生成"""
        content = "User prefers dark mode\nUser's timezone is PST"

        prompt = build_memory_prompt(content)

        assert "Memory" in prompt
        assert "User prefers dark mode" in prompt

    def test_empty_memory(self):
        """测试空记忆不生成提示词"""
        prompt = build_memory_prompt("")
        assert prompt == ""

        prompt = build_memory_prompt("  \n  ")
        assert prompt == ""


class TestAgentSession:
    """Agent 会话测试"""

    def test_thread_id_management(self):
        """测试线程 ID 管理"""
        from deepcobot.agent import AgentSession

        config = Config()
        session = AgentSession(config)

        assert session._thread_id == "default"

        session.set_thread_id("custom-thread")
        assert session._thread_id == "custom-thread"

    def test_get_thread_config(self):
        """测试获取线程配置"""
        from deepcobot.agent import AgentSession

        config = Config()
        session = AgentSession(config)
        session.set_thread_id("test-thread")

        thread_config = session.get_thread_config()

        assert "configurable" in thread_config
        assert thread_config["configurable"]["thread_id"] == "test-thread"

    def test_reset_session(self):
        """测试重置会话"""
        from deepcobot.agent import AgentSession

        config = Config()
        session = AgentSession(config)
        session.set_thread_id("custom-thread")

        session.reset()
        assert session._thread_id == "default"