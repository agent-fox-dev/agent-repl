from __future__ import annotations

from agent_repl.exceptions import QuitRequestedError
from agent_repl.types import CommandContext, PluginContext, SlashCommand


class BuiltinCommandsPlugin:
    """Built-in REPL commands implemented as a plugin."""

    name: str = "builtin"
    description: str = "Built-in REPL commands"

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="help",
                description="List all available commands",
                handler=_handle_help,
                pinned=True,
            ),
            SlashCommand(
                name="quit",
                description="Exit the REPL",
                handler=_handle_quit,
                pinned=True,
            ),
            SlashCommand(
                name="version",
                description="Show application version",
                handler=_handle_version,
                cli_exposed=True,
            ),
            SlashCommand(
                name="copy",
                description="Copy last response to clipboard",
                handler=_handle_copy,
            ),
            SlashCommand(
                name="agent",
                description="Show active agent info",
                handler=_handle_agent,
            ),
            SlashCommand(
                name="stats",
                description="Show token usage statistics",
                handler=_handle_stats,
            ),
        ]

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return []


async def _handle_help(ctx: CommandContext) -> None:
    """List all registered commands with descriptions."""
    commands = ctx.registry.list_all()
    if not commands:
        ctx.tui.show_info("No commands registered.")
        return
    for cmd in commands:
        ctx.tui.show_info(f"  /{cmd.name} — {cmd.description}")


async def _handle_quit(ctx: CommandContext) -> None:
    """Exit the REPL."""
    raise QuitRequestedError()


async def _handle_version(ctx: CommandContext) -> None:
    """Display application name and version."""
    ctx.tui.show_info(f"{ctx.config.app_name} v{ctx.config.app_version}")


async def _handle_copy(ctx: CommandContext) -> None:
    """Copy last assistant response to clipboard."""
    response = ctx.session.last_assistant_response()
    if response is None:
        ctx.tui.show_info("No response to copy.")
        return
    ctx.tui.copy_to_clipboard(response)


async def _handle_agent(ctx: CommandContext) -> None:
    """Show active agent name and model."""
    agent = ctx.plugin_registry.active_agent
    if agent is None:
        ctx.tui.show_info("No agent active.")
        return
    ctx.tui.show_info(f"Agent: {agent.name} (model: {agent.default_model})")


async def _handle_stats(ctx: CommandContext) -> None:
    """Show token usage statistics."""
    stats = ctx.session.stats
    ctx.tui.show_info(f"Sent: {stats.format_input()}")
    ctx.tui.show_info(f"Received: {stats.format_output()}")
