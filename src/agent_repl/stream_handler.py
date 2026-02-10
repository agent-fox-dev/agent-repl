"""Stream handler for agent_repl - consumes agent stream events."""

from __future__ import annotations

from collections.abc import AsyncIterator

from agent_repl.session import Session
from agent_repl.tui import TUIShell
from agent_repl.types import (
    ConversationTurn,
    StreamEvent,
    StreamEventType,
    TokenStatistics,
    TokenUsage,
)


async def handle_stream(
    stream: AsyncIterator[StreamEvent],
    tui: TUIShell,
    session: Session,
    stats: TokenStatistics,
) -> ConversationTurn:
    """Consume a stream of events from the agent and handle each event type.

    Returns a ConversationTurn representing the assistant's response.
    """
    events: list[StreamEvent] = []
    tool_uses: list[dict] = []
    token_usage: TokenUsage | None = None
    first_content = True
    stream_started = False

    tui.start_spinner()

    try:
        async for event in stream:
            events.append(event)

            if event.type == StreamEventType.TEXT_DELTA:
                if first_content:
                    tui.stop_spinner()
                    first_content = False
                if not stream_started:
                    tui.start_stream()
                    stream_started = True
                tui.append_stream(event.content)

            elif event.type == StreamEventType.TOOL_USE_START:
                if first_content:
                    tui.stop_spinner()
                    first_content = False
                tool_name = event.metadata.get("tool_name", "unknown")
                tui.display_info(f"Using tool: {tool_name}")

            elif event.type == StreamEventType.TOOL_RESULT:
                tool_id = event.metadata.get("tool_id", "")
                is_error = event.metadata.get("is_error", False)
                tool_name = event.metadata.get("tool_name", "tool")
                tui.display_tool_result(tool_name, event.content, is_error)
                tool_uses.append({
                    "tool_id": tool_id,
                    "content": event.content,
                    "is_error": is_error,
                })

            elif event.type == StreamEventType.USAGE:
                input_tokens = event.metadata.get("input_tokens", 0)
                output_tokens = event.metadata.get("output_tokens", 0)
                token_usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                stats.accumulate(token_usage)

            elif event.type == StreamEventType.ERROR:
                tui.stop_spinner()
                tui.display_error(event.content)

    finally:
        tui.stop_spinner()
        if stream_started:
            full_text = tui.finish_stream()
        else:
            full_text = ""

    turn = ConversationTurn(
        role="assistant",
        content=full_text,
        tool_uses=tool_uses,
        token_usage=token_usage,
    )
    session.add_turn(turn)

    return turn
