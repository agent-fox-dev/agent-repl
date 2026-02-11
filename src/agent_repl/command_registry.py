from __future__ import annotations

from agent_repl.types import SlashCommand


class CommandRegistry:
    """Stores SlashCommand objects; supports lookup, listing, prefix completion,
    and pinned command resolution."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        """Register a command, replacing any existing command with the same name."""
        self._commands[command.name] = command

    def get(self, name: str) -> SlashCommand | None:
        """Look up a command by exact name."""
        return self._commands.get(name)

    def list_all(self) -> list[SlashCommand]:
        """Return all registered commands, sorted alphabetically by name."""
        return sorted(self._commands.values(), key=lambda c: c.name)

    def complete(self, prefix: str) -> list[SlashCommand]:
        """Return commands whose names start with the given prefix, sorted alphabetically."""
        return sorted(
            (c for c in self._commands.values() if c.name.startswith(prefix)),
            key=lambda c: c.name,
        )

    def get_pinned(self, pinned_names: list[str], max_count: int) -> list[SlashCommand]:
        """Return registered commands in pinned order, capped at max_count.

        Only commands that are both in pinned_names and registered are included.
        Order follows pinned_names order.
        """
        result: list[SlashCommand] = []
        seen: set[str] = set()
        for name in pinned_names:
            if len(result) >= max_count:
                break
            if name in seen:
                continue
            seen.add(name)
            cmd = self._commands.get(name)
            if cmd is not None:
                result.append(cmd)
        return result
