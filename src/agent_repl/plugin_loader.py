from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_repl.types import Plugin

logger = logging.getLogger(__name__)


def load_plugin(dotted_path: str) -> Plugin | None:
    """Import a plugin module by dotted path and call its create_plugin() factory.

    Returns the plugin instance, or None if loading fails for any reason.
    Failures are logged as warnings but never raised.
    """
    try:
        module = importlib.import_module(dotted_path)
    except ImportError as e:
        logger.warning("Failed to import plugin module '%s': %s", dotted_path, e)
        return None

    factory = getattr(module, "create_plugin", None)
    if factory is None:
        logger.warning(
            "Plugin module '%s' has no create_plugin() factory function", dotted_path
        )
        return None

    if not callable(factory):
        logger.warning(
            "Plugin module '%s': create_plugin is not callable", dotted_path
        )
        return None

    try:
        plugin = factory()
    except Exception as e:
        logger.warning(
            "Plugin factory create_plugin() in '%s' raised an error: %s", dotted_path, e
        )
        return None

    return plugin
