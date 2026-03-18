"""渠道基类

定义消息渠道的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from deepcobot.channels.events import InboundMessage, OutboundMessage


class BaseChannel(ABC):
    """
    消息渠道抽象基类。

    所有渠道实现必须继承此类并实现抽象方法。

    设计要点：
    - 统一的生命周期管理（start/stop）
    - 权限控制（allowed_users）
    - 消息格式转换

    Attributes:
        name: 渠道名称标识
        config: 渠道配置对象
        bus: 消息总线实例
    """

    name: str = "base"

    def __init__(
        self,
        config: Any,
        bus: "MessageBus",
    ):
        """
        初始化渠道。

        Args:
            config: 渠道配置对象
            bus: 消息总线实例
        """
        self.config = config
        self.bus = bus
        self._running = False
        self._allowed_users: list[str] = getattr(config, "allowed_users", [])

    @abstractmethod
    async def start(self) -> None:
        """
        启动渠道。

        实现要点：
        1. 连接到消息平台
        2. 开始监听消息
        3. 将消息转发到 MessageBus
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止渠道并清理资源"""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到渠道。

        Args:
            msg: 出站消息
        """
        pass

    @abstractmethod
    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新。

        例如：正在输入...

        Args:
            chat_id: 目标会话 ID
            content: 进度内容
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """
        检查发送者是否有权限使用 Bot。

        权限模型：
        - 如果 allowed_users 为空，允许所有人
        - 支持 user_id 或 username 匹配

        Args:
            sender_id: 发送者 ID

        Returns:
            是否有权限
        """
        if not self._allowed_users:
            return True

        sender_str = str(sender_id)
        if sender_str in self._allowed_users:
            return True

        # 支持 user_id|username 格式
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in self._allowed_users:
                    return True

        return False

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media_urls: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        处理入站消息的通用流程。

        1. 检查权限
        2. 构建消息对象
        3. 发布到消息总线

        Args:
            sender_id: 发送者 ID
            chat_id: 会话 ID
            content: 消息内容
            media_urls: 媒体 URL 列表
            metadata: 渠道特定元数据
        """
        if not self.is_allowed(sender_id):
            logger.warning(
                f"Access denied for sender {sender_id} on channel {self.name}"
            )
            return

        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media_urls=media_urls or [],
            metadata=metadata or {},
        )

        await self.bus.publish_inbound(msg)

    @property
    def is_running(self) -> bool:
        """渠道是否处于运行状态"""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """
        获取渠道状态。

        Returns:
            状态信息字典
        """
        return {
            "name": self.name,
            "running": self._running,
            "allowed_users_count": len(self._allowed_users),
        }


# 类型提示
from deepcobot.bus.queue import MessageBus