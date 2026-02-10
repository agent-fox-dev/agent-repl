"""Demo plugin for agent_repl showcasing custom slash commands.

Implements the Plugin protocol with /greet and /stats commands.
Exposes a create_plugin() factory function at module level.
"""

from agent_repl.types import AppContext, CommandContext, SlashCommand


class DemoPlugin:
    """Example plugin that registers /greet and /stats commands."""

    name: str = "demo"
    description: str = "Example plugin for agent_repl"

    def __init__(self) -> None:
        self._app_context: AppContext | None = None

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="greet",
                description="Display a greeting message",
                help_text="Shows a greeting including the app name.",
                handler=self._handle_greet,
                pinned=True,
            ),
            SlashCommand(
                name="stats",
                description="Display token usage statistics",
                help_text="Shows current session token counts.",
                handler=self._handle_stats,
            ),
        ]

    async def on_load(self, app_context: AppContext) -> None:
        self._app_context = app_context

    async def on_unload(self) -> None:
        pass

    def _handle_greet(self, ctx: CommandContext) -> None:
        app_name = ctx.app_context.config.app_name
        ctx.app_context.tui.display_text(
            f"Hello from {app_name}! Welcome to the demo."
        )

    def _handle_stats(self, ctx: CommandContext) -> None:
        stats = ctx.app_context.stats
        ctx.app_context.tui.display_info(
            f"Token usage — input: {stats.total_input_tokens}, "
            f"output: {stats.total_output_tokens}"
        )


def create_plugin() -> DemoPlugin:
    """Factory function for plugin discovery."""
    return DemoPlugin()
