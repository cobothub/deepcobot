"""Config command - Manage configuration file."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from deepcobot.config import get_default_config_path, create_default_config
from deepcobot.cli.i18n import t
from deepcobot.cli.context import get_lang

console = Console()


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
    lang = get_lang()

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