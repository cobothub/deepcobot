"""CLI 命令定义

使用 Typer 框架实现命令行接口。
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

app = typer.Typer(
    name="deepcobot",
    help="DeepCoBot - 极简封装的个人 AI 助理框架",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """显示版本信息"""
    if value:
        console.print(f"deepcobot version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="显示版本信息",
    ),
) -> None:
    """DeepCoBot - 极简封装的个人 AI 助理框架"""
    pass


@app.command()
def run(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
        exists=False,
    ),
    thread_id: str = typer.Option(
        "default",
        "--thread",
        "-t",
        help="会话线程 ID",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "-y",
        help="自动审批所有工具调用",
    ),
) -> None:
    """
    启动 CLI 交互会话。

    示例:
        deepcobot run
        deepcobot run --config /path/to/config.toml
        deepcobot run --thread my-session
    """
    try:
        # 加载配置
        cfg = load_config(config)

        # 命令行参数覆盖配置
        if auto_approve:
            cfg.agent.auto_approve = True

        console.print(Panel.fit(
            f"[bold green]DeepCoBot[/bold green] v{__version__}\n"
            f"Model: {cfg.agent.model}\n"
            f"Workspace: {cfg.agent.workspace}",
            title="Welcome",
        ))

        # 启动交互会话
        asyncio.run(_run_session(cfg, thread_id))

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        raise typer.Exit(0)


async def _run_session(cfg, thread_id: str) -> None:
    """运行交互会话"""
    session = AgentSession(cfg)
    session.set_thread_id(thread_id)

    console.print("[dim]Type your message and press Enter. Type 'exit' or 'quit' to end.[/dim]")
    console.print("[dim]Type 'reset' to clear conversation history.[/dim]\n")

    while True:
        try:
            # 获取用户输入
            user_input = Prompt.ask("[bold blue]You[/bold blue]")

            if not user_input.strip():
                continue

            # 处理特殊命令
            if user_input.lower() in ("exit", "quit"):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "reset":
                session.reset()
                console.print("[green]Conversation history cleared.[/green]")
                continue

            # 调用 Agent
            console.print("[dim]Thinking...[/dim]")

            try:
                response = await session.invoke(user_input)

                # 渲染 Markdown 响应
                if response:
                    console.print()
                    md = Markdown(response)
                    console.print(Panel(md, title="[bold green]Assistant[/bold green]"))
                    console.print()

            except Exception as e:
                logger.error(f"Agent error: {e}")
                console.print(f"[red]Error:[/red] {e}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' or 'quit' to end the session.[/yellow]")
        except EOFError:
            break


@app.command()
def config(
    init: bool = typer.Option(
        False,
        "--init",
        "-i",
        help="创建默认配置文件",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        "-s",
        help="显示当前配置路径",
    ),
) -> None:
    """
    管理配置文件。

    示例:
        deepcobot config --init    # 创建默认配置文件
        deepcobot config --show    # 显示配置文件路径
    """
    if show:
        config_path = get_default_config_path()
        if config_path.exists():
            console.print(f"Config file: {config_path}")
        else:
            console.print(f"Default config path: {config_path} (not exists)")
        return

    if init:
        config_path = create_default_config()
        console.print(f"[green]Created config file:[/green] {config_path}")
        console.print("\nEdit the file and configure your API keys:")
        console.print(f"  {config_path}")
        return

    # 默认显示帮助
    console.print("Use --init to create a config file or --show to display config path.")


@app.command()
def version_cmd() -> None:
    """显示版本信息"""
    console.print(f"deepcobot version: {__version__}")


@app.command()
def serve(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        "-h",
        help="服务器监听地址",
    ),
    port: int = typer.Option(
        8123,
        "--port",
        "-p",
        help="服务器监听端口",
    ),
) -> None:
    """
    启动 LangGraph 服务器。

    示例:
        deepcobot serve
        deepcobot serve --port 8124
        deepcobot serve --config /path/to/config.toml
    """
    try:
        import subprocess

        # 加载配置
        cfg = load_config(config)

        console.print(Panel.fit(
            f"[bold green]DeepCoBot LangGraph Server[/bold green]\n"
            f"Host: {host}\n"
            f"Port: {port}",
            title="Starting Server",
        ))

        # 生成 langgraph.json
        from deepcobot.server import generate_langgraph_json
        from pathlib import Path

        langgraph_json_path = Path("langgraph.json")
        generate_langgraph_json(cfg, langgraph_json_path)

        console.print(f"[green]Generated langgraph.json[/green]")

        # 启动 LangGraph CLI
        console.print(f"[yellow]Starting LangGraph server...[/yellow]")
        console.print("[dim]Use Ctrl+C to stop[/dim]\n")

        # 使用 langgraph CLI 启动服务
        subprocess.run([
            "langgraph", "dev",
            "--host", host,
            "--port", str(port),
        ])

    except FileNotFoundError:
        console.print("[red]Error: langgraph CLI not found[/red]")
        console.print("Install it with: pip install langgraph-cli")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# Cron 子命令组
cron_app = typer.Typer(
    name="cron",
    help="管理定时任务",
)
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="显示所有任务（包括禁用的）",
    ),
) -> None:
    """
    列出所有定时任务。

    示例:
        deepcobot cron list
        deepcobot cron list --all
    """
    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)
    asyncio.run(service.start())

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("[yellow]No cron jobs found[/yellow]")
        return

    from rich.table import Table
    table = Table(title="Cron Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Schedule", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Next Run", style="blue")

    from datetime import datetime

    for job in jobs:
        status = "[green]enabled[/green]" if job.enabled else "[red]disabled[/red]"
        next_run = "-"
        if job.state.next_run_at_ms:
            next_run = datetime.fromtimestamp(
                job.state.next_run_at_ms / 1000
            ).strftime("%Y-%m-%d %H:%M:%S")

        schedule_str = ""
        if job.schedule.kind == "cron":
            schedule_str = f"cron: {job.schedule.expr}"
        elif job.schedule.kind == "every":
            import datetime as dt
            seconds = (job.schedule.every_ms or 0) // 1000
            if seconds >= 3600:
                schedule_str = f"every {seconds // 3600}h"
            elif seconds >= 60:
                schedule_str = f"every {seconds // 60}m"
            else:
                schedule_str = f"every {seconds}s"
        else:
            schedule_str = "once"

        table.add_row(job.id, job.name, schedule_str, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Argument(..., help="任务名称"),
    message: str = typer.Argument(..., help="发送给 Agent 的消息"),
    every: Optional[str] = typer.Option(
        None,
        "--every",
        "-e",
        help="执行间隔（如 1h, 30m, 1d）",
    ),
    cron: Optional[str] = typer.Option(
        None,
        "--cron",
        help="Cron 表达式（5 字段）",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        help="结果发送渠道",
    ),
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="结果发送目标",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    添加定时任务。

    示例:
        deepcobot cron add "daily-report" "生成日报" --every 24h
        deepcobot cron add "hourly-check" "检查状态" --cron "0 * * * *"
    """
    cfg = load_config(config)
    from deepcobot.cron import CronService, CronSchedule, parse_interval

    schedule = CronSchedule(kind="every", every_ms=3600000)  # 默认每小时

    if every:
        try:
            every_ms = parse_interval(every)
            schedule = CronSchedule(kind="every", every_ms=every_ms)
        except ValueError as e:
            console.print(f"[red]Invalid interval: {e}[/red]")
            raise typer.Exit(1)

    if cron:
        schedule = CronSchedule(kind="cron", expr=cron)

    service = CronService(cfg.cron.store_path)

    async def add():
        await service.start()
        job = service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            channel=channel,
            chat_id=chat_id,
        )
        console.print(f"[green]Created cron job:[/green] {job.id}")
        console.print(f"  Name: {job.name}")
        console.print(f"  Message: {job.payload.message}")

    asyncio.run(add())


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="任务 ID"),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    移除定时任务。

    示例:
        deepcobot cron remove abc123
    """
    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)

    async def remove():
        await service.start()
        if service.remove_job(job_id):
            console.print(f"[green]Removed cron job: {job_id}[/green]")
        else:
            console.print(f"[red]Job not found: {job_id}[/red]")
            raise typer.Exit(1)

    asyncio.run(remove())


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="任务 ID"),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    立即执行定时任务。

    示例:
        deepcobot cron run abc123
    """
    cfg = load_config(config)
    from deepcobot.cron import CronService

    service = CronService(cfg.cron.store_path)

    async def run():
        await service.start()
        console.print(f"[yellow]Running job: {job_id}[/yellow]")
        if await service.run_job_now(job_id):
            console.print(f"[green]Job executed: {job_id}[/green]")
        else:
            console.print(f"[red]Job not found: {job_id}[/red]")
            raise typer.Exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    app()