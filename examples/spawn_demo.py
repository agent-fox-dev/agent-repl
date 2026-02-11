"""Session spawning demo for agent_repl.

Demonstrates spawning independent agent sessions with pre- and post-hooks
using SpawnConfig and App.spawn_session().

Usage:
    uv run python -m examples.spawn_demo
"""

from __future__ import annotations

import asyncio

from agent_repl import App, Config
from agent_repl.types import CommandContext, SlashCommand, SpawnConfig
from examples.echo_agent import EchoAgentPlugin


class SpawnDemoPlugin:
    """Plugin that adds a /spawn command to trigger spawned sessions."""

    name: str = "spawn_demo"
    description: str = "Demo plugin for session spawning"

    def __init__(self, app: App) -> None:
        self._app = app

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="spawn",
                description="Spawn an independent agent session",
                handler=self._handle_spawn,
            ),
        ]

    async def on_load(self, context: object) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return []

    async def _handle_spawn(self, ctx: CommandContext) -> None:
        """Handle /spawn command by creating a spawned session."""
        prompt = ctx.args.strip() or "Say hello from the spawned session!"

        # Define pre- and post-hooks (synchronous callables)
        def pre_hook() -> None:
            print("[Spawn] Starting isolated task...")

        def post_hook() -> None:
            print("[Spawn] Isolated task complete.")

        config = SpawnConfig(
            prompt=prompt,
            pre_hook=pre_hook,
            post_hook=post_hook,
        )

        try:
            task = await self._app.spawn_session(config)
            ctx.tui.show_info("Spawned session started in background.")
            # Optionally await the task (or let it run in background)
            await task
            ctx.tui.show_info("Spawned session finished.")
        except Exception as e:
            ctx.tui.show_error(f"Spawn failed: {e}")


async def main() -> None:
    """Run the spawn demo."""
    config = Config(
        app_name="spawn_demo",
        app_version="0.1.0",
        agent_factory=EchoAgentPlugin,
        pinned_commands=["help", "quit", "spawn"],
    )

    app = App(config=config)

    # Register spawn plugin (needs app reference for spawn_session)
    spawn_plugin = SpawnDemoPlugin(app)
    app._plugin_registry.register(spawn_plugin, app._command_registry)

    # Run the REPL
    # Try: /spawn Say something interesting
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
