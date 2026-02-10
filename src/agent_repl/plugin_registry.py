"""Plugin registry for agent_repl - manages loaded plugins and routes commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_repl.command_registry import CommandRegistry

if TYPE_CHECKING:
    from agent_repl.types import AgentPlugin, Plugin


class PluginRegistry:
    """Maintains loaded plugins, routes commands, identifies active agent."""

    def __init__(self, command_registry: CommandRegistry) -> None:
        self._plugins: list[Plugin] = []
        self._command_registry = command_registry
        self._agent_plugin: AgentPlugin | None = None

    def register_plugin(self, plugin: Plugin) -> None:
        """Register a plugin: store it and route its commands to the command registry."""
        self._plugins.append(plugin)

        for cmd in plugin.get_commands():
            self._command_registry.register(cmd)

        # Check if this is an agent plugin (duck typing via hasattr)
        if hasattr(plugin, "send_message") and hasattr(plugin, "compact_history"):
            if self._agent_plugin is None:
                self._agent_plugin = plugin  # type: ignore[assignment]

    @property
    def agent_plugin(self) -> AgentPlugin | None:
        """Return the active agent plugin (first AgentPlugin found)."""
        return self._agent_plugin

    @agent_plugin.setter
    def agent_plugin(self, plugin: AgentPlugin) -> None:
        """Set the active agent plugin."""
        self._agent_plugin = plugin

    @property
    def plugins(self) -> list[Plugin]:
        """Return all loaded plugins."""
        return list(self._plugins)
