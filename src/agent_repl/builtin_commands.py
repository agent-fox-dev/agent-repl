"""Built-in slash commands for agent_repl (/help, /quit, /version, /copy)."""

from __future__ import annotations

import importlib.metadata

from agent_repl.types import CommandContext, SlashCommand


def create_help_command() -> SlashCommand:
    """Create the /help command."""
    return SlashCommand(
        name="help",
        description="Show available commands",
        help_text="Display a list of all available slash commands with descriptions.",
        handler=_handle_help,
    )


def create_quit_command() -> SlashCommand:
    """Create the /quit command."""
    return SlashCommand(
        name="quit",
        description="Exit the REPL",
        help_text="Cancel any running agent request and exit the application.",
        handler=_handle_quit,
    )


def create_version_command() -> SlashCommand:
    """Create the /version command."""
    return SlashCommand(
        name="version",
        description="Show version",
        help_text="Display the application version.",
        handler=_handle_version,
    )


def _handle_help(ctx: CommandContext) -> None:
    """Display all available commands."""
    commands = ctx.app_context.command_registry.all_commands()
    lines = ["**Available commands:**\n"]
    for cmd in commands:
        lines.append(f"- `/{cmd.name}` — {cmd.description}")
    ctx.app_context.tui.display_text("\n".join(lines))


def _handle_quit(ctx: CommandContext) -> None:
    """Exit the REPL."""
    raise SystemExit(0)


def _handle_version(ctx: CommandContext) -> None:
    """Display the application version."""
    version = importlib.metadata.version("agent_repl")
    app_name = ctx.app_context.config.app_name
    ctx.app_context.tui.display_info(f"{app_name} v{version}")


def create_copy_command() -> SlashCommand:
    """Create the /copy command."""
    return SlashCommand(
        name="copy",
        description="Copy last agent output to clipboard",
        help_text="Copy the most recent agent response (raw markdown) to the system clipboard.",
        handler=_handle_copy,
    )


def _handle_copy(ctx: CommandContext) -> None:
    """Copy the last agent output to the system clipboard."""
    from agent_repl.clipboard import copy_to_clipboard
    from agent_repl.exceptions import ClipboardError

    text = ctx.app_context.session.get_last_assistant_content()
    if text is None:
        ctx.app_context.tui.display_info("No agent output to copy.")
        return

    try:
        copy_to_clipboard(text)
    except ClipboardError as e:
        ctx.app_context.tui.display_error(str(e))
        return

    ctx.app_context.tui.display_info("Copied to clipboard.")


def get_builtin_commands() -> list[SlashCommand]:
    """Return all built-in commands."""
    return [
        create_help_command(),
        create_quit_command(),
        create_version_command(),
        create_copy_command(),
    ]
