"""消息总线

异步消息队列，解耦消息渠道和 Agent 核心。
"""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass

from deepcobot.channels.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    异步消息总线，解耦消息渠道和 Agent 核心。

    设计要点：
    - 双队列模式：inbound 和 outbound 分离
    - 线程安全：支持从任意线程入队
    - 背压控制：队列满时阻塞或丢弃旧消息

    Attributes:
        inbound: 入站消息队列（从渠道到 Agent）
        outbound: 出站消息队列（从 Agent 到渠道）
    """

    def __init__(self, max_size: int = 1000):
        """
        初始化消息总线。

        Args:
            max_size: 队列最大容量
        """
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_size)
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=max_size)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

    async def start(self) -> None:
        """启动消息总线"""
        self._loop = asyncio.get_running_loop()
        self._running = True
        logger.info("MessageBus started")

    async def stop(self) -> None:
        """停止消息总线"""
        self._running = False

        # 清空队列
        while not self.inbound.empty():
            try:
                self.inbound.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self.outbound.empty():
            try:
                self.outbound.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("MessageBus stopped")

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """
        发布入站消息（从渠道到 Agent）。

        Args:
            msg: 入站消息
        """
        await self.inbound.put(msg)
        logger.debug(f"MessageBus: inbound message from {msg.channel}")

    async def consume_inbound(self) -> InboundMessage:
        """
        消费入站消息（阻塞直到有消息）。

        Returns:
            入站消息
        """
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """
        发布出站消息（从 Agent 到渠道）。

        Args:
            msg: 出站消息
        """
        await self.outbound.put(msg)
        logger.debug(f"MessageBus: outbound message to {msg.channel}")

    async def consume_outbound(self) -> OutboundMessage:
        """
        消费出站消息（阻塞直到有消息）。

        Returns:
            出站消息
        """
        return await self.outbound.get()

    def publish_inbound_threadsafe(self, msg: InboundMessage) -> None:
        """
        线程安全地发布入站消息。

        用于从同步回调中调用。

        Args:
            msg: 入站消息
        """
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.publish_inbound(msg))
            )

    def publish_outbound_threadsafe(self, msg: OutboundMessage) -> None:
        """
        线程安全地发布出站消息。

        用于从同步回调中调用。

        Args:
            msg: 出站消息
        """
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.publish_outbound(msg))
            )

    @property
    def inbound_size(self) -> int:
        """入站队列大小"""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """出站队列大小"""
        return self.outbound.qsize()

    @property
    def is_running(self) -> bool:
        """消息总线是否运行中"""
        return self._running

    def get_stats(self) -> dict:
        """
        获取统计信息。

        Returns:
            统计信息字典
        """
        return {
            "running": self._running,
            "inbound_size": self.inbound_size,
            "outbound_size": self.outbound_size,
            "inbound_max_size": self.inbound.maxsize,
            "outbound_max_size": self.outbound.maxsize,
        }