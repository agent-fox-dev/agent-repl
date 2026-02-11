from __future__ import annotations

import logging

from agent_repl.builtin_commands import BuiltinCommandsPlugin
from agent_repl.command_registry import CommandRegistry
from agent_repl.completer import SlashCommandCompleter
from agent_repl.config_loader import load_config
from agent_repl.plugin_loader import load_plugin
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.repl import REPL
from agent_repl.session import Session
from agent_repl.tui import TUIShell
from agent_repl.types import Config, PluginContext

logger = logging.getLogger(__name__)


class App:
    """Top-level entry point; wires all subsystems, loads plugins, starts the REPL."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()
        self._session = Session()
        self._tui = TUIShell(self._config)
        self._command_registry = CommandRegistry()
        self._plugin_registry = PluginRegistry()

    async def _setup(self) -> None:
        """Load plugins, create agent, set up completer and toolbar."""
        plugin_ctx = PluginContext(
            config=self._config,
            session=self._session,
            tui=self._tui,
            registry=self._command_registry,
        )

        # 1. Register built-in commands (always first)
        builtin = BuiltinCommandsPlugin()
        await builtin.on_load(plugin_ctx)
        self._plugin_registry.register(builtin, self._command_registry)

        # 2. Load config from .af/config.toml
        loaded_config = load_config()

        # 3. Load plugins from Config.plugins + LoadedConfig.plugin_paths
        all_plugin_paths = list(self._config.plugins) + loaded_config.plugin_paths
        for dotted_path in all_plugin_paths:
            plugin = load_plugin(dotted_path)
            if plugin is None:
                continue
            try:
                await plugin.on_load(plugin_ctx)
            except Exception as e:
                logger.warning("Plugin '%s' on_load() failed: %s", dotted_path, e)
                continue
            self._plugin_registry.register(plugin, self._command_registry)

        # 4. If agent_factory provided, create and register agent
        if self._config.agent_factory is not None:
            try:
                agent = self._config.agent_factory()
                await agent.on_load(plugin_ctx)
                self._plugin_registry.register(agent, self._command_registry)
            except Exception as e:
                logger.warning("Failed to set up agent: %s", e)

        # 5. Set up completer
        completer = SlashCommandCompleter(
            self._command_registry,
            pinned_names=self._config.pinned_commands,
            max_pinned=self._config.max_pinned_display,
        )
        self._tui.set_completer(completer)

        # 6. Set up toolbar provider
        self._tui.set_toolbar_provider(self._plugin_registry.get_status_hints)

    async def run(self) -> None:
        """Run the application: setup, banner, REPL."""
        await self._setup()

        agent = self._plugin_registry.active_agent
        agent_name = agent.name if agent else None
        model = agent.default_model if agent else None

        self._tui.show_banner(
            self._config.app_name,
            self._config.app_version,
            agent_name,
            model,
        )

        repl = REPL(
            session=self._session,
            tui=self._tui,
            command_registry=self._command_registry,
            plugin_registry=self._plugin_registry,
            config=self._config,
        )
        await repl.run()
