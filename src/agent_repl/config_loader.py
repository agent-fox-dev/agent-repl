from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = """\
# agent_repl configuration file

[plugins]
# Plugin modules to load (dotted Python paths)
# paths = [
#     "myapp.plugins.custom_plugin",
# ]

# Plugin-specific configuration sections
# [plugins.custom_plugin]
# some_key = "some_value"
"""


@dataclass
class LoadedConfig:
    """Result of loading .af/config.toml."""

    plugin_paths: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def load_config(path: str = ".af/config.toml") -> LoadedConfig:
    """Load configuration from a TOML file.

    - Missing file: create default template, return empty LoadedConfig.
    - Malformed TOML: log warning, return empty LoadedConfig.
    - Valid TOML: extract [plugins].paths list, return full raw dict.

    Never raises an exception.
    """
    config_path = Path(path)

    if not config_path.exists():
        _create_default_template(config_path)
        return LoadedConfig()

    try:
        content = config_path.read_bytes()
    except OSError as e:
        logger.warning("Failed to read config file %s: %s", path, e)
        return LoadedConfig()

    if not content:
        return LoadedConfig()

    try:
        raw = tomllib.loads(content.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        logger.warning("Malformed TOML in %s: %s", path, e)
        return LoadedConfig()

    plugin_paths: list[str] = []
    plugins_section = raw.get("plugins")
    if isinstance(plugins_section, dict):
        paths = plugins_section.get("paths")
        if isinstance(paths, list):
            plugin_paths = [str(p) for p in paths]

    return LoadedConfig(plugin_paths=plugin_paths, raw=raw)


def _create_default_template(config_path: Path) -> None:
    """Create the default config template, creating parent directories if needed."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(_DEFAULT_TEMPLATE, encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to create default config at %s: %s", config_path, e)
