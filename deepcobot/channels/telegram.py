"""Telegram 渠道实现

使用 python-telegram-bot 库实现 Telegram Bot 渠道。
"""

import asyncio
import re
from typing import TYPE_CHECKING

from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


def _markdown_to_telegram_html(text: str) -> str:
    """
    将 Markdown 转换为 Telegram 支持的 HTML 格式。

    转换规则：
    - **bold** -> <b>bold</b>
    - *italic* -> <i>italic</i>
    - `code` -> <code>code</code>
    - ```block``` -> <pre><code>block</code></pre>
    - [text](url) -> <a href="url">text</a>

    Args:
        text: Markdown 文本

    Returns:
        Telegram HTML 格式文本
    """
    if not text:
        return ""

    # 保护代码块
    code_blocks: list[str] = []

    def save_code_block(m):
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # 保护行内代码
    inline_codes: list[str] = []

    def save_inline_code(m):
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # 转义 HTML 特殊字符
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Markdown -> HTML
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![a-zA-Z0-9])\*([^*]+)\*(?![a-zA-Z0-9])", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # 恢复代码块
    for i, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    for i, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


class TelegramChannel(BaseChannel):
    """
    Telegram 渠道实现，使用长轮询模式。

    特点：
    - 无需公网 IP
    - 支持 Markdown 格式转换
    - 支持媒体文件
    - 支持"正在输入"指示器

    Attributes:
        name: 渠道名称（"telegram"）
    """

    name = "telegram"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化 Telegram 渠道。

        Args:
            config: 渠道配置（包含 token, proxy, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.token = getattr(config, "token", "")
        self.proxy = getattr(config, "proxy", None)
        self._app = None
        self._typing_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """启动 Telegram Bot（长轮询模式）"""
        if not self.token:
            logger.error("Telegram bot token not configured")
            return

        try:
            from telegram import Update
            from telegram.ext import Application, MessageHandler, filters, ContextTypes
        except ImportError:
            raise ImportError(
                "python-telegram-bot not installed. "
                "Install it with: pip install deepcobot[telegram]"
            )

        self._running = True

        # 构建 Application
        builder = Application.builder().token(self.token)
        if self.proxy:
            builder = builder.proxy(self.proxy).get_updates_proxy(self.proxy)
        self._app = builder.build()

        # 添加消息处理器
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VOICE | filters.Document.ALL)
                & ~filters.COMMAND,
                self._on_message,
            )
        )

        logger.info("Starting Telegram bot (polling mode)...")

        # 初始化并启动
        await self._app.initialize()
        await self._app.start()

        bot_info = await self._app.bot.get_me()
        logger.info(f"Telegram bot @{bot_info.username} connected")

        # 开始轮询
        await self._app.updater.start_polling(drop_pending_updates=True)

        # 保持运行
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """停止 Telegram Bot"""
        self._running = False

        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)

        if self._app:
            logger.info("Stopping Telegram bot...")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到 Telegram。

        Args:
            msg: 出站消息
        """
        if not self._app:
            return

        self._stop_typing(msg.chat_id)

        try:
            chat_id = int(msg.chat_id)
            html_content = _markdown_to_telegram_html(msg.content)

            # 处理超长消息
            if len(html_content) > 4000:
                chunks = self._split_message(html_content, 4000)
                for chunk in chunks:
                    await self._app.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode="HTML",
                    )
            else:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=html_content,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送"正在输入"指示器。

        Args:
            chat_id: 会话 ID
            content: 进度内容（Telegram 只支持 typing 动作）
        """
        self._start_typing(chat_id)

    def _start_typing(self, chat_id: str) -> None:
        """启动"正在输入"指示器"""
        self._stop_typing(chat_id)

        async def typing_loop():
            while self._app and self._running:
                try:
                    await self._app.bot.send_chat_action(
                        chat_id=int(chat_id),
                        action="typing",
                    )
                    await asyncio.sleep(4)
                except Exception:
                    break

        self._typing_tasks[chat_id] = asyncio.create_task(typing_loop())

    def _stop_typing(self, chat_id: str) -> None:
        """停止"正在输入"指示器"""
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """
        分割超长消息。

        Args:
            text: 原始文本
            max_len: 最大长度

        Returns:
            分割后的消息列表
        """
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

    async def _on_message(self, update, context) -> None:
        """
        处理入站消息。

        Args:
            update: Telegram 更新对象
            context: 上下文
        """
        try:
            from telegram import Update
        except ImportError:
            return

        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id

        # 构建发送者 ID
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"

        # 构建消息内容
        content_parts = []
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        content = "\n".join(content_parts) if content_parts else ""

        # 开始输入指示器
        self._start_typing(str(chat_id))

        # 转发到消息总线
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=content,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
            },
        )