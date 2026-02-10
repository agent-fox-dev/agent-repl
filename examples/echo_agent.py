"""Echo agent for testing and demonstration without API credentials.

Implements the AgentPlugin protocol by echoing user input back as
StreamEvent objects. Provides /clear and /compact commands.
"""

from collections.abc import AsyncIterator

from agent_repl.types import (
    AppContext,
    CommandContext,
    ConversationTurn,
    FileContent,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)


class EchoAgent:
    """Lightweight agent that echoes user input as StreamEvents."""

    name: str = "echo"
    description: str = "Echo agent for testing"

    def __init__(self) -> None:
        self._app_context: AppContext | None = None

    async def send_message(
        self,
        message: str,
        file_context: list[FileContent],
        history: list[ConversationTurn],
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type=StreamEventType.TEXT_DELTA, content=message)
        yield StreamEvent(
            type=StreamEventType.USAGE,
            metadata={
                "input_tokens": len(message),
                "output_tokens": len(message),
            },
        )

    async def compact_history(
        self,
        history: list[ConversationTurn],
    ) -> str:
        total_len = sum(len(t.content) for t in history)
        return f"Summary: {len(history)} turns, {total_len} chars"

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="clear",
                description="Clear conversation history",
                help_text="Reset the conversation history to empty.",
                handler=self._handle_clear,
            ),
            SlashCommand(
                name="compact",
                description="Compact conversation history",
                help_text="Replace history with a summary.",
                handler=self._handle_compact,
            ),
        ]

    async def on_load(self, app_context: AppContext) -> None:
        self._app_context = app_context

    async def on_unload(self) -> None:
        pass

    def _handle_clear(self, ctx: CommandContext) -> None:
        ctx.app_context.session.clear()
        ctx.app_context.tui.display_info("Conversation history cleared.")

    def _handle_compact(self, ctx: CommandContext) -> None:
        history = ctx.app_context.session.get_history()
        total_len = sum(len(t.content) for t in history)
        summary = f"Summary: {len(history)} turns, {total_len} chars"
        ctx.app_context.session.replace_with_summary(summary)
        ctx.app_context.tui.display_info("History compacted.")
