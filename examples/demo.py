"""Demo application for agent_repl.

This is the canonical example showing how to build an application with
agent_repl. It demonstrates:

- Creating an App with Config and Theme
- Using the echo agent (no credentials) or Claude agent (with credentials)
- Registering custom plugins with slash commands
- CLI slash command invocation (e.g., `python demo.py --version`)
- Session spawning with pre/post hooks
- @path file context mentions (type `@somefile.py` in the REPL)

Usage:
    # Run with echo agent (no credentials needed):
    uv run python -m examples.demo

    # Run with Claude agent (requires ANTHROPIC_API_KEY):
    uv run python -m examples.demo --claude

    # CLI command invocation (no REPL):
    uv run python -m examples.demo --version
"""

from __future__ import annotations

import asyncio
import sys

from agent_repl import App, Config
from agent_repl.types import Theme
from examples.demo_plugin import DemoPlugin
from examples.echo_agent import EchoAgentPlugin


def _make_echo_config() -> Config:
    """Create a Config using the echo agent."""
    return Config(
        app_name="agent_repl_demo",
        app_version="0.1.0",
        theme=Theme(
            prompt_color="green",
            gutter_color="blue",
            error_color="red",
            info_color="cyan",
        ),
        agent_factory=EchoAgentPlugin,
        # Pinned commands appear first when you type "/" in the REPL
        pinned_commands=["help", "quit", "greet"],
    )


def _make_claude_config() -> Config:
    """Create a Config using the Claude agent (requires credentials)."""
    from agent_repl.agents.claude_agent import ClaudeAgentPlugin

    return Config(
        app_name="agent_repl_demo",
        app_version="0.1.0",
        theme=Theme(
            prompt_color="green",
            gutter_color="blue",
            error_color="red",
            info_color="cyan",
        ),
        agent_factory=ClaudeAgentPlugin,
        pinned_commands=["help", "quit", "compact"],
    )


async def main() -> None:
    """Entry point for the demo application."""
    args = sys.argv[1:]

    # Determine agent type
    use_claude = "--claude" in args
    if use_claude:
        args.remove("--claude")
        config = _make_claude_config()
    else:
        config = _make_echo_config()

    app = App(config=config)

    # Register the demo plugin manually (demonstrates programmatic registration)
    demo_plugin = DemoPlugin()
    await demo_plugin.on_load(
        __import__("agent_repl.types", fromlist=["PluginContext"]).PluginContext(
            config=config,
            session=app._session,
            tui=app._tui,
            registry=app._command_registry,
        )
    )
    app._plugin_registry.register(demo_plugin, app._command_registry)

    # Check for CLI command invocation (e.g., --version)
    cli_flags = [a for a in args if a.startswith("--")]
    if cli_flags:
        exit_code = await app.run_cli_command(cli_flags[0], args[1:])
        sys.exit(exit_code)

    # Run the interactive REPL
    # Try these in the REPL:
    #   hello world          → sends free text to the echo agent
    #   @README.md hello     → includes file context from README.md
    #   /help                → list all commands
    #   /greet Alice         → custom plugin command
    #   /time                → show current time
    #   /stats               → show token usage
    #   /quit                → exit
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
