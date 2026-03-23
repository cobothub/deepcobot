"""Bot command - Start bot channels."""

import asyncio
import signal
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from deepcobot import __version__, apply_config
from deepcobot.config import load_config
from deepcobot.agent import AgentSession
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
        apply_config(cfg)  # 应用日志等配置

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
    from deepcobot.bus.queue import MessageBus
    from deepcobot.channels import ChannelManager, InboundMessage, OutboundMessage
    from deepcobot.cron import CronService, HeartbeatService
    from deepcobot.services import (
        HealthChecker,
        MetricsCollector,
        get_metrics_collector,
        run_health_server,
        run_metrics_server,
    )
    from deepcobot.agent.approval import get_approval_manager

    # 创建共享的 AgentSession 实例
    session = AgentSession(cfg)

    # 获取审批管理器
    approval_manager = get_approval_manager()

    # 创建消息总线
    bus = MessageBus()

    # 创建健康检查器
    health_checker = HealthChecker()

    # 创建指标收集器
    metrics = get_metrics_collector()

    # 注册健康检查
    health_checker.add_check("bus", lambda: bus._running)
    health_checker.add_check("agent", lambda: True)  # Agent 创建成功即为健康

    # 服务任务列表
    service_tasks: list[asyncio.Task] = []

    # 记录上次交互渠道
    last_dispatch: dict[str, str] = {}

    # Agent 消息处理函数（使用 AgentSession）
    async def agent_handler(msg: InboundMessage) -> OutboundMessage | None:
        """处理入站消息并返回响应"""
        nonlocal last_dispatch
        import time
        import json

        # 记录上次交互渠道（排除 heartbeat 自身）
        if msg.channel != "heartbeat":
            last_dispatch = {"channel": msg.channel, "chat_id": msg.chat_id}

        # 生成会话标识
        session_key = f"{msg.channel}:{msg.chat_id}"

        # 检查是否是审批响应
        if approval_manager.has_pending(session_key):
            handled = approval_manager.handle_response(session_key, msg.content)
            if handled:
                logger.info(f"[Agent] Message treated as approval response for {session_key}")
                # 审批响应会被等待中的 session.invoke 处理
                # 这里不需要发送任何消息，结果会由原来的 invoke 流程发送
                return None
            # 如果不是有效的审批响应，继续正常处理

        # 处理特殊命令
        content = msg.content.strip()
        if content.lower() in ("/reset", "/new", "/clear", "重置", "新建会话"):
            session.set_thread_id(msg.chat_id)
            await session.clear_history()
            logger.info(f"[Agent] Session reset for {session_key}")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="✅ 会话已重置，开始新的对话。",
            )

        # 记录请求计数
        metrics.inc_requests(msg.channel)

        start_time = time.time()

        # 设置会话上下文
        session.set_thread_id(msg.chat_id)
        session.set_channel_context(msg.channel, msg.chat_id)

        # 设置消息发送回调（用于审批交互）
        async def send_callback(chat_id: str, content: str) -> None:
            """发送消息回调"""
            await bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=chat_id,
                content=content,
            ))

        session.set_send_callback(send_callback)

        # 进度消息列表
        current_progress: list[str] = []

        # 设置事件回调（用于显示执行进度）
        async def event_callback(event: dict) -> None:
            """处理流式事件的回调函数"""
            nonlocal current_progress

            if not cfg.agent.show_progress:
                return

            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # 工具调用开始
            if event_type == "on_tool_start":
                tool_name = event_name
                tool_input = event_data.get("input", {})

                # 获取渠道实例，判断是否使用 HTML 换行
                channel = manager.channels.get(msg.channel)
                use_html_br = channel and hasattr(channel, 'send_progress')  # 钉钉 AI Card 需要 <br>
                line_break = "<br>" if use_html_br else "\n"

                # 构建进度消息
                progress_line = f"⏳ **{tool_name}**"
                if isinstance(tool_input, dict):
                    # 显示关键参数
                    if tool_name == "execute" and "command" in tool_input:
                        cmd = str(tool_input["command"])[:50]
                        if len(str(tool_input["command"])) > 50:
                            cmd += "..."
                        progress_line += f"{line_break}`{cmd}`"
                    elif tool_name in ("read_file", "write_file", "edit_file") and "file_path" in tool_input:
                        progress_line += f"{line_break}📄 {tool_input['file_path']}"
                    elif tool_name in ("glob", "grep") and "pattern" in tool_input:
                        progress_line += f"{line_break}🔍 {tool_input['pattern']}"
                    elif tool_name == "web_search" and "query" in tool_input:
                        progress_line += f"{line_break}🌐 {tool_input['query'][:50]}"

                current_progress.append(progress_line)

                # 发送进度消息
                # 钉钉用 <br> 换行，其他渠道用 \n
                if channel and hasattr(channel, 'send_progress'):
                    progress_content = "<br><br>".join(current_progress)
                    try:
                        await channel.send_progress(msg.chat_id, progress_content)
                    except Exception as e:
                        logger.debug(f"Failed to send progress: {e}")
                else:
                    # 其他渠道：只发送第一条进度（避免刷屏）
                    if len(current_progress) == 1:
                        progress_content = "\n\n".join(current_progress)
                        await bus.publish_outbound(OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=progress_content,
                        ))

            # 工具调用结束
            elif event_type == "on_tool_end":
                # 更新进度：将 ⏳ 改为 ✅
                if current_progress:
                    current_progress[-1] = current_progress[-1].replace("⏳", "✅")

            # LLM 开始生成
            elif event_type in ("on_chat_model_start", "on_llm_start"):
                if cfg.agent.show_progress:
                    thinking_line = "🤔 正在思考..."
                    current_progress.append(thinking_line)

        session.set_event_callback(event_callback)

        logger.debug(f"[Agent] Starting invoke for {msg.channel}:{msg.chat_id}")
        logger.debug(f"[Agent] Input: {msg.content[:200]}..." if len(msg.content) > 200 else f"[Agent] Input: {msg.content}")

        try:
            response = await session.invoke(msg.content)

            # 记录成功调用
            metrics.inc_agent_invocations("success")
            metrics.observe_request_duration(msg.channel, time.time() - start_time)

            logger.debug(f"[Agent] Response length: {len(response)} chars")

            if response:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response,
                )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            logger.debug(f"[Agent] Error details: {type(e).__name__}: {e}")
            metrics.inc_agent_invocations("error")
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

    # Heartbeat 回调（使用 AgentSession）
    async def on_heartbeat_execute(content: str, session_key: str, channel: str) -> str:
        """Heartbeat 执行回调"""
        import time
        start_time = time.time()

        # 设置会话上下文
        session.set_thread_id(session_key)
        session.set_channel_context(channel, session_key)

        logger.debug(f"[Heartbeat] Starting execution for session: {session_key}")
        logger.debug(f"[Heartbeat] Content: {content[:200]}..." if len(content) > 200 else f"[Heartbeat] Content: {content}")

        try:
            response = await session.invoke(content)

            duration = time.time() - start_time
            logger.debug(f"[Heartbeat] Execution completed in {duration:.2f}s")
            logger.debug(f"[Heartbeat] Response length: {len(response)} chars")

            return response

        except Exception as e:
            logger.error(f"Heartbeat agent error: {e}")
            logger.debug(f"[Heartbeat] Error details: {type(e).__name__}: {e}")
            return ""

    def get_last_dispatch() -> tuple[str, str] | None:
        """获取上次交互渠道"""
        if last_dispatch:
            return last_dispatch.get("channel"), last_dispatch.get("chat_id")
        return None

    # Cron 执行回调（使用 AgentSession）
    async def on_cron_execute(message: str, session_key: str, channel: str) -> str:
        """Cron 任务执行回调"""
        import time
        start_time = time.time()

        # 设置会话上下文
        session.set_thread_id(session_key)
        session.set_channel_context(channel, session_key)

        logger.debug(f"[Cron] Starting execution for session: {session_key}")
        logger.debug(f"[Cron] Message: {message[:200]}..." if len(message) > 200 else f"[Cron] Message: {message}")

        try:
            response = await session.invoke(message)

            duration = time.time() - start_time
            logger.debug(f"[Cron] Execution completed in {duration:.2f}s")
            logger.debug(f"[Cron] Response length: {len(response)} chars")

            return response

        except Exception as e:
            logger.error(f"Cron agent error: {e}")
            logger.debug(f"[Cron] Error details: {type(e).__name__}: {e}")
            return ""

    # 创建 Heartbeat 服务
    workspace = cfg.agent.workspace
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
        # 设置渠道状态指标
        metrics.set_channel_status(name, True)

    # 启动健康检查服务
    if cfg.services.health_enabled:
        health_task = asyncio.create_task(
            run_health_server(
                health_checker,
                port=cfg.services.health_port,
            )
        )
        service_tasks.append(health_task)
        console.print(f"  • health (port {cfg.services.health_port})")

    # 启动指标服务
    if cfg.services.metrics_enabled:
        metrics_task = asyncio.create_task(
            run_metrics_server(port=cfg.services.metrics_port)
        )
        service_tasks.append(metrics_task)
        console.print(f"  • metrics (port {cfg.services.metrics_port})")

    # 启动 Heartbeat 服务
    await heartbeat.start()
    if cfg.heartbeat.enabled:
        console.print(f"  • heartbeat (every {cfg.heartbeat.every})")

    # 启动 Cron 服务
    await cron.start()
    enabled_jobs = len([j for j in cron.list_jobs() if j.enabled])
    disabled_jobs = len([j for j in cron.list_jobs() if not j.enabled])
    if enabled_jobs > 0:
        console.print(f"  • cron ({enabled_jobs} jobs)")
    # 设置 Cron 指标
    metrics.set_cron_jobs(enabled_jobs, disabled_jobs)

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

    # 取消服务任务
    for task in service_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # 停止渠道
    await manager.stop_all()