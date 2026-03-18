"""Main CLI application entry point.

DeepCoBot - A minimalist personal AI assistant framework.
"""

from typing import Optional

import typer
from rich.console import Console

from deepcobot import __version__
from deepcobot.cli.i18n import t
from deepcobot.cli.context import setup_language
from deepcobot.cli.run import run_cmd
from deepcobot.cli.serve import serve_cmd
from deepcobot.cli.config_cmd import config_cmd
from deepcobot.cli.cron import cron_app
from deepcobot.cli.bot import bot_cmd

app = typer.Typer(
    name="deepcobot",
    help="DeepCoBot",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Display version information."""
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
    setup_language(lang=lang)


# Register commands
app.command("run")(run_cmd)
app.command("serve")(serve_cmd)
app.command("config")(config_cmd)
app.command("bot")(bot_cmd)


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    console.print(f"deepcobot version: {__version__}")


# Add subcommand groups
app.add_typer(cron_app, name="cron")


if __name__ == "__main__":
    app()