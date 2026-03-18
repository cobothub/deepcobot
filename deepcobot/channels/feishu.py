"""飞书渠道实现

使用 lark-oapi 库实现飞书机器人渠道。
"""

import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


class FeishuChannel(BaseChannel):
    """
    飞书渠道实现，使用 HTTP 事件回调模式。

    特点：
    - 支持事件订阅
    - 支持消息加密
    - 支持卡片消息

    Attributes:
        name: 渠道名称（"feishu"）
    """

    name = "feishu"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化飞书渠道。

        Args:
            config: 渠道配置（包含 app_id, app_secret, encrypt_key, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.app_id = getattr(config, "app_id", "")
        self.app_secret = getattr(config, "app_secret", "")
        self.encrypt_key = getattr(config, "encrypt_key", None)
        self.verification_token = getattr(config, "verification_token", None)
        self._client = None

    async def start(self) -> None:
        """启动飞书 Bot"""
        if not self.app_id or not self.app_secret:
            logger.error("Feishu app_id or app_secret not configured")
            return

        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )
        except ImportError:
            raise ImportError(
                "lark-oapi not installed. "
                "Install it with: pip install deepcobot[feishu]"
            )

        self._running = True

        # 创建客户端
        self._client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.ERROR) \
            .build()

        logger.info("Feishu client initialized")

        # 飞书需要外部 HTTP 服务器来接收事件
        # 这里只初始化客户端，实际的事件处理需要在 Web 服务中配置
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """停止飞书 Bot"""
        self._running = False
        self._client = None
        logger.info("Feishu channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到飞书。

        Args:
            msg: 出站消息
        """
        if not self._client:
            return

        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )
            import lark_oapi as lark

            # 构建消息内容
            content = json.dumps({
                "text": msg.content,
            })

            # 创建请求
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(msg.chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                ) \
                .build()

            # 发送消息
            response = self._client.im.v1.message.create(request)

            if not response.success():
                logger.error(f"Feishu send error: {response.code} - {response.msg}")

        except Exception as e:
            logger.error(f"Error sending Feishu message: {e}")

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新。

        飞书不支持"正在输入"状态，可以发送临时卡片消息。

        Args:
            chat_id: 会话 ID
            content: 进度内容
        """
        # 飞书不支持输入状态，可以忽略或发送临时消息
        pass

    async def handle_webhook_event(self, event_data: dict) -> None:
        """
        处理 Webhook 事件（需要从外部 HTTP 服务调用）。

        Args:
            event_data: 事件数据
        """
        event = event_data.get("event", {})
        message = event.get("message", {})

        if not message:
            return

        # 解析消息内容
        content = message.get("content", "{}")
        try:
            content_data = json.loads(content)
            text = content_data.get("text", "")
        except json.JSONDecodeError:
            text = content

        # 获取发送者信息
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id", "unknown")

        # 获取会话 ID
        chat_id = message.get("chat_id", "")

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=text,
            metadata={
                "message_id": message.get("message_id"),
                "message_type": message.get("message_type"),
                "sender_open_id": sender_id,
            },
        )