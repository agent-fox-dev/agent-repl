"""App entry point for agent_repl - consumer-facing API."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent_repl.builtin_commands import get_builtin_commands
from agent_repl.command_registry import CommandRegistry
from agent_repl.config_loader import load_config
from agent_repl.plugin_loader import load_plugins
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.repl import REPLCore
from agent_repl.session import Session
from agent_repl.tui import TUIShell
from agent_repl.types import AppContext, Config, TokenStatistics

logger = logging.getLogger(__name__)


class App:
    """Main application class. Accepts a Config and runs the REPL."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def run(self) -> None:
        """Start the application (blocking). Sets up all subsystems and runs the REPL."""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """Async entry point that sets up and runs the REPL loop."""
        # Create subsystems
        session = Session()
        tui = TUIShell(theme=self._config.theme)
        command_registry = CommandRegistry()
        stats = TokenStatistics()

        app_context = AppContext(
            config=self._config,
            session=session,
            tui=tui,
            command_registry=command_registry,
            stats=stats,
        )

        # Register built-in commands
        for cmd in get_builtin_commands():
            command_registry.register(cmd)

        # Load config file plugins
        config_data = load_config(Path.cwd())
        config_plugins = config_data.get("plugins", {}).get("modules", [])

        # Create plugin registry and load all plugins
        plugin_registry = PluginRegistry(command_registry)

        all_plugin_names = list(self._config.plugins) + list(config_plugins)
        loaded_plugins = load_plugins(all_plugin_names, app_context)

        for plugin in loaded_plugins:
            plugin_registry.register_plugin(plugin)
            await plugin.on_load(app_context)

        # Initialize agent
        agent = None
        if self._config.agent_factory is not None:
            agent = self._config.agent_factory(self._config)
        else:
            try:
                from agent_repl.agents.claude_agent import ClaudeAgentPlugin

                agent = ClaudeAgentPlugin(model=self._config.default_model)
            except Exception as e:
                logger.warning("Failed to initialize default Claude agent: %s", e)

        # Register agent as plugin and its commands
        if agent is not None:
            plugin_registry.register_plugin(agent)
            plugin_registry.agent_plugin = agent  # type: ignore[assignment]
            await agent.on_load(app_context)

        # Set up tab completions
        cmd_names = ["/" + c.name for c in command_registry.all_commands()]
        tui.set_completions(cmd_names)

        # Start REPL
        repl = REPLCore(app_context, agent=agent)
        await repl.run_loop()
