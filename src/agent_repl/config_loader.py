"""Config loader for agent_repl - reads plugin configuration from TOML files."""

from __future__ import annotations

import io
import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_TEMPLATE: str = """\
# Agent Fox configuration
# See documentation for available options.

[plugins]
modules = []
"""


def _parse_default() -> dict:
    """Parse DEFAULT_CONFIG_TEMPLATE and return the resulting dict."""
    return tomllib.load(io.BytesIO(DEFAULT_CONFIG_TEMPLATE.encode()))


def load_config(config_dir: Path) -> dict:
    """Load plugin configuration from .af/plugins.toml in the given directory.

    If the file does not exist, creates it with DEFAULT_CONFIG_TEMPLATE
    content and returns the parsed default. If the file cannot be created
    (e.g., permission error), logs a warning and returns the parsed default.
    If the file exists but is malformed, logs a warning and returns empty dict.
    """
    config_path = config_dir / ".af" / "plugins.toml"

    try:
        file_exists = config_path.exists()
    except OSError:
        file_exists = False

    if not file_exists:
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
            logger.info("Created default config at %s", config_path)
        except OSError as e:
            logger.warning("Could not create config: %s", e)
        return _parse_default()

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        logger.warning("Malformed TOML in %s: %s", config_path, e)
        return {}
