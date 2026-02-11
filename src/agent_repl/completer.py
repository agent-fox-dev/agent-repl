from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent

    from agent_repl.command_registry import CommandRegistry


class SlashCommandCompleter(Completer):
    """prompt_toolkit Completer for slash commands with pinned-first and prefix-filtered modes."""

    def __init__(
        self,
        registry: CommandRegistry,
        pinned_names: list[str],
        max_pinned: int = 6,
    ) -> None:
        self._registry = registry
        self._pinned_names = pinned_names
        self._max_pinned = max_pinned
        self._dismissed = False

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> list[Completion]:
        text = document.text_before_cursor

        if self._dismissed:
            return []

        if text == "/":
            # Bare "/" → show pinned commands
            commands = self._registry.get_pinned(self._pinned_names, self._max_pinned)
            return [
                Completion(
                    f"/{cmd.name}",
                    start_position=-1,
                    display=f"/{cmd.name}",
                    display_meta=cmd.description,
                )
                for cmd in commands
            ]

        if text.startswith("/") and len(text) > 1:
            # "/<prefix>" → prefix completion
            prefix = text[1:]
            commands = self._registry.complete(prefix)
            return [
                Completion(
                    f"/{cmd.name}",
                    start_position=-len(text),
                    display=f"/{cmd.name}",
                    display_meta=cmd.description,
                )
                for cmd in commands
            ]

        return []

    def dismiss(self) -> None:
        """Dismiss completions until reset."""
        self._dismissed = True

    def reset_dismiss(self) -> None:
        """Re-enable completions after dismissal."""
        self._dismissed = False
