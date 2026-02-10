"""Command registry for agent_repl - stores and looks up slash commands."""

from __future__ import annotations

from agent_repl.types import SlashCommand


class CommandRegistry:
    """Registry for slash commands. Stores commands by name and provides lookup."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        """Register a slash command by name."""
        self._commands[command.name] = command

    def get(self, name: str) -> SlashCommand | None:
        """Look up a command by name. Returns None if not found."""
        return self._commands.get(name)

    def all_commands(self) -> list[SlashCommand]:
        """Return all registered commands sorted by name."""
        return sorted(self._commands.values(), key=lambda c: c.name)

    def completions(self, prefix: str) -> list[str]:
        """Return command names matching the given prefix (for tab completion)."""
        return sorted(
            name for name in self._commands if name.startswith(prefix)
        )

    def pinned_commands(self, pinned_names: list[str]) -> list[SlashCommand]:
        """Return pinned commands: first those in pinned_names (in order), then
        any registered commands with pinned=True not already included."""
        seen: set[str] = set()
        result: list[SlashCommand] = []

        for name in pinned_names:
            if name not in seen:
                cmd = self._commands.get(name)
                if cmd is not None:
                    result.append(cmd)
                    seen.add(name)

        for cmd in self._commands.values():
            if cmd.pinned and cmd.name not in seen:
                result.append(cmd)
                seen.add(cmd.name)

        return result
