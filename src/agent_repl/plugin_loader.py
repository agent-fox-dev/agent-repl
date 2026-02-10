"""Plugin loader for agent_repl - imports and initializes plugin modules."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_repl.types import AppContext, Plugin

logger = logging.getLogger(__name__)


def load_plugins(plugin_names: list[str], app_context: AppContext) -> list[Plugin]:
    """Load plugins by dotted module path.

    Each plugin module must expose a create_plugin() factory function.
    On import/load failure: log error, skip plugin, continue with remaining.
    """
    plugins: list[Plugin] = []

    for name in plugin_names:
        try:
            module = importlib.import_module(name)
            factory = getattr(module, "create_plugin", None)
            if factory is None:
                logger.error("Plugin %s has no create_plugin() function", name)
                continue
            plugin = factory()
            plugins.append(plugin)
        except Exception:
            logger.error("Failed to load plugin: %s", name, exc_info=True)

    return plugins
