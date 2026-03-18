"""消息渠道模块"""

from deepcobot.channels.events import InboundMessage, OutboundMessage, MessageType
from deepcobot.channels.base import BaseChannel
from deepcobot.channels.manager import ChannelManager

__all__ = [
    "InboundMessage",
    "OutboundMessage",
    "MessageType",
    "BaseChannel",
    "ChannelManager",
]