"""Serve command - Start LangGraph server."""

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from deepcobot.config import load_config
from deepcobot.cli.i18n import t
from deepcobot.cli.context import setup_language

console = Console()


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
    lang = setup_language(config)

    try:
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