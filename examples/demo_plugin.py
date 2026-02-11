"""Demo plugin with custom slash commands.

This module demonstrates creating a Plugin that registers custom slash
commands. It shows how to use get_commands(), on_load(), and
get_status_hints().

Usage:
    Register via Config.plugins or load manually:

    plugin = DemoPlugin()
    await plugin.on_load(plugin_ctx)
    plugin_registry.register(plugin, command_registry)
"""

from __future__ import annotations

import datetime

from agent_repl.types import CommandContext, PluginContext, SlashCommand


class DemoPlugin:
    """Example plugin that adds /greet and /time commands."""

    name: str = "demo"
    description: str = "Demo plugin with example commands"

    def __init__(self) -> None:
        self._loaded = False

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="greet",
                description="Greet the user with a friendly message",
                handler=_handle_greet,
            ),
            SlashCommand(
                name="time",
                description="Show the current date and time",
                handler=_handle_time,
            ),
        ]

    async def on_load(self, context: PluginContext) -> None:
        """Called when the plugin is loaded. Use for initialization."""
        self._loaded = True

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded. Use for cleanup."""
        self._loaded = False

    def get_status_hints(self) -> list[str]:
        """Return status hints displayed in the toolbar."""
        if self._loaded:
            return ["demo: active"]
        return []


async def _handle_greet(ctx: CommandContext) -> None:
    """Handle /greet command."""
    name = ctx.args.strip() if ctx.args.strip() else "World"
    ctx.tui.show_info(f"Hello, {name}! Welcome to agent_repl.")


async def _handle_time(ctx: CommandContext) -> None:
    """Handle /time command."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx.tui.show_info(f"Current time: {now}")


def create_plugin() -> DemoPlugin:
    """Factory function for plugin loading via dotted path."""
    return DemoPlugin()
