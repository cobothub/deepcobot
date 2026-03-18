"""消息数据模型

定义入站和出站消息的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageType(Enum):
    """消息类型"""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class InboundMessage:
    """
    入站消息 - 从渠道接收到 Agent。

    Attributes:
        channel: 渠道标识（telegram、discord、feishu、dingtalk、cli、web）
        sender_id: 发送者唯一标识
        chat_id: 会话唯一标识
        content: 消息文本内容
        message_type: 消息类型
        media_urls: 媒体文件 URL 列表
        metadata: 渠道特定元数据
        timestamp: 消息时间戳
    """

    channel: str
    sender_id: str
    chat_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    media_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def session_key(self) -> str:
        """
        会话标识，用于关联 Agent 状态。

        格式: channel:chat_id
        """
        return f"{self.channel}:{self.chat_id}"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "channel": self.channel,
            "sender_id": self.sender_id,
            "chat_id": self.chat_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "media_urls": self.media_urls,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "session_key": self.session_key,
        }


@dataclass
class OutboundMessage:
    """
    出站消息 - 从 Agent 发送到渠道。

    Attributes:
        channel: 目标渠道标识
        chat_id: 目标会话 ID
        content: 消息文本内容
        reply_to: 回复的消息 ID（可选）
        media_urls: 媒体文件 URL 列表
        metadata: 渠道特定元数据
    """

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "channel": self.channel,
            "chat_id": self.chat_id,
            "content": self.content,
            "reply_to": self.reply_to,
            "media_urls": self.media_urls,
            "metadata": self.metadata,
        }


@dataclass
class ProgressMessage:
    """
    进度消息 - 用于显示中间状态。

    例如：正在输入...、正在处理...
    """

    channel: str
    chat_id: str
    content: str
    message_type: str = "typing"  # typing, processing, etc.

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "channel": self.channel,
            "chat_id": self.chat_id,
            "content": self.content,
            "message_type": self.message_type,
        }