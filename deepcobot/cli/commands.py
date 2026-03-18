"""CLI command definitions.

Uses Typer framework for command line interface with i18n support.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from deepcobot import __version__
from deepcobot.config import load_config, get_default_config_path, create_default_config
from deepcobot.agent import AgentSession
from deepcobot.cli.i18n import t, set_language, get_language, Language

app = typer.Typer(
    name="deepcobot",
    help="DeepCoBot",
    add_completion=False,
)

console = Console()

# Global language setting
_current_lang: Language = "en"


def _get_lang() -> Language:
    """Get current language."""
    return _current_lang


def _set_lang(lang: Language) -> None:
    """Set current language."""
    global _current_lang
    _current_lang = lang
    set_language(lang)


def version_callback(value: bool) -> None:
    """Display version information."""
    if value:
        console.print(f"deepcobot version: {__version__}")
        raise typer.Exit()


def _setup_language(config_path: Optional[Path] = None, lang: Optional[str] = None) -> Language:
    """Setup language from config or CLI argument."""
    if lang:
        _set_lang(lang)
    else:
        try:
            cfg = load_config(config_path)
            _set_lang(cfg.language)
        except Exception:
            _set_lang("en")

    return _get_lang()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version",
    ),
    lang: Optional[str] = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language (en/zh)",
    ),
) -> None:
    """DeepCoBot - A minimalist personal AI assistant framework."""
    _setup_language(lang=lang)


def _run_help() -> str:
    """Get run command help text."""
    lang = _get_lang()
    examples = f"""deepcobot run
deepcobot run --config /path/to/config.toml
deepcobot run --thread my-session"""
    return t("run.description", lang) + "\n\nExamples:\n" + examples


@app.command("run")
def run_cmd(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
    thread_id: str = typer.Option(
        "default",
        "--thread",
        "-t",
        help="Thread ID",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "-y",
        help="Auto approve",
    ),
) -> None:
    """Start an interactive CLI session."""
    lang = _setup_language(config)

    try:
        cfg = load_config(config)

        if auto_approve:
            cfg.agent.auto_approve = True

        console.print(Panel.fit(
            f"[bold green]DeepCoBot[/bold green] v{__version__}\n"
            f"Model: {cfg.agent.model}\n"
            f"Workspace: {cfg.agent.workspace}",
            title=t("welcome.title", lang),
        ))

        asyncio.run(_run_session(cfg, thread_id, lang))

    except FileNotFoundError as e:
        console.print(f"[red]{t('error.config', lang)}[/red] {e}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{t('error.config', lang)}[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('run.goodbye', lang)}[/yellow]")
        raise typer.Exit(0)


async def _run_session(cfg, thread_id: str, lang: Language) -> None:
    """Run interactive session."""
    from rich.status import Status
    from rich.live import Live

    session = AgentSession(cfg)
    session.set_thread_id(thread_id)

    # 当前状态跟踪
    current_status: Status | None = None
    status_live: Live | None = None

    # 设置审批回调
    async def approval_callback(action_requests: list[dict]) -> list[dict]:
        """处理审批请求的回调函数"""
        return await _handle_approval(action_requests, lang)

    session.set_approval_callback(approval_callback)

    # 工具名称的友好显示映射
    tool_display_names = {
        "execute": "执行命令",
        "read_file": "读取文件",
        "write_file": "写入文件",
        "edit_file": "编辑文件",
        "glob": "搜索文件",
        "grep": "搜索内容",
        "web_search": "网页搜索",
        "task": "调用子任务",
        "write_todos": "更新任务列表",
        "ls": "列出目录",
    }

    # 设置事件回调，用于显示执行进度
    async def event_callback(event: dict) -> None:
        """处理流式事件的回调函数"""
        nonlocal current_status, status_live

        event_type = event.get("event")
        event_name = event.get("name", "")
        event_data = event.get("data", {})

        # 工具调用开始
        if event_type == "on_tool_start":
            tool_name = event_name
            tool_input = event_data.get("input", {})

            # 获取友好的工具显示名称
            display_name = tool_display_names.get(tool_name, tool_name)
            status_msg = f"[bold yellow]⏳[/bold yellow] {display_name}"

            # 根据工具类型显示不同的参数预览
            if isinstance(tool_input, dict):
                preview_parts = []
                # 针对不同工具显示不同的关键参数
                if tool_name == "execute" and "command" in tool_input:
                    cmd = str(tool_input["command"])[:40]
                    if len(str(tool_input["command"])) > 40:
                        cmd += "..."
                    preview_parts.append(cmd)
                elif tool_name in ("read_file", "write_file", "edit_file") and "file_path" in tool_input:
                    preview_parts.append(str(tool_input["file_path"]))
                elif tool_name == "glob" and "pattern" in tool_input:
                    preview_parts.append(str(tool_input["pattern"]))
                elif tool_name == "grep" and "pattern" in tool_input:
                    preview_parts.append(str(tool_input["pattern"]))
                elif tool_name == "web_search" and "query" in tool_input:
                    query = str(tool_input["query"])[:30]
                    if len(str(tool_input["query"])) > 30:
                        query += "..."
                    preview_parts.append(query)
                elif tool_name == "task" and "name" in tool_input:
                    preview_parts.append(str(tool_input["name"]))

                if preview_parts:
                    status_msg += f" [dim]{preview_parts[0]}[/dim]"

            if status_live:
                status_live.stop()

            current_status = console.status(status_msg, spinner="dots")
            status_live = Live(current_status, console=console, refresh_per_second=4)
            status_live.start()

        # 工具调用结束
        elif event_type == "on_tool_end":
            if status_live:
                status_live.stop()
                status_live = None

        # LLM 调用开始
        elif event_type == "on_llm_start":
            if status_live:
                status_live.stop()

            thinking_text = t("progress.thinking", lang)
            current_status = console.status(f"[cyan]{thinking_text}[/cyan]", spinner="dots")
            status_live = Live(current_status, console=console, refresh_per_second=4)
            status_live.start()

        # LLM 流式输出
        elif event_type == "on_llm_stream":
            # LLM 开始输出，停止状态显示
            if status_live:
                status_live.stop()
                status_live = None

        # LLM 调用结束
        elif event_type == "on_llm_end":
            if status_live:
                status_live.stop()
                status_live = None

        # 链结束
        elif event_type == "on_chain_end":
            if status_live:
                status_live.stop()
                status_live = None

    session.set_event_callback(event_callback)

    console.print(f"[dim]{t('run.prompt_input', lang)}[/dim]")
    console.print(f"[dim]{t('run.prompt_reset', lang)}[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")

            if not user_input.strip():
                continue

            if user_input.lower() in ("exit", "quit"):
                console.print(f"[yellow]{t('run.goodbye', lang)}[/yellow]")
                break

            if user_input.lower() == "reset":
                session.reset()
                console.print(f"[green]{t('run.history_cleared', lang)}[/green]")
                continue

            try:
                response = await session.invoke(user_input)

                if response:
                    console.print()
                    md = Markdown(response)
                    console.print(Panel(md, title=f"[bold green]{t('assistant.title', lang)}[/bold green]"))
                    console.print()

            except Exception as e:
                logger.error(f"Agent error: {e}")
                if status_live:
                    status_live.stop()
                    status_live = None
                console.print(f"[red]{t('run.error', lang)}[/red] {e}")

        except KeyboardInterrupt:
            if status_live:
                status_live.stop()
                status_live = None
            console.print(f"\n[yellow]{t('run.use_exit', lang)}[/yellow]")
        except EOFError:
            break


async def _handle_approval(action_requests: list[dict], lang: Language) -> list[dict]:
    """处理审批请求

    Args:
        action_requests: 待审批的工具调用列表
        lang: 语言设置

    Returns:
        用户的决策列表
    """
    import json
    from rich.table import Table

    decisions = []

    # 显示待审批的工具调用
    console.print()
    console.print(f"[bold yellow]{t('approval.title', lang)}[/bold yellow]")
    console.print(f"[dim]{len(action_requests)} {t('approval.multiple_tools', lang)}[/dim]\n")

    # 如果有多个工具，询问是否全部批准
    if len(action_requests) > 1:
        approve_all = Prompt.ask(
            f"[bold]{t('approval.approve_all', lang)}[/bold]",
            default="Y",
        )
        if approve_all.lower() in ("y", "yes", ""):
            for req in action_requests:
                decisions.append({"type": "approve"})
            console.print(f"[green]{t('approval.approved', lang)} ({len(action_requests)})[/green]\n")
            return decisions

    # 逐个审批
    for i, req in enumerate(action_requests, 1):
        tool_name = req.get("name", "unknown")
        tool_args = req.get("args", {})
        description = req.get("description", "")

        # 显示工具详情
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row(t("approval.tool", lang), f"[bold]{tool_name}[/bold]")

        # 格式化参数
        args_str = json.dumps(tool_args, indent=2, ensure_ascii=False)
        table.add_row(t("approval.args", lang), args_str)

        if description:
            table.add_row(t("approval.description", lang), description)

        console.print(table)

        # 获取用户决策
        while True:
            choice = Prompt.ask(
                f"\n[bold]{t('approval.prompt', lang)}[/bold]",
                default="y",
            ).lower().strip()

            if choice in ("y", "yes"):
                decisions.append({"type": "approve"})
                console.print(f"[green]{t('approval.approved', lang)}[/green]\n")
                break
            elif choice in ("n", "no"):
                decisions.append({"type": "reject"})
                console.print(f"[red]{t('approval.rejected', lang)}[/red]\n")
                break
            elif choice == "e":
                # 编辑模式
                new_name = Prompt.ask(
                    f"[bold]{t('approval.edit_prompt', lang)}[/bold]",
                    default=tool_name,
                )
                new_args_str = Prompt.ask(
                    f"[bold]{t('approval.edit_args_prompt', lang)}[/bold]",
                    default=json.dumps(tool_args, ensure_ascii=False),
                )
                try:
                    new_args = json.loads(new_args_str)
                except json.JSONDecodeError:
                    console.print(f"[yellow]{t('approval.edit_args_invalid', lang)}[/yellow]")
                    new_args = tool_args

                decisions.append({
                    "type": "edit",
                    "edited_action": {
                        "name": new_name,
                        "args": new_args,
                    }
                })
                console.print(f"[green]{t('approval.approved', lang)} (edited)[/green]\n")
                break
            elif choice == "r":
                # 拒绝并留言
                reject_msg = Prompt.ask(
                    f"[bold]{t('approval.reject_message_prompt', lang)}[/bold]",
                    default="",
                )
                decision = {"type": "reject"}
                if reject_msg.strip():
                    decision["message"] = reject_msg
                decisions.append(decision)
                console.print(f"[red]{t('approval.rejected', lang)}[/red]\n")
                break
            else:
                console.print(f"[yellow]{t('approval.invalid_choice', lang)}[/yellow]")

    return decisions


@app.command("config")
def config_cmd(
    init: bool = typer.Option(
        False,
        "--init",
        "-i",
        help="Create config",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        "-s",
        help="Show path",
    ),
) -> None:
    """Manage configuration file."""
    lang = _get_lang()

    if show:
        config_path = get_default_config_path()
        if config_path.exists():
            console.print(f"Config file: {config_path}")
        else:
            console.print(f"Default config path: {config_path} {t('config.not_exists', lang)}")
        return

    if init:
        config_path = create_default_config()
        console.print(f"[green]{t('config.created', lang)}[/green] {config_path}")
        console.print(f"\n{t('config.edit_hint', lang)}")
        console.print(f"  {config_path}")
        return

    console.print(t("config.use_hint", lang))


@app.command("serve")
def serve_cmd(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        "-h",
        help="Host",
    ),
    port: int = typer.Option(
        8123,
        "--port",
        "-p",
        help="Port",
    ),
    allow_blocking: bool = typer.Option(
        True,
        "--allow-blocking/--no-allow-blocking",
        help="Allow blocking calls (for development)",
    ),
) -> None:
    """Start LangGraph server."""
    lang = _setup_language(config)

    try:
        import subprocess

        cfg = load_config(config)

        console.print(Panel.fit(
            f"[bold green]DeepCoBot LangGraph Server[/bold green]\n"
            f"Host: {host}\n"
            f"Port: {port}",
            title=t("serve.server_title", lang),
        ))

        from deepcobot.server import generate_langgraph_json
        from pathlib import Path as PathLib

        langgraph_json_path = PathLib("langgraph.json")
        generate_langgraph_json(cfg, langgraph_json_path)

        console.print(f"[green]{t('serve.generated', lang)}[/green]")
        console.print(f"[yellow]{t('serve.starting', lang)}[/yellow]")
        console.print(f"[dim]{t('serve.ctrlc', lang)}[/dim]\n")

        cmd = [
            "langgraph", "dev",
            "--host", host,
            "--port", str(port),
        ]

        # 开发模式下允许阻塞调用
        if allow_blocking:
            cmd.append("--allow-blocking")

        subprocess.run(cmd)

    except FileNotFoundError:
        console.print(f"[red]{t('serve.not_found', lang)}[/red]")
        console.print(f"{t('serve.install_hint', lang)}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('serve.stopped', lang)}[/yellow]")
    except Exception as e:
        console.print(f"[red]{t('run.error', lang)}[/red] {e}")
        raise typer.Exit(1)


# Cron subcommand group
cron_app = typer.Typer(
    name="cron",
    help="Manage scheduled tasks",
)
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all",
    ),
) -> None:
    """List all scheduled tasks."""
    lang = _setup_language(config)

    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)
    asyncio.run(service.start())

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print(f"[yellow]{t('cron.no_jobs', lang)}[/yellow]")
        return

    from rich.table import Table
    table = Table(title="Cron Jobs")
    table.add_column(t("cron.table_id", lang), style="cyan")
    table.add_column(t("cron.table_name", lang), style="green")
    table.add_column(t("cron.table_schedule", lang), style="yellow")
    table.add_column(t("cron.table_status", lang), style="magenta")
    table.add_column(t("cron.table_next_run", lang), style="blue")

    for job in jobs:
        status = f"[green]{t('cron.enabled', lang)}[/green]" if job.enabled else f"[red]{t('cron.disabled', lang)}[/red]"
        next_run = "-"
        if job.next_run_at:
            next_run = job.next_run_at.strftime("%Y-%m-%d %H:%M:%S")

        table.add_row(job.id, job.name, job.schedule, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Argument(..., help="Name"),
    message: str = typer.Argument(..., help="Message"),
    every: Optional[str] = typer.Option(
        None,
        "--every",
        "-e",
        help="Interval (e.g., 30m, 1h, 1d)",
    ),
    cron: Optional[str] = typer.Option(
        None,
        "--cron",
        help="Cron expression (5 fields)",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        help="Channel to dispatch results (e.g., telegram, discord)",
    ),
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="Chat ID to dispatch results",
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        "-t",
        help="Execution timeout in seconds",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
) -> None:
    """Add a scheduled task."""
    lang = _setup_language(config)

    cfg = load_config(config)
    from deepcobot.cron import CronService

    # 确定调度表达式
    schedule = every or cron or "1h"

    service = CronService(cfg.cron.store_path)

    async def add():
        await service.start()
        job = service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            channel=channel,
            chat_id=chat_id,
            timeout=timeout,
        )
        console.print(f"[green]{t('cron.created', lang)}[/green] {job.id}")
        console.print(f"  Name: {job.name}")
        console.print(f"  Schedule: {job.schedule}")
        console.print(f"  Message: {job.message}")
        if job.channel:
            console.print(f"  Dispatch: {job.channel}:{job.chat_id}")

    asyncio.run(add())


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="ID"),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
) -> None:
    """Remove a scheduled task."""
    lang = _setup_language(config)

    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)

    async def remove():
        await service.start()
        if service.remove_job(job_id):
            console.print(f"[green]{t('cron.removed', lang)}[/green] {job_id}")
        else:
            console.print(f"[red]{t('cron.not_found', lang)}[/red] {job_id}")
            raise typer.Exit(1)

    asyncio.run(remove())


@cron_app.command("run")
def cron_run_cmd(
    job_id: str = typer.Argument(..., help="ID"),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
) -> None:
    """Execute a task now."""
    lang = _setup_language(config)

    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)

    async def run():
        await service.start()
        console.print(f"[yellow]{t('cron.running', lang)}[/yellow] {job_id}")
        if await service.run_job_now(job_id):
            console.print(f"[green]{t('cron.executed', lang)}[/green] {job_id}")
        else:
            console.print(f"[red]{t('cron.not_found', lang)}[/red] {job_id}")
            raise typer.Exit(1)

    asyncio.run(run())


@app.command("bot")
def bot_cmd(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file",
    ),
) -> None:
    """Start bot channels (Telegram, Discord, Feishu, DingTalk, etc.)."""
    lang = _setup_language(config)

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
    from deepcobot.agent.core import _create_agent_async
    from deepcobot.bus.queue import MessageBus
    from deepcobot.channels import ChannelManager, InboundMessage, OutboundMessage
    from deepcobot.cron import CronService, HeartbeatService

    # 创建 Agent
    resources = await _create_agent_async(cfg)
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


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    console.print(f"deepcobot version: {__version__}")


if __name__ == "__main__":
    app()