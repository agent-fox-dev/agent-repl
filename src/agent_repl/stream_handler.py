from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from agent_repl.types import (
    ConversationTurn,
    StreamEvent,
    StreamEventType,
    TokenUsage,
    ToolUse,
)

if TYPE_CHECKING:
    from agent_repl.session import Session
    from agent_repl.tui import TUIShell

logger = logging.getLogger(__name__)


class StreamHandler:
    """Processes StreamEvent objects and drives TUI rendering."""

    def __init__(self, tui: TUIShell, session: Session) -> None:
        self._tui = tui
        self._session = session

    async def _collect_input(
        self,
        prompt: str,
        input_type: str,
        choices: list[str],
    ) -> str | dict:
        """Dispatch to the appropriate TUI input method."""
        if input_type == "approval":
            if len(choices) != 2:
                self._tui.show_error(
                    "Approval request requires exactly 2 choices."
                )
                return "reject"
            return await self._tui.prompt_approval(prompt, choices)
        elif input_type == "choice":
            if len(choices) < 2:
                self._tui.show_error(
                    "Choice request requires at least 2 choices."
                )
                return "reject"
            return await self._tui.prompt_choice(prompt, choices)
        elif input_type == "text":
            return await self._tui.prompt_text_input(prompt)
        else:
            self._tui.show_error(f"Unknown input type: {input_type}")
            return "reject"

    async def handle_stream(self, events: AsyncIterator[StreamEvent]) -> ConversationTurn:
        """Process a stream of events, rendering to TUI and building a ConversationTurn."""
        text_parts: list[str] = []
        tool_uses: list[ToolUse] = []
        token_usage = TokenUsage()
        first_content = True
        live_started = False

        self._tui.start_spinner()

        try:
            async for event in events:
                if event.type == StreamEventType.TEXT_DELTA:
                    if first_content:
                        self._tui.stop_spinner()
                        self._tui.start_live_text()
                        live_started = True
                        first_content = False
                    text = event.data.get("text", "")
                    self._tui.append_live_text(text)
                    text_parts.append(text)

                elif event.type == StreamEventType.TOOL_USE_START:
                    if first_content:
                        self._tui.stop_spinner()
                        first_content = False
                    name = event.data.get("name", "unknown")
                    tool_input = event.data.get("input", {})
                    self._tui.show_tool_use(name, tool_input)

                elif event.type == StreamEventType.TOOL_RESULT:
                    name = event.data.get("name", "unknown")
                    result = event.data.get("result", "")
                    is_error = event.data.get("is_error", False)
                    self._tui.show_tool_result(name, result, is_error)
                    tool_uses.append(
                        ToolUse(
                            name=name,
                            input=event.data.get("input", {}),
                            result=result,
                            is_error=is_error,
                        )
                    )

                elif event.type == StreamEventType.USAGE:
                    input_tokens = event.data.get("input_tokens", 0)
                    output_tokens = event.data.get("output_tokens", 0)
                    token_usage = TokenUsage(
                        input_tokens=token_usage.input_tokens + input_tokens,
                        output_tokens=token_usage.output_tokens + output_tokens,
                    )

                elif event.type == StreamEventType.ERROR:
                    message = event.data.get("message", "Unknown error")
                    fatal = event.data.get("fatal", False)
                    if fatal:
                        self._tui.stop_spinner()
                        self._tui.show_error(f"Fatal error: {message}")
                        break
                    else:
                        self._tui.show_error(f"Error: {message}")

                elif event.type == StreamEventType.INPUT_REQUEST:
                    # Pause streaming UI
                    self._tui.stop_spinner()
                    if live_started:
                        self._tui.finalize_live_text()
                        live_started = False

                    prompt = event.data.get("prompt", "")
                    input_type = event.data.get("input_type", "approval")
                    choices = event.data.get("choices", [])
                    response_future = event.data.get("response_future")

                    if response_future is None:
                        logger.warning(
                            "INPUT_REQUEST missing response_future, skipping"
                        )
                        continue

                    # Collect user input based on mode
                    response = await self._collect_input(
                        prompt, input_type, choices
                    )

                    # Resolve the future so the agent generator can resume
                    response_future.set_result(response)

                    # If rejected, cancel the stream
                    if response == "reject":
                        self._tui.show_info(
                            "Rejected. Agent response cancelled."
                        )
                        break

                    # Restart spinner for continued agent processing
                    self._tui.start_spinner()

        except (asyncio.CancelledError, KeyboardInterrupt):
            # Stream cancelled — finalize with partial content
            pass

        # Finalize
        self._tui.stop_spinner()
        if live_started:
            self._tui.finalize_live_text()

        full_text = "".join(text_parts)
        turn = ConversationTurn(
            role="assistant",
            content=full_text,
            tool_uses=tool_uses,
            usage=token_usage if (token_usage.input_tokens or token_usage.output_tokens) else None,
        )
        self._session.add_turn(turn)

        if full_text:
            self._tui.set_last_response(full_text)

        return turn
