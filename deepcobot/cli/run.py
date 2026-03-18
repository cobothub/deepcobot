"""Run command - Start an interactive CLI session."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status
from rich.live import Live

from deepcobot import __version__
from deepcobot.config import load_config
from deepcobot.agent import AgentSession
from deepcobot.cli.i18n import t, Language
from deepcobot.cli.context import setup_language, get_lang

console = Console()


def get_run_help() -> str:
    """Get run command help text."""
    lang = get_lang()
    examples = f"""deepcobot run
deepcobot run --config /path/to/config.toml
deepcobot run --thread my-session"""
    return t("run.description", lang) + "\n\nExamples:\n" + examples


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
    lang = setup_language(config)

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

            # 获取友好的工具显示名称（使用 i18n）
            display_name = t(f"tool.{tool_name}", lang)
            if display_name == f"tool.{tool_name}":
                display_name = tool_name  # 未找到翻译时使用原名
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