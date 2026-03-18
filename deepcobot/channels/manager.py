"""渠道管理器

管理所有消息渠道的生命周期和消息路由。
"""

import asyncio
from typing import Any, Callable, Coroutine

from loguru import logger

from deepcobot.bus.queue import MessageBus
from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import InboundMessage, OutboundMessage
from deepcobot.config import Config

# 默认配置
_CHANNEL_QUEUE_MAXSIZE = 1000
_CONSUMER_WORKERS = 4


class ChannelManager:
    """
    渠道管理器，管理所有消息渠道的生命周期和消息路由。

    职责：
    - 根据配置初始化渠道
    - 启动/停止渠道
    - 路由出站消息到对应渠道
    - 处理渠道启动失败

    Attributes:
        config: 配置对象
        bus: 消息总线实例
        agent_handler: Agent 消息处理函数
        channels: 已初始化的渠道字典
    """

    def __init__(
        self,
        config: Config,
        bus: MessageBus,
        agent_handler: Callable[[InboundMessage], Coroutine[Any, Any, OutboundMessage | None]],
    ):
        """
        初始化渠道管理器。

        Args:
            config: 配置对象
            bus: 消息总线实例
            agent_handler: Agent 消息处理函数
        """
        self.config = config
        self.bus = bus
        self.agent_handler = agent_handler
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        self._consumer_task: asyncio.Task | None = None
        self._running = False

        self._init_channels()

    def _init_channels(self) -> None:
        """根据配置初始化渠道"""
        # CLI 渠道（始终可用）
        if self.config.channels.cli.enabled:
            from deepcobot.channels.cli_channel import CLIChannel

            self.channels["cli"] = CLIChannel(
                self.config.channels.cli,
                self.bus,
            )
            logger.info("CLI channel enabled")

        # Telegram 渠道
        if self.config.channels.telegram.enabled:
            try:
                from deepcobot.channels.telegram import TelegramChannel

                self.channels["telegram"] = TelegramChannel(
                    self.config.channels.telegram,
                    self.bus,
                )
                logger.info("Telegram channel enabled")
            except ImportError as e:
                logger.warning(f"Telegram channel not available: {e}")

        # Discord 渠道
        if self.config.channels.discord.enabled:
            try:
                from deepcobot.channels.discord import DiscordChannel

                self.channels["discord"] = DiscordChannel(
                    self.config.channels.discord,
                    self.bus,
                )
                logger.info("Discord channel enabled")
            except ImportError as e:
                logger.warning(f"Discord channel not available: {e}")

        # 飞书渠道
        if self.config.channels.feishu.enabled:
            try:
                from deepcobot.channels.feishu import FeishuChannel

                self.channels["feishu"] = FeishuChannel(
                    self.config.channels.feishu,
                    self.bus,
                )
                logger.info("Feishu channel enabled")
            except ImportError as e:
                logger.warning(f"Feishu channel not available: {e}")

        # 钉钉渠道
        if self.config.channels.dingtalk.enabled:
            try:
                from deepcobot.channels.dingtalk import DingTalkChannel

                self.channels["dingtalk"] = DingTalkChannel(
                    self.config.channels.dingtalk,
                    self.bus,
                )
                logger.info("DingTalk channel enabled")
            except ImportError as e:
                logger.warning(f"DingTalk channel not available: {e}")

        # Web API 渠道
        if self.config.channels.web.enabled:
            try:
                from deepcobot.channels.web import WebAPIChannel

                self.channels["web"] = WebAPIChannel(
                    self.config.channels.web,
                    self.bus,
                )
                logger.info("Web API channel enabled")
            except ImportError as e:
                logger.warning(f"Web API channel not available: {e}")

    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """
        安全启动单个渠道。

        Args:
            name: 渠道名称
            channel: 渠道实例
        """
        try:
            logger.info(f"Starting {name} channel...")
            await channel.start()
            channel._running = True
            logger.info(f"{name} channel started successfully")
        except Exception as e:
            logger.error(f"Failed to start channel {name}: {e}")
            channel._running = False

    async def start_all(self) -> None:
        """启动所有渠道"""
        if not self.channels:
            logger.warning("No channels enabled")
            return

        self._running = True

        # 启动消息总线
        await self.bus.start()

        # 启动出站消息分发器
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # 启动入站消息消费者
        self._consumer_task = asyncio.create_task(self._consume_inbound())

        # 并行启动所有渠道
        tasks = []
        for name, channel in self.channels.items():
            tasks.append(self._start_channel(name, channel))

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Channel manager started with {len(self.channels)} channels")

    async def stop_all(self) -> None:
        """停止所有渠道"""
        logger.info("Stopping all channels...")
        self._running = False

        # 停止分发器
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # 停止所有渠道
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                channel._running = False
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        # 停止消息总线
        await self.bus.stop()

        logger.info("All channels stopped")

    async def _dispatch_outbound(self) -> None:
        """分发出站消息到对应渠道"""
        logger.info("Outbound dispatcher started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0,
                )

                channel = self.channels.get(msg.channel)
                if channel and channel.is_running:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Channel not running: {msg.channel}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dispatch error: {e}")

    async def _consume_inbound(self) -> None:
        """消费入站消息并调用 Agent 处理"""
        logger.info("Inbound consumer started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0,
                )

                # 异步调用 Agent 处理消息
                asyncio.create_task(self._process_message(msg))

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")

    async def _process_message(self, msg: InboundMessage) -> None:
        """
        处理单条入站消息。

        Args:
            msg: 入站消息
        """
        channel = self.channels.get(msg.channel)
        if not channel:
            logger.warning(f"Unknown channel: {msg.channel}")
            return

        try:
            # 发送进度指示
            await channel.send_progress(msg.chat_id, "Thinking...")

            # 调用 Agent 处理
            response = await self.agent_handler(msg)

            # 发送响应
            if response:
                await self.bus.publish_outbound(response)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # 发送错误响应
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=f"Sorry, an error occurred: {e}",
                )
            )

    def get_status(self) -> dict[str, Any]:
        """
        获取所有渠道状态。

        Returns:
            渠道状态信息
        """
        return {
            "running": self._running,
            "channels": {
                name: channel.get_status()
                for name, channel in self.channels.items()
            },
            "bus_stats": self.bus.get_stats(),
        }