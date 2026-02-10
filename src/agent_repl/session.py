"""Session manager for agent_repl - maintains conversation history and token stats."""

from __future__ import annotations

from agent_repl.types import ConversationTurn, TokenStatistics


class Session:
    """Manages conversation history and token statistics for a REPL session."""

    def __init__(self) -> None:
        self._history: list[ConversationTurn] = []
        self.stats = TokenStatistics()

    def add_turn(self, turn: ConversationTurn) -> None:
        """Append a turn to the conversation history.

        If the turn has token_usage, accumulate it into session stats.
        """
        self._history.append(turn)
        if turn.token_usage is not None:
            self.stats.accumulate(turn.token_usage)

    def get_history(self) -> list[ConversationTurn]:
        """Return the ordered list of conversation turns."""
        return list(self._history)

    def clear(self) -> None:
        """Reset the conversation history to empty."""
        self._history.clear()

    def replace_with_summary(self, summary: str) -> None:
        """Replace the entire history with a single assistant turn containing the summary."""
        self._history.clear()
        self._history.append(
            ConversationTurn(role="assistant", content=summary)
        )
