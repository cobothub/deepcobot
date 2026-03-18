"""CLI 渠道实现

提供命令行交互界面。
"""

import asyncio
import sys
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


console = Console()


class CLIChannel(BaseChannel):
    """
    CLI 渠道实现，通过标准输入/输出提供交互界面。

    特点：
    - 支持富文本 Markdown 渲染
    - 支持多行输入
    - 支持命令历史

    Attributes:
        name: 渠道名称（"cli"）
    """

    name = "cli"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化 CLI 渠道。

        Args:
            config: 渠道配置
            bus: 消息总线
        """
        super().__init__(config, bus)
        self._input_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动 CLI 渠道"""
        self._running = True
        logger.info("CLI channel started")

        # 显示欢迎信息
        console.print(Panel.fit(
            "[bold green]DeepCoBot CLI[/bold green]\n"
            "Type your message and press Enter.\n"
            "Type 'exit' or 'quit' to end the session.",
            title="Welcome",
        ))

        # 启动输入循环
        self._input_task = asyncio.create_task(self._input_loop())

    async def stop(self) -> None:
        """停止 CLI 渠道"""
        self._running = False

        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass

        logger.info("CLI channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到 CLI。

        Args:
            msg: 出站消息
        """
        if msg.content:
            # 渲染 Markdown
            md = Markdown(msg.content)
            console.print()
            console.print(Panel(md, title="[bold green]Assistant[/bold green]"))
            console.print()
            console.print("[dim]─" * 50 + "[/dim]")

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度指示。

        Args:
            chat_id: 会话 ID（CLI 中忽略）
            content: 进度内容
        """
        console.print(f"[dim]{content}...[/dim]")

    async def _input_loop(self) -> None:
        """输入循环"""
        while self._running:
            try:
                # 使用异步方式读取输入
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(
                    None,
                    lambda: console.input("[bold blue]You[/bold blue]: "),
                )

                if not user_input or not user_input.strip():
                    continue

                # 处理特殊命令
                if user_input.lower() in ("exit", "quit"):
                    console.print("[yellow]Goodbye![/yellow]")
                    self._running = False
                    break

                # 发送消息到总线
                await self._handle_message(
                    sender_id="cli_user",
                    chat_id="cli_session",
                    content=user_input.strip(),
                )

            except EOFError:
                break
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' or 'quit' to end the session.[/yellow]")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CLI input error: {e}")
                break

        self._running = False