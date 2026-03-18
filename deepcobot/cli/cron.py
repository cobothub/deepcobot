"""Cron commands - Manage scheduled tasks."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from deepcobot.config import load_config
from deepcobot.cron import CronService
from deepcobot.cli.i18n import t
from deepcobot.cli.context import setup_language

console = Console()

# Create cron subcommand group
cron_app = typer.Typer(
    name="cron",
    help="Manage scheduled tasks",
)


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
    lang = setup_language(config)

    cfg = load_config(config)

    service = CronService(cfg.cron.store_path)
    asyncio.run(service.start())

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print(f"[yellow]{t('cron.no_jobs', lang)}[/yellow]")
        return

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
    lang = setup_language(config)

    cfg = load_config(config)

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
    lang = setup_language(config)

    cfg = load_config(config)

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
    lang = setup_language(config)

    cfg = load_config(config)

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