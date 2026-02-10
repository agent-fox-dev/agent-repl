"""Slash command completer for agent_repl - type-ahead dropdown with pinned commands."""

from __future__ import annotations

from collections.abc import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from agent_repl.constants import MAX_PINNED_DISPLAY
from agent_repl.types import SlashCommand


class SlashCommandCompleter(Completer):
    """prompt-toolkit Completer that shows slash commands in a dropdown.

    When the input is exactly ``/``, only pinned commands are shown (up to
    *max_pinned_display*).  When the input is ``/<prefix>``, all commands
    whose names start with *prefix* are shown.  For any other input the
    completer yields nothing.
    """

    def __init__(
        self,
        commands: list[SlashCommand],
        pinned_names: list[str],
        max_pinned_display: int = MAX_PINNED_DISPLAY,
    ) -> None:
        self._commands: list[SlashCommand] = list(commands)
        self._pinned_names: list[str] = list(pinned_names)
        self._max_pinned_display = max_pinned_display

    def update_commands(
        self,
        commands: list[SlashCommand],
        pinned_names: list[str],
    ) -> None:
        """Replace the command list and pinned names (e.g. after plugin load)."""
        self._commands = list(commands)
        self._pinned_names = list(pinned_names)

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        """Yield completions for the current input state."""
        text = document.text_before_cursor

        # Only activate when '/' is the very first character
        if not text.startswith("/"):
            return

        prefix = text[1:]  # everything after the leading '/'

        if prefix == "":
            # Show pinned commands only
            yield from self._pinned_completions(text)
        else:
            # Filter all commands by prefix
            yield from self._filtered_completions(prefix, text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_pinned(self) -> list[SlashCommand]:
        """Resolve the pinned set: config list first, then declarative, deduped."""
        seen: set[str] = set()
        result: list[SlashCommand] = []
        by_name = {c.name: c for c in self._commands}

        for name in self._pinned_names:
            if name not in seen and name in by_name:
                result.append(by_name[name])
                seen.add(name)

        for cmd in self._commands:
            if cmd.pinned and cmd.name not in seen:
                result.append(cmd)
                seen.add(cmd.name)

        return result[: self._max_pinned_display]

    def _pinned_completions(self, text: str) -> Iterable[Completion]:
        for cmd in self._resolve_pinned():
            yield Completion(
                text=f"/{cmd.name}",
                start_position=-len(text),
                display=f"/{cmd.name}",
                display_meta=cmd.description,
            )

    def _filtered_completions(
        self, prefix: str, text: str,
    ) -> Iterable[Completion]:
        for cmd in sorted(self._commands, key=lambda c: c.name):
            if cmd.name.startswith(prefix):
                yield Completion(
                    text=f"/{cmd.name}",
                    start_position=-len(text),
                    display=f"/{cmd.name}",
                    display_meta=cmd.description,
                )
