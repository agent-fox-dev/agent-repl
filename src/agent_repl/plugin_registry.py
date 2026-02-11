from __future__ import annotations

from agent_repl.command_registry import CommandRegistry
from agent_repl.exceptions import PluginError
from agent_repl.types import AgentPlugin, Plugin


class PluginRegistry:
    """Manages plugin lifecycle; registers commands; enforces single-agent constraint."""

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []
        self._active_agent: AgentPlugin | None = None

    def register(self, plugin: Plugin, command_registry: CommandRegistry) -> None:
        """Register a plugin: store it, register its commands, and set as agent if applicable."""
        for command in plugin.get_commands():
            command_registry.register(command)

        if isinstance(plugin, AgentPlugin):
            self.set_agent(plugin)

        self._plugins.append(plugin)

    def set_agent(self, agent: AgentPlugin) -> None:
        """Set the active agent. Raises PluginError if an agent is already set."""
        if self._active_agent is not None:
            raise PluginError(
                f"Cannot register agent '{agent.name}': "
                f"agent '{self._active_agent.name}' is already active. "
                f"Only one agent plugin is allowed."
            )
        self._active_agent = agent

    @property
    def active_agent(self) -> AgentPlugin | None:
        """Return the active agent plugin, or None if no agent is registered."""
        return self._active_agent

    @property
    def plugins(self) -> list[Plugin]:
        """Return a copy of the registered plugins list."""
        return list(self._plugins)

    def get_status_hints(self) -> list[str]:
        """Collect and return status hints from all registered plugins."""
        hints: list[str] = []
        for plugin in self._plugins:
            hints.extend(plugin.get_status_hints())
        return hints
