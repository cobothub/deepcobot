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
    session = AgentSession(cfg)
    session.set_thread_id(thread_id)

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

            console.print(f"[dim]{t('run.thinking', lang)}[/dim]")

            try:
                response = await session.invoke(user_input)

                if response:
                    console.print()
                    md = Markdown(response)
                    console.print(Panel(md, title=f"[bold green]{t('assistant.title', lang)}[/bold green]"))
                    console.print()

            except Exception as e:
                logger.error(f"Agent error: {e}")
                console.print(f"[red]{t('run.error', lang)}[/red] {e}")

        except KeyboardInterrupt:
            console.print(f"\n[yellow]{t('run.use_exit', lang)}[/yellow]")
        except EOFError:
            break


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

        subprocess.run([
            "langgraph", "dev",
            "--host", host,
            "--port", str(port),
        ])

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

    from datetime import datetime

    for job in jobs:
        status = f"[green]{t('cron.enabled', lang)}[/green]" if job.enabled else f"[red]{t('cron.disabled', lang)}[/red]"
        next_run = "-"
        if job.state.next_run_at_ms:
            next_run = datetime.fromtimestamp(
                job.state.next_run_at_ms / 1000
            ).strftime("%Y-%m-%d %H:%M:%S")

        schedule_str = ""
        if job.schedule.kind == "cron":
            schedule_str = f"cron: {job.schedule.expr}"
        elif job.schedule.kind == "every":
            seconds = (job.schedule.every_ms or 0) // 1000
            if seconds >= 3600:
                schedule_str = f"{t('cron.every', lang)} {seconds // 3600}h"
            elif seconds >= 60:
                schedule_str = f"{t('cron.every', lang)} {seconds // 60}m"
            else:
                schedule_str = f"{t('cron.every', lang)} {seconds}s"
        else:
            schedule_str = t("cron.once", lang)

        table.add_row(job.id, job.name, schedule_str, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Argument(..., help="Name"),
    message: str = typer.Argument(..., help="Message"),
    every: Optional[str] = typer.Option(
        None,
        "--every",
        "-e",
        help="Interval",
    ),
    cron: Optional[str] = typer.Option(
        None,
        "--cron",
        help="Cron expr",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        help="Channel",
    ),
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="Chat ID",
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
    from deepcobot.cron import CronService, CronSchedule, parse_interval

    schedule = CronSchedule(kind="every", every_ms=3600000)

    if every:
        try:
            every_ms = parse_interval(every)
            schedule = CronSchedule(kind="every", every_ms=every_ms)
        except ValueError as e:
            console.print(f"[red]{t('cron.invalid_interval', lang)}[/red] {e}")
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
        console.print(f"[green]{t('cron.created', lang)}[/green] {job.id}")
        console.print(f"  Name: {job.name}")
        console.print(f"  Message: {job.payload.message}")

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


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    console.print(f"deepcobot version: {__version__}")


if __name__ == "__main__":
    app()