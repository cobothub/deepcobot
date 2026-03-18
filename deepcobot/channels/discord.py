"""Discord 渠道实现

使用 discord.py 库实现 Discord Bot 渠道。
"""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


class DiscordChannel(BaseChannel):
    """
    Discord 渠道实现，使用 WebSocket Gateway 连接。

    特点：
    - 实时消息接收
    - 支持 Markdown 格式
    - 支持"正在输入"状态

    Attributes:
        name: 渠道名称（"discord"）
    """

    name = "discord"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化 Discord 渠道。

        Args:
            config: 渠道配置（包含 token, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.token = getattr(config, "token", "")
        self._client = None

    async def start(self) -> None:
        """启动 Discord Bot"""
        if not self.token:
            logger.error("Discord bot token not configured")
            return

        try:
            import discord
        except ImportError:
            raise ImportError(
                "discord.py not installed. "
                "Install it with: pip install deepcobot[discord]"
            )

        self._running = True

        # 配置 intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        # 创建客户端
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready():
            logger.info(f"Discord bot {self._client.user} connected")

        @self._client.event
        async def on_message(message):
            # 忽略机器人自己的消息
            if message.author == self._client.user:
                return

            # 构建发送者 ID
            sender_id = str(message.author.id)
            if message.author.name:
                sender_id = f"{sender_id}|{message.author.name}"

            await self._handle_message(
                sender_id=sender_id,
                chat_id=str(message.channel.id),
                content=message.content,
                metadata={
                    "message_id": message.id,
                    "user_id": message.author.id,
                    "username": str(message.author),
                    "channel_name": message.channel.name if hasattr(message.channel, "name") else "DM",
                },
            )

        # 启动客户端
        try:
            await self._client.start(self.token)
        except Exception as e:
            logger.error(f"Discord bot error: {e}")
            self._running = False

    async def stop(self) -> None:
        """停止 Discord Bot"""
        self._running = False

        if self._client:
            logger.info("Stopping Discord bot...")
            await self._client.close()
            self._client = None

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到 Discord。

        Args:
            msg: 出站消息
        """
        if not self._client:
            return

        try:
            # 获取频道
            channel = self._client.get_channel(int(msg.chat_id))
            if not channel:
                logger.warning(f"Discord channel not found: {msg.chat_id}")
                return

            # Discord 支持 Markdown，直接发送
            # 处理超长消息
            if len(msg.content) > 2000:
                chunks = self._split_message(msg.content, 2000)
                for chunk in chunks:
                    await channel.send(chunk)
            else:
                await channel.send(msg.content)

        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新。

        Discord 不支持"正在输入"状态在 DM 中显示，
        这里发送一个临时消息然后删除。

        Args:
            chat_id: 会话 ID
            content: 进度内容
        """
        # Discord API 不支持 DM 中的 typing indicator
        # 可以选择发送临时消息或忽略
        pass

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """分割超长消息"""
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_len:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        return chunks