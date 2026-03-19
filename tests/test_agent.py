"""Agent 核心测试"""

from deepcobot.agent import build_system_prompt
from deepcobot.config import Config, AgentDefaults


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