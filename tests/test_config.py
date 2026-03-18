"""配置系统测试"""

import os
import tempfile
from pathlib import Path

import pytest

from deepcobot.config import (
    Config,
    AgentDefaults,
    ProviderConfig,
    ChannelConfig,
    load_config,
    _expand_env_vars,
)


class TestExpandEnvVars:
    """环境变量替换测试"""

    def test_simple_env_var(self, monkeypatch):
        """测试简单环境变量替换"""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        result = _expand_env_vars("${TEST_API_KEY}")
        assert result == "test-key-123"

    def test_env_var_with_default(self, monkeypatch):
        """测试带默认值的环境变量"""
        # 环境变量不存在时使用默认值
        result = _expand_env_vars("${UNDEFINED_VAR:-default-value}")
        assert result == "default-value"

        # 环境变量存在时使用实际值
        monkeypatch.setenv("DEFINED_VAR", "actual-value")
        result = _expand_env_vars("${DEFINED_VAR:-default-value}")
        assert result == "actual-value"

    def test_env_var_not_defined(self):
        """测试环境变量未定义时抛出异常"""
        with pytest.raises(ValueError, match="Environment variable"):
            _expand_env_vars("${UNDEFINED_VAR_NO_DEFAULT}")

    def test_nested_dict(self, monkeypatch):
        """测试嵌套字典中的环境变量替换"""
        monkeypatch.setenv("API_KEY", "my-key")
        monkeypatch.setenv("API_BASE", "https://api.example.com")

        config = {
            "providers": {
                "test": {
                    "api_key": "${API_KEY}",
                    "api_base": "${API_BASE}",
                }
            }
        }

        result = _expand_env_vars(config)
        assert result["providers"]["test"]["api_key"] == "my-key"
        assert result["providers"]["test"]["api_base"] == "https://api.example.com"

    def test_list_values(self, monkeypatch):
        """测试列表中的环境变量替换"""
        monkeypatch.setenv("USER1", "alice")
        monkeypatch.setenv("USER2", "bob")

        result = _expand_env_vars(["${USER1}", "${USER2}", "static"])
        assert result == ["alice", "bob", "static"]


class TestConfigSchema:
    """配置 Schema 测试"""

    def test_default_values(self):
        """测试默认值"""
        config = Config()

        assert config.agent.workspace == Path("~/.deepcobot/workspace")
        assert config.agent.model == "anthropic:claude-sonnet-4-6"
        assert config.agent.max_tokens == 8192
        assert config.agent.enable_memory is True
        assert config.agent.enable_skills is True
        assert config.agent.auto_approve is False

    def test_provider_config(self):
        """测试提供商配置"""
        config = Config(
            providers={
                "anthropic": ProviderConfig(
                    api_key="test-key",
                    api_base="https://api.anthropic.com"
                )
            }
        )

        assert config.providers["anthropic"].api_key == "test-key"
        assert config.providers["anthropic"].api_base == "https://api.anthropic.com"

    def test_channel_config(self):
        """测试渠道配置"""
        config = Config()

        # CLI 渠道默认启用
        assert config.channels.cli.enabled is True

        # 其他渠道默认禁用
        assert config.channels.telegram.enabled is False
        assert config.channels.discord.enabled is False
        assert config.channels.feishu.enabled is False
        assert config.channels.dingtalk.enabled is False
        assert config.channels.web.enabled is False

    def test_workspace_expansion(self):
        """测试工作空间路径扩展"""
        config = Config(agent=AgentDefaults(workspace="~/my-workspace"))

        # ~ 应该被扩展为用户主目录
        assert str(config.agent.workspace).startswith(str(Path.home()))

    def test_get_provider(self):
        """测试获取提供商配置"""
        config = Config(
            providers={
                "test": ProviderConfig(api_key="test-key")
            }
        )

        provider = config.get_provider("test")
        assert provider is not None
        assert provider.api_key == "test-key"

        provider = config.get_provider("nonexistent")
        assert provider is None

    def test_extra_fields_ignored(self):
        """测试忽略未知字段"""
        # 不应该抛出异常
        config = Config(**{"unknown_field": "value"})
        assert config.agent.model == "anthropic:claude-sonnet-4-6"


class TestLoadConfig:
    """配置加载测试"""

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件抛出异常"""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.toml")

    def test_load_valid_config(self, monkeypatch, tmp_path):
        """测试加载有效配置文件"""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        config_content = """
[agent]
model = "openai:gpt-4"
max_tokens = 4096

[providers.openai]
api_key = "${TEST_API_KEY}"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        config = load_config(config_file)

        assert config.agent.model == "openai:gpt-4"
        assert config.agent.max_tokens == 4096
        assert config.providers["openai"].api_key == "test-key-123"

    def test_load_invalid_toml(self, tmp_path):
        """测试加载无效 TOML 抛出异常"""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid [toml")

        with pytest.raises(ValueError, match="Failed to parse TOML"):
            load_config(config_file)

    def test_load_default_config(self, tmp_path, monkeypatch):
        """测试加载默认配置"""
        # 当配置文件不存在时，使用默认配置
        config = load_config()
        assert config.agent.model == "anthropic:claude-sonnet-4-6"


class TestChannelConfig:
    """渠道配置测试"""

    def test_telegram_config(self):
        """测试 Telegram 渠道配置"""
        from deepcobot.config import TelegramChannelConfig

        config = TelegramChannelConfig(
            enabled=True,
            token="test-token",
            allowed_users=["user1", "user2"]
        )

        assert config.enabled is True
        assert config.token == "test-token"
        assert config.allowed_users == ["user1", "user2"]

    def test_web_config(self):
        """测试 Web API 渠道配置"""
        from deepcobot.config import WebChannelConfig

        config = WebChannelConfig(
            enabled=True,
            host="127.0.0.1",
            port=9000,
            api_key="web-api-key"
        )

        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.api_key == "web-api-key"