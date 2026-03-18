"""Shared context for CLI commands.

Provides language settings and common utilities.
"""

from typing import Optional
from pathlib import Path

from deepcobot.config import load_config
from deepcobot.cli.i18n import set_language, Language

# Global language setting
_current_lang: Language = "en"


def get_lang() -> Language:
    """Get current language."""
    return _current_lang


def set_lang(lang: Language) -> None:
    """Set current language."""
    global _current_lang
    _current_lang = lang
    set_language(lang)


def setup_language(config_path: Optional[Path] = None, lang: Optional[str] = None) -> Language:
    """Setup language from config or CLI argument."""
    if lang:
        set_lang(lang)
    else:
        try:
            cfg = load_config(config_path)
            set_lang(cfg.language)
        except Exception:
            set_lang("en")

    return get_lang()