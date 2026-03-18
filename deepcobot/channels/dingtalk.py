"""钉钉渠道实现

使用 dingtalk-stream 库实现钉钉机器人渠道。
"""

import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


class DingTalkChannel(BaseChannel):
    """
    钉钉渠道实现，使用 Stream 模式连接。

    特点：
    - 无需公网 IP
    - 支持 Stream 模式
    - 支持卡片消息

    Attributes:
        name: 渠道名称（"dingtalk"）
    """

    name = "dingtalk"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化钉钉渠道。

        Args:
            config: 渠道配置（包含 client_id, client_secret, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.client_id = getattr(config, "client_id", "")
        self.client_secret = getattr(config, "client_secret", "")
        self._client = None

    async def start(self) -> None:
        """启动钉钉 Bot"""
        if not self.client_id or not self.client_secret:
            logger.error("DingTalk client_id or client_secret not configured")
            return

        try:
            from dingtalk_stream import DingTalkStreamClient, ChatBotHandler
            from dingtalk_stream.chatbot import ChatBotMessage
        except ImportError:
            raise ImportError(
                "dingtalk-stream not installed. "
                "Install it with: pip install deepcobot[dingtalk]"
            )

        self._running = True

        # 创建自定义处理器
        class CustomChatBotHandler(ChatBotHandler):
            def __init__(self, channel):
                super().__init__()
                self.channel = channel

            async def process(self, callback: ChatBotMessage):
                # 构建发送者 ID
                sender_id = callback.sender_id
                sender_nick = callback.sender_nick or callback.sender_id

                await self.channel._handle_message(
                    sender_id=sender_id,
                    chat_id=callback.conversation_id,
                    content=callback.content,
                    metadata={
                        "message_id": callback.message_id,
                        "sender_nick": sender_nick,
                        "conversation_type": callback.conversation_type,
                    },
                )

        # 创建客户端
        self._client = DingTalkStreamClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self._client.register_callback_handler(
            ChatBotHandler,
            CustomChatBotHandler(self),
        )

        logger.info("DingTalk client initialized")

        # 启动客户端
        try:
            await self._client.start()
        except Exception as e:
            logger.error(f"DingTalk bot error: {e}")
            self._running = False

    async def stop(self) -> None:
        """停止钉钉 Bot"""
        self._running = False
        if self._client:
            await self._client.stop()
            self._client = None
        logger.info("DingTalk channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到钉钉。

        Args:
            msg: 出站消息
        """
        if not self._client:
            return

        try:
            from dingtalk_stream.chatbot import ChatBotMessage

            # 发送 Markdown 消息
            self._client.send_markdown(
                conversation_id=msg.chat_id,
                content=msg.content,
            )

        except Exception as e:
            logger.error(f"Error sending DingTalk message: {e}")

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新。

        钉钉不支持"正在输入"状态。

        Args:
            chat_id: 会话 ID
            content: 进度内容
        """
        # 钉钉不支持输入状态
        pass