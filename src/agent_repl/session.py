from __future__ import annotations

from agent_repl.types import ConversationTurn, TokenUsage


class TokenStatistics:
    """Accumulates token usage across conversation turns."""

    def __init__(self) -> None:
        self.total_input: int = 0
        self.total_output: int = 0

    def accumulate(self, usage: TokenUsage) -> None:
        self.total_input += usage.input_tokens
        self.total_output += usage.output_tokens

    @staticmethod
    def format_tokens(count: int) -> str:
        if count < 1000:
            return f"{count} tokens"
        return f"{count / 1000:.2f} k tokens"

    def format_input(self) -> str:
        return self.format_tokens(self.total_input)

    def format_output(self) -> str:
        return self.format_tokens(self.total_output)


class Session:
    """Maintains conversation history and token statistics."""

    def __init__(self) -> None:
        self._history: list[ConversationTurn] = []
        self._stats = TokenStatistics()

    def add_turn(self, turn: ConversationTurn) -> None:
        self._history.append(turn)
        if turn.usage is not None:
            self._stats.accumulate(turn.usage)

    def get_history(self) -> list[ConversationTurn]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._stats = TokenStatistics()

    def last_assistant_response(self) -> str | None:
        for turn in reversed(self._history):
            if turn.role == "assistant":
                return turn.content
        return None

    def replace_with_summary(self, summary: str) -> None:
        self._history = [ConversationTurn(role="system", content=summary)]
        self._stats = TokenStatistics()

    @property
    def stats(self) -> TokenStatistics:
        return self._stats
