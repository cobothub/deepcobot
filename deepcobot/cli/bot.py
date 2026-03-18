"""Bot command - Start bot channels."""

import asyncio
import signal
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from deepcobot import __version__
from deepcobot.config import load_config
from deepcobot.cli.i18n import t, Language
from deepcobot.cli.context import setup_language

console = Console()


def bot_cmd(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
) -> None:
    """Start bot channels (Telegram, Discord, Feishu, DingTalk, etc.)."""
    lang = setup_language(config)

    try:
        cfg = load_config(config)

        console.print(Panel.fit(
            f"[bold green]DeepCoBot[/bold green] v{__version__}\n"
            f"Model: {cfg.agent.model}\n"
            f"Workspace: {cfg.agent.workspace}",
            title=t("welcome.title", lang),
        ))

        asyncio.run(_run_bot(cfg, lang))

    except FileNotFoundError as e:
        console.print(f"[red]{t('error.config', lang)}[/red] {e}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{t('error.config', lang)}[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('bot.stopped', lang)}[/yellow]")
        raise typer.Exit(0)


async def _run_bot(cfg, lang: Language) -> None:
    """Run bot channels."""
    from deepcobot.agent.factory import create_agent_async
    from deepcobot.bus.queue import MessageBus
    from deepcobot.channels import ChannelManager, InboundMessage, OutboundMessage
    from deepcobot.cron import CronService, HeartbeatService

    # 创建 Agent
    resources = await create_agent_async(cfg)
    graph = resources["graph"]
    workspace = resources["workspace"]

    # 创建消息总线
    bus = MessageBus()

    # 记录上次交互渠道
    last_dispatch: dict[str, str] = {}

    # Agent 消息处理函数
    async def agent_handler(msg: InboundMessage) -> OutboundMessage | None:
        """处理入站消息并返回响应"""
        nonlocal last_dispatch

        # 记录上次交互渠道（排除 heartbeat 自身）
        if msg.channel != "heartbeat":
            last_dispatch = {"channel": msg.channel, "chat_id": msg.chat_id}

        thread_config = {
            "configurable": {
                "thread_id": msg.chat_id,
            }
        }

        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": msg.content}]},
                config=thread_config,
            )

            # 提取最后一条助手消息
            content = ""
            if "messages" in result:
                for m in reversed(result["messages"]):
                    msg_type = type(m).__name__
                    if msg_type == "AIMessage":
                        content = m.content
                        if isinstance(content, list):
                            texts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    texts.append(item.get("text", ""))
                            content = "\n".join(texts) if texts else ""
                        content = str(content) if content else ""
                        break
                    elif isinstance(m, dict) and m.get("role") == "assistant":
                        content = m.get("content", "") or ""
                        break

            if content:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"Error: {e}",
            )

        return None

    # 创建渠道管理器（不包含 CLI 渠道）
    manager = ChannelManager(cfg, bus, agent_handler, include_cli=False)

    # 检查是否有渠道启用
    if not manager.channels:
        console.print(f"[yellow]{t('bot.no_channels', lang)}[/yellow]")
        return

    # 显示渠道状态
    console.print(f"\n[bold]{t('bot.starting', lang)}[/bold]")
    for name, channel in manager.channels.items():
        console.print(f"  • {name}")

    # Heartbeat 回调
    async def on_heartbeat_execute(content: str, session_key: str, channel: str) -> str:
        """Heartbeat 执行回调"""
        thread_config = {
            "configurable": {
                "thread_id": session_key,
            }
        }

        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": content}]},
                config=thread_config,
            )

            # 提取响应
            response = ""
            if "messages" in result:
                for m in reversed(result["messages"]):
                    msg_type = type(m).__name__
                    if msg_type == "AIMessage":
                        response = str(m.content or "")
                        if isinstance(m.content, list):
                            texts = []
                            for item in m.content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    texts.append(item.get("text", ""))
                            response = "\n".join(texts) if texts else ""
                        break
                    elif isinstance(m, dict) and m.get("role") == "assistant":
                        response = m.get("content", "") or ""
                        break

            return response

        except Exception as e:
            logger.error(f"Heartbeat agent error: {e}")
            return ""

    def get_last_dispatch() -> tuple[str, str] | None:
        """获取上次交互渠道"""
        if last_dispatch:
            return last_dispatch.get("channel"), last_dispatch.get("chat_id")
        return None

    # Cron 执行回调
    async def on_cron_execute(message: str, session_key: str, channel: str) -> str:
        """Cron 任务执行回调"""
        thread_config = {
            "configurable": {
                "thread_id": session_key,
            }
        }

        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config=thread_config,
            )

            # 提取响应
            response = ""
            if "messages" in result:
                for m in reversed(result["messages"]):
                    msg_type = type(m).__name__
                    if msg_type == "AIMessage":
                        response = str(m.content or "")
                        if isinstance(m.content, list):
                            texts = []
                            for item in m.content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    texts.append(item.get("text", ""))
                            response = "\n".join(texts) if texts else ""
                        break
                    elif isinstance(m, dict) and m.get("role") == "assistant":
                        response = m.get("content", "") or ""
                        break

            return response

        except Exception as e:
            logger.error(f"Cron agent error: {e}")
            return ""

    # 创建 Heartbeat 服务
    heartbeat = HeartbeatService(
        workspace=workspace,
        bus=bus,
        config=cfg.heartbeat,
        on_execute=on_heartbeat_execute,
        get_last_dispatch=get_last_dispatch,
    )

    # 创建 Cron 服务
    cron = CronService(
        store_path=cfg.cron.store_path,
        bus=bus,
        on_execute=on_cron_execute,
    )

    # 设置信号处理
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    channel_tasks: list[asyncio.Task] = []

    def signal_handler():
        console.print(f"\n[yellow]{t('bot.stopping', lang)}[/yellow]")
        # 先停止渠道，让 DingTalk 的无限循环退出
        for name, channel in manager.channels.items():
            channel._running = False
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    except NotImplementedError:
        # Windows 不支持 add_signal_handler
        pass

    # 启动消息总线
    await bus.start()

    # 设置管理器运行标志
    manager._running = True

    # 启动出站消息分发器
    manager._dispatch_task = asyncio.create_task(manager._dispatch_outbound())

    # 启动入站消息消费者
    manager._consumer_task = asyncio.create_task(manager._consume_inbound())

    # 后台启动所有渠道
    for name, channel in manager.channels.items():
        task = asyncio.create_task(manager._start_channel(name, channel))
        channel_tasks.append(task)

    # 启动 Heartbeat 服务
    await heartbeat.start()
    if cfg.heartbeat.enabled:
        console.print(f"  • heartbeat (every {cfg.heartbeat.every})")

    # 启动 Cron 服务
    await cron.start()
    enabled_jobs = len([j for j in cron.list_jobs() if j.enabled])
    if enabled_jobs > 0:
        console.print(f"  • cron ({enabled_jobs} jobs)")

    console.print(f"[dim]{t('serve.ctrlc', lang)}[/dim]")

    # 等待停止信号
    await stop_event.wait()

    # 停止 Cron
    await cron.stop()

    # 停止 Heartbeat
    await heartbeat.stop()

    # 取消渠道任务
    for task in channel_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # 停止渠道
    await manager.stop_all()