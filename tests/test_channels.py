"""渠道管理器和基类测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import InboundMessage, OutboundMessage
from deepcobot.channels.manager import ChannelManager
from deepcobot.bus.queue import MessageBus
from deepcobot.config import Config


class MockChannel(BaseChannel):
    """测试用模拟渠道"""

    name = "mock"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        pass

    async def send_progress(self, chat_id: str, content: str) -> None:
        pass


class TestBaseChannel:
    """渠道基类测试"""

    def test_is_allowed_empty_list(self):
        """测试空允许列表时允许所有用户"""
        channel = MockChannel(
            config=MagicMock(allowed_users=[]),
            bus=MagicMock(),
        )

        assert channel.is_allowed("user1") is True
        assert channel.is_allowed("anyone") is True

    def test_is_allowed_with_list(self):
        """测试允许列表过滤"""
        channel = MockChannel(
            config=MagicMock(allowed_users=["user1", "user2"]),
            bus=MagicMock(),
        )

        assert channel.is_allowed("user1") is True
        assert channel.is_allowed("user2") is True
        assert channel.is_allowed("user3") is False

    def test_is_allowed_with_pipe_format(self):
        """测试管道分隔格式的用户 ID"""
        channel = MockChannel(
            config=MagicMock(allowed_users=["alice", "bob"]),
            bus=MagicMock(),
        )

        # 格式: user_id|username
        assert channel.is_allowed("123|alice") is True
        assert channel.is_allowed("456|bob") is True
        assert channel.is_allowed("789|charlie") is False

    @pytest.mark.asyncio
    async def test_handle_message(self):
        """测试消息处理通用流程"""
        bus = MessageBus()
        await bus.start()

        channel = MockChannel(
            config=MagicMock(allowed_users=[]),
            bus=bus,
        )

        await channel._handle_message(
            sender_id="user1",
            chat_id="chat1",
            content="Hello",
            metadata={"key": "value"},
        )

        # 消息应该被发布到总线
        assert bus.inbound_size == 1

        msg = await bus.consume_inbound()
        assert msg.channel == "mock"
        assert msg.sender_id == "user1"
        assert msg.chat_id == "chat1"
        assert msg.content == "Hello"
        assert msg.metadata == {"key": "value"}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_handle_message_denied(self):
        """测试权限拒绝时消息不被处理"""
        bus = MessageBus()
        await bus.start()

        channel = MockChannel(
            config=MagicMock(allowed_users=["user1"]),
            bus=bus,
        )

        await channel._handle_message(
            sender_id="user2",
            chat_id="chat1",
            content="Hello",
        )

        # 消息不应该被发布
        assert bus.inbound_size == 0

        await bus.stop()

    def test_get_status(self):
        """测试获取渠道状态"""
        channel = MockChannel(
            config=MagicMock(allowed_users=["user1", "user2"]),
            bus=MagicMock(),
        )

        status = channel.get_status()
        assert status["name"] == "mock"
        assert status["running"] is False
        assert status["allowed_users_count"] == 2


class TestChannelManager:
    """渠道管理器测试"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return Config()

    @pytest.fixture
    def bus(self):
        """创建消息总线"""
        return MessageBus()

    @pytest.fixture
    def agent_handler(self):
        """创建模拟 Agent 处理器"""
        async def handler(msg: InboundMessage) -> OutboundMessage | None:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"Response to: {msg.content}",
            )
        return handler

    def test_init_channels(self, config, bus, agent_handler):
        """测试渠道初始化"""
        manager = ChannelManager(config, bus, agent_handler)

        # 只有 CLI 渠道默认启用
        assert "cli" in manager.channels

    @pytest.mark.asyncio
    async def test_start_stop(self, config, bus, agent_handler):
        """测试启动和停止"""
        manager = ChannelManager(config, bus, agent_handler)

        await manager.start_all()
        assert manager._running is True

        await manager.stop_all()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_dispatch_outbound(self, config, bus, agent_handler):
        """测试出站消息分发"""
        manager = ChannelManager(config, bus, agent_handler)

        # 添加模拟渠道
        mock_channel = MockChannel(
            config=MagicMock(allowed_users=[]),
            bus=bus,
        )
        manager.channels["mock"] = mock_channel

        # 启动管理器
        await manager.start_all()

        # 发布出站消息
        msg = OutboundMessage(
            channel="mock",
            chat_id="chat1",
            content="Test response",
        )
        await bus.publish_outbound(msg)

        # 等待处理
        await asyncio.sleep(0.5)

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_process_message(self, config, bus, agent_handler):
        """测试消息处理"""
        manager = ChannelManager(config, bus, agent_handler)

        # 添加模拟渠道
        mock_channel = MockChannel(
            config=MagicMock(allowed_users=[]),
            bus=bus,
        )
        manager.channels["mock"] = mock_channel

        # 启动管理器
        await manager.start_all()

        # 发布入站消息
        inbound = InboundMessage(
            channel="mock",
            sender_id="user1",
            chat_id="chat1",
            content="Hello",
        )
        await bus.publish_inbound(inbound)

        # 等待处理
        await asyncio.sleep(0.5)

        # 应该有出站响应
        assert bus.outbound_size >= 1

        await manager.stop_all()

    def test_get_status(self, config, bus, agent_handler):
        """测试获取状态"""
        manager = ChannelManager(config, bus, agent_handler)

        status = manager.get_status()
        assert "running" in status
        assert "channels" in status
        assert "bus_stats" in status