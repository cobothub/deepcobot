"""消息总线测试"""

import asyncio

import pytest

from deepcobot.bus.queue import MessageBus
from deepcobot.channels.events import InboundMessage, OutboundMessage, MessageType


class TestMessageBus:
    """消息总线测试"""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """测试启动和停止"""
        bus = MessageBus()

        await bus.start()
        assert bus.is_running is True

        await bus.stop()
        assert bus.is_running is False

    @pytest.mark.asyncio
    async def test_inbound_message(self):
        """测试入站消息发布和消费"""
        bus = MessageBus()
        await bus.start()

        msg = InboundMessage(
            channel="test",
            sender_id="user1",
            chat_id="chat1",
            content="Hello",
        )

        # 发布消息
        await bus.publish_inbound(msg)
        assert bus.inbound_size == 1

        # 消费消息
        consumed = await bus.consume_inbound()
        assert consumed.channel == "test"
        assert consumed.sender_id == "user1"
        assert consumed.content == "Hello"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_outbound_message(self):
        """测试出站消息发布和消费"""
        bus = MessageBus()
        await bus.start()

        msg = OutboundMessage(
            channel="test",
            chat_id="chat1",
            content="Response",
        )

        # 发布消息
        await bus.publish_outbound(msg)
        assert bus.outbound_size == 1

        # 消费消息
        consumed = await bus.consume_outbound()
        assert consumed.channel == "test"
        assert consumed.chat_id == "chat1"
        assert consumed.content == "Response"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_threadsafe_publish(self):
        """测试线程安全发布"""
        bus = MessageBus()
        await bus.start()

        msg = InboundMessage(
            channel="test",
            sender_id="user1",
            chat_id="chat1",
            content="Thread safe",
        )

        # 线程安全发布
        bus.publish_inbound_threadsafe(msg)

        # 等待消息被处理
        await asyncio.sleep(0.1)

        consumed = await bus.consume_inbound()
        assert consumed.content == "Thread safe"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_clear_on_stop(self):
        """测试停止时清空队列"""
        bus = MessageBus(max_size=10)
        await bus.start()

        # 添加多条消息
        for i in range(5):
            await bus.publish_inbound(
                InboundMessage(
                    channel="test",
                    sender_id="user1",
                    chat_id="chat1",
                    content=f"Message {i}",
                )
            )

        assert bus.inbound_size == 5

        # 停止后队列应被清空
        await bus.stop()
        assert bus.inbound_size == 0
        assert bus.outbound_size == 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """测试获取统计信息"""
        bus = MessageBus(max_size=100)
        await bus.start()

        stats = bus.get_stats()
        assert stats["running"] is True
        assert stats["inbound_size"] == 0
        assert stats["outbound_size"] == 0
        assert stats["inbound_max_size"] == 100
        assert stats["outbound_max_size"] == 100

        await bus.stop()

        stats = bus.get_stats()
        assert stats["running"] is False


class TestInboundMessage:
    """入站消息测试"""

    def test_session_key(self):
        """测试会话标识"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user1",
            chat_id="chat123",
            content="Test",
        )

        assert msg.session_key == "telegram:chat123"

    def test_to_dict(self):
        """测试转换为字典"""
        msg = InboundMessage(
            channel="cli",
            sender_id="user1",
            chat_id="chat1",
            content="Hello",
            message_type=MessageType.TEXT,
            media_urls=["http://example.com/image.png"],
            metadata={"key": "value"},
        )

        d = msg.to_dict()
        assert d["channel"] == "cli"
        assert d["sender_id"] == "user1"
        assert d["chat_id"] == "chat1"
        assert d["content"] == "Hello"
        assert d["message_type"] == "text"
        assert d["media_urls"] == ["http://example.com/image.png"]
        assert d["metadata"] == {"key": "value"}
        assert d["session_key"] == "cli:chat1"
        assert "timestamp" in d


class TestOutboundMessage:
    """出站消息测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat1",
            content="Response",
            reply_to="msg123",
            media_urls=["http://example.com/image.png"],
            metadata={"key": "value"},
        )

        d = msg.to_dict()
        assert d["channel"] == "telegram"
        assert d["chat_id"] == "chat1"
        assert d["content"] == "Response"
        assert d["reply_to"] == "msg123"
        assert d["media_urls"] == ["http://example.com/image.png"]
        assert d["metadata"] == {"key": "value"}